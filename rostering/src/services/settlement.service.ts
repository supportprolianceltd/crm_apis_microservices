import { PrismaClient, TimesheetStatus, InvoiceStatus, PayrollStatus } from '@prisma/client';
import { logger } from '../utils/logger';

export interface TimesheetSummary {
  timesheetId: string;
  carerId: string;
  carerName: string;
  periodStart: Date;
  periodEnd: Date;
  scheduledHours: number;
  actualHours: number;
  overtimeHours: number;
  totalPay: number;
  exceptionCount: number;
  status: TimesheetStatus;
}

export interface InvoiceSummary {
  invoiceId: string;
  clientId: string | null;
  invoiceNumber: string;
  invoiceDate: Date;
  dueDate: Date;
  totalAmount: number;
  paidAmount: number;
  status: InvoiceStatus;
  daysOverdue: number;
}

export class SettlementService {
  constructor(private prisma: PrismaClient) {}

  /**
   * Generate timesheet for carer for a period
   */
  async generateTimesheet(
    tenantId: string,
    carerId: string,
    periodStart: Date,
    periodEnd: Date
  ): Promise<TimesheetSummary> {
    try {
      logger.info(`Generating timesheet for carer ${carerId}`, { periodStart, periodEnd });

      // Get all check-ins/outs for period
      const checkIns = await this.prisma.visitCheckIn.findMany({
        where: {
          carerId,
          checkInTime: {
            gte: periodStart,
            lte: periodEnd
          }
        }
      });

      const checkOuts = await this.prisma.visitCheckOut.findMany({
        where: {
          carerId,
          checkOutTime: {
            gte: periodStart,
            lte: periodEnd
          }
        }
      });

      // Get scheduled visits for comparison
      const scheduledVisits = await this.prisma.assignment.findMany({
        where: {
          tenantId,
          carerId,
          scheduledTime: {
            gte: periodStart,
            lte: periodEnd
          },
          status: { in: ['ACCEPTED', 'COMPLETED'] }
        },
        include: {
          visit: true
        }
      });

      // Calculate hours
      let scheduledHours = 0;
      let actualHours = 0;
      const entries = [];
      const exceptions = [];

      for (const assignment of scheduledVisits) {
        const duration = assignment.visit.estimatedDuration || 60;
        scheduledHours += duration / 60;

        // Find corresponding check-in/out
        const checkIn = checkIns.find(ci => ci.visitId === assignment.visitId);
        const checkOut = checkOuts.find(co => co.visitId === assignment.visitId);

        if (!checkIn) {
          exceptions.push({
            type: 'MISSING_CHECK_IN',
            severity: 'ERROR',
            description: `No check-in found for visit ${assignment.visitId}`,
            visitId: assignment.visitId
          });
          continue;
        }

        if (!checkOut) {
          exceptions.push({
            type: 'MISSING_CHECK_OUT',
            severity: 'ERROR',
            description: `No check-out found for visit ${assignment.visitId}`,
            visitId: assignment.visitId
          });
          // Estimate actual duration as scheduled
          actualHours += duration / 60;
          
          entries.push({
            visitId: assignment.visitId,
            checkInTime: checkIn.checkInTime,
            checkOutTime: null,
            scheduledStart: assignment.scheduledTime,
            scheduledEnd: assignment.estimatedEndTime,
            scheduledDuration: duration,
            actualDuration: duration,
            variance: 0,
            withinGeofence: checkIn.withinGeofence,
            validated: false
          });
          continue;
        }

        // Calculate actual duration
        const actualDuration = Math.floor(
          (checkOut.checkOutTime.getTime() - checkIn.checkInTime.getTime()) / 60000
        );
        actualHours += actualDuration / 60;

        const variance = actualDuration - duration;

        // Check for exceptions
        if (Math.abs(variance) > duration * 0.2) {
          // More than 20% variance
          const type = variance > 0 ? 'LONG_VISIT' : 'SHORT_VISIT';
          exceptions.push({
            type,
            severity: 'WARNING',
            description: `Visit ${assignment.visitId} variance: ${variance} minutes`,
            expectedValue: duration.toString(),
            actualValue: actualDuration.toString(),
            variance: variance.toString(),
            visitId: assignment.visitId
          });
        }

        if (!checkIn.withinGeofence || !checkOut) {
          exceptions.push({
            type: 'OUTSIDE_GEOFENCE',
            severity: 'WARNING',
            description: `Check-in/out outside geofence for visit ${assignment.visitId}`,
            visitId: assignment.visitId
          });
        }

        entries.push({
          visitId: assignment.visitId,
          checkInTime: checkIn.checkInTime,
          checkOutTime: checkOut.checkOutTime,
          scheduledStart: assignment.scheduledTime,
          scheduledEnd: assignment.estimatedEndTime,
          scheduledDuration: duration,
          actualDuration,
          variance,
          withinGeofence: checkIn.withinGeofence,
          validated: Math.abs(variance) <= duration * 0.1 // Auto-validate if within 10%
        });
      }

      // Calculate overtime
      const overtimeHours = Math.max(0, actualHours - scheduledHours);

      // Get carer's hourly rate
      const carer = await this.prisma.carer.findUnique({
        where: { id: carerId },
        select: { hourlyRate: true, firstName: true, lastName: true }
      });

      const hourlyRate = carer?.hourlyRate || 15;
      const regularPay = scheduledHours * hourlyRate;
      const overtimePay = overtimeHours * hourlyRate * 1.5; // 1.5x for overtime
      const totalPay = regularPay + overtimePay;

      // Create timesheet record
      const timesheet = await this.prisma.timesheet.create({
        data: {
          tenantId,
          carerId,
          periodStart,
          periodEnd,
          scheduledHours,
          actualHours,
          overtimeHours,
          regularPay,
          overtimePay,
          totalPay,
          status: exceptions.length > 0 ? TimesheetStatus.DRAFT : TimesheetStatus.SUBMITTED
        }
      });

      // Create entries
      await this.prisma.timesheetEntry.createMany({
        data: entries.map(entry => ({
          timesheetId: timesheet.id,
          ...entry
        }))
      });

      // Create exceptions
      if (exceptions.length > 0) {
        await this.prisma.timesheetException.createMany({
          data: exceptions.map(exc => ({
            timesheetId: timesheet.id,
            type: exc.type as any,
            severity: exc.severity as any,
            description: exc.description,
            visitId: exc.visitId,
            expectedValue: exc.expectedValue,
            actualValue: exc.actualValue,
            variance: exc.variance
          }))
        });
      }

      logger.info(`Timesheet generated: ${timesheet.id}`, {
        scheduledHours,
        actualHours,
        overtimeHours,
        exceptions: exceptions.length
      });

      return {
        timesheetId: timesheet.id,
        carerId,
        carerName: `${carer?.firstName} ${carer?.lastName}`,
        periodStart,
        periodEnd,
        scheduledHours,
        actualHours,
        overtimeHours,
        totalPay,
        exceptionCount: exceptions.length,
        status: timesheet.status
      };

    } catch (error) {
      logger.error('Failed to generate timesheet:', error);
      throw error;
    }
  }

