import { Job } from 'bull';
import { PrismaClient } from '@prisma/client';
import { ClusterController } from '../controllers/cluster.controller';
import { AutoAssignJobData } from '../services/job-queue.service';
import { logger, logServiceError } from '../utils/logger';

export class AutoAssignWorker {
  private prisma: PrismaClient;
  private clusterController: ClusterController;
  private isRunning: boolean = false;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
    this.clusterController = new ClusterController(prisma);
  }

  /**
   * Start the auto-assign worker
   */
  start(): void {
    if (this.isRunning) {
      logger.warn('Auto-assign worker is already running');
      return;
    }

    this.isRunning = true;
    logger.info('Starting auto-assign worker...');

    // Import job queue service dynamically to avoid circular dependencies
    import('../services/job-queue.service').then(({ jobQueueService }) => {
      // Process client auto-assignment jobs
      jobQueueService.clientQueue.process('auto-assign', async (job: Job<AutoAssignJobData>) => {
        return await this.processClientAutoAssign(job);
      });

      // Process carer auto-assignment jobs
      jobQueueService.carerQueue.process('auto-assign', async (job: Job<AutoAssignJobData>) => {
        return await this.processCarerAutoAssign(job);
      });

      logger.info('Auto-assign worker started and processing jobs');
    }).catch(error => {
      logServiceError('AutoAssignWorker', 'start', error);
    });
  }

  /**
   * Stop the auto-assign worker
   */
  stop(): void {
    if (!this.isRunning) {
      logger.warn('Auto-assign worker is not running');
      return;
    }

    this.isRunning = false;
    logger.info('Auto-assign worker stopped');
  }

  /**
   * Process client auto-assignment job
   */
  private async processClientAutoAssign(job: Job<AutoAssignJobData>): Promise<any> {
    const { tenantId, userId, data } = job.data;

    try {
      logger.info(`Processing client auto-assign job ${job.id}`, {
        jobId: job.id,
        tenantId,
        userId,
        clientData: { name: data.name, postcode: data.postcode, address: data.address }
      });

      // Create a mock request object for the controller
      const mockReq = {
        user: { tenantId, id: userId },
        body: data,
        headers: {
          authorization: `Bearer mock-token-for-background-job-${job.id}`
        }
      } as any;

      // Create a mock response object that captures the result
      let capturedResult: any = null;
      const mockRes = {
        status: (code: number) => ({
          json: (data: any) => {
            logger.info(`Client auto-assign job ${job.id} completed with status ${code}`, { result: data });
            capturedResult = data;
            return data;
          }
        }),
        json: (data: any) => {
          logger.info(`Client auto-assign job ${job.id} completed`, { result: data });
          capturedResult = data;
          return data;
        }
      } as any;

      // Call the synchronous version of the controller method
      await (this.clusterController as any).autoAssignClientToClusterSync(mockReq, mockRes);

      logger.info(`Client auto-assign job ${job.id} completed successfully`, {
        jobId: job.id,
        tenantId,
        result: capturedResult?.action || 'unknown'
      });

      return capturedResult;

    } catch (error: any) {
      logger.error(`Client auto-assign job ${job.id} failed`, {
        jobId: job.id,
        tenantId,
        error: error.message,
        stack: error.stack
      });

      throw error; // Re-throw to let Bull handle retries
    }
  }

  /**
   * Process carer auto-assignment job
   */
  private async processCarerAutoAssign(job: Job<AutoAssignJobData>): Promise<any> {
    const { tenantId, userId, data } = job.data;

    try {
      logger.info(`Processing carer auto-assign job ${job.id}`, {
        jobId: job.id,
        tenantId,
        userId,
        carerData: { carerId: data.carerId, postcode: data.postcode, address: data.address }
      });

      // Create a mock request object for the controller
      const mockReq = {
        user: { tenantId, id: userId },
        body: data,
        headers: {
          authorization: `Bearer mock-token-for-background-job-${job.id}`
        }
      } as any;

      // Create a mock response object that captures the result
      let capturedResult: any = null;
      const mockRes = {
        status: (code: number) => ({
          json: (data: any) => {
            logger.info(`Carer auto-assign job ${job.id} completed with status ${code}`, { result: data });
            capturedResult = data;
            return data;
          }
        }),
        json: (data: any) => {
          logger.info(`Carer auto-assign job ${job.id} completed`, { result: data });
          capturedResult = data;
          return data;
        }
      } as any;

      // Call the synchronous version of the controller method
      await (this.clusterController as any).autoAssignCarerToClusterSync(mockReq, mockRes);

      logger.info(`Carer auto-assign job ${job.id} completed successfully`, {
        jobId: job.id,
        tenantId,
        result: capturedResult?.action || 'unknown'
      });

      return capturedResult;

    } catch (error: any) {
      logger.error(`Carer auto-assign job ${job.id} failed`, {
        jobId: job.id,
        tenantId,
        error: error.message,
        stack: error.stack
      });

      throw error; // Re-throw to let Bull handle retries
    }
  }

  /**
   * Get worker status
   */
  getStatus(): { isRunning: boolean } {
    return {
      isRunning: this.isRunning
    };
  }

  /**
   * Manual trigger for processing jobs (for testing/debugging)
   */
  async triggerJobProcessing(queueType: 'client' | 'carer', jobId?: string): Promise<void> {
    logger.info('Manually triggering auto-assign job processing...', { queueType, jobId });

    // Import job queue service dynamically
    const { jobQueueService } = await import('../services/job-queue.service');

    if (jobId) {
      // Process specific job
      const job = await (queueType === 'client' ? jobQueueService.clientQueue : jobQueueService.carerQueue).getJob(jobId);
      if (job) {
        await job.retry();
        logger.info(`Retried job ${jobId} in ${queueType} queue`);
      } else {
        logger.warn(`Job ${jobId} not found in ${queueType} queue`);
      }
    } else {
      // Process next waiting job
      const waitingJobs = await (queueType === 'client' ? jobQueueService.clientQueue : jobQueueService.carerQueue).getWaiting(0, 1);
      if (waitingJobs.length > 0) {
        await waitingJobs[0].retry();
        logger.info(`Retried next waiting job in ${queueType} queue`);
      } else {
        logger.info(`No waiting jobs in ${queueType} queue`);
      }
    }
  }
}

export default AutoAssignWorker;