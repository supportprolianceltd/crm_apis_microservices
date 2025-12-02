import { Router } from 'express';
import { AttendanceController } from '../controllers/attendance.controller';

export function createAttendanceRoutes(controller: AttendanceController) {
  const router = Router();

  // List attendance rows. Optional `date=YYYY-MM-DD` filter
  router.get('/', (req, res) => controller.listAttendance(req, res));

  return router;
}
