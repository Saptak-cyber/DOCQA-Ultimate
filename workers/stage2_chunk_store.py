# # workers/stage2_chunk_store.py
# import os
# import json
# import time
# from dotenv import load_dotenv
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# import redis
# from bson import ObjectId
# from pymongo import MongoClient
# from supabase import create_client
# from app.chunker import chunks_from_pages
# import datetime

# load_dotenv()

# MONGO_URI = os.getenv("MONGO_URI")
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# mongo = MongoClient(MONGO_URI)
# db = mongo.get_default_database()
# documents_col = db["documents"]

# r = redis.from_url(REDIS_URL, decode_responses=True)
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# def process_job(job):
#     doc_id = job["document_id"]
#     user_id = job["user_id"]
#     doc = documents_col.find_one({"_id": ObjectId(doc_id)})
#     pages = doc.get("pages_text", {})
#     # create chunks
#     chunks = chunks_from_pages(pages, max_tokens=500, overlap=50)
#     # insert into supabase in batches
#     batch = []
#     for c in chunks:
#         row = {
#             "user_id": user_id,
#             "document_id": doc_id,
#             "page_number": c["page_number"],
#             "chunk_index": c["chunk_index"],
#             "text": c["text"],
#             "tokens": c["tokens"]
#         }
#         batch.append(row)
#         if len(batch) >= 50:
#             supabase.table("chunks").insert(batch).execute()
#             batch = []
#     if batch:
#         supabase.table("chunks").insert(batch).execute()

#     # push to next queue
#     r.lpush("queue:stage3", json.dumps({"document_id": doc_id, "user_id": user_id}))


# def run():
#     print("Stage2 worker started, blocking on queue:stage2")
#     while True:
#         try:
#             _, payload = r.brpop("queue:stage2")
#             job = json.loads(payload)

#             try:
#                 process_job(job)
#             except Exception as job_err:
#                 print("Stage2 failed:", job_err)
#                 documents_col.update_one(
#                     {"_id": ObjectId(job["document_id"])},
#                     {
#                         "$set": {"status": "failed"},
#                         "$push": {"processingErrors": str(job_err)}
#                     }
#                 )
#                 continue

#         except Exception as loop_err:
#             print("Stage2 loop error:", loop_err)
#             time.sleep(1)
#             continue

# if __name__ == "__main__":
#     run()

# workers/stage2_chunk_store.py
import os, json, sys
from dotenv import load_dotenv
import redis
import uuid
from bson import ObjectId
from pymongo import MongoClient
from supabase import create_client
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.chunker import chunks_from_pages, chunks_from_page

load_dotenv()

# Namespace UUID for converting emails to UUIDs (consistent across all workers)
EMAIL_TO_UUID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Standard DNS namespace

def log_info(msg): print(f"\033[94m[STAGE2][INFO]\033[0m {msg}")
def log_warn(msg): print(f"\033[93m[STAGE2][WARN]\033[0m {msg}")
def log_error(msg): print(f"\033[91m[STAGE2][ERROR]\033[0m {msg}")

MONGO_URI = os.getenv("MONGO_URI")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WORKER_STAGE3_URL = os.getenv("WORKER_STAGE3_URL", "http://localhost:8003/health")

mongo = MongoClient(MONGO_URI)
db = mongo.get_default_database()
documents_col = db["documents"]
r = redis.from_url(REDIS_URL, decode_responses=True)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def convert_user_id_to_uuid(user_id):
    """
    Convert user_id (email string) to UUID format for Supabase.
    Uses uuid5 to create deterministic UUID from email.
    """
    try:
        # Try to parse as UUID first
        return str(uuid.UUID(user_id))
    except (ValueError, AttributeError):
        # If not a UUID, convert email to UUID using uuid5
        user_uuid = uuid.uuid5(EMAIL_TO_UUID_NAMESPACE, str(user_id))
        return str(user_uuid)

