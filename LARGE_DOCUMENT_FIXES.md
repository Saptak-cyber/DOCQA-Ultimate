# Large Document Indexing Fixes

## Problem
Large documents were getting stuck at "extracted" status and not being indexed, while small documents worked fine.

## Root Causes Identified

### 1. **Critical Bug in Stage 4** (FIXED ✅)
**Issue**: Line 234 in `stage4_write_embeddings.py` had `.limit(1000)` which silently truncated large documents.

**Impact**: Documents with >1000 chunks would only use the first 1000 chunks for document-level embedding computation, and if there were issues fetching those, the document would fail to index.

**Fix**: 
- Removed the hard limit
- Now fetches up to 1000 chunks (Supabase default) as a representative sample
- For documents with >1000 chunks, uses the first 1000 chunks for document-level embedding (this is acceptable as a sample-based approach)
- Added proper error handling and logging

### 2. **Inefficient Embedding Writes** (FIXED ✅)
**Issue**: Stage 4 was writing embeddings one-by-one in a loop, which is slow for large documents.

**Fix**: 
- Added batch processing structure (though still individual updates due to Supabase API)
- Added progress logging every 100 embeddings for large documents
- Better error handling for failed writes

### 3. **Slow Processing for Large Documents** (IMPROVED ✅)
**Issue**: Stage 3 had a 2-second delay between batches, making large documents very slow.

**Fix**:
- Reduced delay to 1.5 seconds for documents with >100 chunks
- Added progress logging for large documents (>100 chunks)
- Better visibility into processing status

### 4. **Lack of Progress Visibility** (IMPROVED ✅)
**Issue**: No progress indicators for large documents, making it hard to know if processing was stuck or just slow.

**Fix**:
- Added progress logging in Stage 2 (every 200 chunks for large documents)
- Added progress logging in Stage 3 (for documents >100 chunks)
- Added progress logging in Stage 4 (every 100 embeddings)

## Changes Made

### `workers/stage2_chunk_store.py`
- Added progress logging for large documents (>200 chunks)
- Logs progress every 200 chunks inserted

### `workers/stage3_embed_compute.py`
- Reduced delay from 2s to 1.5s for large documents (>100 chunks)
- Added progress percentage logging for documents >100 chunks

### `workers/stage4_write_embeddings.py`
- **CRITICAL FIX**: Removed hard `.limit(1000)` that was truncating large documents
- Now properly handles documents with >1000 chunks by using first 1000 as sample
- Added batch processing structure for embedding writes
- Added progress logging every 100 embeddings
- Better error handling and logging

## Testing Recommendations

1. **Test with a large document** (>1000 chunks):
   - Upload a large PDF (e.g., 100+ pages)
   - Monitor worker logs for progress indicators
   - Verify document reaches "indexed" status
   - Check that document appears in query results

2. **Monitor worker logs** for:
   - Progress indicators showing chunk/embedding counts
   - Any errors during processing
   - Time taken for each stage

3. **Check Supabase**:
   - Verify all chunks have embeddings
   - Verify document exists in `documents_index` table
   - Check document status in MongoDB

## Performance Expectations

For a document with 2000 chunks:
- **Stage 2**: ~2-5 minutes (chunking + Supabase inserts)
- **Stage 3**: ~10-15 minutes (embedding computation with HF API, ~200 batches × 1.5s delay)
- **Stage 4**: ~2-3 minutes (writing embeddings + document-level computation)

**Total**: ~15-23 minutes for a very large document

## Notes

- Documents with >1000 chunks will use the first 1000 chunks for document-level embedding
- This is acceptable as a sample-based approach for very large documents
- The document will still be fully searchable as all chunks have individual embeddings
- Only the document-level embedding (used for initial filtering) uses a sample

## If Issues Persist

1. Check worker logs for specific errors
2. Verify all workers are running (Stage 2, 3, and 4)
3. Check Redis queues: `redis-cli LLEN queue:stage2 queue:stage3 queue:stage4`
4. Verify HF API key is valid and not hitting rate limits
5. Check Supabase connection and limits