  /**
   * Approve timesheet
   */
  async approveTimesheet(
    timesheetId: string,
    approvedBy: string
  ): Promise<void> {
    await this.prisma.timesheet.update({
      where: { id: timesheetId },
      data: {
        status: TimesheetStatus.APPROVED,
        approvedAt: new Date(),
        approvedBy
      }
    });

    logger.info(`Timesheet approved: ${timesheetId} by ${approvedBy}`);
  }

  /**
   * Generate invoice for client
   */
  async generateInvoice(
    tenantId: string,
    clientId: string,
    periodStart: Date,
    periodEnd: Date
  ): Promise<InvoiceSummary> {
    try {
      logger.info(`Generating invoice for client ${clientId}`, { periodStart, periodEnd });

      // Get all completed visits for client in period
      const visits = await this.prisma.externalRequest.findMany({
        where: {
          tenantId,
          requestorEmail: clientId,
          scheduledStartTime: {
            gte: periodStart,
            lte: periodEnd
          },
          status: 'COMPLETED'
        }
      });

      // Get assignments for these visits
      const visitIds = visits.map(v => v.id);
      const assignments = await this.prisma.assignment.findMany({
        where: {
          visitId: { in: visitIds },
          status: 'COMPLETED'
        }
      });

      // Attach assignments to visits
      const visitsWithAssignments = visits.map(visit => ({
        ...visit,
        assignments: assignments.filter(a => a.visitId === visit.id)
      }));

      // Generate invoice number
      const invoiceNumber = `INV-${Date.now()}-${Math.random().toString(36).substr(2, 6).toUpperCase()}`;

      // Calculate line items
      let subtotal = 0;
      const lineItems = [];

      for (const visit of visitsWithAssignments) {
        if (visit.assignments.length === 0) continue;

        const assignment = visit.assignments[0];
        const duration = assignment.actualDuration || visit.estimatedDuration || 60;
        const unitPrice = 25; // £25/hour default rate
        const quantity = duration / 60;
        const lineTotal = quantity * unitPrice;

        subtotal += lineTotal;

        lineItems.push({
          visitId: visit.id,
          description: `Care visit - ${visit.address}`,
          quantity,
          unitPrice,
          lineTotal,
          serviceDate: visit.scheduledStartTime!,
          category: 'Personal Care'
        });
      }

      // Calculate tax
      const taxRate = 0.20; // 20% VAT
      const taxAmount = subtotal * taxRate;
      const totalAmount = subtotal + taxAmount;

      // Create invoice
      const invoice = await this.prisma.invoice.create({
        data: {
          tenantId,
          clientId,
          invoiceNumber,
          invoiceDate: new Date(),
          dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
          periodStart,
          periodEnd,
          subtotal,
          taxAmount,
          taxRate,
          totalAmount,
          status: InvoiceStatus.DRAFT
        }
      });

      // Create line items
      await this.prisma.invoiceLineItem.createMany({
        data: lineItems.map(item => ({
          invoiceId: invoice.id,
          ...item
        }))
      });

      logger.info(`Invoice generated: ${invoice.id}`, {
        invoiceNumber,
        totalAmount,
        lineItems: lineItems.length
      });

      return {
        invoiceId: invoice.id,
        clientId,
        invoiceNumber,
        invoiceDate: invoice.invoiceDate,
        dueDate: invoice.dueDate,
        totalAmount,
        paidAmount: 0,
        status: invoice.status,
        daysOverdue: 0
      };

    } catch (error) {
      logger.error('Failed to generate invoice:', error);
      throw error;
    }
  }

