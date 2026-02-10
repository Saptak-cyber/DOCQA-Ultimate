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
    doc_id = job.get("document_id")
    user_id = job.get("user_id")
    
    if not doc_id or not user_id:
        log_error(f"Invalid job payload: missing document_id or user_id")
        return

    log_info(f"Starting Stage 1 for document {doc_id}")

    try:
        doc = documents_col.find_one({"_id": ObjectId(doc_id)})
        if not doc:
            log_error(f"Document {doc_id} not found in MongoDB.")
            documents_col.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {"status": "failed"},
                    "$push": {"processingErrors": f"Document {doc_id} not found in MongoDB"}
                }
            )
            return
    except Exception as e:
        log_error(f"Error querying MongoDB for document {doc_id}: {e}")
        return

    documents_col.update_one({"_id": ObjectId(doc_id)}, {"$set":{"status":"processing"}})
    log_info("Status updated to processing")
    
    # Sync status change to Supabase
    sync_document_to_supabase(doc_id, doc)

    storage = doc.get("storage", {})
    bucket, path = storage.get("bucket"), storage.get("path")

    if not bucket or not path:
        log_error("Storage info missing in MongoDB document.")
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {"status": "failed"},
                "$push": {"processingErrors": "Missing bucket/path in storage info"}
            }
        )
        # Sync failed status to Supabase
        failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
        if failed_doc:
            sync_document_to_supabase(doc_id, failed_doc)
        return

    try:
        log_info(f"Downloading PDF from Supabase Storage bucket={bucket} path={path}")
        pdf_bytes = supabase.storage.from_(bucket).download(path)
    except Exception as e:
        log_error(f"Failed to download PDF from Supabase: {e}")
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {"status": "failed"},
                "$push": {"processingErrors": f"PDF download failed: {str(e)}"}
            }
        )
        # Sync failed status to Supabase
        failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
        if failed_doc:
            sync_document_to_supabase(doc_id, failed_doc)
        return

    try:
        # Get total page count first (for progress tracking)
        log_info("Getting PDF page count...")
        total_pages = get_pdf_page_count(pdf_bytes)
        log_info(f"PDF has {total_pages} pages")
        
        # Update MongoDB with page count (but NOT pages_text to avoid 16MB limit)
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"page_count": total_pages}}
        )
        
        # For very large documents, use streaming extraction
        # For smaller documents (< 1000 pages), we can still use batch mode for efficiency
        USE_STREAMING = total_pages >= 1000  # Use streaming for 1000+ pages
        
        if USE_STREAMING:
            log_info(f"Using streaming extraction for large document ({total_pages} pages)")
            # Stream pages and send to Stage 2 queue incrementally
            pages_processed = 0
            PAGE_BATCH_SIZE = 100  # Send pages in batches to Stage 2
            
            current_batch = {}
            for page_num, page_text in extract_pages_streaming(pdf_bytes):
                current_batch[page_num] = page_text
                pages_processed += 1
                
                # Send batch to Stage 2 when batch is full or at end
                if len(current_batch) >= PAGE_BATCH_SIZE or pages_processed == total_pages:
                    stage2_job = {
                        "document_id": doc_id,
                        "user_id": user_id,
                        "pages": current_batch,  # Send pages directly in job
                        "is_final_batch": pages_processed == total_pages,
                        "total_pages": total_pages,
                        "pages_processed": pages_processed
                    }
                    r.lpush("queue:stage2", json.dumps(stage2_job))
                    log_info(f"Sent batch to Stage 2: pages {min(current_batch.keys())}-{max(current_batch.keys())} ({pages_processed}/{total_pages})")
                    # Wake up stage2 worker
                    try:
                        with httpx.Client(timeout=30.0) as client:
                            client.get(WORKER_STAGE2_URL)
                    except Exception as e:
                        log_warn(f"Failed to wake stage2 worker: {e}")  # Log instead of silent fail
                    current_batch = {}
            
            log_info(f"✅ Streaming extraction complete: {pages_processed}/{total_pages} pages sent to Stage 2")
        else:
            # For smaller documents, use batch mode (backward compatible)
            log_info("Using batch extraction for smaller document")
            pages = extract_pages_from_pdf_bytes(pdf_bytes)
            log_info(f"Extracted {len(pages)} pages")
            
            # Send all pages to Stage 2 in one job
            stage2_job = {
                "document_id": doc_id,
                "user_id": user_id,
                "pages": pages,
                "is_final_batch": True,
                "total_pages": len(pages),
                "pages_processed": len(pages)
            }
            r.lpush("queue:stage2", json.dumps(stage2_job))
            log_info("Sent all pages to Stage 2")
            # Wake up stage2 worker
            try:
                with httpx.Client(timeout=30.0) as client:
                    client.get(WORKER_STAGE2_URL)
            except Exception as e:
                log_warn(f"Failed to wake stage2 worker: {e}")  # Log instead of silent fail
        
        # Update status to extracted (without storing pages_text in MongoDB)
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "extracted"}}
        )
        log_info("Status updated to extracted")
        
        # Sync to Supabase documents table
        updated_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
        if updated_doc:
            sync_document_to_supabase(doc_id, updated_doc)
        
        log_info("Stage 1 finished. Pages sent to Stage 2 queue.")
        
    except Exception as e:
        log_error(f"Failed to extract pages from PDF: {e}")
        import traceback
        log_error(traceback.format_exc())
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {"status": "failed"},
                "$push": {"processingErrors": f"Page extraction failed: {str(e)}"}
            }
        )
        # Sync failed status to Supabase
        failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
        if failed_doc:
            sync_document_to_supabase(doc_id, failed_doc)
        return


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

