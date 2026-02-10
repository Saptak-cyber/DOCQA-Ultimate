// lib/utils/warmup.ts
import { 
  WORKER_STAGE1_URL, 
  WORKER_STAGE2_URL, 
  WORKER_STAGE3_URL, 
  WORKER_STAGE4_URL 
} from './constants';

export interface WorkerStatus {
  name: string;
  url: string;
  status: 'pending' | 'success' | 'error';
  responseTime?: number;
  error?: string;
}

export interface WarmupResult {
  success: boolean;
  workers: WorkerStatus[];
  totalTime: number;
  successCount: number;
}

/**
 * Ping a single worker's health endpoint
 */
async function pingWorker(name: string, url: string): Promise<WorkerStatus> {
  const startTime = Date.now();
  
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout
    
    const response = await fetch(`${url}/health`, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
      },
    });
    
    clearTimeout(timeoutId);
    const responseTime = Date.now() - startTime;
    
    if (response.ok) {
      return {
        name,
        url,
        status: 'success',
        responseTime,
      };
    } else {
      return {
        name,
        url,
        status: 'error',
        responseTime,
        error: `HTTP ${response.status}`,
      };
    }
  } catch (error) {
    const responseTime = Date.now() - startTime;
    
    return {
      name,
      url,
      status: 'error',
      responseTime,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Warm up all workers by pinging their health endpoints in parallel
 */
export async function warmupWorkers(): Promise<WarmupResult> {
  const startTime = Date.now();
  
  const workers = [
    { name: 'Stage 1', url: WORKER_STAGE1_URL },
    { name: 'Stage 2', url: WORKER_STAGE2_URL },
    { name: 'Stage 3', url: WORKER_STAGE3_URL },
    { name: 'Stage 4', url: WORKER_STAGE4_URL },
  ];
  
  // Ping all workers in parallel
  const results = await Promise.all(
    workers.map(({ name, url }) => pingWorker(name, url))
  );
  
  const totalTime = Date.now() - startTime;
  const successCount = results.filter(r => r.status === 'success').length;
  
  // Log results for debugging
  console.log('Worker warmup completed:', {
    totalTime,
    successCount,
    results: results.map(r => ({
      name: r.name,
      status: r.status,
      responseTime: r.responseTime,
    })),
  });
  
  return {
    success: successCount > 0, // At least one worker responded
    workers: results,
    totalTime,
    successCount,
  };
}
