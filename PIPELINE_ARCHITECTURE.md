# DOCQA Ultimate - Pipeline Architecture

## Pipeline Overview

The DOCQA Ultimate pipeline is a 4-stage asynchronous processing system that transforms uploaded PDFs into searchable vector embeddings. Each stage runs independently, processing one document at a time per stage, but all stages run in parallel.

---

## Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────┐
│                         UPLOAD ENDPOINT                              │
│  FastAPI receives PDF → Uploads to Supabase Storage → Enqueues job  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STAGE 1: PDF EXTRACTION                         │
│  Worker: stage1_extraction.py                                        │
│  Queue: queue:stage1                                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  • Downloads PDF from Supabase Storage                               │
│  • Streams to disk for large files (>10MB)                           │
│  • Extracts text from each page (pdfplumber)                         │
│  • Sends pages to Stage 2 in batches (50 pages)                      │
│  • Updates status: uploaded → processing → extracted                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STAGE 2: CHUNKING                               │
│  Worker: stage2_chunk_store.py                                       │
│  Queue: queue:stage2                                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  • Receives pages from Stage 1                                       │
│  • Splits pages into semantic chunks (500 tokens, 50 overlap)        │
│  • Sanitizes text (removes null bytes)                               │
│  • Inserts chunks to Supabase (embedding=NULL)                       │
│  • Enqueues Stage 3 when all pages processed                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   STAGE 3: EMBEDDING COMPUTATION                     │
│  Worker: stage3_embed_compute.py                                     │
│  Queue: queue:stage3                                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  • Fetches chunks without embeddings                                 │
│  • Calls Hugging Face API in batches (400 chunks)                    │
│  • Model: all-mpnet-base-v2 (768 dimensions)                         │
│  • Enqueues embeddings to Stage 4                                    │
│  • Rate limiting: 1.5-2s delay between batches                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: VECTOR STORAGE                           │
│  Worker: stage4_write_embeddings.py                                  │
│  Queue: queue:stage4                                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  • Writes embeddings to Supabase chunks table                        │
│  • Batch upsert (100 chunks per batch)                               │
│  • Computes document-level embedding (average of chunks)             │
│  • Inserts to documents_index table                                  │
│  • Updates status: extracted → indexed                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: PDF Extraction

### Worker: `stage1_extraction.py`

### Input
- Job from `queue:stage1`
- Contains: `document_id`, `user_id`

### Process

**1. Fetch Document Metadata**
```python
doc = documents_col.find_one({"_id": ObjectId(doc_id)})
storage = doc.get("storage", {})
bucket = storage.get("bucket")
path = storage.get("path")
```

**2. Download PDF**
- Small files (<10MB): Load into memory
- Large files (≥10MB): Stream to disk
```python
if file_size_mb >= 10:
    # Streaming mode
    pdf_temp_path = stream_pdf_from_supabase(bucket, path, doc_id)
else:
    # Batch mode
    pdf_bytes = download_pdf_from_supabase(bucket, path)
```

**3. Extract Pages**
- Small files: Extract all pages at once
- Large files: Stream pages one at a time
```python
if USE_STREAMING:
    for page_num, page_text in extract_pages_streaming(pdf_temp_path):
        # Send batch to Stage 2 every 50 pages
        if len(current_batch) >= 50:
            r.lpush("queue:stage2", json.dumps(stage2_job))
else:
    pages = extract_pages_from_pdf_bytes(pdf_bytes)
    r.lpush("queue:stage2", json.dumps(stage2_job))
```

**4. Update Status**
```python
documents_col.update_one(
    {"_id": ObjectId(doc_id)},
    {"$set": {"status": "extracted"}}
)
```

### Output
- Job to `queue:stage2`
- Contains: `document_id`, `user_id`, `pages`, `is_final_batch`, `total_pages`

### Memory Optimization
- Streams large PDFs to disk (not memory)
- Processes pages in batches
- Forces garbage collection after each batch
- Cleans up temp files

