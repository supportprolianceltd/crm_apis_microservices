import { Router } from 'express';
import { DataValidationController } from '../controllers/data-validation.controller';
import { PrismaClient } from '@prisma/client';

export function createDataValidationRoutes(prisma: PrismaClient): Router {
  const router = Router();
  const controller = new DataValidationController(prisma);

  router.post('/validate', controller.validateData);
  router.post('/fix-issue', controller.fixIssue);

  return router;
}