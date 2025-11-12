import { Router } from 'express';
import { TaskController } from '../controllers/task.controller';

export function createTaskRoutes(controller: TaskController) {
  const router = Router();

  // Create a new task
  router.post('/', (req, res) => controller.createTask(req, res));

  // List all tenant tasks (supports pagination and filters)
  router.get('/', (req, res) => controller.listTenantTasks(req, res));

  // Get single task by ID
  router.get('/:taskId', (req, res) => controller.getTaskById(req, res));

  // Update a task
  router.put('/:taskId', (req, res) => controller.updateTask(req, res));

  // Delete a task
  router.delete('/:taskId', (req, res) => controller.deleteTask(req, res));

  // Get tasks by care plan ID
  router.get('/careplan/:carePlanId', (req, res) => controller.getTasksByCarePlan(req, res));

  // Get tasks by client ID (across all their care plans)
  router.get('/client/:clientId', (req, res) => controller.getTasksByClient(req, res));

  // Get tasks by client ID and related table (e.g., all RiskAssessment tasks for client)
  router.get('/client/:clientId/table/:relatedTable', (req, res) => controller.getTasksByClientAndTable(req, res));

  // Get tasks by carer ID (via CarePlanCarer relationships)
  router.get('/carer/:carerId', (req, res) => controller.getTasksByCarer(req, res));

  return router;
}

