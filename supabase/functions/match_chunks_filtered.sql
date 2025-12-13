-- match_chunks_filtered: Chunk-level vector search filtered by document IDs
-- Returns top matching chunks from specified documents

-- Drop existing function if it exists (with old signature)
drop function if exists match_chunks_filtered(vector, text[], uuid, integer);
drop function if exists match_chunks_filtered(vector, int, text[], uuid);

create or replace function match_chunks_filtered(
  query_embedding vector(768),
  doc_ids text[],
  user_id uuid,
  match_count int default 20
)
returns table(
  id uuid,
  document_id text,
  user_id uuid,
  page_number int,
  chunk_index int,
  text text,
  tokens int,
  embedding vector(768),
  similarity float
)
language sql stable as $$
  select
    c.id,
    c.document_id,
    c.user_id,
    c.page_number,
    c.chunk_index,
    c.text,
    c.tokens,
    c.embedding,
    1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  where c.user_id = match_chunks_filtered.user_id
    and c.document_id = any(doc_ids)
    and c.embedding is not null
  order by c.embedding <-> query_embedding
  limit match_count;
$$;
