import { Router } from 'express';
import { TravelMatrixController } from '../controllers/travel-matrix.controller';
import { PrismaClient } from '@prisma/client';

export function createTravelMatrixRoutes(prisma: PrismaClient): Router {
  const router = Router();
  const controller = new TravelMatrixController(prisma);

  router.get('/travel-time', controller.getTravelTime);
  // Add other routes

  return router;
}