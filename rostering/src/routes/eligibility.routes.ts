import { Router } from 'express';
import { EligibilityController } from '../controllers/eligibility.controller';
import { PrismaClient } from '@prisma/client';

export function createEligibilityRoutes(prisma: PrismaClient): Router {
  const router = Router();
  const controller = new EligibilityController(prisma);

  router.post('/precompute', controller.precomputeEligibility);
  router.get('/visit/:visitId', controller.getEligibleCarers);
  router.post('/batch-precompute', controller.batchPrecomputeEligibility);
  router.post('/matrix', controller.getEligibilityMatrix);
  router.post('/refresh-stale', controller.refreshStaleEligibility);
  router.get('/stats', controller.getEligibilityStats);

  return router;
}


