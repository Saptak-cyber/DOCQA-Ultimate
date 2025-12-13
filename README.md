# DOCQA Ultimate - Setup & Deployment Guide

Complete setup guide for a production-ready RAG system with hierarchical retrieval, Redis queue pipeline, and citation-forcing LLM responses.

---

## 🏗️ Architecture Overview

- **FastAPI Backend**: Upload endpoint + query API
- **Redis Queue**: 4-stage pipeline (extraction → chunking → embedding → storage)
- **MongoDB**: PDF metadata, status tracking, deduplication
- **Supabase Storage**: File storage
- **Supabase + pgvector**: Vector database for hierarchical search
- **Worker Pipeline**: Single-threaded per stage, parallel across stages

---

docker compose up --build

## ✅ 1. ENVIRONMENT VARIABLES

Create `.env` file in the project root:

```bash
# --- Supabase ---
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=xxxxx
SUPABASE_SERVICE_KEY=xxxxx

# --- Supabase DB (vector embeddings) ---
SUPABASE_DB_URL=postgresql://postgres:password@db.supabase.co:5432/postgres

# --- MongoDB ---
MONGO_URI=mongodb+srv://...

# --- Supabase Storage ---
SUPABASE_STORAGE_BUCKET=documents

# --- JWT ---
JWT_SECRET=xxxx

# --- Redis Queue ---
REDIS_URL=redis://localhost:6379/0

# --- Embedding Model ---
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=768

# --- LLM (Groq) ---
LLM_PROVIDER=groq
GROQ_API_KEY=xxxxx
```

Create separate `.env.local`, `.env.production` for different environments.

---

## ✅ 2. SETUP SUPABASE VECTOR DATABASE

### Step 2.1 — Enable pgvector

Run in Supabase SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

### Step 2.2 — Create Tables

**1. Documents table (optional mirror)**

