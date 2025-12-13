'use client';

import { Source } from '@/types/query';
import { Card } from '@/components/ui/Card';
import { ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface SourceCardProps {
  source: Source;
  isExpanded: boolean;
  onToggle: () => void;
}

export function SourceCard({ source, isExpanded, onToggle }: SourceCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-2">
            <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
            <h4 className="text-sm font-semibold text-gray-900 truncate">
              {source.document_title}
            </h4>
          </div>
          
          <div className="flex items-center space-x-4 text-xs text-gray-500 mb-2">
            <span>Page {source.page_number}</span>
            <span>Chunk {source.chunk_index}</span>
            <span>Similarity: {(source.similarity * 100).toFixed(1)}%</span>
          </div>

          {isExpanded ? (
            <p className="text-sm text-gray-700 mt-2 whitespace-pre-wrap">
              {source.text}
            </p>
          ) : (
            <p className="text-sm text-gray-600 mt-2 line-clamp-2">
              {source.text}
            </p>
          )}
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          className="ml-3 flex-shrink-0"
        >
          {isExpanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </Button>
      </div>
    </Card>
  );
}
