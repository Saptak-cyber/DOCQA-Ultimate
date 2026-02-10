# app/main.py
import os
import hashlib
import json
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Header, Body, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
import redis
import base64
import datetime
import jwt  # for decoding JWT; you can replace with your library
from supabase import create_client
from app.retrieval import router as retrieval_router
import httpx

# Load environment variables from .env for local runs
load_dotenv()

# ---------- CONFIG (fill these ENV vars) ----------
MONGO_URI = os.getenv("MONGO_URI")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "documents")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# Support multiple CORS origins (production + development)
CORS_ORIGINS = [
    "https://docqa-ultimate.vercel.app",  # Production frontend
    "http://localhost:3000",               # Local development
    FRONTEND_ORIGIN,                       # Custom origin from env var
]

# Worker URLs for wake-up calls (set in environment variables)
WORKER_STAGE1_URL = os.getenv("WORKER_STAGE1_URL", "http://localhost:8001/health")
WORKER_STAGE2_URL = os.getenv("WORKER_STAGE2_URL", "http://localhost:8002/health")
WORKER_STAGE3_URL = os.getenv("WORKER_STAGE3_URL", "http://localhost:8003/health")
WORKER_STAGE4_URL = os.getenv("WORKER_STAGE4_URL", "http://localhost:8004/health")
# ---------- END CONFIG ----------

mongo = MongoClient(MONGO_URI)
db = mongo.get_default_database()
documents_col = db["documents"]

r = redis.from_url(REDIS_URL, decode_responses=True)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
            "created_at": mongo_doc.get("createdAt", datetime.datetime.utcnow()).isoformat() if isinstance(mongo_doc.get("createdAt"), datetime.datetime) else None
        }
        
        supabase.table("documents").upsert(supabase_doc).execute()
    except Exception as e:
        # Don't fail the main operation if Supabase sync fails
        print(f"Warning: Failed to sync document {doc_id} to Supabase: {e}")