### Error Handling
- File size validation (max 100MB)
- Fallback to pypdf if pdfplumber fails
- Updates status to "failed" on error
- Logs errors to MongoDB

---

## Stage 2: Chunking

### Worker: `stage2_chunk_store.py`

### Input
- Job from `queue:stage2`
- Contains: `document_id`, `user_id`, `pages`, `is_final_batch`

### Process

**1. Receive Pages**
```python
pages = job.get("pages")  # Dict: {page_num: page_text}
is_final_batch = job.get("is_final_batch", False)
```

**2. Chunk Pages**
```python
for page_num, page_text in sorted(pages.items()):
    page_chunks = chunks_from_page(
        page_text, 
        page_num, 
        start_chunk_idx=current_chunk_idx,
        max_tokens=500, 
        overlap=50
    )
    all_chunks.extend(page_chunks)
```

**Chunking Algorithm:**
- Split text into sentences
- Group sentences until reaching max_tokens (500)
- Overlap by 50 tokens with previous chunk
- Maintain global chunk index across pages

**3. Sanitize Text**
```python
def sanitize_text(text):
    # Remove null bytes (\x00) - PostgreSQL doesn't allow these
    text = text.replace('\x00', '')
    # Remove control characters (keep newlines, tabs)
    # Ensure valid UTF-8 encoding
    return text
```

**4. Insert Chunks to Supabase**
```python
batch = []
for chunk in chunks:
    row = {
        "user_id": user_id_uuid,
        "document_id": doc_id,
        "page_number": chunk["page_number"],
        "chunk_index": chunk["chunk_index"],
        "text": sanitize_text(chunk["text"]),
        "tokens": chunk["tokens"]
        # embedding: NULL (will be filled in Stage 4)
    }
    batch.append(row)
    if len(batch) >= 50:
        supabase.table("chunks").insert(batch).execute()
        batch = []
```

**5. Enqueue Stage 3 (if final batch)**
```python
if is_final_batch:
    stage3_job = {"document_id": doc_id, "user_id": user_id}
    r.lpush("queue:stage3", json.dumps(stage3_job))
```

### Output
- Chunks inserted to Supabase `chunks` table
- Job to `queue:stage3` (when all pages processed)

### Key Features
- Streaming mode support (processes batches incrementally)
- Global chunk index tracking via Redis
- Batch inserts (50 chunks per batch)
- Progress logging for large documents

### Error Handling
- Validates chunk creation
- Logs failed inserts
- Marks document as "failed" if >50% inserts fail

---

## Stage 3: Embedding Computation

### Worker: `stage3_embed_compute.py`

### Input
- Job from `queue:stage3`
- Contains: `document_id`, `user_id`

### Process

**1. Fetch Chunks Without Embeddings**
```python
chunks = []
offset = 0
PAGE_SIZE = 1000

while True:
    res = supabase.table("chunks") \
        .select("id,text") \
        .eq("document_id", doc_id) \
        .is_("embedding", "null") \
        .range(offset, offset + PAGE_SIZE - 1) \
        .execute()
    
    page_chunks = res.data or []
    if not page_chunks:
        break
    
    chunks.extend(page_chunks)
    offset += PAGE_SIZE
```

**2. Embed Texts in Batches**
```python
BATCH_SIZE = 400  # For HF API

for i in range(0, total_chunks, BATCH_SIZE):
    batch = chunks[i:i+BATCH_SIZE]
    texts = [c["text"] for c in batch]
    
    # Call Hugging Face API
    embeddings = embed_texts_hf_api(texts)
    
    # Prepare payload for Stage 4
    payload_batch = [
        {"id": chunk_ids[j], "embedding": embeddings[j].tolist()}
        for j in range(len(batch))
    ]
    
    # Enqueue to Stage 4
    r.lpush("queue:stage4", json.dumps({
        "document_id": doc_id,
        "user_id": user_id,
        "embeddings": payload_batch
    }))
    
    # Rate limiting
    time.sleep(1.5)
```

