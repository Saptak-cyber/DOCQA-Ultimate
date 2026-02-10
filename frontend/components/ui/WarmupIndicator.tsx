// components/ui/WarmupIndicator.tsx
'use client';

import React from 'react';
import { Spinner } from './Spinner';
import { Alert } from './Alert';

interface WarmupIndicatorProps {
  isWarmingUp: boolean;
  successCount: number;
  totalWorkers: number;
  onClose?: () => void;
}

export function WarmupIndicator({ 
  isWarmingUp, 
  successCount, 
  totalWorkers,
  onClose 
}: WarmupIndicatorProps) {
  // Don't render if not warming up and no results
  if (!isWarmingUp && successCount === 0) {
    return null;
  }

  // Show loading state
  if (isWarmingUp) {
    return (
      <div className="fixed top-4 right-4 z-50 max-w-md">
        <Alert type="info" onClose={onClose}>
          <div className="flex items-center gap-2">
            <Spinner size="sm" />
            <span className="font-medium">Waking up workers... {successCount}/{totalWorkers}</span>
          </div>
          <p className="text-sm mt-1 opacity-80">
            This may take up to 30 seconds for cold starts
          </p>
        </Alert>
      </div>
    );
  }

  // Show success/warning state
  const allSuccess = successCount === totalWorkers;
  
  return (
    <div className="fixed top-4 right-4 z-50 max-w-md">
      <Alert 
        type={allSuccess ? 'success' : 'warning'} 
        onClose={onClose}
      >
        <div className="font-medium">
          {allSuccess 
            ? '✓ All workers ready' 
            : `⚠️ ${successCount}/${totalWorkers} workers ready`
          }
        </div>
        {!allSuccess && (
          <p className="text-sm mt-1 opacity-80">
            Some workers may take longer to wake up
          </p>
        )}
      </Alert>
    </div>
  );
}
