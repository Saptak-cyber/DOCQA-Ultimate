'use client';

import { useState } from 'react';
import { queryApi } from '@/lib/api/query';
import { QueryResponse } from '@/types/query';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { Spinner } from '@/components/ui/Spinner';
import { MessageSquare, Send } from 'lucide-react';
import { QueryResponse as QueryResponseComponent } from './QueryResponse';

export function QueryInterface() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!query.trim()) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setResponse(null);

    try {
      const data = await queryApi.query({
        query: query.trim(),
        top_docs: 3,
        top_chunks: 20,
      });
      setResponse(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to process query');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Ask Questions</h2>
        <p className="text-gray-600">
          Ask questions about your uploaded documents and get AI-powered answers
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <Card>
          <div className="flex items-start space-x-3">
            <MessageSquare className="h-5 w-5 text-gray-400 mt-2 flex-shrink-0" />
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question about your documents..."
              className="flex-1 min-h-[120px] px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
              disabled={isLoading}
            />
          </div>
        </Card>

        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={!query.trim() || isLoading}
            isLoading={isLoading}
          >
            <Send className="h-4 w-4 mr-2" />
            Ask Question
          </Button>
        </div>
      </form>

      {error && (
        <Alert type="error">
          {error}
        </Alert>
      )}

      {isLoading && (
        <Card>
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
            <span className="ml-3 text-gray-600">Processing your query...</span>
          </div>
        </Card>
      )}

      {response && <QueryResponseComponent response={response} />}
    </div>
  );
}
