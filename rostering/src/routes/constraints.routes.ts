import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { ConstraintsController } from '../controllers/constraints.controller';
import { authenticate } from '../middleware/auth.middleware';

export function createConstraintsRoutes(prisma: PrismaClient) {
  const router = Router();
  const constraintsController = new ConstraintsController(prisma);

  // All routes require authentication
  router.use(authenticate);

  router.get('/', constraintsController.getConstraints);
  router.put('/', constraintsController.updateConstraints);
  router.post('/rule-sets', constraintsController.createRuleSet);
  router.get('/rule-sets', constraintsController.getRuleSets);
  router.post('/validate-assignment', constraintsController.validateAssignment);

  return router;
}



