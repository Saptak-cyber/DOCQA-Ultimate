'use client';

import { useState, useRef, useEffect } from 'react';
import { queryApi } from '@/lib/api/query';
import { ChatMessage, ConversationMessage } from '@/types/query';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { Spinner } from '@/components/ui/Spinner';
import { MessageSquare, Send, Trash2 } from 'lucide-react';
import { QueryResponse as QueryResponseComponent } from './QueryResponse';
import { useLocalStorage } from '@/lib/hooks/useLocalStorage';

export function QueryInterface() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useLocalStorage<ChatMessage[]>('chat-messages', []);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!query.trim() || isLoading) {
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query.trim(),
      timestamp: Date.now(),
    };

    setMessages([...messages, userMessage]);
    setQuery('');
    setIsLoading(true);
    setError(null);

    try {
      // Build conversation history from messages (exclude sources, only role and content)
      const conversationHistory: ConversationMessage[] = messages.map(msg => ({
        role: msg.role,
        content: msg.content,
      }));

      const data = await queryApi.query({
        query: userMessage.content,
        top_docs: 3,
        top_chunks: 20,
        conversation_history: conversationHistory,
      });

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        timestamp: Date.now(),
      };

      setMessages([...messages, userMessage, assistantMessage]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to process query');
      // Remove the user message if the request failed
      setMessages(messages);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    if (confirm('Are you sure you want to clear the entire conversation?')) {
      setMessages([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Compact Header */}
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center space-x-3">
          <MessageSquare className="h-5 w-5 text-gray-400" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Ask Questions</h2>
            <p className="text-xs text-gray-500">
              Query your documents with AI
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            onClick={handleClearChat}
            className="flex items-center"
            size="sm"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            <span className="text-xs">Clear</span>
          </Button>
        )}
      </div>

      {/* Messages Container - Takes most of the space */}
      <div className="flex-1 overflow-y-auto mb-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-400">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-40" />
              <p className="text-sm font-medium">Start a conversation</p>
              <p className="text-xs mt-1">Ask questions about your documents</p>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'user' ? (
              <div className="bg-primary-600 text-white rounded-2xl px-4 py-2.5 max-w-[85%] shadow-sm">
                <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                  {message.content}
                </p>
              </div>
            ) : (
              <div className="w-full">
                <QueryResponseComponent
                  response={{
                    answer: message.content,
                    sources: message.sources || [],
                  }}
                />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <Card className="max-w-[85%]">
              <div className="flex items-center py-3">
                <Spinner size="sm" />
                <span className="ml-2 text-sm text-gray-600">Thinking...</span>
              </div>
            </Card>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-3 flex-shrink-0">
          <Alert type="error">
            {error}
          </Alert>
        </div>
      )}

      {/* Compact Input Form */}
      <form onSubmit={handleSubmit} className="flex-shrink-0">
        <div className="flex items-end space-x-2">
          <div className="flex-1">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question... (Shift+Enter for new line)"
              className="w-full min-h-[56px] max-h-[160px] px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
              disabled={isLoading}
              rows={2}
            />
          </div>
          <Button
            type="submit"
            disabled={!query.trim() || isLoading}
            isLoading={isLoading}
            size="sm"
            className="h-[56px] px-4"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
