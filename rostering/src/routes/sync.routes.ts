import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { AuthSyncService } from '../services/auth-sync.service';
import { TenantEmailConfigService } from '../services/tenant-email-config.service';
import { NotificationService } from '../services/notification.service';
import { authenticate, ensureTenantAccess } from '../middleware/auth.middleware';
import { logger, logServiceError } from '../utils/logger';
import { z } from 'zod';

// Validation schemas
const emailConfigSchema = z.object({
  imapHost: z.string().min(1, 'IMAP host is required'),
  imapPort: z.number().int().min(1).max(65535).default(993),
  imapUser: z.string().email('Valid email is required'),
  imapPassword: z.string().min(1, 'IMAP password is required'),
  imapTls: z.boolean().default(true),
  pollInterval: z.number().int().min(60).default(300),
  isActive: z.boolean().default(true)
});

export function createSyncRoutes(
  prisma: PrismaClient,
  authSyncService: AuthSyncService,
  tenantEmailConfigService: TenantEmailConfigService,
  notificationService: NotificationService
): Router {
  const router = Router();

  // Apply authentication to all routes
  router.use(authenticate);
  router.use(ensureTenantAccess);

  /**
   * Manually trigger carer sync from auth service
   */
  router.post('/sync-carers', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const authToken = req.headers.authorization?.replace('Bearer ', '');

      if (!authToken) {
        return res.status(400).json({ 
          success: false,
          error: 'Auth token required' 
        });
      }

      const syncedCount = await authSyncService.syncCarersFromAuthService(tenantId, authToken);
      
      res.json({
        success: true,
        message: 'Carers synced successfully',
        data: { syncedCount }
      });
      return;

    } catch (error) {
      logServiceError('Sync', 'syncCarers', error, { tenantId: req.user?.tenantId });
      res.status(500).json({ 
        success: false,
        error: 'Failed to sync carers',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
      return;
    }
  });

  /**
   * Get carer sync status
   */
  router.get('/sync-status', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const authToken = req.headers.authorization?.replace('Bearer ', '');

      if (!authToken) {
        return res.status(400).json({ 
          success: false,
          error: 'Auth token required' 
        });
      }

      const status = await authSyncService.getCarerSyncStatus(tenantId, authToken);
      
      res.json({
        success: true,
        data: status
      });
      return;

    } catch (error) {
      logServiceError('Sync', 'getSyncStatus', error, { tenantId: req.user?.tenantId });
      res.status(500).json({ 
        success: false,
        error: 'Failed to get sync status'
      });
      return;
    }
  });

  /**
   * Sync a single carer from auth service
   */
  router.post('/sync-carer/:carerId', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const carerId = req.params.carerId;
      const authToken = req.headers.authorization?.replace('Bearer ', '');

      if (!authToken) {
        return res.status(400).json({ 
          success: false,
          error: 'Auth token required' 
        });
      }

      await authSyncService.syncSingleCarer(carerId, tenantId, authToken);
      
      res.json({
        success: true,
        message: 'Carer synced successfully'
      });
      return;

    } catch (error) {
      logServiceError('Sync', 'syncSingleCarer', error, { 
        tenantId: req.user?.tenantId,
        carerId: req.params.carerId 
      });
      res.status(500).json({ 
        success: false,
        error: 'Failed to sync carer'
      });
      return;
    }
  });

  /**
   * Create or update tenant email configuration
   */
  router.put('/email-config', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      
      // Validate request body
      const validatedData = emailConfigSchema.parse(req.body);

      const config = await tenantEmailConfigService.upsertTenantEmailConfig(
        tenantId,
        validatedData
      );

      res.json({
        success: true,
        data: config,
        message: 'Email configuration updated successfully'
      });
      return;

    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({
          success: false,
          error: 'Validation error',
          details: error.errors
        });
      }

      logServiceError('Sync', 'updateEmailConfig', error, { tenantId: req.user?.tenantId });
      res.status(500).json({ 
        success: false,
        error: 'Failed to update email configuration'
      });
      return;
    }
  });

  /**
   * Get tenant email configuration
   */
  router.get('/email-config', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      
      const config = await tenantEmailConfigService.getTenantEmailConfig(tenantId);

      if (!config) {
        return res.status(404).json({
          success: false,
          error: 'Email configuration not found'
        });
      }

      res.json({
        success: true,
        data: config
      });
      return;

    } catch (error) {
      logServiceError('Sync', 'getEmailConfig', error, { tenantId: req.user?.tenantId });
      res.status(500).json({ 
        success: false,
        error: 'Failed to get email configuration'
      });
      return;
    }
  });

  /**
   * Test email connection
   */
  router.post('/test-email', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      
      const result = await tenantEmailConfigService.testEmailConnection(tenantId);

      if (result.success) {
        res.json({
          success: true,
          message: 'Email connection test successful'
        });
      } else {
        res.status(400).json({
          success: false,
          error: 'Email connection failed',
          message: result.error
        });
      }

    } catch (error) {
      logServiceError('Sync', 'testEmail', error, { tenantId: req.user?.tenantId });
      res.status(500).json({ 
        success: false,
        error: 'Failed to test email connection'
      });
    }
  });

  /**
   * Delete tenant email configuration
   */
  router.delete('/email-config', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      
      await tenantEmailConfigService.deleteTenantEmailConfig(tenantId);

      res.json({
        success: true,
        message: 'Email configuration deleted successfully'
      });

    } catch (error) {
      logServiceError('Sync', 'deleteEmailConfig', error, { tenantId: req.user?.tenantId });
      res.status(500).json({ 
        success: false,
        error: 'Failed to delete email configuration'
      });
    }
  });

  /**
   * Send test notification
   */
  router.post('/test-notification', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const { email } = req.body;

      if (!email) {
        return res.status(400).json({
          success: false,
          error: 'Email address is required'
        });
      }

      await notificationService.sendTestNotification(email, tenantId);

      res.json({
        success: true,
        message: 'Test notification sent successfully'
      });
      return;

    } catch (error) {
      logServiceError('Sync', 'testNotification', error, { tenantId: req.user?.tenantId });
      res.status(500).json({ 
        success: false,
        error: 'Failed to send test notification'
      });
      return;
    }
  });

  return router;
}