# workers/stage1_extraction.py
# import os, sys, json
# from dotenv import load_dotenv
# from bson import ObjectId
# from pymongo import MongoClient
# import redis
# from supabase import create_client

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# load_dotenv()
# from app.chunker import extract_pages_from_pdf_bytes

# MONGO_URI = os.getenv("MONGO_URI")
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# mongo = MongoClient(MONGO_URI)
# db = mongo.get_default_database()
# documents_col = db["documents"]

# r = redis.from_url(REDIS_URL, decode_responses=True)
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# def mark_failed(doc_id, message):
#     try:
#         documents_col.update_one(
#             {"_id": ObjectId(doc_id)},
#             {"$set": {"status": "failed"}, "$push": {"processingErrors": message}},
#         )
#     except Exception as e:
#         print(f"Failed to mark doc {doc_id} as failed: {e}")

# def process_job(job):
#     # Basic validation
#     if "document_id" not in job or "user_id" not in job:
#         print("Job missing document_id/user_id; skipping")
#         return

#     doc_id = job["document_id"]
#     user_id = job["user_id"]

#     try:
#         obj_id = ObjectId(doc_id)
#     except Exception:
#         print(f"Invalid ObjectId: {doc_id}; skipping")
#         return

#     doc = documents_col.find_one({"_id": obj_id})
#     if not doc:
#         print(f"Doc not found: {doc_id}; skipping")
#         return

#     # Mark processing
#     documents_col.update_one({"_id": obj_id}, {"$set": {"status": "processing"}})

#     # Download PDF from storage
#     storage_info = doc.get("storage") or {}
#     bucket = storage_info.get("bucket")
#     path = storage_info.get("path")
#     if not bucket or not path:
#         mark_failed(doc_id, "Missing storage info")
#         return

#     try:
#         pdf_bytes = supabase.storage.from_(bucket).download(path)
#     except Exception as e:
#         print(f"Download failed for {doc_id}: {e}")
#         mark_failed(doc_id, f"Download failed: {e}")
#         return

#     # Extract pages
#     try:
#         pages = extract_pages_from_pdf_bytes(pdf_bytes)
#     except Exception as e:
#         print(f"Extraction failed for {doc_id}: {e}")
#         mark_failed(doc_id, f"Extraction failed: {e}")
#         return

#     pages_str = {str(k): v for k, v in pages.items()}
#     documents_col.update_one(
#         {"_id": obj_id},
#         {"$set": {"pages_text": pages_str, "page_count": len(pages_str), "status": "extracted"}},
#     )

#     # Push to next stage
#     r.lpush("queue:stage2", json.dumps({"document_id": doc_id, "user_id": user_id}))
#     print(f"Processed doc {doc_id}, queued for stage2")

# def run():
#     print("Stage1 worker started, blocking on queue:stage1")
#     while True:
#         try:
#             _, payload = r.brpop("queue:stage1")
#         except Exception as e:
#             print(f"Redis BRPOP failed: {e}")
#             continue  # keep trying

#         try:
#             job = json.loads(payload)
#         except Exception as e:
#             print(f"Bad job payload '{payload}': {e}")
#             continue

#         try:
#             process_job(job)
#         except Exception as e:
#             # Catch-all so the worker never dies
#             print(f"Stage1 unexpected failure for job {job}: {e}")
#             if isinstance(job, dict) and "document_id" in job:
#                 mark_failed(job["document_id"], f"Unexpected failure: {e}")
#             continue

# if __name__ == "__main__":
#     run()