  /**
   * Process payroll batch
   */
  async processPayrollBatch(
    tenantId: string,
    periodStart: Date,
    periodEnd: Date,
    processedBy: string
  ): Promise<{
    batchId: string;
    totalGrossPay: number;
    totalNetPay: number;
    employeeCount: number;
  }> {
    try {
      logger.info('Processing payroll batch', { periodStart, periodEnd });

      // Get all approved timesheets for period
      const timesheets = await this.prisma.timesheet.findMany({
        where: {
          tenantId,
          periodStart: { gte: periodStart },
          periodEnd: { lte: periodEnd },
          status: TimesheetStatus.APPROVED
        },
        include: {
          carer: {
            select: {
              id: true,
              firstName: true,
              lastName: true,
              hourlyRate: true
            }
          }
        }
      });

      if (timesheets.length === 0) {
        throw new Error('No approved timesheets found for period');
      }

      // Generate batch number
      const batchNumber = `PAY-${Date.now()}-${Math.random().toString(36).substr(2, 6).toUpperCase()}`;

      // Calculate totals
      let totalGrossPay = 0;
      let totalNetPay = 0;
      let totalTax = 0;
      let totalNI = 0;

      const payslips = [];

      for (const timesheet of timesheets) {
        const grossPay = timesheet.totalPay;
        
        // Simple tax calculation (UK basic rate)
        const taxDeduction = grossPay * 0.20; // 20% basic rate
        const niDeduction = grossPay * 0.12; // 12% NI
        const netPay = grossPay - taxDeduction - niDeduction;

        totalGrossPay += grossPay;
        totalNetPay += netPay;
        totalTax += taxDeduction;
        totalNI += niDeduction;

        payslips.push({
          carerId: timesheet.carerId,
          timesheetId: timesheet.id,
          periodStart: timesheet.periodStart,
          periodEnd: timesheet.periodEnd,
          regularHours: timesheet.scheduledHours,
          overtimeHours: timesheet.overtimeHours,
          totalHours: timesheet.actualHours,
          regularPay: timesheet.regularPay,
          overtimePay: timesheet.overtimePay,
          grossPay,
          taxDeduction,
          niDeduction,
          pensionDeduction: 0,
          otherDeductions: 0,
          totalDeductions: taxDeduction + niDeduction,
          netPay,
          status: 'GENERATED'
        });
      }

      // Create payroll batch
      const batch = await this.prisma.payrollBatch.create({
        data: {
          tenantId,
          batchNumber,
          periodStart,
          periodEnd,
          status: PayrollStatus.PROCESSING,
          totalGrossPay,
          totalNetPay,
          totalTax,
          totalNI,
          totalPension: 0,
          employeeCount: timesheets.length,
          processedAt: new Date(),
          processedBy
        }
      });

      // Create payslips
      await this.prisma.payslip.createMany({
        data: payslips.map(slip => ({
          batchId: batch.id,
          carerId: slip.carerId,
          timesheetId: slip.timesheetId,
          periodStart: slip.periodStart,
          periodEnd: slip.periodEnd,
          regularHours: slip.regularHours,
          overtimeHours: slip.overtimeHours,
          totalHours: slip.totalHours,
          regularPay: slip.regularPay,
          overtimePay: slip.overtimePay,
          grossPay: slip.grossPay,
          taxDeduction: slip.taxDeduction,
          niDeduction: slip.niDeduction,
          pensionDeduction: slip.pensionDeduction,
          otherDeductions: slip.otherDeductions,
          totalDeductions: slip.totalDeductions,
          netPay: slip.netPay,
          status: slip.status as any
        }))
      });

      // Mark timesheets as processed
      await this.prisma.timesheet.updateMany({
        where: {
          id: { in: timesheets.map(t => t.id) }
        },
        data: {
          status: TimesheetStatus.PROCESSED,
          processedAt: new Date(),
          processedBy,
          payrollBatchId: batch.id
        }
      });

      logger.info(`Payroll batch processed: ${batch.id}`, {
        batchNumber,
        employeeCount: timesheets.length,
        totalGrossPay,
        totalNetPay
      });

      return {
        batchId: batch.id,
        totalGrossPay,
        totalNetPay,
        employeeCount: timesheets.length
      };

    } catch (error) {
      logger.error('Failed to process payroll batch:', error);
      throw error;
    }
  }

