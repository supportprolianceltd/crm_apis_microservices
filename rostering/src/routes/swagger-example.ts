import { Router } from 'express';
import { PrismaClient } from '@prisma/client';

const router = Router();

/**
 * @swagger
 * components:
 *   schemas:
 *     HealthResponse:
 *       type: object
 *       properties:
 *         status:
 *           type: string
 *         timestamp:
 *           type: string
 *           format: date-time
 *         service:
 *           type: string
 */

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
 *       500:
 *         description: Service is unhealthy
 */
router.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'rostering'
  });
});

/**
 * @swagger
 * /api/rostering/example:
 *   get:
 *     summary: Example endpoint
 *     description: This is an example endpoint for Swagger testing
 *     tags: [Examples]
 *     responses:
 *       200:
 *         description: Successful response
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 message:
 *                   type: string
 *                 timestamp:
 *                   type: string
 *                   format: date-time
 */
router.get('/example', (req, res) => {
  res.json({
    message: 'This is an example endpoint for Swagger',
    timestamp: new Date().toISOString()
  });
});

export function createExampleRoutes(prisma: PrismaClient): Router {
  return router;
}


