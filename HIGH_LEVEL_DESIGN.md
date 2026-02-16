# DOCQA Ultimate - High-Level Design

## System Overview

DOCQA Ultimate is a production-ready RAG (Retrieval-Augmented Generation) system that enables users to upload PDF documents and query them using natural language. The system uses hierarchical retrieval to find relevant information and generates accurate answers with page-level citations.

---

## Core Architecture

### Technology Stack

**Backend Services:**
- FastAPI - REST API server
- Redis - Task queue management
- MongoDB - Document metadata & status tracking
- Supabase (PostgreSQL + pgvector) - Vector database for semantic search
- Supabase Storage - PDF file storage

**AI/ML Components:**
- Hugging Face Inference API - Text embeddings (all-mpnet-base-v2, 768 dimensions)
- Groq LLM - Answer generation (meta-llama/llama-4-scout-17b-16e-instruct)

**Frontend:**
- Next.js 14 (App Router) - React framework
- Tailwind CSS - Styling
- Axios - HTTP client

---

## System Components

### 1. API Layer (FastAPI)

**Responsibilities:**
- User authentication (JWT-based)
- Document upload endpoint
- Document management (list, delete)
- Query endpoint for RAG

**Key Features:**
- CORS support for frontend
- JWT token validation
- Duplicate detection via SHA-256 hashing
- Background task processing

### 2. Storage Layer

**MongoDB:**
- User accounts (email, password hash)
- Document metadata (title, status, storage info)
- Processing status tracking
- Error logging

**Supabase Storage:**
- PDF file storage
- Public URL generation
- Organized by user ID

**Supabase PostgreSQL + pgvector:**
- `documents` table - Document metadata mirror
- `documents_index` table - Document-level embeddings
- `chunks` table - Chunk-level embeddings with text
- Vector similarity search (IVFFlat index)

### 3. Queue System (Redis)

**Purpose:** Asynchronous processing pipeline

**Queues:**
- `queue:stage1` - PDF extraction
- `queue:stage2` - Text chunking
- `queue:stage3` - Embedding computation
- `queue:stage4` - Vector storage

**Benefits:**
- Non-blocking uploads
- Parallel stage processing
- Fault tolerance
- Scalability

### 4. Worker Pipeline (4 Stages)

**Stage 1 - PDF Extraction:**
- Downloads PDF from Supabase Storage
- Extracts text from each page
- Handles large files (streaming mode for >10MB)
- Memory-optimized processing

**Stage 2 - Chunking:**
- Splits pages into semantic chunks
- Configurable chunk size (500 tokens) and overlap (50 tokens)
- Stores chunks in Supabase (without embeddings)
- Sanitizes text for PostgreSQL

**Stage 3 - Embedding Computation:**
- Generates embeddings using Hugging Face API
- Processes in batches (400 chunks)
- Rate limiting and retry logic
- Queues embeddings for storage

**Stage 4 - Vector Storage:**
- Writes embeddings to Supabase chunks table
- Computes document-level embedding (average of chunks)
- Marks document as "indexed"
- Syncs status to MongoDB

### 5. Query System (Hierarchical RAG)

**Two-Stage Retrieval:**

**Stage 1 - Document-level Search:**
- Embeds user query
- Searches `documents_index` table
- Returns top N relevant documents (default: 3)

**Stage 2 - Chunk-level Search:**
- Searches `chunks` table filtered by top documents
- Returns top M relevant chunks (default: 20)
- Includes page numbers and similarity scores

**Answer Generation:**
- Builds context from retrieved chunks
- Calls Groq LLM with strict citation prompt
- Returns answer with page-level citations

---

## Data Flow

### Upload Flow

```
User uploads PDF
    ↓
FastAPI /api/upload
    ↓
Compute SHA-256 hash → Check MongoDB for duplicates
    ↓ (if not duplicate)
Upload to Supabase Storage
    ↓
Insert metadata to MongoDB (status: "uploaded")
    ↓
Push to queue:stage1
    ↓
[Worker 1] Extract pages → Push to queue:stage2
    ↓
[Worker 2] Chunk pages → Insert chunks to Supabase → Push to queue:stage3
    ↓
[Worker 3] Compute embeddings → Push to queue:stage4
    ↓
[Worker 4] Write embeddings → Create doc-level embedding → Mark "indexed"
```

