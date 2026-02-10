# workers/stage3_embed_compute.py
import os
import json
import time
import traceback
from dotenv import load_dotenv
import redis
from supabase import create_client
import numpy as np
from bson import ObjectId
from pymongo import MongoClient
from huggingface_hub import InferenceClient
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread
import httpx

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MONGO_URI = os.getenv("MONGO_URI")
WORKER_STAGE4_URL = os.getenv("WORKER_STAGE4_URL", "http://localhost:8004/health")

# Hugging Face Inference API Configuration
HF_API_KEY = os.getenv("HF_API_KEY")  # Get from https://huggingface.co/settings/tokens
HF_EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")

# Embedding configuration
EXPECTED_DIM = int(os.getenv("EMBED_DIM", "768"))  # Default matches all-mpnet-base-v2
USE_HF_API = os.getenv("USE_HF_API", "true").lower() == "true"  # Default to HF API

# Initialize Hugging Face Inference Client
if USE_HF_API and HF_API_KEY:
    hf_client = InferenceClient(
        provider="hf-inference",
        api_key=HF_API_KEY,
    )
else:
    hf_client = None

# Redis
r = redis.from_url(REDIS_URL, decode_responses=True)

# Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# MongoDB (for status updates)
if MONGO_URI:
    mongo = MongoClient(MONGO_URI)
    db = mongo.get_default_database()
    documents_col = db["documents"]
else:
    documents_col = None

# Batch size - smaller for API calls to avoid rate limits
BATCH = 400 if USE_HF_API else 32

def log(msg: str):
    """Unified stage3 logger"""
    print(f"[Stage3] {msg}", flush=True)

