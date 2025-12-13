export type DocumentStatus = 
  | 'uploaded' 
  | 'processing' 
  | 'extracted' 
  | 'indexed' 
  | 'failed';

export interface Document {
  _id: string;
  title: string;
  status: DocumentStatus;
  createdAt: string;
  originalFilename?: string;
  page_count?: number;
  processingErrors?: string[];
}

export interface UploadResponse {
  status: 'queued' | 'exists';
  document_id: string;
}