  /**
   * Generate compliance report
   */
  async generateComplianceReport(
    tenantId: string,
    reportType: string,
    periodStart: Date,
    periodEnd: Date,
    generatedBy: string
  ): Promise<{
    reportId: string;
    passRate: number;
    failCount: number;
    warningCount: number;
  }> {
    try {
      logger.info(`Generating ${reportType} compliance report`, { periodStart, periodEnd });

      let reportData: any = {};
      let passRate = 0;
      let failCount = 0;
      let warningCount = 0;

      switch (reportType) {
        case 'WTD_COMPLIANCE':
          const wtdResult = await this.checkWTDCompliance(tenantId, periodStart, periodEnd);
          reportData = wtdResult.data;
          passRate = wtdResult.passRate;
          failCount = wtdResult.failCount;
          warningCount = wtdResult.warningCount;
          break;

        case 'VISIT_PUNCTUALITY':
          const punctualityResult = await this.checkVisitPunctuality(tenantId, periodStart, periodEnd);
          reportData = punctualityResult.data;
          passRate = punctualityResult.passRate;
          failCount = punctualityResult.failCount;
          break;

        default:
          throw new Error(`Unknown report type: ${reportType}`);
      }

      // Create report
      const report = await this.prisma.complianceReport.create({
        data: {
          tenantId,
          reportType: reportType as any,
          title: `${reportType.replace(/_/g, ' ')} Report`,
          periodStart,
          periodEnd,
          reportData,
          summary: {
            passRate,
            failCount,
            warningCount,
            generatedAt: new Date().toISOString()
          },
          passRate,
          failCount,
          warningCount,
          status: 'COMPLETED',
          generatedAt: new Date(),
          generatedBy
        }
      });

      logger.info(`Compliance report generated: ${report.id}`, {
        reportType,
        passRate,
        failCount,
        warningCount
      });

      return {
        reportId: report.id,
        passRate,
        failCount,
        warningCount
      };

    } catch (error) {
      logger.error('Failed to generate compliance report:', error);
      throw error;
    }
  }

