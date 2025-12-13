'use client';

import { useAuth } from '@/lib/context/AuthContext';
import { User } from 'lucide-react';

export function Header() {
  const { user } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="flex items-center justify-between px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900">Dashboard</h2>
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 text-sm text-gray-700">
            <User className="h-5 w-5 text-gray-400" />
            <span>{user?.email}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
