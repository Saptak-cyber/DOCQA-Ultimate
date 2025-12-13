# Diagnostic Guide: Document Stuck at "Extracted"

## Pipeline Flow

1. **Stage 1** (`stage1_extraction.py`): Extracts text → Sets status to `"extracted"` → Pushes to `queue:stage2`
2. **Stage 2** (`stage2_chunk_store.py`): Chunks text → Stores in Supabase → Pushes to `queue:stage3`
3. **Stage 3** (`stage3_embed_compute.py`): Computes embeddings → Pushes to `queue:stage4`
4. **Stage 4** (`stage4_write_embeddings.py`): Writes embeddings → Sets status to `"indexed"` ✅

## Where Indexing Happens

**Answer: `workers/stage4_write_embeddings.py`** (line 299)

This is the final stage that:
- Writes chunk embeddings to Supabase
- Computes document-level embedding
- Upserts to `documents_index` table
- **Marks document as "indexed" in MongoDB**

## Troubleshooting: Document Stuck at "Extracted"

### Step 1: Check Which Workers Are Running

```bash
# Check if workers are running
ps aux | grep stage
```

You should see:
- `stage1_extraction.py` (if processing new uploads)
- `stage2_chunk_store.py` ⚠️ **REQUIRED**
- `stage3_embed_compute.py` ⚠️ **REQUIRED**
- `stage4_write_embeddings.py` ⚠️ **REQUIRED**

### Step 2: Check Redis Queues

```bash
# Connect to Redis
redis-cli

# Check queue lengths
LLEN queue:stage2
LLEN queue:stage3
LLEN queue:stage4

# Check if your document is in stage2 queue
LRANGE queue:stage2 0 -1
```

### Step 3: Check Worker Logs

Look for errors in:
- Stage 2 logs (chunking/storage)
- Stage 3 logs (embedding computation)
- Stage 4 logs (embedding writing)

### Step 4: Check MongoDB Document Status

```python
from pymongo import MongoClient
from bson import ObjectId

mongo = MongoClient("your_mongo_uri")
db = mongo.get_default_database()
doc = db["documents"].find_one({"_id": ObjectId("your_doc_id")})
print(f"Status: {doc['status']}")
print(f"Errors: {doc.get('processingErrors', [])}")
```

### Step 5: Check Supabase Chunks

```sql
-- Check if chunks exist for the document
SELECT COUNT(*) FROM chunks WHERE document_id = 'your_doc_id';

-- Check if chunks have embeddings
SELECT COUNT(*) FROM chunks 
WHERE document_id = 'your_doc_id' 
AND embedding IS NOT NULL;

-- Check if document is in documents_index
SELECT * FROM documents_index WHERE document_id = 'your_doc_id';
```

## Common Issues

### Issue 1: Stage 2 Worker Not Running
**Symptom**: Document stuck at "extracted", nothing in stage2 queue
**Fix**: Start Stage 2 worker
```bash
python workers/stage2_chunk_store.py
```

### Issue 2: Stage 3 Worker Not Running
**Symptom**: Chunks exist but no embeddings
**Fix**: Start Stage 3 worker
```bash
python workers/stage3_embed_compute.py
```

### Issue 3: Stage 4 Worker Not Running
**Symptom**: Embeddings computed but document not indexed
**Fix**: Start Stage 4 worker
```bash
python workers/stage4_write_embeddings.py
```

### Issue 4: Embedding Dimension Mismatch
**Symptom**: Stage 3 or Stage 4 errors about dimensions
**Fix**: Check `.env` file - `EMBED_MODEL` should be `all-mpnet-base-v2` (768 dims)

### Issue 5: HF API Issues
**Symptom**: Stage 3 fails with API errors
**Fix**: Check `HF_API_KEY` is set correctly

## Quick Fix: Restart All Workers

```bash
# Terminal 1
python workers/stage2_chunk_store.py

# Terminal 2
python workers/stage3_embed_compute.py

# Terminal 3
python workers/stage4_write_embeddings.py
```

## Manual Re-queue (If Needed)

If a document is stuck, you can manually re-queue it:

```python
import redis
import json
from bson import ObjectId

r = redis.from_url("redis://localhost:6379/0")
doc_id = "your_document_id"
user_id = "your_user_id"

# Re-queue to stage2
r.lpush("queue:stage2", json.dumps({"document_id": doc_id, "user_id": user_id}))
```
