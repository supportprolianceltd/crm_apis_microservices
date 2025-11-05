import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { SettlementController } from '../controllers/settlement.controller';

export function createSettlementRoutes(prisma: PrismaClient): Router {
  const router = Router();
  const controller = new SettlementController(prisma);

  // Timesheet routes
  router.post('/timesheets/generate', controller.generateTimesheet);
  router.get('/timesheets', controller.listTimesheets);
  router.get('/timesheets/:id', controller.getTimesheet);
  router.post('/timesheets/:id/approve', controller.approveTimesheet);

  // Invoice routes
  router.post('/invoices/generate', controller.generateInvoice);
  router.get('/invoices', controller.listInvoices);
  router.get('/invoices/:id', controller.getInvoice);

  // Payroll routes
  router.post('/payroll/process', controller.processPayrollBatch);
  router.get('/payroll/:id', controller.getPayrollBatch);

  // Compliance reports
  router.post('/reports/compliance', controller.generateComplianceReport);
  router.get('/reports/:id', controller.getComplianceReport);

  return router;
}