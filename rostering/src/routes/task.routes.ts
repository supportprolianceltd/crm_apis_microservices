import { Router } from 'express';
import { TaskController } from '../controllers/task.controller';

export function createTaskRoutes(controller: TaskController) {
  const router = Router();

  // Create a new task
  router.post('/', (req, res) => controller.createTask(req, res));

  // List all tenant tasks (supports pagination and filters)
  router.get('/', (req, res) => controller.listTenantTasks(req, res));

  // Assign a carer to an existing visit (visit-level assignment)
  // Place visit routes before the generic '/:taskId' route so '/visits' is not captured as a taskId.
  router.post('/visits/:visitId/assign', (req, res) => controller.assignCarerToVisit(req, res));

  // Clock in / clock out on a visit
  router.post('/visits/:visitId/clockin', (req, res) => controller.clockInVisit(req, res));
  router.post('/visits/:visitId/clockout', (req, res) => controller.clockOutVisit(req, res));

  // List all visits for the tenant (supports pagination and optional carerId filter)
  // Get a single visit by id
  router.get('/visits/:visitId', (req, res) => controller.getVisitById(req, res));
  // Delete a visit by id
  router.delete('/visits/:visitId', (req, res) => controller.deleteVisit(req, res));

  // List all visits for the tenant (supports pagination and optional carerId filter)
  router.get('/visits', (req, res) => controller.listTenantVisits(req, res));

  // Get single task by ID
  router.get('/:taskId', (req, res) => controller.getTaskById(req, res));

  // Update a task (partial updates supported) - use PATCH
  router.patch('/:taskId', (req, res) => controller.updateTask(req, res));

  // Delete a task
  router.delete('/:taskId', (req, res) => controller.deleteTask(req, res));

  // Assign a task to a carer (auto-find/create carerVisit and attach)
  router.post('/:taskId/assign', (req, res) => controller.assignTaskToCarer(req, res));

  // Assign a carer to an existing visit (visit-level assignment)
  router.post('/visits/:visitId/assign', (req, res) => controller.assignCarerToVisit(req, res));

  // List all visits for the tenant (supports pagination and optional carerId filter)
  router.get('/visits', (req, res) => controller.listTenantVisits(req, res));

  // Get tasks by care plan ID
  router.get('/careplan/:carePlanId', (req, res) => controller.getTasksByCarePlan(req, res));

  // Get visits for a specific client (visit list across all care plans for the client)
  // Place before the generic '/client/:clientId' route so 'visits' isn't captured as clientId
  router.get('/client/:clientId/visits', (req, res) => controller.getVisitsByClient(req, res));

  // Get tasks by client ID (across all their care plans)
  router.get('/client/:clientId', (req, res) => controller.getTasksByClient(req, res));

  // Get tasks by client ID and related table (e.g., all RiskAssessment tasks for client)
  router.get('/client/:clientId/table/:relatedTable', (req, res) => controller.getTasksByClientAndTable(req, res));

  // Get tasks by carer ID (via CarePlanCarer relationships)
  router.get('/carer/:carerId', (req, res) => controller.getTasksByCarer(req, res));
  // Get carer visits (optionally filter by date, day or range)
  router.get('/carer/:carerId/visits', (req, res) => controller.getCarerVisits(req, res));

  return router;
}

