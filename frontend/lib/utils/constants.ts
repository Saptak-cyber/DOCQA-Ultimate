export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const TOKEN_KEY = 'docqa_token';
export const USER_KEY = 'docqa_user';

export const MAX_FILE_SIZE = undefined; // No file size limit
export const ACCEPTED_FILE_TYPES = ['.pdf'];

export const DOCUMENT_STATUS_COLORS: Record<string, string> = {
  uploaded: 'bg-gray-500',
  processing: 'bg-yellow-500',
  extracted: 'bg-blue-500',
  indexed: 'bg-green-500',
  failed: 'bg-red-500',
};

export const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  extracted: 'Extracted',
  indexed: 'Indexed',
  failed: 'Failed',
};
