# app/retrieval.py
import os
import uuid
import jwt
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client
from groq import Groq
from huggingface_hub import InferenceClient

load_dotenv()

router = APIRouter()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")

# Hugging Face Inference API Configuration
HF_API_KEY = os.getenv("HF_API_KEY")  # Get from https://huggingface.co/settings/tokens
HF_EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")

# Embedding configuration
EXPECTED_EMBED_DIM = 768  # Must match schema VECTOR(768)

# Initialize clients
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize Hugging Face Inference Client
if HF_API_KEY:
    hf_client = InferenceClient(
        provider="hf-inference",
        api_key=HF_API_KEY,
    )
    print(f"✅ Using Hugging Face Inference API: {HF_EMBED_MODEL}")
    print(f"✅ Expected embedding dimension: {EXPECTED_EMBED_DIM}")
else:
    hf_client = None
    print("⚠️ WARNING: HF_API_KEY not set. Query embeddings will fail!")
    print("⚠️ Get your token from: https://huggingface.co/settings/tokens")

# Namespace UUID for converting emails to UUIDs (consistent across all workers)
EMAIL_TO_UUID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')

def convert_user_id_to_uuid(user_id):
    """Convert user_id (email string) to UUID format for Supabase."""
    try:
        return str(uuid.UUID(user_id))
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(EMAIL_TO_UUID_NAMESPACE, str(user_id))
        return str(user_uuid)

def get_user_id_from_jwt(authorization: str):
    """Extract user_id from JWT token."""
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]  # Returns email
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# ------------ Request Schema -------------
class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class QueryRequest(BaseModel):
    query: str
    top_docs: int = 3
    top_chunks: int = 20
    conversation_history: Optional[List[ConversationMessage]] = []

# ------------ Response Schema -------------
class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]

# ------------ Helper: Embed text using Hugging Face API -------------
def embed_text(text: str) -> List[float]:
    """Convert text to embedding vector using Hugging Face Inference API."""
    if not hf_client:
        raise HTTPException(
            status_code=500,
            detail="HF_API_KEY not configured. Please set it in environment variables."
        )
    
    try:
        # Use the official InferenceClient feature_extraction method
        result = hf_client.feature_extraction(
            text,
            model=HF_EMBED_MODEL,
        )
        
        # Convert to list of floats
        if isinstance(result, list):
            embedding_vector = result
        else:
            # If it's a numpy array or similar, convert to list
            embedding_vector = result.tolist() if hasattr(result, 'tolist') else list(result)
        
        return embedding_vector
            
    except Exception as e:
        error_str = str(e)
        if "503" in error_str or "loading" in error_str.lower():
            raise HTTPException(
                status_code=503,
                detail="Hugging Face model is loading. Please try again in a few seconds."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Hugging Face API request failed: {str(e)}"
        )

# ------------ Helper: Document-level search -------------
def search_documents(user_id_uuid: str, query_emb: List[float], limit: int = 3):
    """Search documents_index table using vector similarity."""
    try:
        res = supabase.rpc(
            "match_documents_index",
            {
                "query_embedding": query_emb,
                "match_count": limit,
                "user_id": user_id_uuid
            }
        ).execute()
        return res.data or []
    except Exception as e:
        print(f"Error in document search: {e}")
        # Fallback: return empty list
        return []

# ------------ Helper: Chunk-level search -------------
def search_chunks(user_id_uuid: str, doc_ids: List[str], query_emb: List[float], limit: int = 20):
    """Search chunks table filtered by document IDs."""
    try:
        res = supabase.rpc(
            "match_chunks_filtered",
            {
                "query_embedding": query_emb,
                "match_count": limit,
                "doc_ids": doc_ids,
                "user_id": user_id_uuid
            }
        ).execute()
        return res.data or []
    except Exception as e:
        print(f"Error in chunk search: {e}")
        # Fallback: return empty list
        return []

# ------------ Helper: Get document titles -------------
def get_document_titles(doc_ids: List[str]) -> dict:
    """Fetch document titles from Supabase documents table."""
    try:
        res = supabase.table("documents").select("id,title").in_("id", doc_ids).execute()
        return {d["id"]: d.get("title", "Unknown Document") for d in (res.data or [])}
    except Exception as e:
        print(f"Warning: Could not fetch document titles: {e}")
        return {}