### Query Flow

```
User asks question
    ↓
FastAPI /api/query
    ↓
Embed query (Hugging Face API)
    ↓
Search documents_index (top 3 docs)
    ↓
Search chunks filtered by docs (top 20 chunks)
    ↓
Build context with citations
    ↓
Call Groq LLM
    ↓
Return answer with page citations
```

---

## Key Design Decisions

### 1. Hierarchical Retrieval

**Why:** Improves accuracy and reduces search space
- Document-level search narrows down relevant documents
- Chunk-level search finds specific passages
- Better than flat chunk search across all documents

### 2. Asynchronous Pipeline

**Why:** Non-blocking user experience
- Users get immediate response after upload
- Query endpoint always available during processing
- Workers process independently

### 3. Streaming for Large Files

**Why:** Memory efficiency
- Stage 1 streams PDFs >10MB to disk
- Processes pages in batches
- Prevents OOM errors on 512MB RAM workers

### 4. Duplicate Detection

**Why:** Storage efficiency and user experience
- SHA-256 hash prevents duplicate uploads
- Instant response for existing documents
- Saves storage and processing costs

### 5. Citation-Forcing LLM Prompt

**Why:** Accuracy and trust
- Forces LLM to cite page numbers
- Users can verify answers
- Reduces hallucinations

### 6. Hugging Face API for Embeddings

**Why:** Scalability and cost
- No local model loading (saves memory)
- Consistent embeddings across workers
- Easy to scale horizontally

---

## Security Features

### Authentication
- JWT-based authentication
- 7-day token expiration
- Password hashing (SHA-256)

### Data Isolation
- User ID filtering on all queries
- UUID conversion for Supabase
- Document ownership validation

### Input Validation
- File size limits (100MB)
- Content type validation
- SQL injection prevention (parameterized queries)

---

## Scalability Considerations

### Horizontal Scaling
- API: Multiple FastAPI instances behind load balancer
- Workers: One worker per stage (by design)
- Redis: Managed Redis (Upstash, Redis Cloud)
- MongoDB: MongoDB Atlas with auto-scaling

### Performance Optimization
- IVFFlat index for vector search
- Batch processing in workers
- Connection pooling
- Caching (future enhancement)

### Cost Optimization
- Duplicate detection saves storage
- Efficient chunking reduces embeddings
- Serverless deployment (Render, Vercel)

---

## Monitoring & Observability

### Status Tracking
- Document status: uploaded → processing → extracted → indexed → failed
- Error logging in MongoDB
- Worker health checks

### Metrics (Future)
- Upload success rate
- Processing time per stage
- Query latency
- Embedding API usage

---

## Frontend Architecture

### Pages
- Landing page
- Login/Signup
- Documents list
- Upload page
- Query interface

### Key Features
- Real-time status updates
- Drag & drop upload
- Source citations with page numbers
- Responsive design

### State Management
- Auth context (JWT token)
- Local storage for persistence
- Custom hooks for API calls

---

## Deployment Architecture

### Production Setup
- **API:** Render (FastAPI)
- **Workers:** Render (4 separate services)
- **Frontend:** Vercel (Next.js)
- **Redis:** Upstash Redis
- **MongoDB:** MongoDB Atlas
- **Supabase:** Hosted (PostgreSQL + Storage)

### Environment Variables
- Supabase credentials
- MongoDB URI
- Redis URL
- JWT secret
- Hugging Face API key
- Groq API key

---

## Future Enhancements

### Planned Features
- Multi-file query (search across all documents)
- Document summarization
- OCR for scanned PDFs
- Support for more file types (DOCX, TXT)
- Query history
- Document sharing

### Performance Improvements
- Caching layer (Redis)
- Reranking with cross-encoder
- Streaming LLM responses
- Incremental indexing

### User Experience
- Real-time processing updates (WebSockets)
- Document preview
- Highlighted source text
- Export answers to PDF

---

## Conclusion

DOCQA Ultimate is a robust, scalable RAG system designed for production use. The hierarchical retrieval approach ensures accurate answers, while the asynchronous pipeline provides a smooth user experience. The system is built with modern best practices for security, scalability, and maintainability.
