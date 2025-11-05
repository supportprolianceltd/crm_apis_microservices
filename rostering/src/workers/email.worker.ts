import * as cron from 'node-cron';
import { PrismaClient } from '@prisma/client';
import { EmailService } from '../services/email.service';
import { MatchingService } from '../services/matching.service';
import { GeocodingService } from '../services/geocoding.service';
import { TenantEmailConfigService } from '../services/tenant-email-config.service';
import { NotificationService } from '../services/notification.service';
import { logger, logServiceError } from '../utils/logger';

export class EmailWorker {
  private prisma: PrismaClient;
  private emailService: EmailService;
  private matchingService: MatchingService;
  private tenantEmailConfigService: TenantEmailConfigService;
  private notificationService: NotificationService;
  private isRunning: boolean = false;
  private cronJobs: cron.ScheduledTask[] = [];

  constructor(
    prisma: PrismaClient,
    emailService: EmailService,
    matchingService: MatchingService,
    tenantEmailConfigService: TenantEmailConfigService,
    notificationService: NotificationService
  ) {
    this.prisma = prisma;
    this.emailService = emailService;
    this.matchingService = matchingService;
    this.tenantEmailConfigService = tenantEmailConfigService;
    this.notificationService = notificationService;
  }

  /**
   * Start the email worker with scheduled tasks
   */
  start(): void {
    if (this.isRunning) {
      logger.warn('Email worker is already running');
      return;
    }

    this.isRunning = true;
    logger.info('Starting email worker...');

    // Schedule email polling based on environment variable
    const pollingInterval = parseInt(process.env.EMAIL_POLLING_INTERVAL || '5', 10);
    const cronExpression = `*/${pollingInterval} * * * *`; // Every X minutes

    // Schedule email processing
    const emailCronJob = cron.schedule(cronExpression, async () => {
      await this.processEmails();
    });

    // Schedule cleanup tasks (daily at 2 AM)
    const cleanupCronJob = cron.schedule('0 2 * * *', async () => {
      await this.cleanupOldLogs();
    });

    // Schedule geocoding cache cleanup (weekly on Sunday at 3 AM)
    const geocodingCleanupJob = cron.schedule('0 3 * * 0', async () => {
      await this.cleanupGeocodingCache();
    });

    this.cronJobs = [emailCronJob, cleanupCronJob, geocodingCleanupJob];

    // Start all cron jobs
    this.cronJobs.forEach(job => job.start());

    logger.info(`Email worker started with ${pollingInterval} minute polling interval`);
  }

  /**
   * Stop the email worker
   */
  stop(): void {
    if (!this.isRunning) {
      logger.warn('Email worker is not running');
      return;
    }

    this.isRunning = false;

    // Stop all cron jobs
    this.cronJobs.forEach(job => job.stop());
    this.cronJobs = [];

    logger.info('Email worker stopped');
  }

