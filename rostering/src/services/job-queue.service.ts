import Bull, { Job, JobId, JobOptions } from 'bull';
import IORedis from 'ioredis';
import { logger, logServiceError } from '../utils/logger';

export interface AutoAssignJobData {
  type: 'client' | 'carer';
  tenantId: string;
  userId: string;
  data: {
    // For clients
    name?: string;
    postcode: string;
    address: string;
    town?: string;
    city?: string;
    latitude?: number;
    longitude?: number;
    clientId?: string;

    // For carers
    carerId?: string;
  };
}

export interface JobResult {
  success: boolean;
  data?: any;
  error?: string;
  completedAt: Date;
}

export class JobQueueService {
  public clientQueue: Bull.Queue;
  public carerQueue: Bull.Queue;
  private redis: IORedis;

  constructor(redisUrl?: string) {
    // Initialize Redis connection
    this.redis = new IORedis(redisUrl || process.env.REDIS_URL || 'redis://localhost:6379');

    // Initialize job queues
    this.clientQueue = new Bull('client-auto-assign', {
      redis: redisUrl || process.env.REDIS_URL || 'redis://localhost:6379',
      defaultJobOptions: {
        removeOnComplete: 50, // Keep last 50 completed jobs
        removeOnFail: 20,     // Keep last 20 failed jobs
        attempts: 3,          // Retry failed jobs 3 times
        backoff: {
          type: 'exponential',
          delay: 5000,        // 5 seconds initial delay
        },
      },
    });

    this.carerQueue = new Bull('carer-auto-assign', {
      redis: redisUrl || process.env.REDIS_URL || 'redis://localhost:6379',
      defaultJobOptions: {
        removeOnComplete: 50,
        removeOnFail: 20,
        attempts: 3,
        backoff: {
          type: 'exponential',
          delay: 5000,
        },
      },
    });

    this.setupEventHandlers();
  }

  /**
   * Add client auto-assignment job to queue
   */
  async addClientAutoAssignJob(
    data: Omit<AutoAssignJobData, 'type'>,
    options?: JobOptions
  ): Promise<Job<AutoAssignJobData>> {
    const jobData: AutoAssignJobData = {
      type: 'client',
      ...data,
    };

    return await this.clientQueue.add('auto-assign', jobData, {
      priority: 5, // Medium priority
      delay: 1000, // 1 second delay to allow immediate response
      ...options,
    });
  }

  /**
   * Add carer auto-assignment job to queue
   */
  async addCarerAutoAssignJob(
    data: Omit<AutoAssignJobData, 'type'>,
    options?: JobOptions
  ): Promise<Job<AutoAssignJobData>> {
    const jobData: AutoAssignJobData = {
      type: 'carer',
      ...data,
    };

    return await this.carerQueue.add('auto-assign', jobData, {
      priority: 5, // Medium priority
      delay: 1000, // 1 second delay to allow immediate response
      ...options,
    });
  }

  /**
   * Get job status by ID and queue type
   */
  async getJobStatus(queueType: 'client' | 'carer', jobId: JobId): Promise<any> {
    const queue = queueType === 'client' ? this.clientQueue : this.carerQueue;
    const job = await queue.getJob(jobId);

    if (!job) {
      return { status: 'not_found' };
    }

    const state = await job.getState();
    const result = job.returnvalue;
    const error = job.failedReason;

    return {
      id: job.id,
      status: state,
      progress: job.progress(),
      data: job.data,
      result,
      error,
      createdAt: job.timestamp,
      processedAt: job.processedOn,
      finishedAt: job.finishedOn,
      attemptsMade: job.attemptsMade,
      attemptsRemaining: (job.opts.attempts || 3) - job.attemptsMade,
    };
  }

  /**
   * Get all jobs for a specific queue
   */
  async getJobs(queueType: 'client' | 'carer', status?: string, limit = 10): Promise<any[]> {
    const queue = queueType === 'client' ? this.clientQueue : this.carerQueue;

    let jobs: Job[];
    switch (status) {
      case 'active':
        jobs = await queue.getActive(0, limit);
        break;
      case 'waiting':
        jobs = await queue.getWaiting(0, limit);
        break;
      case 'completed':
        jobs = await queue.getCompleted(0, limit);
        break;
      case 'failed':
        jobs = await queue.getFailed(0, limit);
        break;
      default:
        jobs = await queue.getJobs(['active', 'waiting', 'completed', 'failed'], 0, limit);
    }

    return jobs.map(job => ({
      id: job.id,
      status: job.finishedOn ? 'completed' : job.failedReason ? 'failed' : 'active',
      data: job.data,
      result: job.returnvalue,
      error: job.failedReason,
      createdAt: job.timestamp,
      finishedAt: job.finishedOn,
    }));
  }

  /**
   * Cancel a job
   */
  async cancelJob(queueType: 'client' | 'carer', jobId: JobId): Promise<boolean> {
    const queue = queueType === 'client' ? this.clientQueue : this.carerQueue;
    const job = await queue.getJob(jobId);

    if (job) {
      await job.remove();
      return true;
    }

    return false;
  }

  /**
   * Setup event handlers for logging
   */
  private setupEventHandlers(): void {
    // Client queue events
    this.clientQueue.on('completed', (job, result) => {
      logger.info(`Client auto-assign job ${job.id} completed`, {
        jobId: job.id,
        tenantId: job.data.tenantId,
        result: result?.action,
      });
    });

    this.clientQueue.on('failed', (job, err) => {
      logger.error(`Client auto-assign job ${job.id} failed`, {
        jobId: job.id,
        tenantId: job.data.tenantId,
        error: err.message,
        attempts: job.attemptsMade,
      });
    });

    // Carer queue events
    this.carerQueue.on('completed', (job, result) => {
      logger.info(`Carer auto-assign job ${job.id} completed`, {
        jobId: job.id,
        tenantId: job.data.tenantId,
        result: result?.action,
      });
    });

    this.carerQueue.on('failed', (job, err) => {
      logger.error(`Carer auto-assign job ${job.id} failed`, {
        jobId: job.id,
        tenantId: job.data.tenantId,
        error: err.message,
        attempts: job.attemptsMade,
      });
    });
  }

  /**
   * Gracefully close queues and Redis connection
   */
  async close(): Promise<void> {
    await this.clientQueue.close();
    await this.carerQueue.close();
    await this.redis.quit();
    logger.info('Job queue service closed');
  }

  /**
   * Get queue statistics
   */
  async getStats(): Promise<any> {
    const [clientStats, carerStats] = await Promise.all([
      this.clientQueue.getJobCounts(),
      this.carerQueue.getJobCounts(),
    ]);

    return {
      clientQueue: clientStats,
      carerQueue: carerStats,
      redis: {
        status: this.redis.status,
        connected: this.redis.status === 'ready',
      },
    };
  }
}

// Export singleton instance
export const jobQueueService = new JobQueueService();