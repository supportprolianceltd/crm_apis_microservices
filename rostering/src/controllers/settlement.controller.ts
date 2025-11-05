import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { SettlementService } from '../services/settlement.service';
import { logger } from '../utils/logger';

export class SettlementController {
  private settlementService: SettlementService;

  constructor(private prisma: PrismaClient) {
    this.settlementService = new SettlementService(prisma);
  }

  /**
   * Generate timesheet for carer
   * POST /api/rostering/settlement/timesheets/generate
   */
  generateTimesheet = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const { carerId, periodStart, periodEnd } = req.body;

      if (!carerId || !periodStart || !periodEnd) {
        res.status(400).json({
          success: false,
          error: 'carerId, periodStart, and periodEnd are required'
        });
        return;
      }

      const timesheet = await this.settlementService.generateTimesheet(
        tenantId,
        carerId,
        new Date(periodStart),
        new Date(periodEnd)
      );

      res.json({
        success: true,
        data: timesheet,
        message: 'Timesheet generated successfully'
      });

    } catch (error: any) {
      logger.error('Failed to generate timesheet:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to generate timesheet',
        message: error.message
      });
    }
  };

  /**
   * Get timesheet by ID
   * GET /api/rostering/settlement/timesheets/:id
   */
  getTimesheet = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const timesheetId = req.params.id;

      const timesheet = await this.prisma.timesheet.findFirst({
        where: {
          id: timesheetId,
          tenantId
        },
        include: {
          carer: {
            select: {
              firstName: true,
              lastName: true,
              email: true
            }
          },
          entries: {
            include: {
              visit: {
                select: {
                  requestorName: true,
                  address: true
                }
              }
            }
          },
          exceptions: true,
          adjustments: true
        }
      });

      if (!timesheet) {
        res.status(404).json({
          success: false,
          error: 'Timesheet not found'
        });
        return;
      }

      res.json({
        success: true,
        data: timesheet
      });

    } catch (error) {
      logger.error('Failed to get timesheet:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve timesheet'
      });
    }
  };

  /**
   * Approve timesheet
   * POST /api/rostering/settlement/timesheets/:id/approve
   */
  approveTimesheet = async (req: Request, res: Response): Promise<void> => {
    try {
      const timesheetId = req.params.id;
      const approvedBy = req.user!.id;

      await this.settlementService.approveTimesheet(timesheetId, approvedBy);

      res.json({
        success: true,
        message: 'Timesheet approved successfully'
      });

    } catch (error) {
      logger.error('Failed to approve timesheet:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to approve timesheet'
      });
    }
  };

  /**
   * Generate invoice for client
   * POST /api/rostering/settlement/invoices/generate
   */
  generateInvoice = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const { clientId, periodStart, periodEnd } = req.body;

      if (!clientId || !periodStart || !periodEnd) {
        res.status(400).json({
          success: false,
          error: 'clientId, periodStart, and periodEnd are required'
        });
        return;
      }

      const invoice = await this.settlementService.generateInvoice(
        tenantId,
        clientId,
        new Date(periodStart),
        new Date(periodEnd)
      );

      res.json({
        success: true,
        data: invoice,
        message: 'Invoice generated successfully'
      });

    } catch (error: any) {
      logger.error('Failed to generate invoice:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to generate invoice',
        message: error.message
      });
    }
  };

  /**
   * Get invoice by ID
   * GET /api/rostering/settlement/invoices/:id
   */
  getInvoice = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const invoiceId = req.params.id;

      const invoice = await this.prisma.invoice.findFirst({
        where: {
          id: invoiceId,
          tenantId
        },
        include: {
          lineItems: {
            include: {
              visit: {
                select: {
                  requestorName: true,
                  address: true,
                  scheduledStartTime: true
                }
              }
            }
          },
          payments: true
        }
      });

      if (!invoice) {
        res.status(404).json({
          success: false,
          error: 'Invoice not found'
        });
        return;
      }

      res.json({
        success: true,
        data: invoice
      });

    } catch (error) {
      logger.error('Failed to get invoice:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve invoice'
      });
    }
  };

  /**
   * Process payroll batch
   * POST /api/rostering/settlement/payroll/process
   */
  processPayrollBatch = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const processedBy = req.user!.id;
      const { periodStart, periodEnd } = req.body;

      if (!periodStart || !periodEnd) {
        res.status(400).json({
          success: false,
          error: 'periodStart and periodEnd are required'
        });
        return;
      }

      const batch = await this.settlementService.processPayrollBatch(
        tenantId,
        new Date(periodStart),
        new Date(periodEnd),
        processedBy
      );

      res.json({
        success: true,
        data: batch,
        message: 'Payroll batch processed successfully'
      });

    } catch (error: any) {
      logger.error('Failed to process payroll:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to process payroll',
        message: error.message
      });
    }
  };

  /**
   * Get payroll batch by ID
   * GET /api/rostering/settlement/payroll/:id
   */
  getPayrollBatch = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const batchId = req.params.id;

      const batch = await this.prisma.payrollBatch.findFirst({
        where: {
          id: batchId,
          tenantId
        },
        include: {
          payslips: {
            include: {
              carer: {
                select: {
                  firstName: true,
                  lastName: true,
                  email: true
                }
              }
            }
          }
        }
      });

      if (!batch) {
        res.status(404).json({
          success: false,
          error: 'Payroll batch not found'
        });
        return;
      }

      res.json({
        success: true,
        data: batch
      });

    } catch (error) {
      logger.error('Failed to get payroll batch:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve payroll batch'
      });
    }
  };

  /**
   * Generate compliance report
   * POST /api/rostering/settlement/reports/compliance
   */
  generateComplianceReport = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const generatedBy = req.user!.id;
      const { reportType, periodStart, periodEnd } = req.body;

      if (!reportType || !periodStart || !periodEnd) {
        res.status(400).json({
          success: false,
          error: 'reportType, periodStart, and periodEnd are required'
        });
        return;
      }

      const report = await this.settlementService.generateComplianceReport(
        tenantId,
        reportType,
        new Date(periodStart),
        new Date(periodEnd),
        generatedBy
      );

      res.json({
        success: true,
        data: report,
        message: 'Compliance report generated successfully'
      });

    } catch (error: any) {
      logger.error('Failed to generate compliance report:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to generate compliance report',
        message: error.message
      });
    }
  };

  /**
   * Get compliance report by ID
   * GET /api/rostering/settlement/reports/:id
   */
  getComplianceReport = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const reportId = req.params.id;

      const report = await this.prisma.complianceReport.findFirst({
        where: {
          id: reportId,
          tenantId
        }
      });

      if (!report) {
        res.status(404).json({
          success: false,
          error: 'Report not found'
        });
        return;
      }

      res.json({
        success: true,
        data: report
      });

    } catch (error) {
      logger.error('Failed to get compliance report:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve compliance report'
      });
    }
  };

  /**
   * List timesheets with filters
   * GET /api/rostering/settlement/timesheets
   */
  listTimesheets = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const { status, carerId, page = 1, limit = 20 } = req.query;

      const where: any = { tenantId };
      if (status) where.status = status;
      if (carerId) where.carerId = carerId;

      const skip = (Number(page) - 1) * Number(limit);

      const [total, timesheets] = await Promise.all([
        this.prisma.timesheet.count({ where }),
        this.prisma.timesheet.findMany({
          where,
          skip,
          take: Number(limit),
          orderBy: { createdAt: 'desc' },
          include: {
            carer: {
              select: {
                firstName: true,
                lastName: true,
                email: true
              }
            }
          }
        })
      ]);

      res.json({
        success: true,
        data: timesheets,
        pagination: {
          page: Number(page),
          limit: Number(limit),
          total,
          pages: Math.ceil(total / Number(limit))
        }
      });

    } catch (error) {
      logger.error('Failed to list timesheets:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to list timesheets'
      });
    }
  };

  /**
   * List invoices with filters
   * GET /api/rostering/settlement/invoices
   */
  listInvoices = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const { status, clientId, page = 1, limit = 20 } = req.query;

      const where: any = { tenantId };
      if (status) where.status = status;
      if (clientId) where.clientId = clientId;

      const skip = (Number(page) - 1) * Number(limit);

      const [total, invoices] = await Promise.all([
        this.prisma.invoice.count({ where }),
        this.prisma.invoice.findMany({
          where,
          skip,
          take: Number(limit),
          orderBy: { invoiceDate: 'desc' }
        })
      ]);

      res.json({
        success: true,
        data: invoices,
        pagination: {
          page: Number(page),
          limit: Number(limit),
          total,
          pages: Math.ceil(total / Number(limit))
        }
      });

    } catch (error) {
      logger.error('Failed to list invoices:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to list invoices'
      });
    }
  };
}