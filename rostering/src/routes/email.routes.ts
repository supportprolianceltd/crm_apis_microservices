import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { EmailService } from '../services/email.service';
import { EmailWorker } from '../workers/email.worker';
import { authenticate, ensureTenantAccess } from '../middleware/auth.middleware';
import { logger, logServiceError } from '../utils/logger';

export function createEmailRoutes(
  prisma: PrismaClient,
  emailService: EmailService,
  emailWorker: EmailWorker
): Router {
  const router = Router();

  // Apply authentication to all routes
  router.use(authenticate);
  router.use(ensureTenantAccess);

  /**
   * Manually trigger email processing for current tenant
   */
  router.post('/process-emails', async (req, res) => {
    const startTime = Date.now();
    
    try {
      const tenantId = req.user!.tenantId.toString();
      const limit = parseInt(req.body.limit as string) || 1; // Default to 1 email
      
      logger.info(`Manual email processing triggered for tenant: ${tenantId} (limit: ${limit})`);
      
      // Add timeout to the entire email processing operation
      const processPromise = emailService.fetchNewEmails(tenantId, limit);
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('Email processing timeout after 2 minutes')), 120000);
      });

      // Fetch new emails with timeout
      const emails = await Promise.race([processPromise, timeoutPromise]);
      
      const fetchTime = Date.now() - startTime;
      logger.debug(`Email fetch completed in ${fetchTime}ms for tenant: ${tenantId}`);
      
      if (emails.length === 0) {
        return res.json({
          success: true,
          message: 'No new emails found',
          data: { emailCount: 0, requestsCreated: 0, processingTime: fetchTime }
        });
      }

      // Process each email
      const requestIds: string[] = [];
      const errors: string[] = [];
      
      for (const email of emails) {
        try {
          const requestId = await emailService.processEmailToRequest(tenantId, email);
          if (requestId) {
            requestIds.push(requestId);
          }
        } catch (emailError) {
          const errorMsg = `Failed to process email ${email.messageId}: ${emailError instanceof Error ? emailError.message : 'Unknown error'}`;
          errors.push(errorMsg);
          logServiceError('EmailRoutes', 'processEmail', emailError, { 
            tenantId, 
            messageId: email.messageId 
          });
        }
      }

      const totalTime = Date.now() - startTime;
      logger.info(`Email processing completed for tenant: ${tenantId} in ${totalTime}ms`);

      res.json({
        success: true,
        message: `Processed ${emails.length} emails in ${totalTime}ms`,
        data: {
          emailCount: emails.length,
          requestsCreated: requestIds.length,
          requestIds,
          processingTime: totalTime,
          errors: errors.length > 0 ? errors : undefined
        }
      });
      return;

    } catch (error) {
      const totalTime = Date.now() - startTime;
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      logger.error(`Email processing failed for tenant: ${req.user?.tenantId} after ${totalTime}ms: ${errorMessage}`);
      
      logServiceError('EmailRoutes', 'processEmails', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to process emails',
        message: errorMessage,
        processingTime: totalTime
      });
      return;
    }
  });

  /**
   * Get email processing status and recent logs
   */
  router.get('/processing-logs', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const limit = parseInt(req.query.limit as string) || 20;

      const logs = await prisma.emailProcessingLog.findMany({
        where: { tenantId },
        orderBy: { processedAt: 'desc' },
        take: limit,
        select: {
          id: true,
          messageId: true,
          subject: true,
          fromAddress: true,
          status: true,
          errorMessage: true,
          requestId: true,
          processedAt: true
        }
      });

      const summary = await prisma.emailProcessingLog.groupBy({
        by: ['status'],
        where: {
          tenantId,
          processedAt: {
            gte: new Date(Date.now() - 24 * 60 * 60 * 1000) // Last 24 hours
          }
        },
        _count: { status: true }
      });

      res.json({
        success: true,
        data: {
          recentLogs: logs,
          last24Hours: summary.reduce((acc, item) => {
            acc[item.status] = item._count.status;
            return acc;
          }, {} as Record<string, number>)
        }
      });
      return;

    } catch (error) {
      logServiceError('EmailRoutes', 'getProcessingLogs', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to get processing logs'
      });
      return;
    }
  });

  /**
   * Get email worker status
   */
  router.get('/worker-status', async (req, res) => {
    try {
      const status = emailWorker.getStatus();
      
      res.json({
        success: true,
        data: {
          ...status,
          pollingInterval: parseInt(process.env.EMAIL_POLLING_INTERVAL || '5', 10)
        }
      });
      return;

    } catch (error) {
      logServiceError('EmailRoutes', 'getWorkerStatus', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get worker status'
      });
      return;
    }
  });

  /**
   * Stop email worker
   */
  router.post('/worker/stop', async (req, res) => {
    try {
      emailWorker.stop();
      logger.info(`Email worker stopped by user: ${req.user!.email}`);
      
      res.json({
        success: true,
        message: 'Email worker stopped successfully',
        data: emailWorker.getStatus()
      });
      return;

    } catch (error) {
      logServiceError('EmailRoutes', 'stopWorker', error, { userId: req.user?.id });
      res.status(500).json({
        success: false,
        error: 'Failed to stop email worker',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
      return;
    }
  });

  /**
   * Start email worker
   */
  router.post('/worker/start', async (req, res) => {
    try {
      emailWorker.start();
      logger.info(`Email worker started by user: ${req.user!.email}`);
      
      res.json({
        success: true,
        message: 'Email worker started successfully',
        data: emailWorker.getStatus()
      });
      return;

    } catch (error) {
      logServiceError('EmailRoutes', 'startWorker', error, { userId: req.user?.id });
      res.status(500).json({
        success: false,
        error: 'Failed to start email worker',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
      return;
    }
  });

  /**
   * Manually trigger email processing cycle (for all tenants)
   */
  router.post('/worker/trigger', async (req, res) => {
    try {
      logger.info(`Manual email processing cycle triggered by user: ${req.user!.email}`);
      
      // Trigger the processing without waiting for it to complete
      emailWorker.triggerEmailProcessing().catch(error => {
        logServiceError('EmailWorker', 'manualTrigger', error);
      });
      
      res.json({
        success: true,
        message: 'Email processing cycle triggered (running in background)',
        data: emailWorker.getStatus()
      });
      return;

    } catch (error) {
      logServiceError('EmailRoutes', 'triggerWorker', error, { userId: req.user?.id });
      res.status(500).json({
        success: false,
        error: 'Failed to trigger email processing',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
      return;
    }
  });

  /**
   * Test email connection and fetch count
   */
  router.get('/connection-test', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      
      // Test connection
      const client = await emailService.connectToImap(tenantId);
      if (!client) {
        return res.status(400).json({
          success: false,
          error: 'Failed to connect to email server'
        });
      }

      // Get unread count
      await client.mailboxOpen('INBOX');
      const unreadCount = await client.status('INBOX', { unseen: true });
      
      res.json({
        success: true,
        message: 'Email connection successful',
        data: {
          connected: true,
          unreadEmails: unreadCount.unseen || 0
        }
      });
      return;

    } catch (error) {
      logServiceError('EmailRoutes', 'connectionTest', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Email connection test failed',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
      return;
    }
  });

  return router;
}



