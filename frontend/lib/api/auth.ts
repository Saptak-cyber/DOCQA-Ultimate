import apiClient from './client';
import { LoginRequest, SignupRequest, AuthResponse } from '@/types/auth';

export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/api/login', data);
    return response.data;
  },

  signup: async (data: SignupRequest): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/api/signup', data);
    return response.data;
  },
};