**3. Hugging Face API Call**
```python
def embed_texts_hf_api(text_list):
    result = hf_client.feature_extraction(
        text_list,
        model="sentence-transformers/all-mpnet-base-v2"
    )
    embeddings_array = np.array(result)
    return embeddings_array  # Shape: (N, 768)
```

### Output
- Jobs to `queue:stage4` (one per batch)
- Contains: `document_id`, `user_id`, `embeddings` (list of {id, embedding})

### Key Features
- Pagination for large documents (>1000 chunks)
- Batch processing (400 chunks per API call)
- Retry logic with exponential backoff
- Model loading detection (503 errors)
- Rate limiting (1.5-2s between batches)

### Error Handling
- Validates embedding dimensions (768)
- Retries on API failures (max 3 attempts)
- Marks document as "failed" on persistent errors
- Logs detailed error traces

---

## Stage 4: Vector Storage

### Worker: `stage4_write_embeddings.py`

### Input
- Job from `queue:stage4`
- Contains: `document_id`, `user_id`, `embeddings` (list of {id, embedding})

### Process

**1. Validate Embedding Dimensions**
```python
first_emb_dim = len(emb_list[0]["embedding"])
expected_dim = 768  # Schema: VECTOR(768)

if first_emb_dim != expected_dim:
    raise ValueError(f"Dimension mismatch: {first_emb_dim} != {expected_dim}")
```

**2. Write Embeddings to Supabase**
```python
BATCH_WRITE_SIZE = 100

for batch_start in range(0, len(emb_list), BATCH_WRITE_SIZE):
    batch_items = emb_list[batch_start:batch_start + BATCH_WRITE_SIZE]
    
    # Bulk upsert with all required fields
    update_payload = []
    for item in batch_items:
        update_payload.append({
            "id": item["id"],
            "embedding": item["embedding"],
            "text": existing_data["text"],
            "user_id": existing_data["user_id"],
            "document_id": existing_data["document_id"],
            # ... other fields
        })
    
    supabase.table("chunks").upsert(update_payload).execute()
```

**3. Check Completion**
```python
# Check if all chunks have embeddings
pending = supabase.table("chunks") \
    .select("id") \
    .eq("document_id", doc_id) \
    .is_("embedding", "null") \
    .execute().data

if len(pending) > 0:
    # More batches coming, wait
    return
```

**4. Compute Document-Level Embedding**
```python
# Fetch all chunk embeddings (paginated)
running_sum = None
total_count = 0
offset = 0

while True:
    rows = supabase.table("chunks") \
        .select("embedding") \
        .eq("document_id", doc_id) \
        .not_.is_("embedding", "null") \
        .range(offset, offset + 1000 - 1) \
        .execute().data
    
    if not rows:
        break
    
    batch_arr = np.array([r["embedding"] for r in rows])
    running_sum += batch_arr.sum(axis=0)
    total_count += len(rows)
    offset += 1000

# Compute average
doc_emb = (running_sum / total_count).tolist()
```

**5. Insert Document-Level Embedding**
```python
supabase.table("documents_index").upsert({
    "document_id": doc_id,
    "user_id": user_id_uuid,
    "title": "",
    "summary": "",
    "embedding": doc_emb
}).execute()
```

**6. Mark Document as Indexed**
```python
documents_col.update_one(
    {"_id": ObjectId(doc_id)},
    {"$set": {"status": "indexed"}}
)
```

### Output
- Embeddings written to `chunks` table
- Document-level embedding in `documents_index` table
- Status updated to "indexed"

### Key Features
- Batch upsert (100 chunks per batch)
- Stuck document detection (Redis state tracking)
- Automatic re-queuing of Stage 3 if stuck
- Paginated document-level embedding computation
- Fallback to individual updates on bulk failure

### Error Handling
- Dimension validation before writes
- Tracks processing state across worker instances
- Re-queues Stage 3 if >80% complete but stuck
- Marks document as "failed" if <50% writes succeed