def sanitize_text(text):
    """
    Sanitize text for PostgreSQL/Supabase insertion.
    Removes null bytes and other problematic control characters.
    Returns sanitized text and a flag indicating if sanitization occurred.
    """
    if not isinstance(text, str):
        text = str(text)
    
    original_text = text
    had_null_bytes = '\x00' in text or '\u0000' in text
    
    # Remove null bytes (\u0000) - PostgreSQL doesn't allow these in text fields
    text = text.replace('\x00', '')
    text = text.replace('\u0000', '')
    
    # Remove other problematic control characters (but keep newlines, tabs, etc.)
    # Keep: \n (0x0A), \r (0x0D), \t (0x09)
    # Remove: other control chars (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F)
    cleaned = []
    removed_chars = 0
    for char in text:
        code = ord(char)
        # Keep printable characters, newlines, carriage returns, and tabs
        if code >= 32 or code in [9, 10, 13]:  # 9=tab, 10=newline, 13=carriage return
            cleaned.append(char)
        else:
            removed_chars += 1
    text = ''.join(cleaned)
    
    # Ensure valid UTF-8 encoding
    try:
        text = text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        # If encoding fails, replace problematic characters
        text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Log if sanitization occurred (only for null bytes to avoid spam)
    if had_null_bytes:
        log_warn(f"⚠️ Removed null bytes from chunk text (original length: {len(original_text)}, cleaned length: {len(text)})")
    
    return text

