'use client';

import { Document } from '@/types/document';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { formatRelativeTime } from '@/lib/utils/formatDate';
import { FileText, Clock, Trash2 } from 'lucide-react';
import { DOCUMENT_STATUS_LABELS } from '@/lib/utils/constants';

interface DocumentCardProps {
  document: Document;
  onClick?: () => void;
  onDelete?: (documentId: string) => void;
  isDeleting?: boolean;
}

export function DocumentCard({ document, onClick, onDelete, isDeleting }: DocumentCardProps) {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click when clicking delete
    if (onDelete && window.confirm(`Are you sure you want to delete "${document.title}"? This will permanently delete the file and all associated data.`)) {
      onDelete(document._id);
    }
  };

  return (
    <Card
      className={`hover:shadow-md transition-shadow ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-2">
            <FileText className="h-5 w-5 text-gray-400 flex-shrink-0" />
            <h3 className="text-lg font-semibold text-gray-900 truncate">
              {document.title}
            </h3>
          </div>
          
          <div className="flex items-center space-x-4 text-sm text-gray-500 mb-3">
            <div className="flex items-center space-x-1">
              <Clock className="h-4 w-4" />
              <span>{formatRelativeTime(document.createdAt)}</span>
            </div>
            {document.page_count && (
              <span>{document.page_count} pages</span>
            )}
          </div>
          
          <Badge status={document.status}>
            {DOCUMENT_STATUS_LABELS[document.status] || document.status}
          </Badge>
        </div>
        
        {onDelete && (
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="ml-4 p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Delete document"
          >
            <Trash2 className="h-5 w-5" />
          </button>
        )}
      </div>
      
      {document.processingErrors && document.processingErrors.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <p className="text-sm text-red-600">
            {document.processingErrors[document.processingErrors.length - 1]}
          </p>
        </div>
      )}
    </Card>
  );
}
