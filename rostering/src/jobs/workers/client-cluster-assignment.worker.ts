import { clientClusterAssignmentQueue } from '../queues/client-cluster-assignment.queue';
import processClientClusterAssignment from '../processors/client-cluster-assignment.processor';
import { logger } from '../../utils/logger';

export class ClientClusterAssignmentWorker {
  private isRunning = false;

  /**
   * Start the worker to process jobs
   */
  start(): void {
    if (this.isRunning) {
      logger.warn('Client cluster assignment worker already running');
      return;
    }

    logger.info('Starting client cluster assignment worker...');

    // Process jobs with concurrency of 5 (can handle 5 jobs simultaneously)
    clientClusterAssignmentQueue.process(5, async (job) => {
      logger.debug('Worker picked up job', {
        jobId: job.id,
        clientId: job.data.clientId
      });

      return await processClientClusterAssignment(job);
    });

    this.isRunning = true;
    logger.info('✅ Client cluster assignment worker started (concurrency: 5)');

    // Setup periodic queue stats logging
    this.startStatsLogging();

    // Setup periodic cleanup
    this.startPeriodicCleanup();
  }

  /**
   * Stop the worker gracefully
   */
  async stop(): Promise<void> {
    if (!this.isRunning) {
      logger.warn('Client cluster assignment worker not running');
      return;
    }

    logger.info('Stopping client cluster assignment worker...');

    await clientClusterAssignmentQueue.close();

    this.isRunning = false;
    logger.info('✅ Client cluster assignment worker stopped');
  }

  /**
   * Get worker status
   */
  getStatus() {
    return {
      isRunning: this.isRunning,
      queueName: 'client-cluster-assignment'
    };
  }

  /**
   * Log queue statistics periodically
   */
  private startStatsLogging(): void {
    setInterval(async () => {
      try {
        const [
          waiting,
          active,
          completed,
          failed
        ] = await Promise.all([
          clientClusterAssignmentQueue.getWaitingCount(),
          clientClusterAssignmentQueue.getActiveCount(),
          clientClusterAssignmentQueue.getCompletedCount(),
          clientClusterAssignmentQueue.getFailedCount()
        ]);

        if (waiting > 0 || active > 0) {
          logger.debug('Queue stats', {
            waiting,
            active,
            completed,
            failed
          });
        }
      } catch (error) {
        logger.error('Failed to get queue stats:', error);
      }
    }, 30000); // Every 30 seconds
  }

  /**
   * Cleanup old jobs periodically
   */
  private startPeriodicCleanup(): void {
    setInterval(async () => {
      try {
        const gracePeriod = 24 * 60 * 60 * 1000; // 24 hours
        
        await Promise.all([
          clientClusterAssignmentQueue.clean(gracePeriod, 'completed'),
          clientClusterAssignmentQueue.clean(gracePeriod * 7, 'failed') // Keep failed jobs for 7 days
        ]);

        logger.debug('Cleaned old jobs from queue');
      } catch (error) {
        logger.error('Failed to clean queue:', error);
      }
    }, 60 * 60 * 1000); // Every hour
  }
}

// Singleton instance
export const clientClusterWorker = new ClientClusterAssignmentWorker();