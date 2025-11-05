import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { PublicationService } from '../services/publication.service';
import { NotificationService } from '../services/notification.service';
import { logger } from '../utils/logger';

interface AuthenticatedRequest extends Request {
  user: {
    id: string;
    email: string;
    tenantId: string;
    permissions?: string[];
  };
}

export class PublicationController {
  private publicationService: PublicationService;

  constructor(private prisma: PrismaClient) {
    const notificationService = new NotificationService();
    this.publicationService = new PublicationService(prisma, notificationService);
  }

  /**
   * Publish roster to carers
   * POST /api/rostering/publications/publish
   */
  publishRoster = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const userId = (req as AuthenticatedRequest).user.id;
      const { rosterId, versionLabel, notificationChannels, acceptanceDeadlineMinutes, notes } = req.body;

      if (!rosterId) {
        res.status(400).json({
          success: false,
          error: 'rosterId is required'
        });
        return;
      }

      const publication = await this.publicationService.publishRoster(
        tenantId,
        rosterId,
        userId,
        {
          versionLabel,
          notificationChannels,
          acceptanceDeadlineMinutes,
          notes
        }
      );

      res.json({
        success: true,
        data: publication,
        message: 'Roster published successfully'
      });

    } catch (error: any) {
      logger.error('Failed to publish roster:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to publish roster',
        message: error.message
      });
    }
  };

  /**
   * Get publication status
   * GET /api/rostering/publications/:publicationId
   */
  getPublicationStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const publicationId = req.params.publicationId;

      const publication = await this.publicationService.getPublicationStatus(publicationId);

      res.json({
        success: true,
        data: publication
      });

    } catch (error: any) {
      logger.error('Failed to get publication status:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get publication status',
        message: error.message
      });
    }
  };

  /**
   * Accept assignment
   * POST /api/rostering/publications/assignments/:assignmentId/accept
   */
  acceptAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const assignmentId = req.params.assignmentId;
      const carerId = (req as AuthenticatedRequest).user.id;

      const assignment = await this.publicationService.acceptAssignment(
        tenantId,
        assignmentId,
        carerId
      );

      res.json({
        success: true,
        data: assignment,
        message: 'Assignment accepted successfully'
      });

    } catch (error: any) {
      logger.error('Failed to accept assignment:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to accept assignment',
        message: error.message
      });
    }
  };

  /**
   * Decline assignment
   * POST /api/rostering/publications/assignments/:assignmentId/decline
   */
  declineAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const assignmentId = req.params.assignmentId;
      const carerId = (req as AuthenticatedRequest).user.id;
      const { reason } = req.body;

      const assignment = await this.publicationService.declineAssignment(
        tenantId,
        assignmentId,
        carerId,
        reason
      );

      res.json({
        success: true,
        data: assignment,
        message: 'Assignment declined successfully'
      });

    } catch (error: any) {
      logger.error('Failed to decline assignment:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to decline assignment',
        message: error.message
      });
    }
  };

  /**
   * Get pending assignments for carer
   * GET /api/rostering/publications/carer/pending
   */
  getPendingAssignments = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const carerId = (req as AuthenticatedRequest).user.id;

      const assignments = await this.publicationService.getPendingAssignmentsForCarer(
        tenantId,
        carerId
      );

      res.json({
        success: true,
        data: assignments
      });

    } catch (error: any) {
      logger.error('Failed to get pending assignments:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get pending assignments',
        message: error.message
      });
    }
  };

  /**
   * Manually escalate assignment
   * POST /api/rostering/publications/assignments/:assignmentId/escalate
   */
  escalateAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const assignmentId = req.params.assignmentId;
      const escalatedBy = (req as AuthenticatedRequest).user.id;

      await this.publicationService.manuallyEscalateAssignment(assignmentId, escalatedBy);

      res.json({
        success: true,
        message: 'Assignment escalated successfully'
      });

    } catch (error: any) {
      logger.error('Failed to escalate assignment:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to escalate assignment',
        message: error.message
      });
    }
  };
}