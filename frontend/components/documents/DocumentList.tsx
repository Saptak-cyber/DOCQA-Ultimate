'use client';

import { useEffect, useState } from 'react';
import { Document } from '@/types/document';
import { documentsApi } from '@/lib/api/documents';
import { DocumentCard } from './DocumentCard';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export function DocumentList() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchDocuments = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await documentsApi.getDocuments();
      setDocuments(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (documentId: string) => {
    try {
      setDeletingId(documentId);
      setError(null);
      await documentsApi.deleteDocument(documentId);
      // Remove document from local state
      setDocuments((prev) => prev.filter((doc) => doc._id !== documentId));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete document');
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => {
    fetchDocuments();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchDocuments, 5000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading && documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert type="error" className="mb-6">
        {error}
        <Button
          variant="secondary"
          size="sm"
          onClick={fetchDocuments}
          className="mt-4"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </Alert>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 mb-4">No documents yet</p>
        <p className="text-sm text-gray-400">
          Upload your first document to get started
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">
          Documents ({documents.length})
        </h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={fetchDocuments}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {documents.map((doc) => (
          <DocumentCard
            key={doc._id}
            document={doc}
            onDelete={handleDelete}
            isDeleting={deletingId === doc._id}
          />
        ))}
      </div>
    </div>
  );
}