def process_job(job):
    doc_id = job["document_id"]
    user_id_raw = job["user_id"]
    
    # Convert user_id to UUID format for Supabase
    user_id = convert_user_id_to_uuid(user_id_raw)
    
    if user_id_raw != user_id:
        log_info(f"Converted user_id from '{user_id_raw}' to UUID '{user_id}'")

    log_info(f"Starting Stage 2 for doc={doc_id}, user_id={user_id}")

    # Check if this is a streaming job (has pages in job) or legacy job (needs MongoDB)
    pages = job.get("pages")
    is_final_batch = job.get("is_final_batch", False)
    total_pages = job.get("total_pages", 0)
    pages_processed = job.get("pages_processed", 0)
    
    if pages:
        # Streaming mode: pages are in the job payload
        log_info(f"✅ Received {len(pages)} pages from Stage 1 queue (streaming mode)")
        log_info(f"Progress: {pages_processed}/{total_pages} pages processed")
    else:
        # Legacy mode: fetch from MongoDB (for backward compatibility with old jobs)
        log_info(f"Legacy mode: Fetching pages from MongoDB...")
        try:
            doc = documents_col.find_one({"_id": ObjectId(doc_id)})
            if not doc:
                log_error(f"❌ Document {doc_id} not found in MongoDB")
                raise ValueError(f"Document {doc_id} not found in MongoDB")
            
            pages = doc.get("pages_text", {})
            if not pages:
                log_error(f"❌ Document {doc_id} has no pages_text data")
                log_error(f"Document keys: {list(doc.keys())}")
                raise ValueError(f"Document {doc_id} has no pages_text data")
            
            log_info(f"✅ Found {len(pages)} pages in MongoDB")
            is_final_batch = True
            total_pages = len(pages)
        except Exception as e:
            log_error(f"❌ MongoDB query failed: {e}")
            import traceback
            log_error(traceback.format_exc())
            raise

    # Get current chunk index from Redis (for streaming mode to maintain global chunk numbering)
    chunk_index_key = f"stage2_chunk_idx:{doc_id}"
    current_chunk_idx = 0
    try:
        idx_str = r.get(chunk_index_key)
        if idx_str:
            current_chunk_idx = int(idx_str)
    except Exception:
        pass

    log_info(f"Chunking {len(pages)} pages...")
    try:
        # Chunk pages - use streaming chunking for large documents
        all_chunks = []
        for page_num, page_text in sorted(pages.items()):
            page_num_int = int(page_num) if isinstance(page_num, str) else page_num
            page_chunks = chunks_from_page(page_text, page_num_int, start_chunk_idx=current_chunk_idx, max_tokens=500, overlap=50)
            all_chunks.extend(page_chunks)
            current_chunk_idx += len(page_chunks)
        
        # Update chunk index in Redis for next batch
        if not is_final_batch:
            r.set(chunk_index_key, str(current_chunk_idx), ex=3600)  # Expire after 1 hour
        
        chunks = all_chunks
        log_info(f"✅ Chunking completed! Created {len(chunks)} chunks from {len(pages)} pages")
    except Exception as e:
        log_error(f"❌ Chunking failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        raise

    if not chunks:
        log_warn(f"⚠️ No chunks created from {len(pages)} pages - document may be empty")
        if is_final_batch:
            raise ValueError(f"No chunks created for document {doc_id}")
        else:
            log_warn("Skipping empty batch, continuing...")
            return

    log_info(f"Preparing to upload {len(chunks)} chunks to Supabase...")

    batch = []
    inserted_count = 0
    total_chunks = len(chunks)
    log_info(f"Processing {total_chunks} chunks in batches of 50...")
    
    # For large documents, log progress periodically
    is_large_doc = total_chunks > 200
    
    for idx, c in enumerate(chunks, 1):
        try:
            # Sanitize text to remove null bytes and problematic characters
            sanitized_text = sanitize_text(c["text"])
            
            row = {
                "user_id": user_id,  # Note: Must be UUID format, not email string
                "document_id": doc_id,
                "page_number": c["page_number"],
                "chunk_index": c["chunk_index"],
                "text": sanitized_text,
                "tokens": c["tokens"]
            }
            batch.append(row)
        except Exception as e:
            log_error(f"Failed to prepare chunk {idx}/{total_chunks}: {e}")
            log_error(f"Chunk data: {c}")
            raise
        
        if len(batch) >= 50:
            try:
                if is_large_doc and inserted_count % 200 == 0:
                    progress_pct = (inserted_count / total_chunks) * 100
                    log_info(f"Progress: {inserted_count}/{total_chunks} chunks ({progress_pct:.1f}%)")
                log_info(f"Inserting batch of {len(batch)} chunks (chunks {inserted_count+1}-{inserted_count+len(batch)}/{total_chunks})...")
                result = supabase.table("chunks").insert(batch).execute()
                inserted_count += len(batch)
                log_info(f"✅ Successfully uploaded batch of {len(batch)} chunks (total uploaded: {inserted_count}/{total_chunks})")
            except Exception as e:
                log_error(f"❌ Failed to insert batch of {len(batch)} chunks: {e}")
                log_error(f"Batch contains chunks {inserted_count+1}-{inserted_count+len(batch)}")
                if batch:
                    log_error(f"First chunk in batch: page={batch[0].get('page_number')}, chunk_idx={batch[0].get('chunk_index')}, text_len={len(batch[0].get('text', ''))}")
                import traceback
                log_error(traceback.format_exc())
                raise  # Re-raise to mark job as failed
            batch = []

    if batch:
        try:
            log_info(f"Inserting final batch of {len(batch)} remaining chunks (chunks {inserted_count+1}-{inserted_count+len(batch)}/{total_chunks})...")
            result = supabase.table("chunks").insert(batch).execute()
            inserted_count += len(batch)
            log_info(f"✅ Successfully uploaded final batch of {len(batch)} chunks")
        except Exception as e:
            log_error(f"❌ Failed to insert final batch of {len(batch)} chunks: {e}")
            log_error(f"Final batch contains chunks {inserted_count+1}-{inserted_count+len(batch)}")
            if batch:
                log_error(f"First chunk in final batch: page={batch[0].get('page_number')}, chunk_idx={batch[0].get('chunk_index')}, text_len={len(batch[0].get('text', ''))}")
            import traceback
            log_error(traceback.format_exc())
            raise  # Re-raise to mark job as failed
    
    if inserted_count != total_chunks:
        log_warn(f"⚠️ Mismatch: Expected {total_chunks} chunks but inserted {inserted_count}")
    else:
        log_info(f"✅ Successfully inserted all {inserted_count} chunks to Supabase")

    # Only enqueue Stage 3 if this is the final batch
    if is_final_batch:
        log_info("✅ Stage 2 completed successfully!")
        
        # Clean up chunk index tracking
        try:
            r.delete(chunk_index_key)
        except Exception:
            pass
        
        log_info(f"Enqueuing job for Stage 3 (doc={doc_id})...")
        try:
            # Pass original user_id (email) to next stage, not UUID
            stage3_job = {"document_id": doc_id, "user_id": user_id_raw}
            r.lpush("queue:stage3", json.dumps(stage3_job))
            log_info(f"✅ Successfully enqueued to queue:stage3")
            # Wake up stage3 worker
            try:
                httpx.get(WORKER_STAGE3_URL, timeout=30.0)
                log_info(f"✅ Woke up stage3 worker at {WORKER_STAGE3_URL}")
            except Exception as e:
                log_warn(f"⚠️ Failed to wake stage3 worker: {e}")
        except Exception as e:
            log_error(f"❌ Failed to enqueue to Stage 3: {e}")
            import traceback
            log_error(traceback.format_exc())
            raise
    else:
        log_info(f"✅ Processed batch successfully. Waiting for next batch... ({pages_processed}/{total_pages} pages)")


def run():
    """Queue-based worker loop (runs in background thread)"""
    print("\033[92m[STAGE2] Worker loop started. Waiting for jobs from queue...\033[0m")
    while True:
        try:
            log_info("Waiting for job from queue:stage2...")
            result = r.brpop("queue:stage2", timeout=30)
            if result is None:
                continue  # Timeout, check again
            
            _, payload = result
            log_info(f"Received job payload (length: {len(payload)} chars)")
            
            try:
                job = json.loads(payload)
                log_info(f"Parsed job: doc_id={job.get('document_id')}, user_id={job.get('user_id')}")
            except json.JSONDecodeError as e:
                log_error(f"❌ Failed to parse job JSON: {e}")
                log_error(f"Payload: {payload[:200]}...")  # First 200 chars
                continue
            
            try:
                process_job(job)
                log_info("=" * 60)
                log_info("Job completed successfully, waiting for next job...")
                log_info("=" * 60)
            except Exception as job_err:
                log_error("=" * 60)
                log_error(f"❌ Job processing failed: {job_err}")
                log_error(f"Failed job: doc_id={job.get('document_id')}, user_id={job.get('user_id')}")
                import traceback
                log_error("Full traceback:")
                log_error(traceback.format_exc())
                log_error("=" * 60)
                
                # Mark document as failed in MongoDB
                try:
                    doc_id = job.get("document_id")
                    if doc_id:
                        log_info(f"Marking document {doc_id} as failed in MongoDB...")
                        documents_col.update_one(
                            {"_id": ObjectId(doc_id)},
                            {
                                "$set": {"status": "failed"},
                                "$push": {"processingErrors": str(job_err)}
                            }
                        )
                        log_info(f"✅ Document {doc_id} marked as failed")
                except Exception as mongo_err:
                    log_error(f"❌ Failed to update MongoDB status: {mongo_err}")
                    import traceback
                    log_error(traceback.format_exc())
                continue  # Continue to next job
        except KeyboardInterrupt:
            log_info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            log_error("=" * 60)
            log_error(f"❌ Unhandled error in worker loop: {e}")
            import traceback
            log_error(traceback.format_exc())
            log_error("=" * 60)
            log_info("Continuing to next iteration...")
            continue

# FastAPI app for HTTP endpoints
worker_app = FastAPI(title="Stage2 Worker")

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
    return {"status": "ok", "worker": "stage2"}

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
