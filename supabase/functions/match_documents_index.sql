-- match_documents_index: Document-level vector search
-- Returns top matching documents for a query embedding

-- Drop existing function if it exists (with old signature)
drop function if exists match_documents_index(vector, uuid, int);
drop function if exists match_documents_index(vector, int, uuid);

create or replace function match_documents_index(
  query_embedding vector(768),
  user_id uuid,
  match_count int default 5
)
returns table(
  document_id text,
  user_id uuid,
  title text,
  summary text,
  embedding vector(768),
  similarity float
)
language sql stable as $$
  select
    di.document_id,
    di.user_id,
    di.title,
    di.summary,
    di.embedding,
    1 - (di.embedding <=> query_embedding) as similarity
  from documents_index di
  where di.user_id = match_documents_index.user_id
  order by di.embedding <-> query_embedding
  limit match_count;
$$;