# ------------ Helper: Build LLM prompt -------------
def build_prompt(query: str, chunks: List[dict], doc_titles: dict, conversation_history: List[dict] = None) -> tuple:
    """Build prompt with context chunks, citations, and conversation history."""
    context_str = ""
    for idx, c in enumerate(chunks, 1):
        doc_id = c.get("document_id", "Unknown")
        doc_title = doc_titles.get(doc_id, f"Document {doc_id[:8]}")
        page = c.get("page_number", "?")
        text = c.get("text", "")
        context_str += (
            f"\n[Source {idx}: {doc_title}, Page: {page}]\n"
            f"{text}\n"
        )
    
    system_message = """You are a RAG assistant. Answer using ONLY the provided context.

If the user asks for an answer from a particular document by name, prioritize information from that specific document in your response.

If the answer is not in the context, reply: "I don't know based on the provided documents."

IMPORTANT: When citing sources, use inline citation numbers like this:
- For regular text: "This is a fact [1]."
- For code blocks and technical content: Add citation numbers at the end of relevant lines or sections using the format [1], [2], etc.
- Each [Source N] in the context corresponds to citation number [N]

Example with code:
```java
public class Example extends Base {  [1]
    // This demonstrates inheritance  [1]
}
```"""
    
    # Build messages array with conversation history
    messages = [{"role": "system", "content": system_message}]
    
    # Add conversation history if provided
    if conversation_history:
        for msg in conversation_history:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
    
    # Add current query with context
    user_message = f"""USER QUERY:
{query}

-------------------------

CONTEXT:
{context_str}

-------------------------

Give your final answer now:"""
    
    messages.append({"role": "user", "content": user_message})
    
    return messages

# ------------ The Query Endpoint -------------
@router.post("/api/query", response_model=QueryResponse)
async def query_rag(req: QueryRequest, authorization: str = Header(...)):
    """
    Hierarchical RAG query endpoint:
    1. Document-level search (documents_index)
    2. Chunk-level search (chunks) filtered by top docs
    3. LLM answer with citations
    """
    # Get user_id from JWT and convert to UUID
    user_id_email = get_user_id_from_jwt(authorization)
    user_id_uuid = convert_user_id_to_uuid(user_id_email)
    
    # Step 1 — Embed the query using Hugging Face API
    try:
        query_emb = embed_text(req.query)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to embed query: {str(e)}")
    
    # Validate embedding dimension
    if len(query_emb) != EXPECTED_EMBED_DIM:
        raise HTTPException(
            status_code=500,
            detail=f"Embedding dimension mismatch: got {len(query_emb)}, expected {EXPECTED_EMBED_DIM}. Check HF_EMBED_MODEL."
        )
    
    # Step 2 — Document-level search
    print(f"🔎 Searching top {req.top_docs} documents...")
    top_docs = search_documents(user_id_uuid, query_emb, req.top_docs)
    
    if not top_docs:
        return QueryResponse(
            answer="No indexed documents found for this query.",
            sources=[]
        )
    
    doc_ids = [d["document_id"] for d in top_docs]
    print(f"✅ Found {len(doc_ids)} relevant documents: {doc_ids}")
    
    # Step 3 — Chunk-level search
    print(f"🔎 Searching top {req.top_chunks} chunks inside top docs...")
    chunk_matches = search_chunks(user_id_uuid, doc_ids, query_emb, req.top_chunks)
    
    if not chunk_matches:
        return QueryResponse(
            answer="I don't know based on the provided documents.",
            sources=[]
        )
    
    print(f"✅ Found {len(chunk_matches)} relevant chunks")
    
    # Step 4 — Get document titles for better citations
    doc_titles = get_document_titles(doc_ids)
    
    # Step 5 — Build LLM prompt with conversation history
    messages = build_prompt(req.query, chunk_matches, doc_titles, req.conversation_history)
    
    # Step 6 — Call Groq LLM
    print(f"🧠 Calling Groq LLM ({GROQ_MODEL})...")
    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
            top_p=0.9,
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        print(f"❌ LLM error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")
    
    # Step 7 — Format sources with document titles
    sources = [
        {
            "document_id": c.get("document_id"),
            "document_title": doc_titles.get(c.get("document_id"), "Unknown Document"),
            "page_number": c.get("page_number"),
            "chunk_index": c.get("chunk_index"),
            "text": c.get("text"),
            "similarity": round(c.get("similarity", 0), 4)
        }
        for c in chunk_matches
    ]
    
    print(f"✅ Query completed successfully")
    
    return QueryResponse(
        answer=answer,
        sources=sources
    )
