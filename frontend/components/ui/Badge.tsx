import React from 'react';
import { cn } from '@/lib/utils/cn';
import { DOCUMENT_STATUS_COLORS } from '@/lib/utils/constants';

interface BadgeProps {
  status: string;
  children?: React.ReactNode;
  className?: string;
}

export function Badge({ status, children, className }: BadgeProps) {
  const colorClass = DOCUMENT_STATUS_COLORS[status] || 'bg-gray-500';
  
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium text-white',
        colorClass,
        className
      )}
    >
      {children || status}
    </span>
  );
}
