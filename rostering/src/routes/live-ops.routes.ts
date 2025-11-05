import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { LiveOperationsService } from '../services/live-operations.service';
import { logger } from '../utils/logger';

export function createLiveOpsRoutes(
  prisma: PrismaClient,
  liveOpsService: LiveOperationsService
): Router {
  const router = Router();

  /**
   * Update carer location
   * POST /api/rostering/live/location/:carerId
   */
  router.post('/location/:carerId', async (req, res) => {
    try {
      const { carerId } = req.params;
      const { latitude, longitude, accuracy } = req.body;

      if (!latitude || !longitude) {
        return res.status(400).json({
          success: false,
          error: 'latitude and longitude are required'
        });
      }

      const location = await liveOpsService.updateCarerLocation(carerId, {
        latitude,
        longitude,
        accuracy: accuracy || 10
      });

      res.json({ success: true, data: location });
      return;
    } catch (error: any) {
      logger.error('Failed to update location:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Check-in to visit
   * POST /api/rostering/live/visits/:visitId/check-in
   */
  router.post('/visits/:visitId/check-in', async (req, res) => {
    try {
      const { visitId } = req.params;
      const { carerId, latitude, longitude, notes } = req.body;

      if (!carerId || !latitude || !longitude) {
        return res.status(400).json({
          success: false,
          error: 'carerId, latitude, and longitude are required'
        });
      }

      const checkIn = await liveOpsService.checkIn(
        visitId,
        carerId,
        { latitude, longitude },
        notes
      );

      res.json({ success: true, data: checkIn });
      return;
    } catch (error: any) {
      logger.error('Failed to check in:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Check-out from visit
   * POST /api/rostering/live/visits/:visitId/check-out
   */
  router.post('/visits/:visitId/check-out', async (req, res) => {
    try {
      const { visitId } = req.params;
      const { carerId, latitude, longitude, ...data } = req.body;

      if (!carerId || !latitude || !longitude) {
        return res.status(400).json({
          success: false,
          error: 'carerId, latitude, and longitude are required'
        });
      }

      const checkOut = await liveOpsService.checkOut(
        visitId,
        carerId,
        { latitude, longitude },
        data
      );

      res.json({ success: true, data: checkOut });
      return;
    } catch (error: any) {
      logger.error('Failed to check out:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Get lateness predictions for carer
   * GET /api/rostering/live/carers/:carerId/lateness-predictions
   */
  router.get('/carers/:carerId/lateness-predictions', async (req, res) => {
    try {
      const { carerId } = req.params;
      const alerts = await liveOpsService.predictLateness(carerId);
      res.json({ success: true, data: alerts });
      return;
    } catch (error: any) {
      logger.error('Failed to get lateness predictions:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Get swap suggestions for delayed visit
   * POST /api/rostering/live/visits/:visitId/suggest-swaps
   */
  router.post('/visits/:visitId/suggest-swaps', async (req, res) => {
    try {
      const { visitId } = req.params;
      const { delayMinutes } = req.body;

      if (!delayMinutes) {
        return res.status(400).json({
          success: false,
          error: 'delayMinutes is required'
        });
      }

      const suggestions = await liveOpsService.suggestSwaps(visitId, delayMinutes);
      res.json({ success: true, data: suggestions });
      return;
    } catch (error: any) {
      logger.error('Failed to suggest swaps:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Get live operations dashboard data
   * GET /api/rostering/live/dashboard
   */
  router.get('/dashboard', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const data = await liveOpsService.getDashboardData(tenantId);
      res.json({ success: true, data });
      return;
    } catch (error: any) {
      logger.error('Failed to get dashboard data:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Get today's schedule for a carer
   * GET /api/rostering/live/carers/:carerId/schedule
   */
  router.get('/carers/:carerId/schedule', async (req, res) => {
    try {
      const { carerId } = req.params;
      const tenantId = req.user!.tenantId.toString();

      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const tomorrow = new Date(today);
      tomorrow.setDate(tomorrow.getDate() + 1);

      const visits = await prisma.externalRequest.findMany({
        where: {
          tenantId,
          scheduledStartTime: {
            gte: today,
            lt: tomorrow
          },
          matches: {
            some: {
              carerId,
              status: 'ACCEPTED'
            }
          }
        },
        orderBy: { scheduledStartTime: 'asc' }
      });

      res.json({ success: true, data: visits });
      return;
    } catch (error: any) {
      logger.error('Failed to get carer schedule:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  return router;
}

