# Running DOCQA Ultimate Locally

This guide explains how to run the entire DOCQA application on your local machine for development.

## Prerequisites

1. **Python 3.11+**: [Download Python](https://www.python.org/downloads/)
2. **Node.js 18+**: [Download Node.js](https://nodejs.org/)
3. **MongoDB**: [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) (free cloud) or local installation
4. **Redis**: [Upstash Redis](https://upstash.com/) (free cloud) or local installation
5. **Supabase Account**: [Supabase](https://supabase.com/) (free tier)
6. **Hugging Face API Key**: [Get token](https://huggingface.co/settings/tokens)
7. **Groq API Key**: [Get key](https://console.groq.com/)

## Step 1: Clone Repository

```bash
git clone <your-repo-url>
cd "DOCQA Ultimate"
```

## Step 2: Setup Backend Environment

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

### Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### Create Backend .env File

Create `.env` in the root directory:

```bash
# MongoDB
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/docqa

# Redis
REDIS_URL=redis://localhost:6379/0  # Or use Upstash URL

# Supabase
SUPABASE_URL=https://gztekltpixtxliezfxiz.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
SUPABASE_STORAGE_BUCKET=Docqa

# Authentication
JWT_SECRET=your-secret-key-here

# CORS
FRONTEND_ORIGIN=http://localhost:3000

# Groq API
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

# Hugging Face
HF_API_KEY=your-huggingface-api-key
HF_EMBED_MODEL=sentence-transformers/all-mpnet-base-v2
EMBED_DIM=768
USE_HF_API=true

# Worker URLs (local)
WORKER_STAGE1_URL=http://localhost:8001/health
WORKER_STAGE2_URL=http://localhost:8002/health
WORKER_STAGE3_URL=http://localhost:8003/health
WORKER_STAGE4_URL=http://localhost:8004/health
```

## Step 3: Setup Frontend Environment

### Install Frontend Dependencies

```bash
cd frontend
npm install
```

### Create Frontend .env File

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT=30000
```

## Step 4: Setup Local Services

### Option 1: Use Cloud Services (Recommended for Development)

- **MongoDB**: Use MongoDB Atlas (free tier)
- **Redis**: Use Upstash Redis (free tier)
- **Supabase**: Already cloud-based

### Option 2: Run Services Locally

#### Install and Run Redis Locally

**macOS (using Homebrew):**
```bash
brew install redis
brew services start redis
```

**Linux:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Windows:**
Download from [Redis Windows](https://github.com/microsoftarchive/redis/releases)

#### Install and Run MongoDB Locally

**macOS (using Homebrew):**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

**Linux:**
```bash
sudo apt-get install mongodb
sudo systemctl start mongodb
```

**Windows:**
Download from [MongoDB Download Center](https://www.mongodb.com/try/download/community)

Update `.env` with local MongoDB URI:
```bash
MONGO_URI=mongodb://localhost:27017/docqa
```

## Step 5: Run the Application

You'll need **6 terminal windows/tabs** to run everything:

### Terminal 1: FastAPI Backend

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server will run at: `http://localhost:8000`

### Terminal 2: Worker Stage 1 (PDF Extraction)

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run worker
PORT=8001 python -m workers.stage1_extraction
```

Worker will run at: `http://localhost:8001`

### Terminal 3: Worker Stage 2 (Chunking)

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run worker
PORT=8002 python -m workers.stage2_chunk_store
```

Worker will run at: `http://localhost:8002`

### Terminal 4: Worker Stage 3 (Embedding)

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run worker
PORT=8003 python -m workers.stage3_embed_compute
```

Worker will run at: `http://localhost:8003`

### Terminal 5: Worker Stage 4 (Write Embeddings)

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run worker
PORT=8004 python -m workers.stage4_write_embeddings
```

Worker will run at: `http://localhost:8004`

### Terminal 6: Next.js Frontend

```bash
cd frontend
npm run dev
```

Frontend will run at: `http://localhost:3000`

## Step 6: Verify Everything is Running

### Check Backend

Visit `http://localhost:8000/docs` to see the FastAPI Swagger documentation.

### Check Workers

- Worker 1: `http://localhost:8001/health`
- Worker 2: `http://localhost:8002/health`
- Worker 3: `http://localhost:8003/health`
- Worker 4: `http://localhost:8004/health`

### Check Frontend

Visit `http://localhost:3000` to see the application.

## Step 7: Test the Application

1. **Sign Up**: Create a new account at `http://localhost:3000/signup`
2. **Upload PDF**: Go to Upload page and upload a test PDF
3. **Check Logs**: Watch the worker terminals to see processing stages
4. **Query Document**: Go to Query page and ask questions about your document

## Development Workflow

### Making Changes

#### Backend Changes

1. Edit Python files in `app/` or `workers/`
2. FastAPI auto-reloads (if using `--reload` flag)
3. Workers need manual restart (Ctrl+C, then restart)

#### Frontend Changes

1. Edit TypeScript/React files in `frontend/`
2. Next.js auto-reloads
3. Changes reflect immediately in browser

### Debugging

#### Backend Debugging

Add print statements or use Python debugger:

```python
import pdb; pdb.set_trace()  # Add breakpoint
```

#### Frontend Debugging

Use browser DevTools:
- **Console**: Check for JavaScript errors
- **Network**: Inspect API requests/responses
- **React DevTools**: Inspect component state

### Database Inspection

#### MongoDB

**Using MongoDB Compass:**
1. Download [MongoDB Compass](https://www.mongodb.com/products/compass)
2. Connect using your `MONGO_URI`
3. Browse collections: `documents`, `users`, etc.

**Using CLI:**
```bash
mongosh "mongodb://localhost:27017/docqa"
db.documents.find()
db.users.find()
```

#### Redis

**Using redis-cli:**
```bash
redis-cli
KEYS *
LLEN queue:stage1
LRANGE queue:stage1 0 -1
```

#### Supabase

1. Go to [Supabase Dashboard](https://app.supabase.com/)
2. Select your project
3. Navigate to:
   - **Table Editor**: View `documents`, `chunks` tables
   - **Storage**: View uploaded PDFs
   - **SQL Editor**: Run custom queries

## Troubleshooting

### Port Already in Use

If you get "Address already in use" error:

**Find and kill process:**
```bash
# macOS/Linux
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Python Module Not Found

```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify virtual environment is activated
which python  # Should show venv path
```

### Frontend Build Errors

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Worker Not Processing Jobs

1. Check Redis connection: `redis-cli ping`
2. Verify worker is running: Visit health endpoint
3. Check Redis queue: `redis-cli LLEN queue:stage1`
4. Check worker logs for errors

### CORS Errors

Ensure `FRONTEND_ORIGIN=http://localhost:3000` is set in backend `.env`

### Supabase Connection Issues

1. Verify `SUPABASE_URL` and `SUPABASE_KEY` are correct
2. Check Supabase project is active
3. Verify storage bucket exists and is public

## Environment Variables Summary

### Backend (.env)

```bash
# Required
MONGO_URI=<mongodb-connection-string>
REDIS_URL=<redis-connection-string>
SUPABASE_URL=<supabase-project-url>
SUPABASE_KEY=<supabase-anon-key>
SUPABASE_SERVICE_KEY=<supabase-service-role-key>
SUPABASE_STORAGE_BUCKET=Docqa
JWT_SECRET=<random-secret-string>
GROQ_API_KEY=<groq-api-key>
HF_API_KEY=<huggingface-api-key>

# Optional (with defaults)
FRONTEND_ORIGIN=http://localhost:3000
GROQ_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
HF_EMBED_MODEL=sentence-transformers/all-mpnet-base-v2
EMBED_DIM=768
USE_HF_API=true
WORKER_STAGE1_URL=http://localhost:8001/health
WORKER_STAGE2_URL=http://localhost:8002/health
WORKER_STAGE3_URL=http://localhost:8003/health
WORKER_STAGE4_URL=http://localhost:8004/health
```

### Frontend (frontend/.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT=30000
```

## Stopping the Application

Press `Ctrl+C` in each terminal to stop:
1. FastAPI backend
2. All 4 workers
3. Frontend

To stop local services:
```bash
# Redis
brew services stop redis

# MongoDB
brew services stop mongodb-community
```

## Quick Start Script (Optional)

Create `start.sh` for easier startup:

```bash
#!/bin/bash

# Start backend and workers in background
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
PORT=8001 python -m workers.stage1_extraction &
PORT=8002 python -m workers.stage2_chunk_store &
PORT=8003 python -m workers.stage3_embed_compute &
PORT=8004 python -m workers.stage4_write_embeddings &

# Start frontend
cd frontend && npm run dev
```

Make executable and run:
```bash
chmod +x start.sh
./start.sh
```

## Next Steps

- Read [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) for production deployment
- Read [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for frontend deployment
- Check [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for codebase overview
