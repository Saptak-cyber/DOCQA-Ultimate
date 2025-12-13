'use client';

import { useState } from 'react';
import { Source } from '@/types/query';
import { Card } from '@/components/ui/Card';
import { SourceCard } from './SourceCard';
import { FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface SourceListProps {
  sources: Source[];
}

export function SourceList({ sources }: SourceListProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [showAll, setShowAll] = useState(false);

  const displayedSources = showAll ? sources : sources.slice(0, 3);

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <FileText className="h-5 w-5 text-gray-400" />
          <h3 className="text-lg font-semibold text-gray-900">
            Sources ({sources.length})
          </h3>
        </div>
        {sources.length > 3 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? (
              <>
                <ChevronUp className="h-4 w-4 mr-1" />
                Show Less
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4 mr-1" />
                Show All
              </>
            )}
          </Button>
        )}
      </div>

      <div className="space-y-3">
        {displayedSources.map((source, index) => (
          <SourceCard
            key={index}
            source={source}
            isExpanded={expandedIndex === index}
            onToggle={() =>
              setExpandedIndex(expandedIndex === index ? null : index)
            }
          />
        ))}
      </div>
    </Card>
  );
}
