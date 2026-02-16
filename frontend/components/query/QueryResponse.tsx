'use client';

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

export function QueryResponse({ response }: QueryResponseProps) {
  // Preprocess markdown to ensure proper spacing around code blocks
  const processedAnswer = response.answer
    // Add newlines before code blocks if missing
    .replace(/([^\n])(```)/g, '$1\n\n$2')
    // Add newlines after code blocks if missing
    .replace(/(```\n?)([^\n])/g, '$1\n$2')
    // Fix numbered lists followed by code blocks
    .replace(/(\d+\.\s+[^\n]+)(```)/g, '$1\n\n$2');
  
  console.log('Processed markdown:', processedAnswer);
  
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
                // Check if this is a code block (has language class or is not inline)
                if (!inline) {
                  return (
                    <code 
                      className={`block bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto font-mono text-sm leading-relaxed whitespace-pre ${className || ''}`}
                      {...props}
                    >
                      {children}
                    </code>
                  );
                }
                
                // Inline code
                return (
                  <code className="bg-gray-100 text-primary-700 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                    {children}
                  </code>
                );
              },
              pre({ children }: any) {
                // Wrap code blocks with proper spacing
                return <div className="my-4">{children}</div>;
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
              p: ({ children }: any) => (
                <p className="text-gray-700 mb-3 leading-relaxed break-words">{children}</p>
              ),
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
        <SourceList sources={response.sources} />
      )}
    </div>
  );
}