  // Helper methods

  private async checkWTDCompliance(
    tenantId: string,
    periodStart: Date,
    periodEnd: Date
  ): Promise<{
    data: any;
    passRate: number;
    failCount: number;
    warningCount: number;
  }> {
    const timesheets = await this.prisma.timesheet.findMany({
      where: {
        tenantId,
        periodStart: { gte: periodStart },
        periodEnd: { lte: periodEnd }
      },
      include: {
        carer: {
          select: {
            firstName: true,
            lastName: true
          }
        }
      }
    });

    const constraints = await this.prisma.rosteringConstraints.findFirst({
      where: { tenantId, isActive: true }
    });

    const maxHours = constraints?.wtdMaxHoursPerWeek || 48;

    let passCount = 0;
    let failCount = 0;
    let warningCount = 0;

    const carerData = timesheets.map(ts => {
      const compliant = ts.actualHours <= maxHours;
      const warning = ts.actualHours > maxHours * 0.9 && ts.actualHours <= maxHours;

      if (compliant && !warning) passCount++;
      if (!compliant) failCount++;
      if (warning) warningCount++;

      return {
        carerId: ts.carerId,
        carerName: `${ts.carer.firstName} ${ts.carer.lastName}`,
        actualHours: ts.actualHours,
        maxHours,
        compliant,
        warning
      };
    });

    const passRate = timesheets.length > 0 ? (passCount / timesheets.length) * 100 : 100;

    return {
      data: {
        carers: carerData,
        summary: {
          totalCarers: timesheets.length,
          passCount,
          failCount,
          warningCount
        }
      },
      passRate,
      failCount,
      warningCount
    };
  }

  private async checkVisitPunctuality(
    tenantId: string,
    periodStart: Date,
    periodEnd: Date
  ): Promise<{
    data: any;
    passRate: number;
    failCount: number;
  }> {
    const checkIns = await this.prisma.visitCheckIn.findMany({
      where: {
        checkInTime: {
          gte: periodStart,
          lte: periodEnd
        }
      }
    }) as any[];

    let onTimeCount = 0;
    let lateCount = 0;

    const visitData = checkIns.map((checkIn: any) => {
      const scheduled = checkIn.visit?.scheduledStartTime;
      if (!scheduled) return null;

      const delayMinutes = Math.floor(
        (checkIn.checkInTime.getTime() - scheduled.getTime()) / 60000
      );

      const onTime = delayMinutes <= 5; // 5 min tolerance
      if (onTime) onTimeCount++;
      else lateCount++;

      return {
        visitId: checkIn.visitId,
        clientName: checkIn.visit?.requestorName || 'Unknown',
        scheduledTime: scheduled,
        actualCheckIn: checkIn.checkInTime,
        delayMinutes,
        onTime
      };
    }).filter(Boolean);

    const passRate = checkIns.length > 0 ? (onTimeCount / checkIns.length) * 100 : 100;

    return {
      data: {
        visits: visitData,
        summary: {
          totalVisits: checkIns.length,
          onTimeCount,
          lateCount,
          averageDelay: visitData.reduce((sum: number, v: any) => sum + (v?.delayMinutes || 0), 0) / visitData.length
        }
      },
      passRate,
      failCount: lateCount
    };
  }
}