---

## Pipeline Characteristics

### Concurrency Model

**Per-Stage Concurrency:** 1 document at a time
- Each worker processes one job at a time
- Prevents resource contention
- Simplifies error handling

**Cross-Stage Parallelism:** All stages run in parallel
- Stage 1 can extract Doc A
- Stage 2 can chunk Doc B
- Stage 3 can embed Doc C
- Stage 4 can store Doc D

### Queue Behavior

**Redis Lists (FIFO):**
- `LPUSH` - Add job to queue (left push)
- `BRPOP` - Block until job available (right pop)
- Timeout: 30 seconds (prevents infinite blocking)

**Job Payload:**
```json
{
  "document_id": "507f1f77bcf86cd799439011",
  "user_id": "user@example.com",
  "pages": {"1": "page text...", "2": "..."},
  "is_final_batch": true,
  "total_pages": 100
}
```

### Worker Communication

**Worker Wake-Up:**
- Each stage wakes up the next stage via HTTP health check
- Non-blocking (background task)
- Graceful failure (job still in queue)

**Status Tracking:**
- MongoDB: Primary status store
- Supabase: Mirror for frontend queries
- Redis: Temporary state (chunk indices, stuck detection)

### Memory Management

**Stage 1 (PDF Extraction):**
- Streams large files to disk
- Processes pages in batches
- Forces garbage collection
- Cleans up temp files

**Stage 2 (Chunking):**
- Processes pages incrementally
- Batch inserts (50 chunks)
- No full document in memory

**Stage 3 (Embedding):**
- Fetches chunks in pages (1000 at a time)
- Processes in batches (400 chunks)
- No full document in memory

**Stage 4 (Vector Storage):**
- Batch upserts (100 chunks)
- Paginated document-level computation
- Running sum (no full array in memory)

### Error Recovery

**Retry Logic:**
- Stage 3: 3 retries with exponential backoff
- Stage 4: Fallback to individual updates

