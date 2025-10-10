import { Router } from 'express';
import { RequestController } from '../controllers/request.controller';
import { authenticate, ensureTenantAccess } from '../middleware/auth.middleware';

export function createRequestRoutes(requestController: RequestController): Router {
  const router = Router();

  // Apply authentication to all routes
  router.use(authenticate);
  router.use(ensureTenantAccess);

  // Request CRUD operations
  router.get('/', requestController.listRequests);
  router.post('/', requestController.createRequest);
  router.get('/search', requestController.searchRequests);
  router.get('/:id', requestController.getRequest);
  router.put('/:id', requestController.updateRequest);
  router.delete('/:id', requestController.deleteRequest);

  // Matching operations
  router.post('/:id/match', requestController.triggerMatching);

  return router;
}