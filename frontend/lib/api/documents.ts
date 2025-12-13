import apiClient from './client';
import { Document, UploadResponse } from '@/types/document';

export const documentsApi = {
  getDocuments: async (): Promise<Document[]> => {
    const response = await apiClient.get<Document[]>('/api/documents');
    // Ensure _id is a string
    return response.data.map((doc) => ({
      ...doc,
      _id: doc._id || String(doc._id),
    }));
  },

  uploadDocument: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await apiClient.post<UploadResponse>(
      '/api/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  deleteDocument: async (documentId: string): Promise<{ status: string; document_id: string; message: string; warnings?: string[] }> => {
    const response = await apiClient.delete(`/api/documents/${documentId}`);
    return response.data;
  },
};