def embed_texts_hf_api(text_list):
    """Embed texts using Hugging Face Inference API via InferenceClient."""
    if not hf_client:
        raise ValueError("HF_API_KEY environment variable is required for Hugging Face API")
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            log(f"Calling Hugging Face API (attempt {attempt + 1}/{max_retries})...")
            log(f"Model: {HF_EMBED_MODEL}, Batch size: {len(text_list)}")
            
            # Use the official InferenceClient feature_extraction method
            # It accepts either a single string or a list of strings
            result = hf_client.feature_extraction(
                text_list,
                model=HF_EMBED_MODEL,
            )
            
            # Convert to numpy array
            # The API returns a list of embeddings (each is a list of floats)
            if isinstance(result, list):
                embeddings_array = np.array(result)
            else:
                # Single embedding case
                embeddings_array = np.array([result])
            
            # Handle nested structures: if shape is (1, N, 768), reshape to (N, 768)
            if len(embeddings_array.shape) == 3 and embeddings_array.shape[0] == 1:
                embeddings_array = embeddings_array[0]  # Remove the outer dimension
            elif len(embeddings_array.shape) == 1:
                # Single embedding, reshape to (1, dim)
                embeddings_array = embeddings_array.reshape(1, -1)
            
            log(f"✅ Received embeddings: shape {embeddings_array.shape}")
            return embeddings_array
                
        except Exception as e:
            error_str = str(e)
            # Handle model loading (503-like errors)
            if "503" in error_str or "loading" in error_str.lower() or "unavailable" in error_str.lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    log(f"⚠️ Model is loading, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    log(f"❌ Model still loading after {max_retries} attempts")
                    raise
            
            # For other errors, retry with exponential backoff
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                log(f"⚠️ API request failed, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                log(f"❌ HF API request failed after {max_retries} attempts: {e}")
                traceback.print_exc()
                raise
    
    raise Exception("Failed to get embeddings from Hugging Face API")

def embed_texts(text_list):
    """Embed list of texts using Hugging Face API."""
    log(f"Embedding batch of {len(text_list)} texts using Hugging Face API...")
    try:
        embeddings = embed_texts_hf_api(text_list)
        return embeddings
    except Exception as e:
        log(f"⚠️ Embedding failed: {e}")
        traceback.print_exc()
        return None

def process_job(job):
    doc_id = job["document_id"]
    user_id = job["user_id"]

    log(f"---- Starting Stage3 for document {doc_id} (user {user_id}) ----")
    log(f"Using Hugging Face Inference API: {HF_EMBED_MODEL}")

     # Fetch chunks WITHOUT embeddings (with pagination to handle >1000 chunks)
    log("Fetching chunks without embeddings...")
    chunks = []
    PAGE_SIZE = 1000  # Supabase default limit
    offset = 0
    
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
        
        # If we got fewer than PAGE_SIZE, we've reached the end
        if len(page_chunks) < PAGE_SIZE:
            break
        
        offset += PAGE_SIZE
        log(f"Fetched {len(chunks)} chunks so far...")
    
    total_chunks = len(chunks)
    log(f"Found {total_chunks} chunks with missing embeddings.")

    if total_chunks == 0:
        log("No chunks to embed. Skipping document.")
        return

    # Process in batches
    for i in range(0, total_chunks, BATCH):
        batch = chunks[i:i+BATCH]
        texts = [c["text"] for c in batch]
        chunk_ids = [c["id"] for c in batch]

        log(f"Processing batch {i//BATCH + 1}/{(total_chunks-1)//BATCH + 1} ({len(texts)} chunks)...")

        embs = embed_texts(texts)
        if embs is None:
            log("⚠️ Skipping this batch due to embedding failure.")
            continue

        # Validate embedding dimensions and shape
        if len(embs.shape) == 1:
            # Single embedding, reshape
            embs = embs.reshape(1, -1)
        elif len(embs.shape) == 3:
            # Nested structure (1, N, 768), flatten to (N, 768)
            if embs.shape[0] == 1:
                embs = embs[0]
            else:
                log(f"⚠️ Unexpected 3D shape: {embs.shape}, attempting to reshape...")
                embs = embs.reshape(-1, embs.shape[-1])
        
        # Ensure we have the right number of embeddings
        if embs.shape[0] != len(batch):
            log(f"⚠️ Embedding count mismatch: got {embs.shape[0]} embeddings for {len(batch)} texts")
            log(f"⚠️ Shape: {embs.shape}")
            # Try to fix if possible
            if embs.shape[0] > len(batch):
                embs = embs[:len(batch)]
            elif embs.shape[0] < len(batch):
                log(f"❌ Not enough embeddings, skipping batch")
                continue
        
        if embs.shape[1] != EXPECTED_DIM:
            log(f"❌ ERROR: Embeddings have {embs.shape[1]} dimensions but expected {EXPECTED_DIM}")
            log(f"❌ This batch will fail in Stage 4. Check HF_EMBED_MODEL and EMBED_DIM settings.")
            # Still send it, but Stage 4 will catch and fail gracefully

        # Prepare payload for Stage4
        payload_batch = [
            {"id": chunk_ids[j], "embedding": embs[j].tolist()}
            for j in range(len(batch))
        ]

        r.lpush(
            "queue:stage4",
            json.dumps({
                "document_id": doc_id,
                "user_id": user_id,
                "embeddings": payload_batch
            })
        )

        log(f"Batch pushed to stage4 queue: {len(payload_batch)} embeddings.")
        # Wake up stage4 worker
        try:
            httpx.get(WORKER_STAGE4_URL, timeout=30.0)
            log(f"✅ Woke up stage4 worker at {WORKER_STAGE4_URL}")
        except Exception as e:
            log(f"⚠️ Failed to wake stage4 worker: {e}")
        
        # Progress logging for large documents
        if total_chunks > 100:
            progress_pct = ((i + len(batch)) / total_chunks) * 100
            log(f"Progress: {i + len(batch)}/{total_chunks} chunks ({progress_pct:.1f}%)")
        
        # Small delay to respect rate limits (HF free tier: ~30 requests/min)
        # Reduce delay slightly for large documents to speed up processing
        time.sleep(1.5 if total_chunks > 100 else 2)

    log(f"---- Completed Stage3 for document {doc_id} ----")

def run():
    """Queue-based worker loop (runs in background thread)"""
    log("Stage3 worker loop started. Waiting for jobs in queue:stage3")
    
    if USE_HF_API:
        if not HF_API_KEY:
            log("❌ ERROR: USE_HF_API is true but HF_API_KEY is not set!")
            log("❌ Please set HF_API_KEY in your .env file (get token from https://huggingface.co/settings/tokens)")
            return
        log(f"✅ Using Hugging Face Inference API: {HF_EMBED_MODEL}")
        log(f"✅ Expected embedding dimension: {EXPECTED_DIM}")
    else:
        log("⚠️ USE_HF_API is false - but local embedding is not implemented in this version")
        log("⚠️ Please set USE_HF_API=true and provide HF_API_KEY")
        return
    
    while True:
        try:
            result = r.brpop("queue:stage3", timeout=30)
            if result is None:
                continue  # Timeout, check again
            
            _, payload = result
            try:
                job = json.loads(payload)
            except json.JSONDecodeError as e:
                log(f"❌ Failed to parse job JSON: {e}")
                log(f"Payload: {payload[:200]}...")
                continue

            log(f"Received job for document {job.get('document_id')}")
            try:
                process_job(job)
            except Exception as job_err:
                log(f"❌ Stage3 job processing failed: {job_err}")
                traceback.print_exc()
                # Mark document as failed in MongoDB
                if documents_col is not None:
                    try:
                        doc_id = job.get("document_id")
                        if doc_id:
                            documents_col.update_one(
                                {"_id": ObjectId(doc_id)},
                                {
                                    "$set": {"status": "failed"},
                                    "$push": {"processingErrors": f"Stage3 failed: {str(job_err)}"}
                                }
                            )
                            log(f"Marked document {doc_id} as failed in MongoDB")
                    except Exception as mongo_err:
                        log(f"⚠️ Failed to update MongoDB status: {mongo_err}")
                log("Waiting for next job...")
                continue

        except KeyboardInterrupt:
            log("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            log(f"❌ Stage3 crashed for a job but worker continues running: {e}")
            traceback.print_exc()
            log("Waiting for next job...")

# FastAPI app for HTTP endpoints
worker_app = FastAPI(title="Stage3 Worker")

# Add CORS middleware to allow frontend warmup pings
worker_app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://docqa-ultimate.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@worker_app.get("/health")
async def health():
    """Health check endpoint - used to wake up the worker"""
    return {"status": "ok", "worker": "stage3"}

@worker_app.post("/process")
async def process_job_endpoint(job: dict, background_tasks: BackgroundTasks):
    """HTTP endpoint to process a job directly"""
    doc_id = job.get("document_id")
    user_id = job.get("user_id")
    
    if not doc_id or not user_id:
        return JSONResponse(
            {"error": "Missing document_id or user_id"},
            status_code=400
        )
    
    # Process in background
    background_tasks.add_task(process_job, job)
    return {"status": "processing", "document_id": doc_id}

if __name__ == "__main__":
    # Start queue worker in background thread
    worker_thread = Thread(target=run, daemon=True)
    worker_thread.start()
    log("Queue worker thread started")
    
    # Start HTTP server
    port = int(os.getenv("PORT", "8000"))
    log(f"Starting HTTP server on port {port}")
    uvicorn.run(worker_app, host="0.0.0.0", port=port)
