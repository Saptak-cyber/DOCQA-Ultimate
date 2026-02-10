# workers/stage1_extraction.py
# workers/stage1_extraction.py
import os, json, sys
import uuid
from dotenv import load_dotenv
from bson import ObjectId
from pymongo import MongoClient
import redis
from supabase import create_client
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread
import httpx
import gc

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.chunker import extract_pages_from_pdf_bytes, extract_pages_streaming, get_pdf_page_count

load_dotenv()

# Namespace UUID for converting emails to UUIDs (consistent across all workers)
EMAIL_TO_UUID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')

def convert_user_id_to_uuid(user_id):
    """Convert user_id (email string) to UUID format for Supabase."""
    try:
        return str(uuid.UUID(user_id))
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(EMAIL_TO_UUID_NAMESPACE, str(user_id))
        return str(user_uuid)

def sync_document_to_supabase(doc_id, mongo_doc):
    """Sync MongoDB document to Supabase documents table."""
    try:
        user_id_raw = mongo_doc.get("userId", "")
        user_id = convert_user_id_to_uuid(user_id_raw)
        
        storage = mongo_doc.get("storage", {})
        
        supabase_doc = {
            "id": doc_id,
            "user_id": user_id,
            "title": mongo_doc.get("title", ""),
            "storage_bucket": storage.get("bucket"),
            "storage_path": storage.get("path"),
            "storage_public_url": storage.get("public_url"),
            "status": mongo_doc.get("status", "uploaded"),
            "pages": mongo_doc.get("page_count"),
        }
        
        supabase.table("documents").upsert(supabase_doc).execute()
        log_info(f"Synced document {doc_id} to Supabase documents table")
    except Exception as e:
        log_warn(f"Failed to sync document {doc_id} to Supabase: {e}")

def log_info(msg): print(f"\033[94m[STAGE1][INFO]\033[0m {msg}")
def log_warn(msg): print(f"\033[93m[STAGE1][WARN]\033[0m {msg}")
def log_error(msg): print(f"\033[91m[STAGE1][ERROR]\033[0m {msg}")

MONGO_URI = os.getenv("MONGO_URI")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WORKER_STAGE2_URL = os.getenv("WORKER_STAGE2_URL", "http://localhost:8002/health")

mongo = MongoClient(MONGO_URI)
db = mongo.get_default_database()
documents_col = db["documents"]
r = redis.from_url(REDIS_URL, decode_responses=True)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def process_job(job):
    doc_id = job["document_id"]
    user_id = job["user_id"]
    
    log_info(f"Processing document {doc_id}")
    
    # 1. Fetch document from MongoDB
    mongo_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
    if not mongo_doc:
        log_error(f"Document {doc_id} not found in MongoDB")
        return
    
    # 2. Update status to extracting
    documents_col.update_one(
        {"_id": ObjectId(doc_id)},
        {"$set": {"status": "extracting"}}
    )
    sync_document_to_supabase(doc_id, {**mongo_doc, "status": "extracting"})
    
    # 3. Get PDF bytes
    pdf_bytes = mongo_doc.get("pdf_bytes")
    if not pdf_bytes:
        log_error(f"No pdf_bytes found for document {doc_id}")
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "failed"}, "$push": {"processingErrors": "No PDF data"}}
        )
        return
    
    # 4. Stream pages and save in batches (memory efficient)
    pages_batch = {}
    batch_size = 10
    total_pages = 0
    
    log_info(f"Starting PDF extraction for {doc_id}")
    
    for page_num, page_text in extract_pages_streaming(pdf_bytes):
        pages_batch[str(page_num)] = page_text
        total_pages += 1
        
        if len(pages_batch) >= batch_size:
            # Save batch to MongoDB
            update_dict = {f"pages_text.{k}": v for k, v in pages_batch.items()}
            documents_col.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": update_dict}
            )
            log_info(f"Saved batch of {len(pages_batch)} pages")
            pages_batch = {}
            gc.collect()  # Force garbage collection
    
    # 5. Save remaining pages
    if pages_batch:
        update_dict = {f"pages_text.{k}": v for k, v in pages_batch.items()}
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": update_dict}
        )
        log_info(f"Saved final batch of {len(pages_batch)} pages")
        gc.collect()
    
    # 6. Update status and page count
    documents_col.update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {
                "status": "extracted",
                "page_count": total_pages
            }
        }
    )
    
    # 7. Sync to Supabase
    updated_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
    sync_document_to_supabase(doc_id, updated_doc)
    
    log_info(f"✅ Extracted {total_pages} pages from document {doc_id}")
    
    # 8. Push to stage2 queue
    stage2_job = {
        "document_id": doc_id,
        "user_id": user_id
    }
    r.lpush("queue:stage2", json.dumps(stage2_job))
    log_info(f"Pushed to stage2 queue: {doc_id}")
    
    # 9. Wake up stage2 worker
    try:
        httpx.get(WORKER_STAGE2_URL, timeout=5)
        log_info(f"✅ Woke up stage2 worker at {WORKER_STAGE2_URL}")
    except Exception as e:
        log_warn(f"Failed to wake stage2 worker: {e}")
    
    # 10. Final cleanup
    gc.collect()

