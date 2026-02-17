'use client';

import React, { useState } from 'react';
import { QueryResponse as QueryResponseType } from '@/types/query';
import { Card } from '@/components/ui/Card';
import { SourceList } from './SourceList';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';

interface QueryResponseProps {
  response: QueryResponseType;
}

// Helper to parse and render text with inline citations
function renderTextWithCitations(text: string, onCitationClick: (index: number) => void) {
  // Match citation patterns like [1], [2], etc.
  const parts = text.split(/(\[\d+\])/g);
  
  return parts.map((part, idx) => {
    const match = part.match(/\[(\d+)\]/);
    if (match) {
      const citationNum = parseInt(match[1], 10);
      return (
        <sup
          key={idx}
          className="inline-flex items-center justify-center w-5 h-5 ml-0.5 text-xs font-medium text-white bg-blue-600 rounded cursor-pointer hover:bg-blue-700 transition-colors"
          onClick={() => onCitationClick(citationNum - 1)}
          title={`View source ${citationNum}`}
        >
          {citationNum}
        </sup>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

export function QueryResponse({ response }: QueryResponseProps) {
  const [highlightedSource, setHighlightedSource] = useState<number | null>(null);

  const handleCitationClick = (sourceIndex: number) => {
    setHighlightedSource(sourceIndex);
    // Scroll to sources section
    setTimeout(() => {
      const sourcesElement = document.getElementById('sources-section');
      if (sourcesElement) {
        sourcesElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 100);
    // Clear highlight after 3 seconds
    setTimeout(() => setHighlightedSource(null), 3000);
  };

  // Preprocess markdown to ensure proper spacing around code blocks (triple backticks only)
  const processedAnswer = response.answer
    // Add newlines before code blocks if missing (only triple backticks)
    .replace(/([^\n])(```[a-z]*\n)/g, '$1\n\n$2')
    // Add newlines after code blocks if missing (only triple backticks)
    .replace(/(```\n?)([^\n`])/g, '$1\n$2');
  
  return (
    <div className="space-y-4">
      <Card>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Answer</h3>
        <div className="prose prose-sm max-w-none break-words prose-headings:font-semibold prose-p:text-gray-700 prose-a:text-primary-600 prose-strong:text-gray-900">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw, rehypeHighlight]}
            components={{
              code({ node, inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '');
                
                // Inline code (single backticks) - light background
                if (inline && !match) {
                  // Check if inline code contains citations
                  const text = String(children);
                  if (/\[\d+\]/.test(text)) {
                    return (
                      <code className="bg-gray-100 text-primary-700 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                        {renderTextWithCitations(text, handleCitationClick)}
                      </code>
                    );
                  }
                  return (
                    <code className="bg-gray-100 text-primary-700 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                      {children}
                    </code>
                  );
                }
                
                // Code block (triple backticks) - dark background with citation support
                const codeText = String(children);
                const lines = codeText.split('\n');
                
                return (
                  <code 
                    className={`block bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto font-mono text-sm leading-relaxed whitespace-pre ${className || ''}`}
                    {...props}
                  >
                    {lines.map((line, idx) => {
                      // Check if line contains citations
                      if (/\[\d+\]/.test(line)) {
                        return (
                          <span key={idx} className="block">
                            {renderTextWithCitations(line, handleCitationClick)}
                            {idx < lines.length - 1 ? '\n' : ''}
                          </span>
                        );
                      }
                      return line + (idx < lines.length - 1 ? '\n' : '');
                    })}
                  </code>
                );
              },
              pre({ children, ...props }: any) {
                // Only wrap actual code blocks (children should be a code element)
                const isCodeBlock = React.Children.toArray(children).some(
                  (child: any) => child?.type === 'code'
                );
                
                if (isCodeBlock) {
                  return <div className="my-4">{children}</div>;
                }
                
                // Not a code block, render as-is
                return <pre {...props}>{children}</pre>;
              },
              h1: ({ children }: any) => (
                <h1 className="text-2xl font-bold text-gray-900 mt-6 mb-4 break-words">{children}</h1>
              ),
              h2: ({ children }: any) => (
                <h2 className="text-xl font-bold text-gray-900 mt-5 mb-3 break-words">{children}</h2>
              ),
              h3: ({ children }: any) => (
                <h3 className="text-lg font-semibold text-gray-900 mt-4 mb-2 break-words">{children}</h3>
              ),
              p: ({ children }: any) => {
                // Check if paragraph contains citations
                const text = React.Children.toArray(children)
                  .map(child => typeof child === 'string' ? child : '')
                  .join('');
                
                if (/\[\d+\]/.test(text)) {
                  return (
                    <p className="text-gray-700 mb-3 leading-relaxed break-words">
                      {React.Children.map(children, (child) => {
                        if (typeof child === 'string') {
                          return renderTextWithCitations(child, handleCitationClick);
                        }
                        return child;
                      })}
                    </p>
                  );
                }
                
                return (
                  <p className="text-gray-700 mb-3 leading-relaxed break-words">{children}</p>
                );
              },
              ul: ({ children }: any) => (
                <ul className="list-disc list-outside ml-6 mb-4 space-y-2 text-gray-700">{children}</ul>
              ),
              ol: ({ children }: any) => (
                <ol className="list-decimal list-outside ml-6 mb-4 space-y-2 text-gray-700">{children}</ol>
              ),
              li: ({ children }: any) => (
                <li className="break-words">{children}</li>
              ),
              blockquote: ({ children }: any) => (
                <blockquote className="border-l-4 border-primary-500 pl-4 italic text-gray-600 my-4 break-words">
                  {children}
                </blockquote>
              ),
              a: ({ href, children }: any) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-600 hover:text-primary-700 underline break-words"
                >
                  {children}
                </a>
              ),
              table: ({ children }: any) => (
                <div className="overflow-x-auto my-4">
                  <table className="min-w-full border border-gray-300 rounded-lg">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }: any) => (
                <thead className="bg-gray-100">{children}</thead>
              ),
              tbody: ({ children }: any) => (
                <tbody className="divide-y divide-gray-200">{children}</tbody>
              ),
              tr: ({ children }: any) => (
                <tr className="hover:bg-gray-50">{children}</tr>
              ),
              th: ({ children }: any) => (
                <th className="px-4 py-2 text-left font-semibold text-gray-900 border-b border-gray-300 break-words">
                  {children}
                </th>
              ),
              td: ({ children }: any) => (
                <td className="px-4 py-2 text-gray-700 border-b border-gray-200 break-words">{children}</td>
              ),
            }}
          >
            {processedAnswer}
          </ReactMarkdown>
        </div>
      </Card>

      {response.sources && response.sources.length > 0 && (
        <div id="sources-section">
          <SourceList sources={response.sources} highlightedIndex={highlightedSource} />
        </div>
      )}
    </div>
  );
}
