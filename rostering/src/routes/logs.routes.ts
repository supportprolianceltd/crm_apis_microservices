import { Router } from 'express';
import { LogsController } from '../controllers/logs.controller';

export function createLogsRoutes(controller: LogsController) {
  const router = Router();

  // Get visit logs (client_visit_logs)
  router.get('/visits/:visitId/logs', (req, res) => controller.getVisitLogs(req, res));

  // Get all logs for the tenant
  router.get('/', (req, res) => controller.getAllLogs(req, res));

  

  return router;
}