import { Router } from 'express';
import { authenticate, ensureTenantAccess } from '../middleware/auth.middleware';

/**
 * @swagger
 * components:
 *   schemas:
 *     HealthResponse:
 *       type: object
 *       properties:
 *         success:
 *           type: boolean
 *         service:
 *           type: string
 *         version:
 *           type: string
 *         timestamp:
 *           type: string
 *           format: date-time
 *         status:
 *           type: string
 *     StatusResponse:
 *       type: object
 *       properties:
 *         success:
 *           type: boolean
 *         service:
 *           type: string
 *         tenant:
 *           type: string
 *         user:
 *           type: string
 *         timestamp:
 *           type: string
 *           format: date-time
 *         status:
 *           type: string
 */

export function createHealthRoutes(): Router {
  const router = Router();

  /**
   * @swagger
   * /api/rostering/health:
   *   get:
   *     summary: Get service health status
   *     description: Returns the health status of the rostering service
   *     tags: [Health]
   *     responses:
   *       200:
   *         description: Service is healthy
   *         content:
   *           application/json:
   *             schema:
   *               $ref: '#/components/schemas/HealthResponse'
   */
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

  /**
   * @swagger
   * /api/rostering/status:
   *   get:
   *     summary: Get authenticated service status
   *     description: Returns the authenticated status of the rostering service
   *     tags: [Health]
   *     security:
   *       - BearerAuth: []
   *     responses:
   *       200:
   *         description: Service is authenticated
   *         content:
   *           application/json:
   *             schema:
   *               $ref: '#/components/schemas/StatusResponse'
   *       401:
   *         description: Unauthorized
   */
  // Protected status check
  router.get('/status', authenticate, ensureTenantAccess, (req, res) => {
    const user = (req as any).user;
    res.json({
      success: true,
      service: 'rostering-service',
      tenant: user?.tenantId,
      user: user?.email,
      timestamp: new Date().toISOString(),
      status: 'authenticated'
    });
  });

  return router;
}