**Failure Handling:**
- Updates status to "failed"
- Logs error to MongoDB
- Continues to next job (doesn't crash worker)

**Stuck Detection:**
- Stage 4 tracks pending chunks via Redis
- Re-queues Stage 3 if no progress after 10 checks
- Proceeds with indexing if >80% complete

---

## Performance Characteristics

### Throughput

**Small Documents (<10MB, <100 pages):**
- Stage 1: ~30 seconds
- Stage 2: ~10 seconds
- Stage 3: ~2 minutes (depends on chunk count)
- Stage 4: ~30 seconds
- **Total:** ~3-4 minutes

**Large Documents (50-100MB, 500+ pages):**
- Stage 1: ~2-3 minutes (streaming)
- Stage 2: ~1-2 minutes (incremental)
- Stage 3: ~10-15 minutes (rate limiting)
- Stage 4: ~2-3 minutes
- **Total:** ~15-25 minutes

### Bottlenecks

**Stage 3 (Embedding Computation):**
- Hugging Face API rate limits
- Network latency
- Model loading time (cold start)

**Mitigation:**
- Batch processing (400 chunks)
- Rate limiting (1.5-2s delay)
- Retry logic

### Scalability

**Horizontal Scaling:**
- Can run multiple instances of each worker
- Redis queue handles distribution
- Requires coordination for "1 at a time" constraint

**Vertical Scaling:**
- Increase batch sizes (if API allows)
- Reduce rate limiting delays
- Use faster embedding models

---

## Monitoring & Debugging

### Status Tracking

**Document Status Flow:**
```
uploaded → processing → extracted → indexed
                ↓
              failed
```

**Check Status:**
```javascript
db.documents.findOne({_id: ObjectId("...")})
```

### Queue Monitoring

**Check Queue Lengths:**
```bash
redis-cli
> LLEN queue:stage1
> LLEN queue:stage2
> LLEN queue:stage3
> LLEN queue:stage4
```

**Inspect Job:**
```bash
> LRANGE queue:stage1 0 0  # Peek at first job
```

### Worker Health

**Health Check Endpoints:**
- Stage 1: `http://localhost:8001/health`
- Stage 2: `http://localhost:8002/health`
- Stage 3: `http://localhost:8003/health`
- Stage 4: `http://localhost:8004/health`

**Response:**
```json
{"status": "ok", "worker": "stage1"}
```

### Logging

**Log Format:**
```
[STAGE1][INFO] Starting Stage 1 for document 507f1f77bcf86cd799439011
[STAGE1][WARN] ⚠️ Model is loading, waiting 2s before retry...
[STAGE1][ERROR] ❌ Failed to stream PDF from Supabase: ...
```

**Log Levels:**
- INFO (blue) - Normal operations
- WARN (yellow) - Recoverable issues
- ERROR (red) - Failures

---

## Deployment Considerations

### Environment Variables

**Required for All Workers:**
```bash
MONGO_URI=mongodb+srv://...
REDIS_URL=redis://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
```

**Stage 3 & 4 Specific:**
```bash
HF_API_KEY=hf_xxx
HF_EMBED_MODEL=sentence-transformers/all-mpnet-base-v2
EMBED_DIM=768
```

**Worker URLs (for wake-up):**
```bash
WORKER_STAGE1_URL=https://stage1.onrender.com/health
WORKER_STAGE2_URL=https://stage2.onrender.com/health
WORKER_STAGE3_URL=https://stage3.onrender.com/health
WORKER_STAGE4_URL=https://stage4.onrender.com/health
```

### Resource Requirements

**Per Worker:**
- RAM: 512MB minimum (1GB recommended)
- CPU: 1 core
- Disk: 1GB (for temp files in Stage 1)

**Redis:**
- RAM: 256MB minimum
- Persistence: Optional (jobs are transient)

**MongoDB:**
- Storage: 1GB per 10,000 documents
- RAM: 512MB minimum

**Supabase:**
- Storage: Depends on PDF sizes
- Database: 1GB per 1M chunks

### Deployment Platforms

**Recommended:**
- Workers: Render (Web Services)
- Redis: Upstash Redis
- MongoDB: MongoDB Atlas
- Supabase: Hosted

**Docker Deployment:**
```yaml
services:
  redis:
    image: redis:7
    ports: ["6379:6379"]
  
  worker-stage1:
    build: ./docker/worker
    environment:
      - STAGE=stage1
      - PORT=8001
  
  worker-stage2:
    build: ./docker/worker
    environment:
      - STAGE=stage2
      - PORT=8002
  
  # ... stage3, stage4
```

---

## Troubleshooting

### Common Issues

**1. Workers Not Processing**
- Check Redis connection: `redis-cli ping`
- Check queue has items: `LLEN queue:stage1`
- Check worker logs for errors
- Verify environment variables

**2. Embeddings Not Working**
- Check HF_API_KEY is set
- Verify model name: `all-mpnet-base-v2`
- Check embedding dimensions match schema (768)
- Test API: `curl -H "Authorization: Bearer $HF_API_KEY" ...`

**3. Documents Stuck in "processing"**
- Check which stage failed (look at queue lengths)
- Check worker logs for errors
- Manually re-queue job if needed
- Check MongoDB for error messages

**4. Out of Memory Errors**
- Reduce batch sizes (Stage 2: 50 → 25, Stage 3: 400 → 200)
- Enable streaming mode for all files (lower threshold)
- Increase worker RAM

**5. Slow Processing**
- Check Hugging Face API rate limits
- Reduce rate limiting delay (Stage 3)
- Use faster embedding model (trade-off: accuracy)
- Scale horizontally (multiple workers)

---

## Conclusion

The DOCQA Ultimate pipeline is designed for reliability, scalability, and efficiency. The 4-stage architecture separates concerns, enables parallel processing, and provides clear failure points for debugging. The streaming approach ensures memory efficiency for large documents, while the asynchronous design keeps the query endpoint always available.
