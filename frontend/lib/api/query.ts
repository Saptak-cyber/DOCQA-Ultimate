import apiClient from './client';
import { QueryRequest, QueryResponse } from '@/types/query';

export const queryApi = {
  query: async (data: QueryRequest): Promise<QueryResponse> => {
    const response = await apiClient.post<QueryResponse>('/api/query', data);
    return response.data;
  },
};