  /**
   * Process emails for all tenants
   */
  private async processEmails(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    try {
      logger.debug('Starting email processing cycle...');

      // Get all tenants that need email checking
      const tenantIds = await this.getConfiguredTenants();

      if (tenantIds.length === 0) {
        logger.debug('No tenants need email processing at this time');
        return;
      }

      // Process emails for each tenant
      const results = await Promise.allSettled(
        tenantIds.map(tenantId => this.processTenantEmails(tenantId))
      );

      // Log results
      let successCount = 0;
      let errorCount = 0;

      results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          successCount++;
        } else {
          errorCount++;
          logServiceError('EmailWorker', 'processTenantEmails', result.reason, { 
            tenantId: tenantIds[index] 
          });
        }
      });

      logger.info(`Email processing cycle completed: ${successCount} tenants processed, ${errorCount} errors`);

    } catch (error) {
      logServiceError('EmailWorker', 'processEmails', error);
    }
  }

  /**
   * Process emails for a specific tenant
   */
  private async processTenantEmails(tenantId: string): Promise<void> {
    try {
      logger.debug(`Processing emails for tenant: ${tenantId}`);

      // Fetch new emails (limit to 5 per polling cycle for performance)
      const emails = await this.emailService.fetchNewEmails(tenantId, 5);

      if (emails.length === 0) {
        logger.debug(`No new emails found for tenant: ${tenantId}`);
        return;
      }

      logger.info(`Found ${emails.length} new emails for tenant: ${tenantId}`);

      // Process each email
      const requestIds: string[] = [];
      
      for (const email of emails) {
        try {
          const requestId = await this.emailService.processEmailToRequest(tenantId, email);
          if (requestId) {
            requestIds.push(requestId);
          }
        } catch (emailError) {
          logServiceError('EmailWorker', 'processEmailToRequest', emailError, { 
            tenantId, 
            messageId: email.messageId 
          });
        }
      }

      // Auto-match all created requests
      if (requestIds.length > 0) {
        logger.info(`Created ${requestIds.length} requests from emails for tenant: ${tenantId}, starting auto-matching...`);
        
        const matchingPromises = requestIds.map(requestId => 
          this.matchingService.autoMatchRequest(requestId).catch(error =>
            logServiceError('EmailWorker', 'autoMatchRequest', error, { requestId })
          )
        );

        await Promise.allSettled(matchingPromises);
      }

    } catch (error) {
      logServiceError('EmailWorker', 'processTenantEmails', error, { tenantId });
      throw error; // Re-throw to be caught by the caller
    }
  }

  /**
   * Get tenant IDs that have active email configuration and need checking
   */
  private async getConfiguredTenants(): Promise<string[]> {
    try {
      return await this.emailService.getActiveEmailTenants();
    } catch (error) {
      logServiceError('EmailWorker', 'getConfiguredTenants', error);
      return [];
    }
  }

  /**
   * Clean up old email processing logs
   */
  private async cleanupOldLogs(): Promise<void> {
    try {
      logger.info('Starting cleanup of old email processing logs...');

      // Delete logs older than 30 days
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

      const deleteResult = await this.prisma.emailProcessingLog.deleteMany({
        where: {
          processedAt: {
            lt: thirtyDaysAgo
          }
        }
      });

      logger.info(`Cleaned up ${deleteResult.count} old email processing logs`);

    } catch (error) {
      logServiceError('EmailWorker', 'cleanupOldLogs', error);
    }
  }

  /**
   * Clean up old geocoding cache entries
   */
  private async cleanupGeocodingCache(): Promise<void> {
    try {
      logger.info('Starting cleanup of old geocoding cache...');

      // Delete cache entries older than 90 days
      const ninetyDaysAgo = new Date();
      ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);

      const deleteResult = await this.prisma.geocodingCache.deleteMany({
        where: {
          updatedAt: {
            lt: ninetyDaysAgo
          }
        }
      });

      logger.info(`Cleaned up ${deleteResult.count} old geocoding cache entries`);

    } catch (error) {
      logServiceError('EmailWorker', 'cleanupGeocodingCache', error);
    }
  }

  /**
   * Manual trigger for email processing (for testing/debugging)
   */
  async triggerEmailProcessing(): Promise<void> {
    logger.info('Manually triggering email processing...');
    await this.processEmails();
  }

  /**
   * Get worker status
   */
  getStatus(): { isRunning: boolean; activeCronJobs: number } {
    return {
      isRunning: this.isRunning,
      activeCronJobs: this.cronJobs.length
    };
  }

  /**
   * Process a single email manually (for testing)
   */
  async processEmailManually(tenantId: string, messageId: string): Promise<string | null> {
    try {
      // This would require implementing a way to fetch a specific email by messageId
      // For now, this is a placeholder for manual email processing
      logger.info(`Manual email processing requested for tenant: ${tenantId}, messageId: ${messageId}`);
      
      // In a real implementation, you would:
      // 1. Connect to IMAP
      // 2. Search for the specific message
      // 3. Parse and process it
      
      return null;
    } catch (error) {
      logServiceError('EmailWorker', 'processEmailManually', error, { tenantId, messageId });
      return null;
    }
  }
}

export default EmailWorker;