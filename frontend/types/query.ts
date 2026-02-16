export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface QueryRequest {
  query: string;
  top_docs?: number;
  top_chunks?: number;
  conversation_history?: ConversationMessage[];
}

export interface Source {
  document_id: string;
  document_title: string;
  page_number: number;
  chunk_index: number;
  text: string;
  similarity: number;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: number;
}
