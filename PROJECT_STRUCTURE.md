DOCQA Ultimate – Project Structure (short)

- app/ — FastAPI backend (upload, retrieval, chunking helpers)
- workers/ — 4 pipeline stages: extraction, chunk store, embed compute, write embeddings
- queue/ — Redis queue helper
- docker/ — worker image Dockerfile; docker-compose.yml at root
- supabase/ — SQL RPC functions (match_documents_index, match_chunks_filtered); supabase_schema.sql at root
- my-frontend/ — Next.js client
- requirements.txt — backend deps
- README.md — full setup guide
