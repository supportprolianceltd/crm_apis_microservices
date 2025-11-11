import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { EnhancedTravelMatrixController } from '../controllers/enhanced-travel-matrix.controller';
import { authenticate } from '../middleware/auth.middleware';

export function createEnhancedTravelMatrixRoutes(prisma: PrismaClient): Router {
  const router = Router();
  const controller = new EnhancedTravelMatrixController(prisma);

  /**
   * @swagger
   * /api/rostering/travel-matrix/calculate:
   *   post:
   *     summary: Calculate travel time and distance between locations
   *     tags: [Travel Matrix]
   *     security:
   *       - BearerAuth: []
   *     requestBody:
   *       required: true
   *       content:
   *         application/json:
   *           schema:
   *             type: object
   *             required:
   *               - from
   *               - to
   *             properties:
   *               from:
   *                 type: object
   *                 properties:
   *                   address:
   *                     type: string
   *                     example: "#1 Enugu Street, Town Portharcourt Rivers state"
   *                   postcode:
   *                     type: string
   *                     example: "PH001"
   *                   latitude:
   *                     type: number
   *                     example: 4.8156
   *                   longitude:
   *                     type: number
   *                     example: 7.0498
   *               to:
   *                 type: object
   *                 properties:
   *                   address:
   *                     type: string
   *                     example: "#10 Station Road, Port Harcourt, Rivers State"
   *                   postcode:
   *                     type: string
   *                     example: "PH002"
   *                   latitude:
   *                     type: number
*                     example: 4.8242
   *                   longitude:
   *                     type: number
   *                     example: 7.0333
   *               mode:
   *                 type: string
   *                 enum: [driving, walking, transit, bicycling]
   *                 default: driving
   *               forceRefresh:
   *                 type: boolean
   *                 default: false
   *                 description: Bypass cache and force fresh calculation
   *     responses:
   *       200:
   *         description: Travel calculation successful
   *         content:
   *           application/json:
   *             schema:
   *               type: object
   *               properties:
   *                 success:
   *                   type: boolean
   *                   example: true
   *                 data:
   *                   type: object
   *                   properties:
   *                     distance:
   *                       type: object
   *                       properties:
   *                         meters:
   *                           type: number
   *                         kilometers:
   *                           type: number
   *                         text:
   *                           type: string
   *                     duration:
   *                       type: object
   *                       properties:
   *                         seconds:
   *                           type: number
   *                         minutes:
   *                           type: number
   *                         text:
   *                           type: string
   *                     from:
   *                       type: object
   *                     to:
   *                       type: object
   *                     mode:
   *                       type: string
   *                     precisionLevel:
   *                       type: string
   *                       enum: [COORDINATES, ADDRESS, POSTCODE]
   *                     cached:
   *                       type: boolean
   *                     warnings:
   *                       type: array
   *       400:
   *         description: Invalid request
   *       502:
   *         description: Google Maps API error
   */
  router.post('/calculate', authenticate, controller.calculateTravel);

  /**
   * @swagger
   * /api/rostering/travel-matrix/cache/stats:
   *   get:
   *     summary: Get cache statistics
   *     tags: [Travel Matrix]
   *     security:
   *       - BearerAuth: []
   *     responses:
   *       200:
   *         description: Cache statistics retrieved
   */
  router.get('/cache/stats', authenticate, controller.getCacheStats);

  /**
   * @swagger
   * /api/rostering/travel-matrix/cache/cleanup:
   *   delete:
   *     summary: Clean up expired cache entries
   *     tags: [Travel Matrix]
   *     security:
   *       - BearerAuth: []
   *     responses:
   *       200:
   *         description: Cache cleaned up successfully
   */
  router.delete('/cache/cleanup', authenticate, controller.cleanupCache);

  return router;
}