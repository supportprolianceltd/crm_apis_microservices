import { Router } from 'express';
import { authenticate, ensureTenantAccess } from '../middleware/auth.middleware';

export function createHealthRoutes(): Router {
  const router = Router();

  // Public health check
  router.get('/health', (req, res) => {
    res.json({
      success: true,
      service: 'rostering-service',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
      status: 'healthy'
    });
  });

  // Protected status check
  router.get('/status', authenticate, ensureTenantAccess, (req, res) => {
    res.json({
      success: true,
      service: 'rostering-service',
      tenant: req.user?.tenantId,
      user: req.user?.email,
      timestamp: new Date().toISOString(),
      status: 'authenticated'
    });
  });

  return router;
}