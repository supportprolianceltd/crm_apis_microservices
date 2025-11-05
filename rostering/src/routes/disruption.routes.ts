import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { DisruptionService } from '../services/disruption.service';
import { logger } from '../utils/logger';

export function createDisruptionRoutes(
  prisma: PrismaClient,
  disruptionService: DisruptionService
): Router {
  const router = Router();

  /**
   * Report a new disruption
   * POST /api/rostering/disruptions
   */
  router.post('/', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const userId =req.user!.id;

      const {
        type,
        description,
        affectedVisits,
        affectedCarers,
        severity
      } = req.body;

      if (!type || !description) {
        return res.status(400).json({
          success: false,
          error: 'type and description are required'
        });
      }

      const disruption = await disruptionService.reportDisruption(tenantId, {
        type,
        description,
        reportedBy: userId,
        affectedVisits: affectedVisits || [],
        affectedCarers: affectedCarers || [],
        severity
      });

      res.status(201).json({ success: true, data: disruption });
      return;
    } catch (error: any) {
      logger.error('Failed to report disruption:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Get all active disruptions
   * GET /api/rostering/disruptions/active
   */
  router.get('/active', async (req, res) => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const disruptions = await disruptionService.getActiveDisruptions(tenantId);
      res.json({ success: true, data: disruptions });
      return;
    } catch (error: any) {
      logger.error('Failed to get active disruptions:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Get disruption by ID
   * GET /api/rostering/disruptions/:id
   */
  router.get('/:id', async (req, res) => {
    try {
      const { id } = req.params;
      const disruption = await disruptionService.getDisruption(id);

      if (!disruption) {
        return res.status(404).json({
          success: false,
          error: 'Disruption not found'
        });
      }

      res.json({ success: true, data: disruption });
      return;
    } catch (error: any) {
      logger.error('Failed to get disruption:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Apply a resolution to a disruption
   * POST /api/rostering/disruptions/:id/resolve
   */
  router.post('/:id/resolve', async (req, res) => {
    try {
      const { id } = req.params;
      const { resolutionId } = req.body;
      const userId =req.user!.id;

      if (!resolutionId) {
        return res.status(400).json({
          success: false,
          error: 'resolutionId is required'
        });
      }

      const disruption = await disruptionService.applyResolution(
        id,
        resolutionId,
        userId
      );

      res.json({
        success: true,
        data: disruption,
        message: 'Resolution applied successfully'
      });
      return;
    } catch (error: any) {
      logger.error('Failed to apply resolution:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Escalate a disruption
   * POST /api/rostering/disruptions/:id/escalate
   */
  router.post('/:id/escalate', async (req, res) => {
    try {
      const { id } = req.params;
      const { reason, escalateTo } = req.body;

      // Would implement escalation logic
      res.json({
        success: true,
        message: 'Disruption escalated',
        data: { id, escalatedTo: escalateTo }
      });
      return;
    } catch (error: any) {
      logger.error('Failed to escalate disruption:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  /**
   * Add notes to a disruption
   * POST /api/rostering/disruptions/:id/notes
   */
  router.post('/:id/notes', async (req, res) => {
    try {
      const { id } = req.params;
      const { note } = req.body;
      const userId =req.user!.id;

      if (!note) {
        return res.status(400).json({
          success: false,
          error: 'note is required'
        });
      }

      // Would store note in database
      res.json({
        success: true,
        message: 'Note added successfully',
        data: {
          id,
          note,
          addedBy: userId,
          addedAt: new Date()
        }
      });
      return;
    } catch (error: any) {
      logger.error('Failed to add note:', error);
      res.status(500).json({ success: false, error: error.message });
      return;
    }
  });

  return router;
}


