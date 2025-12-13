# Delete Document Endpoint

## Overview
A comprehensive delete endpoint that removes all data associated with a document across all storage systems.

## Endpoint
```
DELETE /api/documents/{document_id}
```

**Authentication**: Required (JWT Bearer token)

## What Gets Deleted

The endpoint performs the following deletions in order:

1. **Supabase Storage** - Deletes the PDF file from the storage bucket
2. **Supabase Chunks Table** - Deletes all chunks associated with the document
3. **Supabase documents_index Table** - Deletes the document-level vector embedding
4. **Supabase documents Table** - Deletes the document metadata record
5. **MongoDB** - Deletes the document record (final step)

## Implementation Details

### Backend (`app/main.py`)

- **Route**: `@app.delete("/api/documents/{document_id}")`
- **Authentication**: Uses JWT token to verify user ownership
- **Error Handling**: 
  - Validates document exists and belongs to user
  - Continues deletion even if some non-critical steps fail
  - Returns warnings if any cleanup operations had issues
- **Security**: 
  - Verifies user owns the document before deletion
  - Uses user_id filtering in all Supabase queries

### Frontend

#### API Client (`frontend/lib/api/documents.ts`)
- Added `deleteDocument()` function

#### Components
- **DocumentCard** (`frontend/components/documents/DocumentCard.tsx`):
  - Added delete button with trash icon
  - Shows confirmation dialog before deletion
  - Disables button during deletion operation

- **DocumentList** (`frontend/components/documents/DocumentList.tsx`):
  - Handles delete action
  - Updates local state after successful deletion
  - Shows error messages if deletion fails

## Usage

### Backend (cURL)
```bash
curl -X DELETE \
  http://localhost:8000/api/documents/{document_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Frontend
The delete button appears on each document card in the documents list. Clicking it:
1. Shows a confirmation dialog
2. Calls the delete API
3. Removes the document from the UI on success
4. Shows an error message on failure

## Response Format

### Success
```json
{
  "status": "deleted",
  "document_id": "507f1f77bcf86cd799439011",
  "message": "Document and all associated data deleted successfully"
}
```

### Success with Warnings
```json
{
  "status": "deleted",
  "document_id": "507f1f77bcf86cd799439011",
  "warnings": [
    "Failed to delete file from storage: File not found"
  ],
  "message": "Document deleted, but some cleanup operations had warnings"
}
```

### Error
```json
{
  "detail": "Document not found"
}
```

## Error Handling

- **404**: Document not found or doesn't belong to user
- **400**: Invalid document ID format
- **401**: Invalid or missing authentication token
- **500**: Critical error (e.g., MongoDB deletion failed)

## Notes

- The endpoint is idempotent - deleting an already-deleted document returns 404
- Deletion is permanent and cannot be undone
- The endpoint continues with remaining deletions even if some steps fail (except MongoDB deletion, which is critical)
- All Supabase deletions are filtered by `user_id` to ensure users can only delete their own documents