```sql
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT,
  storage_bucket TEXT,
  storage_path TEXT,
  storage_public_url TEXT,
  status TEXT DEFAULT 'uploaded',
  pages INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**2. Document-level embeddings (documents_index)**

```sql
CREATE TABLE IF NOT EXISTS documents_index (
    document_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    title TEXT,
    summary TEXT,
    embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Index:**

```sql
CREATE INDEX documents_index_embedding_idx
ON documents_index USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);
```

**3. Chunk-level embeddings (chunks)**

```sql
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    document_id TEXT NOT NULL,
    page_number INT,
    chunk_index INT,
    text TEXT NOT NULL,
    tokens INT,
    embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**

```sql
CREATE INDEX chunks_document_id_idx ON chunks (document_id);
CREATE INDEX chunks_user_id_idx ON chunks (user_id);
CREATE INDEX chunks_embedding_idx 
ON chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 500);
```

### Step 2.3 — Create Supabase RPC Functions

**match_documents_index** (Stage 1: get top documents)

Run the SQL from `supabase/functions/match_documents_index.sql`:

```sql
create or replace function match_documents_index(
  query_embedding vector(768),
  user_id uuid,
  match_count int default 5
)
returns table(
  document_id text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    di.document_id,
    1 - (di.embedding <=> query_embedding) as similarity
  from documents_index di
  where di.user_id = match_documents_index.user_id
  order by di.embedding <-> query_embedding
  limit match_count;
end;
$$;
```

**match_chunks_filtered** (Stage 2: search within docs)

Run the SQL from `supabase/functions/match_chunks_filtered.sql`:

```sql
create or replace function match_chunks_filtered(
  query_embedding vector(768),
  doc_ids text[],
  user_id uuid,
  match_count int default 20
)
returns table(
  id uuid,
  document_id text,
  page_number int,
  chunk_index int,
  text text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    c.id,
    c.document_id,
    c.page_number,
    c.chunk_index,
    c.text,
    1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  where c.user_id = match_chunks_filtered.user_id
  and c.document_id = any(doc_ids)
  order by c.embedding <-> query_embedding
  limit match_count;
end;
$$;
```

✔ Now Python can pass embeddings as list → Supabase RPC handles vector search.

---

## ✅ 3. SETUP REDIS TASK QUEUE

### Step 3.1 — Install Redis locally

**macOS:**

```bash
brew install redis
brew services start redis

redis-server
redis-cli shutdown
```
For Homebrew Redis, the logs depend on how it’s started:
If started via brew services start redis:
Show recent service logs: brew services logs redis or follow: brew services logs redis -f.
Direct log file (Intel): /usr/local/var/log/redis.log; (Apple Silicon): /opt/homebrew/var/log/redis.log. Tail it: tail -f /opt/homebrew/var/log/redis.log (adjust prefix).
If you start Redis manually (redis-server), it logs to stdout unless logfile is set in redis.conf. Run it in a terminal to see logs, or set logfile /path/to/redis.log in the config and restart.
To see live traffic/commands (not a log, but handy): redis-cli MONITOR (only use briefly; it’s verbose).
Check which prefix you have with brew --prefix and adjust the log path accordingly.

brew services start redis.
brew services stop redis.
**Docker:**

```bash
docker run -d -p 6379:6379 redis
docker compose up --build
```

### Step 3.2 — Queue Structure

You have 4 queues (Redis lists):

- `queue:stage1` - PDF extraction
- `queue:stage2` - Chunking
- `queue:stage3` - Embedding computation
- `queue:stage4` - Vector storage

Each step processes **1 PDF at a time**, but steps run **in parallel**.

### Step 3.3 — Worker Execution Rules

| Step | Queue | Concurrent? | Starts when? |
|------|-------|-------------|--------------|
| 1. PDF extraction | `queue:stage1` | 1 at a time | Immediately after upload |
| 2. Chunking | `queue:stage2` | 1 at a time | After extraction completes |
| 3. Embedding | `queue:stage3` | 1 at a time | After chunking completes |
| 4. Store vectors | `queue:stage4` | 1 at a time | After embedding completes |

**Important**: While these run, the **query endpoint ALWAYS works** (no blocking).

---

## ✅ 4. QUERY ENDPOINT AVAILABILITY

**Guarantee**: Query endpoint works during processing.

**How?**

- Workers insert chunks in small batches (50-100)
- No table-wide locks or EXCLUSIVE transactions
- pgvector allows queries while inserting
- Workers run asynchronously from API

**Query Flow** (always available):

```
User query → Embed question → 
Supabase RPC: match_documents_index → 
Supabase RPC: match_chunks_filtered → 
Rerank (optional) → LLM → 
Answer with [Document: page X] citations
```

---

## ✅ 5. SETUP MONGODB

### Collections

**documents** - stores:
- Document metadata
- Supabase Storage info (bucket, path, public_url)
- Status flags (`uploaded`, `processing`, `indexed`, `failed`)
- SHA-256 hash for deduplication
- Page-level text (temporary, for chunking)

### Index for Deduplication

```javascript
db.documents.createIndex({ userId: 1, "metadata.hash": 1 }, { unique: true });
```

This prevents uploading the same file twice.

---

## ✅ 6. UPLOAD & DEDUPLICATION (SUPABASE STORAGE)

### Upload Flow with Duplicate Prevention

1. **Compute SHA-256** checksum of file (backend on upload)
2. **Query MongoDB**:
   ```javascript
   db.documents.findOne({ userId: "user_id", "metadata.hash": "sha256_hash" })
   ```
3. **If exists** → Return: `{ status: "exists", document_id: "..." }`
4. **Else**:
   - Upload to Supabase Storage bucket
   - Store metadata in MongoDB
   - Push to `queue:stage1`

---

## ✅ 7. INSTALL DEPENDENCIES

Create `requirements.txt`:

```txt
fastapi
uvicorn
python-multipart
pydantic
pymongo
redis
supabase
pyjwt
pypdf
sentence-transformers
groq
psycopg2-binary
numpy
scikit-learn
```

Install:

```bash
pip install -r requirements.txt
```

---

## ✅ 8. HOW TO RUN EVERYTHING (LOCAL SETUP)

### Step 1 — Start Redis

```bash
redis-server
```

Or with Docker:

```bash
docker-compose up redis
```

### Step 2 — Start Workers (4 separate terminals/processes)

Each worker runs **one at a time per stage**:

**Terminal 1:**
```bash
python workers/stage1_extraction.py
```

**Terminal 2:**
```bash
python workers/stage2_chunk_store.py
```

**Terminal 3:**
```bash
python workers/stage3_embed_compute.py
```

**Terminal 4:**
```bash
python workers/stage4_write_embeddings.py
```

### Step 3 — Start FastAPI Backend

```bash
uvicorn app.main:app --reload --port 8000
```

### Step 4 — Test Upload

```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "file=@test.pdf"
```

---

## ✅ 9. DOCKER DEPLOYMENT (OPTIONAL)

### Using docker-compose

```bash
docker-compose up --build
```

This starts:
- Redis queue
- Worker container (runs all 4 workers)
- FastAPI API container (optional, add if needed)

### docker-compose.yml

Already created at `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7
    container_name: redis_queue
    ports:
      - "6379:6379"
    restart: always

  worker:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile.worker
    depends_on:
      - redis
    environment:
      REDIS_URL: "redis://redis_queue:6379/0"
    restart: always
```

**Note**: Update `docker/worker/Dockerfile.worker` to copy correct paths and run all workers.

---

## 📌 FINAL PIPELINE FLOW

### PDF Upload Flow

```
User uploads PDF
    ↓
FastAPI /upload endpoint
    ↓
Compute SHA-256 hash → Check MongoDB duplicate
    ↓ (if not duplicate)
Upload to Cloudinary
    ↓
Insert metadata to MongoDB (status: "uploaded")
    ↓
Push to queue:stage1
    ↓
[Worker 1] Extract pages → Store pages_text in Mongo → Push to queue:stage2
    ↓
[Worker 2] Chunk pages → Insert chunks to Supabase (embedding=NULL) → Push to queue:stage3
    ↓
[Worker 3] Compute embeddings → Push batches to queue:stage4
    ↓
[Worker 4] Write embeddings to Supabase → Create doc-level embedding → Mark status="indexed"
```

### Query Flow (ALWAYS AVAILABLE)

```
User asks question
    ↓
Embed question with same model
    ↓
Call Supabase RPC: match_documents_index (top 3 docs)
    ↓
Call Supabase RPC: match_chunks_filtered (top 12 chunks from those docs)
    ↓
Optional: Rerank with cross-encoder
    ↓
Format context with [DocumentTitle: page X] labels
    ↓
Call LLM with strict prompt forcing citations
    ↓
Return answer with page citations
```

---

## 🎯 TUNING IVFFLAT INDEX

### Run Benchmark

After loading data:

```bash
python benchmark_lists.py
```

This tests different `lists` values and recommends optimal setting based on:
- Latency (ms)
- Recall@20

Update your SQL schema with the recommended `lists` value.

---

## 🚀 PRODUCTION DEPLOYMENT

### Recommended Platforms

- **API**: Render, Fly.io, Railway, Google Cloud Run
- **Workers**: Docker containers on same platform
- **Redis**: Upstash Redis, Redis Cloud, or managed Redis
- **MongoDB**: MongoDB Atlas
- **Supabase**: Already hosted

### Environment Variables

Set all `.env` variables in your deployment platform's dashboard.

### Scaling

- Run multiple API instances (horizontal scaling)
- Keep **1 worker per stage** (as designed)
- Use managed Redis for reliability
- Monitor queue lengths with Redis monitoring

---

## 🧪 TESTING

### Test Upload

```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer YOUR_JWT" \
  -F "file=@sample.pdf"
```

### Check Queue Status

```bash
redis-cli
> LLEN queue:stage1
> LLEN queue:stage2
> LLEN queue:stage3
> LLEN queue:stage4
```

### Check Processing Status

Query MongoDB:

```javascript
db.documents.findOne({ _id: ObjectId("...") })
```

Look at `status` field: `uploaded`, `processing`, `indexed`, or `failed`.

---

## 📚 PROJECT STRUCTURE

```
DOCQA Ultimate/
├── app/
│   ├── main.py              # FastAPI upload endpoint
│   ├── chunker.py           # PDF extraction & chunking logic
│   └── retrieval.py         # Hierarchical retrieval + LLM
├── workers/
│   ├── stage1_extraction.py # Worker 1: PDF → pages
│   ├── stage2_chunk_store.py # Worker 2: pages → chunks
│   ├── stage3_embed_compute.py # Worker 3: chunks → embeddings
│   └── stage4_write_embeddings.py # Worker 4: embeddings → DB
├── queue/
│   └── queue.py             # Redis queue helpers
├── supabase/
│   └── functions/
│       ├── match_documents_index.sql
│       └── match_chunks_filtered.sql
├── docker/
│   └── worker/
│       └── Dockerfile.worker
├── supabase_schema.sql      # Full DB schema
├── docker-compose.yml       # Redis + worker services
├── benchmark_lists.py       # IVFFlat tuning script
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (DO NOT COMMIT)
└── README.md                # This file
```

---

## 🔧 TROUBLESHOOTING

### Workers not processing

1. Check Redis is running: `redis-cli ping`
2. Check queue has items: `redis-cli LLEN queue:stage1`
3. Check worker logs for errors
4. Verify MongoDB connection
5. Verify Supabase connection

### Embeddings not working

1. Check `EMBED_MODEL` is downloaded (sentence-transformers)
2. Verify embedding dimensions match SQL schema (768 or 1536)
3. Check GPU availability if using large models

### Search returns no results

1. Verify documents are `indexed` in MongoDB
2. Check chunks table has embeddings: `SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL`
3. Test RPC functions directly in Supabase SQL editor
4. Run `benchmark_lists.py` to tune index

### Duplicate uploads not prevented

1. Check MongoDB index exists on `userId` + `metadata.hash`
2. Verify hash computation is consistent
3. Check upload endpoint hash lookup logic

---

## 📞 SUPPORT

For issues or questions:
1. Check worker logs
2. Check Redis queue lengths
3. Check MongoDB document status
4. Verify Supabase RPC functions exist
5. Test with small PDF first

---

## 🎉 YOU'RE READY!

Your production-ready RAG system with:
✅ Hierarchical retrieval (doc-level → chunk-level)  
✅ Citation-forcing LLM with page numbers  
✅ Redis queue pipeline (1 PDF per stage, parallel stages)  
✅ Duplicate prevention  
✅ Query endpoint always available  
✅ pgvector for fast semantic search  

Start the workers, upload a PDF, and query away! 🚀


Parameters in query
retrieval.py

`temperature (currently: 0.1): Controls randomness`
`Lower (0.0-0.3) = more deterministic, focused`
`Higher (0.7-1.0) = more creative, varied`
`max_tokens (currently: 1024): Maximum tokens in the response`
`Higher = longer answers, more cost`
`top_p (currently: 0.9): Nucleus sampling parameter`
`Controls diversity of token selection`
`Lower = more focused, Higher = more diverse`

`temperature=0.1,`
`max_tokens=1024,`
`top_p=0.9,`
`top_docs: int = 3`
`top_chunks: int = 20`