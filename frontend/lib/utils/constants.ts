export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Worker URLs for warmup pinging
export const WORKER_STAGE1_URL = process.env.NEXT_PUBLIC_WORKER_STAGE1_URL || 'http://localhost:8001';
export const WORKER_STAGE2_URL = process.env.NEXT_PUBLIC_WORKER_STAGE2_URL || 'http://localhost:8002';
export const WORKER_STAGE3_URL = process.env.NEXT_PUBLIC_WORKER_STAGE3_URL || 'http://localhost:8003';
export const WORKER_STAGE4_URL = process.env.NEXT_PUBLIC_WORKER_STAGE4_URL || 'http://localhost:8004';

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
