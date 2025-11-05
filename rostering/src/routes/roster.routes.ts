import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { RosterController } from '../controllers/roster.controller';

export function createRosterRoutes(prisma: PrismaClient): Router {
  const router = Router();
  const controller = new RosterController(prisma);

  // ===== EXISTING ROUTES =====
  // Roster generation
  router.post('/generate', controller.generateRoster);
  
  // Roster retrieval
  router.get('/:id', controller.getRoster);
  
  // Roster publication (Phase 2)
  router.post('/:id/publish', controller.publishRoster);
  
  // Acceptance tracking (Phase 2)
  router.get('/:id/acceptance', controller.getAcceptanceStatus);
  
  // Scenario comparison
  router.post('/compare', controller.compareScenarios);
  
  // Assignment management
  router.post('/assignments', controller.createAssignment);
  router.post('/assignments/validate', controller.validateAssignment);

  // ===== NEW ROUTES - REAL-TIME OPTIMIZATION =====
  
  // Optimize roster immediately (re-run clustering and assignment)
  router.post('/optimize-now', controller.optimizeNow);
  
  // Get current optimization status
  router.get('/optimization-status/:tenantId', controller.getOptimizationStatus);

  // ===== NEW ROUTES - EMERGENCY HANDLING =====
  
  // Add emergency visit and auto-reassign
  router.post('/emergency-visit', controller.addEmergencyVisit);
  
  // Handle carer unavailability (sick/emergency)
  router.post('/carer-unavailable', controller.handleCarerUnavailable);
  
  // Get emergency resolution options
  router.post('/emergency-options', controller.getEmergencyResolutionOptions);
  
  // Apply emergency resolution
  router.post('/apply-emergency-resolution', controller.applyEmergencyResolution);

  // ===== NEW ROUTES - MANUAL OVERRIDES =====
  
  // Swap two assignments
  router.post('/swap-assignments', controller.swapAssignments);
  
  // Move assignment to different carer
  router.post('/reassign', controller.reassignVisit);
  
  // Lock/unlock assignment (prevent auto-optimization from changing it)
  router.post('/assignments/:id/lock', controller.lockAssignment);
  router.delete('/assignments/:id/lock', controller.unlockAssignment);
  
  // Get all locked assignments
  router.get('/locked-assignments/:rosterId', controller.getLockedAssignments);
  
  // Validate manual change before applying
  router.post('/validate-manual-change', controller.validateManualChange);
  
  // Bulk update assignments
  router.post('/bulk-update', controller.bulkUpdateAssignments);

  // ===== NEW ROUTES - CONTINUITY TRACKING =====
  
  // Get continuity score for a client
  router.get('/continuity/client/:clientId', controller.getClientContinuity);
  
  // Get continuity report for date range
  router.post('/continuity/report', controller.getContinuityReport);
  
  // Get continuity alerts (clients losing preferred carer)
  router.get('/continuity/alerts/:tenantId', controller.getContinuityAlerts);

  // ===== NEW ROUTES - LIVE OPERATIONS =====
  
  // Get real-time roster status
  router.get('/live-status/:rosterId', controller.getLiveRosterStatus);
  
  // Update visit status (started, completed, delayed)
  router.patch('/visits/:visitId/status', controller.updateVisitStatus);
  
  // Get late/at-risk visits
  router.get('/at-risk-visits/:rosterId', controller.getAtRiskVisits);

  return router;
}