async def wake_worker(worker_url: str, worker_name: str):
    """Wake up a worker by calling its health endpoint"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(worker_url)
            print(f"[WAKE] {worker_name} health check: {response.status_code}")
    except Exception as e:
        # Don't fail if worker wake-up fails - job is still in queue
        print(f"⚠️ Failed to wake {worker_name} (this is OK, worker will wake when processing): {e}")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include retrieval router
app.include_router(retrieval_router)

# Health check endpoint for Render
@app.get("/health")
async def health():
    """Health check endpoint - Render uses this to verify the service is running"""
    return {"status": "ok", "service": "docqa-api"}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "DOCQA Ultimate API", "status": "running"}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_jwt(sub: str) -> str:
    payload = {"sub": sub, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_user_id_from_jwt(authorization: str = Header(...)):
    # Expects Authorization: Bearer <token>
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/api/signup")
async def signup(email: str = Body(...), password: str = Body(...)):
    users_col = db["users"]
    existing = users_col.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    users_col.insert_one(
        {
            "email": email,
            "password_hash": hash_password(password),
            "createdAt": datetime.datetime.utcnow(),
        }
    )
    token = create_jwt(email)
    return {"token": token}


@app.post("/api/login")
async def login(email: str = Body(...), password: str = Body(...)):
    users_col = db["users"]
    user = users_col.find_one({"email": email})
    if not user or user.get("password_hash") != hash_password(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt(email)
    return {"token": token}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), authorization: str = Header(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    user_id = get_user_id_from_jwt(authorization)
    filename = file.filename

    # read file bytes
    data = await file.read()
    sha = hashlib.sha256(data).hexdigest()

    # Check duplicates by hash or cloudinary public_id (we use hash here)
    existing = documents_col.find_one({"metadata.hash": sha, "userId": user_id})
    if existing:
        return JSONResponse({"status": "exists", "document_id": str(existing["_id"])}, status_code=200)

    # Upload to Supabase Storage
    storage_path = f"docs/{user_id}/{os.path.splitext(filename)[0]}-{sha[:8]}.pdf"
    content_type = file.content_type or "application/pdf"
    supabase.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
        storage_path,
        data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    public_url = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

    # create document metadata in Mongo
    doc = {
        "userId": user_id,
        "title": filename,
        "originalFilename": filename,
        "storage": {
            "bucket": SUPABASE_STORAGE_BUCKET,
            "path": storage_path,
            "public_url": public_url,
            "bytes": len(data),
            "content_type": content_type,
        },
        "status": "uploaded",
        "metadata": {
            "hash": sha
        },
        "createdAt": datetime.datetime.utcnow()
    }
    inserted = documents_col.insert_one(doc)
    doc_id = str(inserted.inserted_id)

    # Sync to Supabase documents table
    sync_document_to_supabase(doc_id, doc)

    # push job to stage1 queue (extract)
    job = json.dumps({"document_id": doc_id, "user_id": user_id})
    r.lpush("queue:stage1", job)

    # Wake up stage1 worker (non-blocking)
    background_tasks.add_task(wake_worker, WORKER_STAGE1_URL, "stage1 worker")
    
    return {"status": "queued", "document_id": doc_id}

# Backward-compatible route (if older clients call /upload)
@app.post("/upload")
async def upload_file_legacy(file: UploadFile = File(...), authorization: str = Header(...)):
    return await upload_file(file, authorization)


@app.get("/api/documents")
async def list_documents(authorization: str = Header(...)):
    user_id = get_user_id_from_jwt(authorization)
    docs = list(
        documents_col.find(
            {"userId": user_id},
            {
                "_id": {"$toString": "$_id"},
                "title": 1,
                "status": 1,
                "createdAt": 1,
            },
        )
    )
    # If the above projection with $toString is unsupported, fallback:
    if not docs:
        docs = []
        cursor = documents_col.find({"userId": user_id}, {"title": 1, "status": 1, "createdAt": 1})
        for d in cursor:
            d["_id"] = str(d.get("_id"))
            docs.append(d)
    return docs


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str, authorization: str = Header(...)):
    """
    Delete a document and all associated data:
    1. Delete file from Supabase Storage
    2. Delete chunks from Supabase
    3. Delete document-level embedding from documents_index
    4. Delete document from Supabase documents table
    5. Delete document from MongoDB
    """
    user_id = get_user_id_from_jwt(authorization)
    user_id_uuid = convert_user_id_to_uuid(user_id)
    
    # Step 1: Get document from MongoDB to retrieve storage info
    try:
        doc = documents_col.find_one({"_id": ObjectId(document_id), "userId": user_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"Invalid document ID: {str(e)}")
    
    storage_info = doc.get("storage", {})
    storage_path = storage_info.get("path")
    storage_bucket = storage_info.get("bucket", SUPABASE_STORAGE_BUCKET)
    
    errors = []
    
    # Step 2: Delete file from Supabase Storage
    if storage_path:
        try:
            supabase.storage.from_(storage_bucket).remove([storage_path])
            print(f"✅ Deleted file from storage: {storage_path}")
        except Exception as e:
            error_msg = f"Failed to delete file from storage: {str(e)}"
            print(f"⚠️ {error_msg}")
            errors.append(error_msg)
    
    # Step 3: Delete chunks from Supabase (cascade delete by document_id)
    try:
        chunks_result = supabase.table("chunks").delete().eq("document_id", document_id).eq("user_id", user_id_uuid).execute()
        chunks_deleted = len(chunks_result.data) if chunks_result.data else 0
        print(f"✅ Deleted {chunks_deleted} chunks from Supabase")
    except Exception as e:
        error_msg = f"Failed to delete chunks: {str(e)}"
        print(f"⚠️ {error_msg}")
        errors.append(error_msg)
    
    # Step 4: Delete document-level embedding from documents_index
    try:
        supabase.table("documents_index").delete().eq("document_id", document_id).eq("user_id", user_id_uuid).execute()
        print(f"✅ Deleted document-level embedding from documents_index")
    except Exception as e:
        error_msg = f"Failed to delete document embedding: {str(e)}"
        print(f"⚠️ {error_msg}")
        errors.append(error_msg)
    
    # Step 5: Delete document from Supabase documents table
    try:
        supabase.table("documents").delete().eq("id", document_id).eq("user_id", user_id_uuid).execute()
        print(f"✅ Deleted document from Supabase documents table")
    except Exception as e:
        error_msg = f"Failed to delete document from Supabase: {str(e)}"
        print(f"⚠️ {error_msg}")
        errors.append(error_msg)
    
    # Step 6: Delete document from MongoDB (final step)
    try:
        result = documents_col.delete_one({"_id": ObjectId(document_id), "userId": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found in MongoDB")
        print(f"✅ Deleted document from MongoDB")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        error_msg = f"Failed to delete document from MongoDB: {str(e)}"
        print(f"❌ {error_msg}")
        errors.append(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    
    # Return success even if some non-critical deletions failed
    if errors:
        return {
            "status": "deleted",
            "document_id": document_id,
            "warnings": errors,
            "message": "Document deleted, but some cleanup operations had warnings"
        }
    
    return {
        "status": "deleted",
        "document_id": document_id,
        "message": "Document and all associated data deleted successfully"
    }
