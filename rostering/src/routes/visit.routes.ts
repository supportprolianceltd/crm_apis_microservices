import { Router } from 'express';
import { VisitController } from '../controllers/visit.controller';
import { authenticate, ensureTenantAccess } from '../middleware/auth.middleware';

export function createVisitRoutes(visitController: VisitController): Router {
  const router = Router();

  // Apply authentication to all routes
  router.use(authenticate);
  router.use(ensureTenantAccess);

  // Visit CRUD operations
  router.get('/', visitController.listVisits);
  router.post('/', visitController.createVisit);
  router.get('/search', visitController.searchVisits);
  router.get('/:id', visitController.getVisit);
  router.put('/:id', visitController.updateVisit);
  router.delete('/:id', visitController.deleteVisit);
  router.get('/status/:status', visitController.getVisitsByStatus);

  return router;
}