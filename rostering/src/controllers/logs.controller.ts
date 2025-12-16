import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { format } from 'date-fns';

export class LogsController {
  private prisma: PrismaClient;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  // Helper to format date-time for logs
  private formatDateTime(d: Date | null | undefined): string | null {
    if (!d) return null;
    try {
      // e.g. "12 January 2025 at 4:03am"
      return format(d, "d LLLL yyyy 'at' h:mma").replace('AM', 'am').replace('PM', 'pm');
    } catch (e) {
      return d.toISOString();
    }
  }

  // Helper to map task status for logs
  private mapStatus(s: string | null | undefined): string {
    if (!s) return 'Unknown';
    switch (s) {
      case 'PENDING': return 'Pending';
      case 'IN_PROGRESS': return 'In Progress';
      case 'COMPLETED': return 'Completed';
      case 'MISSED': return 'Missed';
      case 'CANCELLED': return 'Cancelled';
      case 'ON_HOLD': return 'On Hold';
      default: return s;
    }
  }

  // Get logs for a specific visit (client_visit_logs)
  public async getVisitLogs(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId) ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const visitId = req.params.visitId;
      if (!visitId) return res.status(400).json({ error: 'visitId required in path' });

      // Optional filters
      const action = req.query.action as string | undefined;
      const since = req.query.since as string | undefined;
      const limit = Math.min(Math.max(parseInt((req.query.limit as string) || '100', 10), 1), 1000);

      const where: any = { tenantId: tenantId.toString(), visitId };
      // Only allow task-level actions in the visit logs. Accept TASK_COMPLETED and TASK_MISSED.
      if (action) {
        if (action !== 'TASK_COMPLETED' && action !== 'TASK_MISSED') {
          return res.json([]);
        }
        where.action = action;
      } else {
        // default to task actions only (both completed and missed)
        where.action = { in: ['TASK_COMPLETED', 'TASK_MISSED'] };
      }
      if (since) {
        const d = new Date(since);
        if (!isNaN(d.getTime())) where.createdAt = { gte: d };
      }

      // If caller requests raw logs, return the client_visit_logs rows
      const raw = (req.query.raw as string | undefined) === 'true';
      if (raw) {
        const logs = await (this.prisma as any).clientVisitLog.findMany({
          where,
          orderBy: { createdAt: 'desc' },
          take: limit,
        });
        return res.json(logs);
      }

      // Otherwise return a simplified visit-log view derived from tasks attached to the visit
      // Only include tasks with status COMPLETED or MISSED in the visit-log simplified view
      const tasks: any[] = await (this.prisma as any).task.findMany({
        where: { tenantId: tenantId.toString(), carerVisitId: visitId, status: { in: ['COMPLETED', 'MISSED'] } },
        select: { id: true, title: true, status: true, dueDate: true, completedAt: true, additionalNotes: true, updatedAt: true, createdAt: true },
        orderBy: { createdAt: 'desc' },
      });

      // Get performedById from ClientVisitLog for each task
      const taskIds = tasks.map(t => t.id);
      const logs = await (this.prisma as any).clientVisitLog.findMany({
        where: {
          tenantId: tenantId.toString(),
          visitId,
          taskId: { in: taskIds },
          action: { in: ['TASK_COMPLETED', 'TASK_MISSED'] }
        },
        select: { taskId: true, performedById: true }
      });

      // Create a map of taskId to performedById
      const performedByMap = new Map(logs.map((log: any) => [log.taskId, log.performedById]));

      const simplified = tasks.map(t => {
        const date = t.completedAt ?? t.dueDate ?? t.updatedAt ?? t.createdAt;
        return {
          task: t.title,
          status: this.mapStatus(t.status),
          dateTime: this.formatDateTime(date),
          comment: t.additionalNotes ?? null,
          taskId: t.id,
          performedById: performedByMap.get(t.id) || null,
        };
      }).sort((a, b) => {
        const ad = a.dateTime ? new Date(a.dateTime) : new Date(0);
        const bd = b.dateTime ? new Date(b.dateTime) : new Date(0);
        return bd.getTime() - ad.getTime();
      });

