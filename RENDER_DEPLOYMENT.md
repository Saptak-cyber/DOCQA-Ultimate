# Render Deployment Guide (Free Tier)

This guide explains how to deploy your DOCQA application on Render's free tier with on-demand workers.

## Architecture

```
Frontend (Vercel) → FastAPI (Render Free) → Upstash Redis → Workers (Render Free × 4)
```

## Prerequisites

1. **Render Account**: Sign up at [render.com](https://render.com)
2. **Upstash Redis**: Create a free Redis instance at [upstash.com](https://upstash.com)
3. **GitHub Repository**: Push your code to GitHub

## Step 1: Deploy FastAPI Backend

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `docqa-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **Free**

5. Add Environment Variables:
   ```
   MONGO_URI=<your-mongodb-uri>
   REDIS_URL=<your-upstash-redis-url>
   SUPABASE_URL=<your-supabase-url>
   SUPABASE_KEY=<your-supabase-key>
   SUPABASE_STORAGE_BUCKET=documents
   JWT_SECRET=<your-jwt-secret>
   FRONTEND_ORIGIN=https://your-frontend.vercel.app
   WORKER_STAGE1_URL=https://worker-stage1.onrender.com/health
   WORKER_STAGE2_URL=https://worker-stage2.onrender.com/health
   WORKER_STAGE3_URL=https://worker-stage3.onrender.com/health
   WORKER_STAGE4_URL=https://worker-stage4.onrender.com/health
   ```

6. Click **"Create Web Service"**

## Step 2: Deploy Workers

Deploy each worker as a separate Web Service (not Background Worker - free tier doesn't support that).

### Worker Stage 1 (PDF Extraction)

1. Click **"New +"** → **"Web Service"**
2. Connect same GitHub repository
3. Configure:
   - **Name**: `worker-stage1`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m workers.stage1_extraction`
   - **Instance Type**: **Free**

4. Add Environment Variables (same as FastAPI):
   ```
   MONGO_URI=<your-mongodb-uri>
   REDIS_URL=<your-upstash-redis-url>
   SUPABASE_URL=<your-supabase-url>
   SUPABASE_KEY=<your-supabase-key>
   SUPABASE_STORAGE_BUCKET=documents
   JWT_SECRET=<your-jwt-secret>
   PORT=10000
   ```

5. Click **"Create Web Service"**

### Worker Stage 2 (Chunking)

Repeat the same process:
- **Name**: `worker-stage2`
- **Start Command**: `python -m workers.stage2_chunk_store`
- **PORT**: `10001`

### Worker Stage 3 (Embedding)

- **Name**: `worker-stage3`
- **Start Command**: `python -m workers.stage3_embed_compute`
- **PORT**: `10002`
- **Additional Env Var**: `HF_API_KEY=<your-huggingface-api-key>`

### Worker Stage 4 (Write Embeddings)

- **Name**: `worker-stage4`
- **Start Command**: `python -m workers.stage4_write_embeddings`
- **PORT**: `10003`

## Step 3: Update Worker URLs in FastAPI

After deploying all workers, update the FastAPI environment variables with the actual Render URLs:

```
WORKER_STAGE1_URL=https://worker-stage1.onrender.com/health
WORKER_STAGE2_URL=https://worker-stage2.onrender.com/health
WORKER_STAGE3_URL=https://worker-stage3.onrender.com/health
WORKER_STAGE4_URL=https://worker-stage4.onrender.com/health
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


## How It Works

1. **User uploads PDF** → FastAPI queues job in Redis
2. **FastAPI calls worker health endpoint** → Worker wakes up (Render auto-wake)
3. **Worker processes job from queue** → Stays alive for ~15 minutes
4. **Worker completes job** → Queues next stage job
5. **If no new jobs** → Worker spins down after 15 min idle

## Free Tier Limitations

- **750 free hours/month** (~31 days if running 24/7)
- **Spins down after 15 min idle** (auto-wakes on next request)
- **Cold start delay**: ~30-60 seconds when waking from sleep

## Cost: $0/month

All services run on Render's free tier. Workers only consume hours when processing jobs.

## Monitoring

- Check worker logs in Render Dashboard
- Monitor Redis queue lengths: `redis-cli LLEN queue:stage1`
- Check document status in MongoDB

## Troubleshooting

### Workers not processing jobs
- Check if workers are awake (visit health endpoint)
- Verify Redis connection
- Check worker logs for errors

### Slow processing
- Normal on free tier (cold starts)
- Workers wake up automatically when jobs arrive
- Processing happens asynchronously

### Workers spinning down
- This is expected behavior on free tier
- They wake automatically when FastAPI calls health endpoint
- Jobs remain in Redis queue until processed
