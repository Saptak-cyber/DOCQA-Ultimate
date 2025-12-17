# On-Demand Workers Implementation

## Overview

Your workers have been converted to **on-demand HTTP endpoints** that work perfectly with Render's free tier. Workers only consume resources when users are actively using your website.

## What Changed

### 1. Workers Now Have HTTP Endpoints

Each worker now runs:
- **HTTP server** (FastAPI) on port 8000 (or `$PORT` env var)
- **Queue worker** in background thread (processes Redis jobs)
- **Health endpoint** (`/health`) - used to wake up workers
- **Process endpoint** (`/process`) - can process jobs directly via HTTP

### 2. Automatic Wake-Up System

- **FastAPI** wakes Stage 1 worker when a file is uploaded
- **Stage 1** wakes Stage 2 when it completes
- **Stage 2** wakes Stage 3 when it completes  
- **Stage 3** wakes Stage 4 when it completes

This ensures workers wake up automatically when jobs are queued.

### 3. Dual Processing Mode

Workers support two ways to process jobs:
1. **Queue-based** (existing): Workers pull jobs from Redis queue
2. **HTTP-triggered** (new): API can call `/process` endpoint directly

Both methods work simultaneously - workers process from queue AND can be triggered via HTTP.

## How It Works

```
User uploads PDF
    ↓
FastAPI queues job in Redis
    ↓
FastAPI calls worker-stage1.onrender.com/health
    ↓
Worker wakes up (Render auto-wake)
    ↓
Worker processes job from queue
    ↓
Worker queues next stage job
    ↓
Worker wakes up next stage worker
    ↓
Process continues...
```

## Environment Variables

### FastAPI Backend

Add these to your FastAPI service on Render:

```bash
WORKER_STAGE1_URL=https://worker-stage1.onrender.com/health
WORKER_STAGE2_URL=https://worker-stage2.onrender.com/health
WORKER_STAGE3_URL=https://worker-stage3.onrender.com/health
WORKER_STAGE4_URL=https://worker-stage4.onrender.com/health
```

### Workers

Each worker needs:

```bash
# Stage 1
WORKER_STAGE2_URL=https://worker-stage2.onrender.com/health

# Stage 2
WORKER_STAGE3_URL=https://worker-stage3.onrender.com/health

# Stage 3
WORKER_STAGE4_URL=https://worker-stage4.onrender.com/health

# Stage 4
# (no next stage)
```

## Local Development

For local testing, workers use default URLs:

```bash
# Defaults (localhost)
WORKER_STAGE1_URL=http://localhost:8001/health
WORKER_STAGE2_URL=http://localhost:8002/health
WORKER_STAGE3_URL=http://localhost:8003/health
WORKER_STAGE4_URL=http://localhost:8004/health
```

Run workers locally:

```bash
# Terminal 1
PORT=8001 python -m workers.stage1_extraction

# Terminal 2
PORT=8002 python -m workers.stage2_chunk_store

# Terminal 3
PORT=8003 python -m workers.stage3_embed_compute

# Terminal 4
PORT=8004 python -m workers.stage4_write_embeddings
```

## Benefits

✅ **Free tier compatible** - Workers spin down when idle  
✅ **Auto-wake** - Workers wake automatically when jobs arrive  
✅ **No wasted resources** - Only runs when users are active  
✅ **Backward compatible** - Queue-based processing still works  
✅ **Resilient** - Jobs stay in Redis queue if worker is down  

## Cost: $0/month

All services run on Render's free tier. Workers only consume hours when processing jobs.

## Testing

1. **Check worker health**:
   ```bash
   curl https://worker-stage1.onrender.com/health
   # Should return: {"status":"ok","worker":"stage1"}
   ```

2. **Upload a document** - Workers should wake up automatically

3. **Monitor logs** in Render Dashboard to see wake-up calls

## Troubleshooting

### Workers not waking up
- Check worker URLs in FastAPI environment variables
- Verify workers are deployed and accessible
- Check Render logs for errors

### Jobs stuck in queue
- Workers may be sleeping - they'll wake on next job
- Check Redis connection
- Verify worker logs for processing errors

### Slow processing
- Normal on free tier (cold starts take ~30-60 seconds)
- Workers wake automatically when needed
- Processing is asynchronous (doesn't block API)