      return res.json(simplified);
    } catch (error: any) {
      console.error('getVisitLogs error', error);
      return res.status(500).json({ error: 'Failed to fetch visit logs', details: error?.message });
    }
  }

  // Get all logs for the tenant
  public async getAllLogs(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId) ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      // Optional filters
      const action = req.query.action as string | undefined;
      const since = req.query.since as string | undefined;
      const visitId = req.query.visitId as string | undefined;
      const clientId = req.query.clientId as string | undefined;
      const limit = Math.min(Math.max(parseInt((req.query.limit as string) || '100', 10), 1), 1000);

      const where: any = { tenantId: tenantId.toString() };
      
      // Filter by visitId if provided
      if (visitId) {
        where.visitId = visitId;
      }

      // Filter by clientId if provided - join through CarerVisit
      let visitIds: string[] | undefined;
      if (clientId) {
        const carerVisits = await (this.prisma as any).carerVisit.findMany({
          where: { 
            tenantId: tenantId.toString(),
            clientId: clientId
          },
          select: { id: true }
        });
        visitIds = carerVisits.map((cv: any) => cv.id);
        if (!visitIds || visitIds.length === 0) {
          // No visits found for this client, return empty result
          return res.json([]);
        }
        where.visitId = { in: visitIds };
      }

      // Only allow task-level actions in the logs. Accept TASK_COMPLETED and TASK_MISSED.
      if (action) {
        if (action !== 'TASK_COMPLETED' && action !== 'TASK_MISSED') {
          return res.json([]);
        }
        where.action = action;
      } else {
        // default to task actions only (both completed and missed)
        where.action = { in: ['TASK_COMPLETED', 'TASK_MISSED'] };
      }
      
      if (since) {
        const d = new Date(since);
        if (!isNaN(d.getTime())) where.createdAt = { gte: d };
      }

      // If caller requests raw logs, return the client_visit_logs rows
      const raw = (req.query.raw as string | undefined) === 'true';
      if (raw) {
        const logs = await (this.prisma as any).clientVisitLog.findMany({
          where,
          include: {
            carerVisit: {
              select: {
                clientId: true
              }
            }
          },
          orderBy: { createdAt: 'desc' },
          take: limit,
        });
        return res.json(logs);
      }

      // Otherwise return a simplified log view derived from tasks
      // Only include tasks with status COMPLETED or MISSED in the simplified view
      const taskWhere: any = { 
        tenantId: tenantId.toString(), 
        status: { in: ['COMPLETED', 'MISSED'] }
      };
      
      // Apply visitId or clientId filtering to tasks
      if (visitId) {
        taskWhere.carerVisitId = visitId;
      } else if (visitIds && visitIds.length > 0) {
        taskWhere.carerVisitId = { in: visitIds };
      }

      const tasks: any[] = await (this.prisma as any).task.findMany({
        where: taskWhere,
        select: { 
          id: true, 
          title: true, 
          status: true, 
          dueDate: true, 
          completedAt: true, 
          additionalNotes: true, 
          updatedAt: true, 
          createdAt: true,
          carerVisitId: true,
          carerVisit: {
            select: {
              clientId: true
            }
          }
        },
        orderBy: { createdAt: 'desc' },
        take: limit,
      });

      // Get performedById from ClientVisitLog for each task
      const taskIds = tasks.map(t => t.id);
      const logsWhere: any = {
        tenantId: tenantId.toString(),
        taskId: { in: taskIds },
        action: { in: ['TASK_COMPLETED', 'TASK_MISSED'] }
      };
      
      // Apply the same visitId/clientId filtering to logs
      if (visitId) {
        logsWhere.visitId = visitId;
      } else if (visitIds && visitIds.length > 0) {
        logsWhere.visitId = { in: visitIds };
      }

      const logs = await (this.prisma as any).clientVisitLog.findMany({
        where: logsWhere,
        select: { taskId: true, performedById: true }
      });

      // Create a map of taskId to performedById
      const performedByMap = new Map(logs.map((log: any) => [log.taskId, log.performedById]));

      const simplified = tasks.map(t => {
        const date = t.completedAt ?? t.dueDate ?? t.updatedAt ?? t.createdAt;
        return {
          task: t.title,
          status: this.mapStatus(t.status),
          dateTime: this.formatDateTime(date),
          comment: t.additionalNotes ?? null,
          taskId: t.id,
          visitId: t.carerVisitId,
          clientId: t.carerVisit?.clientId,
          performedById: performedByMap.get(t.id) || null,
        };
      }).sort((a, b) => {
        const ad = a.dateTime ? new Date(a.dateTime) : new Date(0);
        const bd = b.dateTime ? new Date(b.dateTime) : new Date(0);
        return bd.getTime() - ad.getTime();
      });

      return res.json(simplified);
    } catch (error: any) {
      console.error('getAllLogs error', error);
      return res.status(500).json({ error: 'Failed to fetch all logs', details: error?.message });
    }
  }
}