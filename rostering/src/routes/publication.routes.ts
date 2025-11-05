import { Router } from 'express';
import { PublicationController } from '../controllers/publication.controller';

export const createPublicationRoutes = (prisma: any) => {
  const router = Router();
  const publicationController = new PublicationController(prisma);

  /**
   * @swagger
   * /api/rostering/publications/publish:
   *   post:
   *     summary: Publish roster to carers
   *     tags: [Publications]
   *     requestBody:
   *       required: true
   *       content:
   *         application/json:
   *           schema:
   *             type: object
   *             required:
   *               - rosterId
   *             properties:
   *               rosterId:
   *                 type: string
   *               versionLabel:
   *                 type: string
   *               notificationChannels:
   *                 type: array
   *                 items:
   *                   type: string
   *                   enum: [push, sms, email]
   *               acceptanceDeadlineMinutes:
   *                 type: number
   *                 default: 30
   *               notes:
   *                 type: string
   *     responses:
   *       200:
   *         description: Roster published successfully
   */
  router.post('/publish', publicationController.publishRoster);

  /**
   * @swagger
   * /api/rostering/publications/{publicationId}:
   *   get:
   *     summary: Get publication status
   *     tags: [Publications]
   *     parameters:
   *       - in: path
   *         name: publicationId
   *         required: true
   *         schema:
   *           type: string
   *     responses:
   *       200:
   *         description: Publication status retrieved
   */
  router.get('/:publicationId', publicationController.getPublicationStatus);

  /**
   * @swagger
   * /api/rostering/publications/assignments/{assignmentId}/accept:
   *   post:
   *     summary: Accept assignment
   *     tags: [Publications]
   *     parameters:
   *       - in: path
   *         name: assignmentId
   *         required: true
   *         schema:
   *           type: string
   *     responses:
   *       200:
   *         description: Assignment accepted successfully
   */
  router.post('/assignments/:assignmentId/accept', publicationController.acceptAssignment);

  /**
   * @swagger
   * /api/rostering/publications/assignments/{assignmentId}/decline:
   *   post:
   *     summary: Decline assignment
   *     tags: [Publications]
   *     parameters:
   *       - in: path
   *         name: assignmentId
   *         required: true
   *         schema:
   *           type: string
   *     requestBody:
   *       content:
   *         application/json:
   *           schema:
   *             type: object
   *             properties:
   *               reason:
   *                 type: string
   *     responses:
   *       200:
   *         description: Assignment declined successfully
   */
  router.post('/assignments/:assignmentId/decline', publicationController.declineAssignment);

  /**
   * @swagger
   * /api/rostering/publications/carer/pending:
   *   get:
   *     summary: Get pending assignments for carer
   *     tags: [Publications]
   *     responses:
   *       200:
   *         description: Pending assignments retrieved
   */
  router.get('/carer/pending', publicationController.getPendingAssignments);

  /**
   * @swagger
   * /api/rostering/publications/assignments/{assignmentId}/escalate:
   *   post:
   *     summary: Manually escalate assignment
   *     tags: [Publications]
   *     parameters:
   *       - in: path
   *         name: assignmentId
   *         required: true
   *         schema:
   *           type: string
   *     responses:
   *       200:
   *         description: Assignment escalated successfully
   */
  router.post('/assignments/:assignmentId/escalate', publicationController.escalateAssignment);

  return router;
};