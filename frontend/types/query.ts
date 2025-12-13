export interface QueryRequest {
  query: string;
  top_docs?: number;
  top_chunks?: number;
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