def run():
    """Queue-based worker loop (runs in background thread)"""
    print("\033[92m[STAGE1] Worker loop started. Waiting for jobs from queue...\033[0m")
    while True:
        try:
            # Use timeout to allow periodic checks
            result = r.brpop("queue:stage1", timeout=30)
            if result is None:
                continue  # Timeout, check again
            
            _, payload = result
            try:
                job = json.loads(payload)
            except json.JSONDecodeError as e:
                log_error(f"Failed to parse job JSON: {e}")
                log_error(f"Payload: {payload[:200]}...")
                continue
            
            try:
                process_job(job)
            except Exception as job_err:
                log_error(f"Job processing failed: {job_err}")
                import traceback
                log_error(traceback.format_exc())
                # Try to mark document as failed if we have doc_id
                try:
                    doc_id = job.get("document_id")
                    if doc_id:
                        documents_col.update_one(
                            {"_id": ObjectId(doc_id)},
                            {
                                "$set": {"status": "failed"},
                                "$push": {"processingErrors": str(job_err)}
                            }
                        )
                        # Sync failed status to Supabase
                        failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
                        if failed_doc:
                            sync_document_to_supabase(doc_id, failed_doc)
                except Exception as mongo_err:
                    log_error(f"Failed to update MongoDB status: {mongo_err}")
                continue
        except KeyboardInterrupt:
            log_info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            log_error(f"Unhandled error in worker loop: {e}")
            import traceback
            log_error(traceback.format_exc())
            continue  # DO NOT STOP WORKER

# FastAPI app for HTTP endpoints
worker_app = FastAPI(title="Stage1 Worker")

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
    return {"status": "ok", "worker": "stage1"}

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
    log_info("Queue worker thread started")
    
    # Start HTTP server
    port = int(os.getenv("PORT", "8000"))
    log_info(f"Starting HTTP server on port {port}")
    uvicorn.run(worker_app, host="0.0.0.0", port=port)

# def run():
#     print("Stage1 worker started, blocking on queue:stage1")
#     while True:
#         _, payload = r.brpop("queue:stage1")
#         job = json.loads(payload)
#         try:
#             process_job(job)
#         except Exception as e:
#             print("Stage1 failed:", e)
#             # store error in mongo
#             documents_col.update_one({"_id": ObjectId(job["document_id"])}, {"$push": {"processingErrors": str(e)}})
#             # mark failed
#             documents_col.update_one({"_id": ObjectId(job["document_id"])}, {"$set": {"status":"failed"}})

# if __name__ == "__main__":
#     run()