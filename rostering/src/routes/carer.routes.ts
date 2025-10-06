import { Router } from 'express';
import { CarerController } from '../controllers/carer.controller';
import { authenticate, ensureTenantAccess } from '../middleware/auth.middleware';

export function createCarerRoutes(carerController: CarerController): Router {
  const router = Router();

  // Apply authentication to all routes
  router.use(authenticate);
  router.use(ensureTenantAccess);

  // Read-only carer operations (management is handled by auth service)
  router.get('/search', carerController.searchCarers);
  router.get('/:id', carerController.getCarer);
  router.get('/:id/availability', carerController.getCarerAvailability);

  return router;
}