-- Enable pgvector (Supabase must have pgvector enabled on project)
CREATE EXTENSION IF NOT EXISTS vector;

-- documents table (optional mirror for quick SQL joins)
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,             -- store Mongo _id as text
  user_id UUID NOT NULL,
  title TEXT,
  storage_bucket TEXT,
  storage_path TEXT,
  storage_public_url TEXT,
  status TEXT DEFAULT 'uploaded',  -- uploaded | processing | indexed | failed
  pages INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- documents_index: one embedding per document (for hierarchical retrieval)
CREATE TABLE IF NOT EXISTS documents_index (
  document_id TEXT PRIMARY KEY, -- same as documents.id
  user_id UUID NOT NULL,
  title TEXT,
  summary TEXT,
  embedding VECTOR(768), -- adjust dim to your embedding model (e.g., 1536 for OpenAI text-embedding-3-large)
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- chunks: stores chunk text + page number + embedding column
CREATE TABLE IF NOT EXISTS chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  document_id TEXT NOT NULL,
  page_number INT,
  chunk_index INT, -- order within doc
  text TEXT NOT NULL,
  tokens INT,
  embedding VECTOR(768),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_user_id ON chunks (user_id);
-- Vector index: tune lists value later
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
  ON chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 500);

-- documents_index vector index (small number of docs)
CREATE INDEX IF NOT EXISTS idx_documents_index_embedding
  ON documents_index USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- Example: enable pgcrypto if gen_random_uuid used
CREATE EXTENSION IF NOT EXISTS pgcrypto;
