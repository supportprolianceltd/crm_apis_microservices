import Queue from 'bull';
import { logger } from '../../utils/logger';

export interface ClientClusterAssignmentJobData {
  tenantId: string;
  clientId: string;
  clientName: string;
  address: string;
  postcode: string;
  town?: string;
  city?: string;
  requestId?: string; // For tracking
  userId?: string; // Who triggered the job
}

export interface JobProgress {
  step: string;
  percentage: number;
  message: string;
}

// Create Bull queue for client cluster assignments
export const clientClusterAssignmentQueue = new Queue<ClientClusterAssignmentJobData>(
  'client-cluster-assignment',
  {
    redis: {
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      password: process.env.REDIS_PASSWORD || undefined,
      db: parseInt(process.env.REDIS_DB || '0')
    },
    defaultJobOptions: {
      attempts: 3, // Retry up to 3 times
      backoff: {
        type: 'exponential',
        delay: 5000 // Start with 5 second delay
      },
      removeOnComplete: 100, // Keep last 100 completed jobs
      removeOnFail: 500, // Keep last 500 failed jobs
      timeout: 60000 // 60 second timeout
    }
  }
);

// Queue event handlers
clientClusterAssignmentQueue.on('error', (error) => {
  logger.error('Queue error:', error);
});

clientClusterAssignmentQueue.on('failed', (job, error) => {
  logger.error('Job failed:', {
    jobId: job.id,
    clientId: job.data.clientId,
    error: error.message
  });
});

clientClusterAssignmentQueue.on('completed', (job, result) => {
  logger.info('Job completed successfully:', {
    jobId: job.id,
    clientId: job.data.clientId,
    clusterId: result?.clusterId
  });
});

clientClusterAssignmentQueue.on('stalled', (job) => {
  logger.warn('Job stalled (taking too long):', {
    jobId: job.id,
    clientId: job.data.clientId
  });
});

// Add job to queue
export async function addClientClusterAssignmentJob(
  data: ClientClusterAssignmentJobData,
  options?: {
    priority?: number;
    delay?: number;
  }
): Promise<Queue.Job<ClientClusterAssignmentJobData>> {
  logger.info('Adding client cluster assignment job to queue', {
    clientId: data.clientId,
    tenantId: data.tenantId
  });

  const job = await clientClusterAssignmentQueue.add(data, {
    priority: options?.priority || 10,
    delay: options?.delay || 0,
    jobId: `cluster-assign-${data.clientId}-${Date.now()}` // Unique job ID
  });

  return job;
}

// Get job status
export async function getJobStatus(jobId: string) {
  const job = await clientClusterAssignmentQueue.getJob(jobId);
  
  if (!job) {
    return null;
  }

  const state = await job.getState();
  const progress = job.progress();

  return {
    id: job.id,
    state,
    progress,
    data: job.data,
    result: await job.finished().catch(() => null),
    failedReason: job.failedReason,
    attemptsMade: job.attemptsMade,
    processedOn: job.processedOn,
    finishedOn: job.finishedOn,
    timestamp: job.timestamp
  };
}

// Get queue statistics
export async function getQueueStats() {
  const [
    waiting,
    active,
    completed,
    failed,
    delayed,
    paused
  ] = await Promise.all([
    clientClusterAssignmentQueue.getWaitingCount(),
    clientClusterAssignmentQueue.getActiveCount(),
    clientClusterAssignmentQueue.getCompletedCount(),
    clientClusterAssignmentQueue.getFailedCount(),
    clientClusterAssignmentQueue.getDelayedCount(),
    clientClusterAssignmentQueue.getPausedCount()
  ]);

  return {
    waiting,
    active,
    completed,
    failed,
    delayed,
    paused,
    total: waiting + active + completed + failed + delayed + paused
  };
}

// Clean old jobs
export async function cleanOldJobs() {
  const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
  
  await Promise.all([
    clientClusterAssignmentQueue.clean(oneDayAgo, 'completed'),
    clientClusterAssignmentQueue.clean(oneDayAgo, 'failed')
  ]);

  logger.info('Cleaned old jobs from queue');
}

logger.info('Client cluster assignment queue initialized');