// components/ui/WarmupProvider.tsx
'use client';

import React, { useEffect, useState } from 'react';
import { warmupWorkers } from '@/lib/utils/warmup';
import { WarmupIndicator } from './WarmupIndicator';

export function WarmupProvider({ children }: { children: React.ReactNode }) {
  const [isWarmingUp, setIsWarmingUp] = useState(false);
  const [successCount, setSuccessCount] = useState(0);
  const [showIndicator, setShowIndicator] = useState(false);
  const [hasWarmedUp, setHasWarmedUp] = useState(false);

  useEffect(() => {
    // Only run warmup once when component mounts
    if (!hasWarmedUp) {
      performWarmup();
    }
  }, [hasWarmedUp]);

  const performWarmup = async () => {
    setIsWarmingUp(true);
    setShowIndicator(true);
    setHasWarmedUp(true);

    try {
      const result = await warmupWorkers();
      setSuccessCount(result.successCount);
      
      // Keep the indicator visible for 2 seconds after completion
      setTimeout(() => {
        setIsWarmingUp(false);
        
        // Auto-hide after another 3 seconds
        setTimeout(() => {
          setShowIndicator(false);
        }, 3000);
      }, 1000);
    } catch (error) {
      console.error('Worker warmup failed:', error);
      setIsWarmingUp(false);
      
      // Hide indicator after error
      setTimeout(() => {
        setShowIndicator(false);
      }, 5000);
    }
  };

  const handleClose = () => {
    setShowIndicator(false);
  };

  return (
    <>
      {children}
      {showIndicator && (
        <WarmupIndicator
          isWarmingUp={isWarmingUp}
          successCount={successCount}
          totalWorkers={4}
          onClose={handleClose}
        />
      )}
    </>
  );
}
