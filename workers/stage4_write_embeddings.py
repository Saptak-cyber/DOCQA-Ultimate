# # workers/stage4_write_embeddings.py
# import os
# import json
# import time
# from dotenv import load_dotenv
# import redis
# from supabase import create_client
# import numpy as np
# from bson import ObjectId
# from sentence_transformers import SentenceTransformer
# from pymongo import MongoClient

# load_dotenv()

# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# MONGO_URI = os.getenv("MONGO_URI")
# EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))

# r = redis.from_url(REDIS_URL, decode_responses=True)
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# mongo = MongoClient(MONGO_URI)
# db = mongo.get_default_database()
# documents_col = db["documents"]

# # for doc-level embedding, reuse same model
# model = SentenceTransformer(os.getenv("EMBED_MODEL", "all-mpnet-base-v2"))

# def process_job(job):
#     doc_id = job["document_id"]
#     user_id = job["user_id"]
#     embeddings_payload = job["embeddings"]  # list of {id, embedding}
#     # write embeddings to supabase in batches using UPDATE
#     for item in embeddings_payload:
#         chunk_id = item["id"]
#         emb = item["embedding"]
#         # supabase python client: update by id
#         supabase.table("chunks").update({"embedding": emb}).eq("id", chunk_id).execute()

#     # We might receive multiple stage4 jobs for same doc (per batch). We need a way to detect completion.
#     # Simple heuristic: check if any chunks for doc still have embedding IS NULL
#     pending = supabase.table("chunks").select("id").eq("document_id", doc_id).is_("embedding", "null").execute().data
#     if not pending:
#         # compute a document-level embedding (simple average of chunk embeddings OR embed doc summary)
#         # We'll fetch a sample of chunk embeddings and average
#         rows = supabase.table("chunks").select("embedding").eq("document_id", doc_id).limit(500).execute().data
#         vecs = [r["embedding"] for r in rows if r.get("embedding")]
#         if vecs:
#             import numpy as np
#             arr = np.array(vecs, dtype=float)
#             doc_emb = arr.mean(axis=0).tolist()
#             # upsert into documents_index
#             supabase.table("documents_index").upsert({
#                 "document_id": doc_id,
#                 "user_id": user_id,
#                 "title": "",  # optionally fill
#                 "summary": "",  # optionally store LLM-generated summary
#                 "embedding": doc_emb
#             }).execute()
#             # mark document in mongo as indexed
#             documents_col.update_one({"_id": ObjectId(doc_id)}, {"$set": {"status":"indexed"}})


# def run():
#     print("Stage4 worker started, blocking on queue:stage4")
#     while True:
#         try:
#             _, payload = r.brpop("queue:stage4")
#             job = json.loads(payload)

#             try:
#                 process_job(job)
#             except Exception as job_err:
#                 print("Stage4 failed:", job_err)
#                 documents_col.update_one(
#                     {"_id": ObjectId(job["document_id"])},
#                     {
#                         "$set": {"status": "failed"},
#                         "$push": {"processingErrors": str(job_err)}
#                     }
#                 )
#                 continue

#         except Exception as loop_err:
#             print("Stage4 loop error:", loop_err)
#             time.sleep(1)
#             continue

# if __name__ == "__main__":
#     run()

# workers/stage4_write_embeddings.py
import os, json
import uuid
import time
from dotenv import load_dotenv
import redis
from supabase import create_client
from pymongo import MongoClient
import numpy as np
from bson import ObjectId
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread

load_dotenv()

# Namespace UUID for converting emails to UUIDs (consistent across all workers)
EMAIL_TO_UUID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Standard DNS namespace

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

def log_info(msg): print(f"\033[94m[STAGE4][INFO]\033[0m {msg}")
def log_warn(msg): print(f"\033[93m[STAGE4][WARN]\033[0m {msg}")
def log_error(msg): print(f"\033[91m[STAGE4][ERROR]\033[0m {msg}")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MONGO_URI = os.getenv("MONGO_URI")

r = redis.from_url(REDIS_URL, decode_responses=True)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
mongo = MongoClient(MONGO_URI)
db = mongo.get_default_database()
documents_col = db["documents"]

