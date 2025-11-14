import { Router } from 'express';
import { CarePlanController } from '../controllers/careplan.controller';

export function createCarePlanRoutes(controller: CarePlanController) {
  const router = Router();

  router.post('/', (req, res) => controller.createCarePlan(req, res));

  // List care plans for tenant (supports ?page & ?pageSize)
  router.get('/', (req, res) => controller.listCarePlans(req, res));

  // Get a single care plan by id
  router.get('/:id', (req, res) => controller.getCarePlanById(req, res));

  // Get care plans by clientId
  router.get('/client/:clientId', (req, res) => controller.getCarePlansByClient(req, res));

  // Get care plans by carerId
  router.get('/carer/:carerId', (req, res) => controller.getCarePlansByCarer(req, res));

  // Update an existing care plan (upsert careRequirements + schedules/slots when provided)
  router.patch('/:id', (req, res) => controller.updateCarePlan(req, res));

  // Delete a care plan
  router.delete('/:id', (req, res) => controller.deleteCarePlan(req, res));

  return router;
}