def process_job(job):
    global r  # Declare r as global to access Redis client
    doc_id = job["document_id"]
    user_id_raw = job["user_id"]
    # Convert user_id to UUID format for Supabase
    user_id = convert_user_id_to_uuid(user_id_raw)
    emb_list = job["embeddings"]  # list of {id, embedding}

    log_info(f"Stage 4: Received {len(emb_list)} embeddings for doc {doc_id}")

    # Check if document was deleted (safeguard against race conditions)
    try:
        doc = documents_col.find_one({"_id": ObjectId(doc_id)})
        if doc and doc.get("status") == "deleted":
            log_warn(f"Document {doc_id} was deleted, skipping processing")
            # Clean up tracking state
            state_key = f"stage4_state:{doc_id}"
            r.delete(state_key)
            return
    except Exception as e:
        log_warn(f"Failed to check document status: {e}")

    # Validate embedding dimensions before attempting writes
    if emb_list:
        first_emb_dim = len(emb_list[0]["embedding"])
        expected_dim = 768  # Schema expects VECTOR(768)
        if first_emb_dim != expected_dim:
            error_msg = f"Embedding dimension mismatch: received {first_emb_dim} dimensions but schema expects {expected_dim}. Check EMBED_MODEL in Stage 3 (should be 'all-mpnet-base-v2' for 768 dims, not 'all-MiniLM-L6-v2' which produces 384 dims)"
            log_error(f"❌ {error_msg}")
            documents_col.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {"status": "failed"},
                    "$push": {"processingErrors": error_msg}
                }
            )
            # Sync failed status to Supabase
            failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
            if failed_doc:
                sync_document_to_supabase(doc_id, failed_doc)
            raise ValueError(error_msg)
        log_info(f"✅ Validated embedding dimensions: {first_emb_dim} (matches schema)")

    # Write embeddings in batches for better performance
    failed_writes = []
    BATCH_WRITE_SIZE = 100  # Process in batches
    
    # Fetch existing chunk data in batches to include all required fields for upsert
    chunk_ids = [item["id"] for item in emb_list]
    chunk_data_map = {}  # Map chunk_id -> existing chunk data
    
    # Fetch chunks in batches to get required fields (text, user_id, document_id, etc.)
    FETCH_BATCH_SIZE = 1000  # Supabase limit
    for fetch_start in range(0, len(chunk_ids), FETCH_BATCH_SIZE):
        fetch_batch_ids = chunk_ids[fetch_start:fetch_start + FETCH_BATCH_SIZE]
        try:
            # Fetch existing chunks with all fields
            existing_chunks = supabase.table("chunks") \
                .select("id,text,user_id,document_id,page_number,chunk_index,tokens") \
                .in_("id", fetch_batch_ids) \
                .execute().data
            
            # Build map for quick lookup
            for chunk in existing_chunks:
                chunk_data_map[chunk["id"]] = chunk
        except Exception as e:
            log_warn(f"Failed to fetch chunk data for batch: {e}")
            # Continue anyway - will fall back to individual updates
    
    # Now do bulk upsert with all required fields
    for batch_start in range(0, len(emb_list), BATCH_WRITE_SIZE):
        batch_items = emb_list[batch_start:batch_start + BATCH_WRITE_SIZE]
        
        # Try bulk upsert with all required fields
        try:
            update_payload = []
            for item in batch_items:
                chunk_id = item["id"]
                emb = item["embedding"]
                
                # Get existing chunk data
                existing_data = chunk_data_map.get(chunk_id)
                if existing_data:
                    # Include all required fields for upsert
                    update_payload.append({
                        "id": chunk_id,
                        "embedding": emb,
                        "text": existing_data.get("text"),  # Required NOT NULL
                        "user_id": existing_data.get("user_id") or user_id,  # Required NOT NULL
                        "document_id": existing_data.get("document_id") or doc_id,  # Required NOT NULL
                        "page_number": existing_data.get("page_number"),
                        "chunk_index": existing_data.get("chunk_index"),
                        "tokens": existing_data.get("tokens")
                    })
                else:
                    # Chunk not found in database - skip bulk upsert for this one
                    log_warn(f"Chunk {chunk_id} not found in database, will update individually")
                    # Will be handled in fallback
            
            if update_payload:
                supabase.table("chunks").upsert(update_payload).execute()
            
            # Handle any chunks that weren't in the map (fallback to individual updates)
            for item in batch_items:
                if item["id"] not in chunk_data_map:
                    chunk_id = item["id"]
                    emb = item["embedding"]
                    try:
                        supabase.table("chunks").update({"embedding": emb}).eq("id", chunk_id).execute()
                    except Exception as e2:
                        log_error(f"Failed to write embedding for chunk {chunk_id}: {e2}")
                        failed_writes.append(chunk_id)
            
        except Exception as e:
            # Fall back to individual updates if bulk fails
            log_warn(f"Bulk upsert failed for batch of {len(batch_items)}, falling back to individual updates: {e}")
            for item in batch_items:
                chunk_id = item["id"]
                emb = item["embedding"]
                try:
                    supabase.table("chunks").update({"embedding": emb}).eq("id", chunk_id).execute()
                except Exception as e2:
                    log_error(f"Failed to write embedding for chunk {chunk_id}: {e2}")
                    failed_writes.append(chunk_id)
        
        if (batch_start + BATCH_WRITE_SIZE) % 400 == 0:
            log_info(f"Progress: Written {min(batch_start + BATCH_WRITE_SIZE, len(emb_list))}/{len(emb_list)} embeddings...")
    
    # Always log final progress if not already logged at 400-interval boundary
    if len(emb_list) > 0:
        final_count = len(emb_list)
        last_logged = (final_count // 400) * 400
        if final_count != last_logged:
            log_info(f"Progress: Written {final_count}/{final_count} embeddings...")
    
    if failed_writes:
        error_msg = f"Failed to write {len(failed_writes)} embeddings out of {len(emb_list)}"
        log_error(error_msg)
        # Mark document as failed if too many writes failed
        if len(failed_writes) > len(emb_list) / 2:  # More than 50% failed
            documents_col.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {"status": "failed"},
                    "$push": {"processingErrors": error_msg}
                }
            )
            # Sync failed status to Supabase
            failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
            if failed_doc:
                sync_document_to_supabase(doc_id, failed_doc)
            raise Exception(error_msg)

    # Check if all embeddings are written
    pending = supabase.table("chunks").select("id").eq("document_id", doc_id).is_("embedding", "null").execute().data
    pending_count = len(pending) if pending else 0

    if pending_count > 0:
        # Track processing state to detect stuck documents
        current_time = time.time()
        
        # Use Redis to track document state across worker instances
        state_key = f"stage4_state:{doc_id}"
        state_data = r.get(state_key)
        
        if state_data:
            state = json.loads(state_data)
            last_pending = state.get("last_pending_count", pending_count)
            check_count = state.get("check_count", 0)
            
            # Check if progress is being made
            if pending_count < last_pending:
                # Progress made, reset counter
                r.set(state_key, json.dumps({
                    "last_pending_count": pending_count,
                    "last_update_time": current_time,
                    "check_count": 0
                }), ex=3600)  # Expire after 1 hour
                log_info(f"Embeddings pending count: {pending_count} → more batches coming. (Progress: {last_pending - pending_count} chunks processed)")
            else:
                # No progress, increment counter
                check_count += 1
                r.set(state_key, json.dumps({
                    "last_pending_count": pending_count,
                    "last_update_time": current_time,
                    "check_count": check_count
                }), ex=3600)
                
                # If stuck for 10+ checks, take action
                if check_count >= 10:
                    log_warn(f"⚠️ Document {doc_id} appears stuck: {pending_count} chunks still pending after {check_count} checks with no progress")
                    
                    # Get total chunks and embedded chunks
                    total_res = supabase.table("chunks").select("id", count="exact").eq("document_id", doc_id).execute()
                    total_chunks = total_res.count if hasattr(total_res, 'count') else None
                    
                    # Count embedded chunks by subtracting pending from total
                    embedded_chunks = total_chunks - pending_count if total_chunks else None
                    
                    if total_chunks and embedded_chunks:
                        completion_pct = (embedded_chunks / total_chunks) * 100
                        log_warn(f"⚠️ Progress: {embedded_chunks}/{total_chunks} chunks have embeddings ({completion_pct:.1f}%)")
                        
                        if completion_pct >= 80:
                            log_warn(f"⚠️ Proceeding with indexing despite {pending_count} missing chunks ({completion_pct:.1f}% complete)")
                            r.delete(state_key)  # Clear state
                            # Fall through to compute document-level embedding
                        else:
                            log_warn(f"⚠️ Re-queuing Stage 3 to process remaining {pending_count} chunks...")
                            try:
                                stage3_job = {"document_id": doc_id, "user_id": user_id_raw}
                                r.lpush("queue:stage3", json.dumps(stage3_job))
                                log_info(f"✅ Re-queued Stage 3 for document {doc_id}")
                                r.delete(state_key)  # Reset state
                            except Exception as e:
                                log_error(f"❌ Failed to re-queue Stage 3: {e}")
                            log_info(f"Embeddings pending count: {pending_count} → re-queued Stage 3, waiting...")
                            return
                    else:
                        log_warn(f"⚠️ Cannot determine completion status. Continuing to wait...")
                        log_info(f"Embeddings pending count: {pending_count} → more batches coming.")
                        return
                else:
                    log_info(f"Embeddings pending count: {pending_count} → more batches coming. (Stuck check: {check_count}/10)")
                    return
        else:
            # First time seeing this document, initialize state
            r.set(state_key, json.dumps({
                "last_pending_count": pending_count,
                "last_update_time": current_time,
                "check_count": 0
            }), ex=3600)
            log_info(f"Embeddings pending count: {pending_count} → more batches coming.")
            return

    # Clear tracking state if document completes
    state_key = f"stage4_state:{doc_id}"
    r.delete(state_key)
    
    log_info("All chunk embeddings written. Computing document-level embedding...")

    try:
        # For large documents, paginate through ALL embeddings and compute a running mean
        PAGE_SIZE = 1000  # Supabase default limit
        log_info("Fetching chunks for document-level embedding computation (full scan)...")

        # Small delay to ensure database writes are committed and visible
        time.sleep(0.5)

        running_sum = None
        total_count = 0
        offset = 0

        while True:
            try:
                rows = supabase.table("chunks") \
                    .select("embedding") \
                    .eq("document_id", doc_id) \
                    .not_.is_("embedding", "null") \
                    .range(offset, offset + PAGE_SIZE - 1) \
                    .execute().data
            except Exception as e:
                log_error(f"Error fetching chunk embeddings (offset {offset}): {e}")
                import traceback
                log_error(traceback.format_exc())
                raise

            if not rows:
                break

            parsed_embeddings = []
            for row in rows:
                emb = row.get("embedding")
                if not emb:
                    continue
                if isinstance(emb, str):
                    try:
                        emb = json.loads(emb)
                    except (json.JSONDecodeError, TypeError):
                        log_warn(f"Skipping invalid embedding format: {type(emb)}")
                        continue
                if isinstance(emb, (list, tuple)):
                    parsed_embeddings.append(emb)
                else:
                    log_warn(f"Skipping embedding with unexpected type: {type(emb)}")

            if parsed_embeddings:
                batch_arr = np.array(parsed_embeddings, dtype=float)
                batch_sum = batch_arr.sum(axis=0)
                batch_count = batch_arr.shape[0]

                if running_sum is None:
                    running_sum = batch_sum
                else:
                    running_sum += batch_sum

                total_count += batch_count
                log_info(f"Processed batch: {batch_count} embeddings (total so far: {total_count})")

            # If fewer than PAGE_SIZE rows, we've reached the end
            if len(rows) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        if running_sum is None or total_count == 0:
            log_warn("No embeddings found for document-level embedding computation")
            documents_col.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {"status": "failed"},
                    "$push": {"processingErrors": "No chunk embeddings found for document-level embedding"}
                }
            )
            failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
            if failed_doc:
                sync_document_to_supabase(doc_id, failed_doc)
            return

        doc_emb = (running_sum / total_count).tolist()
        log_info(f"Computing document-level embedding from {total_count} chunk embeddings...")
        log_info(f"✅ Document-level embedding computed: {len(doc_emb)} dimensions")

        log_info("Uploading doc-level embedding to documents_index")
        supabase.table("documents_index").upsert({
            "document_id": doc_id,
            "user_id": user_id,
            "title": "",
            "summary": "",
            "embedding": doc_emb
        }).execute()
        log_info("✅ Document-level embedding uploaded successfully")
    except Exception as e:
        log_error(f"Failed to compute/upload document-level embedding: {e}")
        import traceback
        log_error(traceback.format_exc())
        documents_col.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {"status": "failed"},
                "$push": {"processingErrors": f"Document-level embedding failed: {str(e)}"}
            }
        )
        # Sync failed status to Supabase
        failed_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
        if failed_doc:
            sync_document_to_supabase(doc_id, failed_doc)
        raise

    # Only mark as indexed if everything succeeded
    documents_col.update_one({"_id": ObjectId(doc_id)}, {"$set": {"status": "indexed"}})
    log_info(f"✅ Document {doc_id} marked as indexed in MongoDB.")
    
    # Sync status change to Supabase documents table
    updated_doc = documents_col.find_one({"_id": ObjectId(doc_id)})
    if updated_doc:
        sync_document_to_supabase(doc_id, updated_doc)

def run():
    """Queue-based worker loop (runs in background thread)"""
    print("\033[92m[STAGE4] Worker loop started. Waiting for jobs from queue...\033[0m")
    while True:
        try:
            result = r.brpop("queue:stage4", timeout=30)
            if result is None:
                continue  # Timeout, check again
            
            _, payload = result
            try:
                job = json.loads(payload)
            except json.JSONDecodeError as e:
                log_error(f"❌ Failed to parse job JSON: {e}")
                log_error(f"Payload: {payload[:200]}...")
                continue
            
            try:
                process_job(job)
            except Exception as job_err:
                log_error(f"❌ Job processing failed: {job_err}")
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
            log_error(f"❌ Unhandled error in worker loop: {e}")
            import traceback
            log_error(traceback.format_exc())
            continue

# FastAPI app for HTTP endpoints
worker_app = FastAPI(title="Stage4 Worker")

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
    return {"status": "ok", "worker": "stage4"}

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
