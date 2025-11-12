import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';

export class TaskController {
  private prisma: PrismaClient;

  // Valid table names that tasks can be related to
  private validRelatedTables = [
    'RiskAssessment',
    'PersonalCare', 
    'EverydayActivityPlan',
    'FallsAndMobility',
    'MedicalInformation',
    'PsychologicalInformation',
    'FoodNutritionHydration',
    'RoutinePreference',
    'CultureValues',
    'BodyMap',
    'MovingHandling',
    'LegalRequirement',
    'CareRequirements'
  ];

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  // Convert a time representation to minutes since midnight (0-1439).
  // Accepts "HH:MM" or "HH:MM:SS" strings, or Date objects (where only the time component is used).
  private timeStringToMinutes(hhmm: string | Date): number | null {
    if (!hhmm) return null;
    if (hhmm instanceof Date) {
      const hh = hhmm.getHours();
      const mm = hhmm.getMinutes();
      return hh * 60 + mm;
    }
    if (typeof hhmm !== 'string') return null;
    const parts = hhmm.split(':');
    if (parts.length < 2) return null;
    const hh = parseInt(parts[0], 10);
    const mm = parseInt(parts[1], 10);
    if (isNaN(hh) || isNaN(mm) || hh < 0 || hh > 23 || mm < 0 || mm > 59) return null;
    return hh * 60 + mm;
  }

  // Map JS Date to DayOfWeek enum string used in DB (MONDAY..SUNDAY)
  private dayOfWeekString(d: Date): string {
    const dow = d.getDay(); // 0 = Sunday, 1 = Monday ...
    switch (dow) {
      case 1: return 'MONDAY';
      case 2: return 'TUESDAY';
      case 3: return 'WEDNESDAY';
      case 4: return 'THURSDAY';
      case 5: return 'FRIDAY';
      case 6: return 'SATURDAY';
      default: return 'SUNDAY';
    }
  }

  // Check whether a given start (and optional end) Date falls within any agreed slot for that day.
  // schedules: array of AgreedCareSchedule objects, each containing `day` and `slots` array with startTime/endTime strings.
  private isWithinAgreedSlots(start: Date, end: Date | null, schedules: any[] | undefined) {
    // If there are no schedules, treat as unrestricted
    if (!schedules || !Array.isArray(schedules) || schedules.length === 0) return { ok: true };

    const dayStr = this.dayOfWeekString(start);
    const matching = schedules.find((s: any) => s && s.day === dayStr && (s.enabled === undefined || s.enabled));
    if (!matching) {
      // Build allowed days summary
      const daysWithSlots = schedules
        .filter((s: any) => s && (s.enabled === undefined || s.enabled) && Array.isArray(s.slots) && s.slots.length)
        .map((s: any) => s.day + ':' + (s.slots || []).map((sl: any) => `${sl.startTime}-${sl.endTime}`).join(',')).slice(0, 10);
      return { ok: false, reason: `No agreed windows for ${dayStr}`, allowed: daysWithSlots };
    }

    const slots = Array.isArray(matching.slots) ? matching.slots : [];
    if (slots.length === 0) return { ok: false, reason: `No slots defined for ${dayStr}`, allowed: [] };

    const startMinutes = start.getHours() * 60 + start.getMinutes();
    let endMinutes: number | null = null;
    if (end) {
      if (end.getDate() !== start.getDate() || end.getMonth() !== start.getMonth() || end.getFullYear() !== start.getFullYear()) {
        return { ok: false, reason: 'Task spans multiple days which is not supported by agreed slots' };
      }
      endMinutes = end.getHours() * 60 + end.getMinutes();
    }

    const allowedSlots: string[] = [];
    for (const sl of slots) {
      const sMin = this.timeStringToMinutes(sl.startTime);
      const eMin = this.timeStringToMinutes(sl.endTime);
      if (sMin === null || eMin === null) continue;
      allowedSlots.push(`${sl.startTime}-${sl.endTime}`);
      // Check containment: start >= sMin && (no end || end <= eMin)
      if (startMinutes >= sMin && (endMinutes === null || endMinutes <= eMin)) {
        return { ok: true, slot: `${sl.startTime}-${sl.endTime}` };
      }
    }

    return { ok: false, reason: `Requested time not within any agreed slots for ${dayStr}`, allowed: allowedSlots };
  }

  private validateCreatePayload(body: any) {
    const errors: string[] = [];
    if (!body) errors.push('body required');
    if (!body.carePlanId || typeof body.carePlanId !== 'string') errors.push('carePlanId is required and must be a string');
    if (!body.relatedTable || typeof body.relatedTable !== 'string') errors.push('relatedTable is required and must be a string');
    if (!body.relatedId || typeof body.relatedId !== 'string') errors.push('relatedId is required and must be a string');
    if (!body.title || typeof body.title !== 'string') errors.push('title is required and must be a string');
    if (!body.description || typeof body.description !== 'string') errors.push('description is required and must be a string');
    if (!body.riskFrequency || typeof body.riskFrequency !== 'string') errors.push('riskFrequency is required and must be a string');
    
    if (body.relatedTable && !this.validRelatedTables.includes(body.relatedTable)) {
      errors.push(`relatedTable must be one of: ${this.validRelatedTables.join(', ')}`);
    }
    
    if (body.status && !['PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ON_HOLD'].includes(body.status)) {
      errors.push('status must be one of: PENDING, IN_PROGRESS, COMPLETED, CANCELLED, ON_HOLD');
    }

    if (body.riskCategory && !Array.isArray(body.riskCategory)) {
      errors.push('riskCategory must be an array of strings');
    }

    return errors;
  }

  private toDateOrNull(val: any) {
    if (!val) return null;
    const d = new Date(val);
    return isNaN(d.getTime()) ? null : d;
  }

  // Create a new task
  public async createTask(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const payload = req.body || {};
      const errors = this.validateCreatePayload(payload);
      if (errors.length) return res.status(400).json({ errors });

      // Verify the care plan exists and belongs to this tenant
      // Also load careRequirements -> schedules -> slots so we can validate agreed windows
      const carePlan = await (this.prisma as any).carePlan.findUnique({
        where: { id: payload.carePlanId },
        include: {
          careRequirements: {
            include: {
              schedules: {
                include: { slots: true }
              }
            }
          }
        }
      });

      if (!carePlan) {
        return res.status(404).json({ error: 'Care plan not found' });
      }

      if (carePlan.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: 'Access denied to this care plan' });
      }

      // If start/due times are provided, validate against the client's agreed care schedule slots
      if (payload.startDate) {
        const start = new Date(payload.startDate);
        if (isNaN(start.getTime())) return res.status(400).json({ error: 'Invalid startDate' });
        const end = payload.dueDate ? new Date(payload.dueDate) : null;
        if (end && isNaN(end.getTime())) return res.status(400).json({ error: 'Invalid dueDate' });

        const schedules = carePlan.careRequirements ? (Array.isArray(carePlan.careRequirements.schedules) ? carePlan.careRequirements.schedules : []) : [];
        const check = this.isWithinAgreedSlots(start, end, schedules);
        if (!check.ok) {
          return res.status(400).json({ success: false, error: 'Outside agreed care windows', details: check });
        }
      }

      const data: any = {
        tenantId: tenantId.toString(),
        carePlanId: payload.carePlanId,
        relatedTable: payload.relatedTable,
        relatedId: payload.relatedId,
        title: payload.title,
        description: payload.description,
        riskFrequency: payload.riskFrequency,
      };

      if (payload.status) data.status = payload.status;
      if (payload.startDate) data.startDate = this.toDateOrNull(payload.startDate);
      if (payload.dueDate) data.dueDate = this.toDateOrNull(payload.dueDate);
      if (payload.additionalNotes !== undefined) data.additionalNotes = payload.additionalNotes;
      if (payload.createdBy) data.createdBy = payload.createdBy;
      if (Array.isArray(payload.riskCategory)) data.riskCategory = payload.riskCategory;

      const created = await (this.prisma as any).task.create({
        data,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true
            }
          }
        }
      });

      return res.status(201).json(created);
    } catch (error: any) {
      console.error('createTask error', error);
      return res.status(500).json({ error: 'Failed to create task', details: error?.message });
    }
  }

  // Get tasks for a specific care plan
  public async getTasksByCarePlan(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const carePlanId = req.params.carePlanId;
      if (!carePlanId) return res.status(400).json({ error: 'carePlanId required in path' });

      // Optional filters from query params
      const relatedTable = req.query.relatedTable as string;
      const status = req.query.status as string;

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId
      };

      if (relatedTable) where.relatedTable = relatedTable;
      if (status) where.status = status;

      const tasks = await (this.prisma as any).task.findMany({
        where,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true
            }
          }
        },
        orderBy: [
          { status: 'asc' },
          { dueDate: 'asc' },
          { createdAt: 'desc' }
        ]
      });

      return res.json(tasks);
    } catch (error: any) {
      console.error('getTasksByCarePlan error', error);
      return res.status(500).json({ error: 'Failed to fetch tasks', details: error?.message });
    }
  }

  // Get tasks for a specific client (across all their care plans)
  public async getTasksByClient(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const clientId = req.params.clientId;
      if (!clientId) return res.status(400).json({ error: 'clientId required in path' });

      // Optional filters from query params
      const relatedTable = req.query.relatedTable as string;
      const status = req.query.status as string;

      // First find all care plans for this client
      const carePlans = await (this.prisma as any).carePlan.findMany({
        where: {
          tenantId: tenantId.toString(),
          clientId
        },
        select: { id: true }
      });

      const carePlanIds = carePlans.map((cp: any) => cp.id);
      if (!carePlanIds.length) return res.json([]);

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId: { in: carePlanIds }
      };

      if (relatedTable) where.relatedTable = relatedTable;
      if (status) where.status = status;

      const tasks = await (this.prisma as any).task.findMany({
        where,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true
            }
          }
        },
        orderBy: [
          { status: 'asc' },
          { dueDate: 'asc' },
          { createdAt: 'desc' }
        ]
      });

      return res.json(tasks);
    } catch (error: any) {
      console.error('getTasksByClient error', error);
      return res.status(500).json({ error: 'Failed to fetch tasks for client', details: error?.message });
    }
  }

  // Get tasks for a specific client and related table (e.g., all RiskAssessment tasks for client)
  public async getTasksByClientAndTable(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const clientId = req.params.clientId;
      const relatedTable = req.params.relatedTable;
      
      if (!clientId) return res.status(400).json({ error: 'clientId required in path' });
      if (!relatedTable) return res.status(400).json({ error: 'relatedTable required in path' });

      // Validate relatedTable
      if (!this.validRelatedTables.includes(relatedTable)) {
        return res.status(400).json({ 
          error: `Invalid relatedTable. Must be one of: ${this.validRelatedTables.join(', ')}` 
        });
      }

      // Optional status filter from query params
      const status = req.query.status as string;

      // First find all care plans for this client
      const carePlans = await (this.prisma as any).carePlan.findMany({
        where: {
          tenantId: tenantId.toString(),
          clientId
        },
        select: { id: true }
      });

      const carePlanIds = carePlans.map((cp: any) => cp.id);
      if (!carePlanIds.length) return res.json([]);

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId: { in: carePlanIds },
        relatedTable
      };

      if (status) where.status = status;

      const tasks = await (this.prisma as any).task.findMany({
        where,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true
            }
          }
        },
        orderBy: [
          { status: 'asc' },
          { dueDate: 'asc' },
          { createdAt: 'desc' }
        ]
      });

      return res.json({
        clientId,
        relatedTable,
        tasks
      });
    } catch (error: any) {
      console.error('getTasksByClientAndTable error', error);
      return res.status(500).json({ error: 'Failed to fetch tasks for client and table', details: error?.message });
    }
  }

  // Get tasks assigned to a carer (via CarePlanCarer relationships)
  public async getTasksByCarer(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const carerId = req.params.carerId;
      if (!carerId) return res.status(400).json({ error: 'carerId required in path' });

      // Find all care plans this carer is assigned to
      const careLinks = await (this.prisma as any).carePlanCarer.findMany({
        where: {
          tenantId: tenantId.toString(),
          carerId
        },
        select: { carePlanId: true }
      });

      const carePlanIds = careLinks.map((link: any) => link.carePlanId);
      if (!carePlanIds.length) return res.json([]);

      // Optional filters from query params
      const relatedTable = req.query.relatedTable as string;
      const status = req.query.status as string;

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId: { in: carePlanIds }
      };

      if (relatedTable) where.relatedTable = relatedTable;
      if (status) where.status = status;

      const tasks = await (this.prisma as any).task.findMany({
        where,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true
            }
          }
        },
        orderBy: [
          { status: 'asc' },
          { dueDate: 'asc' },
          { createdAt: 'desc' }
        ]
      });

      return res.json(tasks);
    } catch (error: any) {
      console.error('getTasksByCarer error', error);
      return res.status(500).json({ error: 'Failed to fetch tasks for carer', details: error?.message });
    }
  }

  // List all tasks for the requesting tenant with optional pagination and filters
  public async listTenantTasks(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const page = parseInt((req.query.page as string) || '1', 10);
      const pageSize = parseInt((req.query.pageSize as string) || '50', 10);
      const skip = (Math.max(page, 1) - 1) * pageSize;

      // Optional filters
      const relatedTable = req.query.relatedTable as string | undefined;
      const status = req.query.status as string | undefined;
      const carePlanId = req.query.carePlanId as string | undefined;
      const clientId = req.query.clientId as string | undefined;

      const where: any = { tenantId: tenantId.toString() };

      if (relatedTable) where.relatedTable = relatedTable;
      if (status) where.status = status;
      if (carePlanId) where.carePlanId = carePlanId;

      // If clientId is supplied, resolve to carePlanIds
      if (clientId) {
        const cps = await (this.prisma as any).carePlan.findMany({ where: { tenantId: tenantId.toString(), clientId }, select: { id: true } });
        const cpIds = cps.map((c: any) => c.id);
        if (!cpIds.length) return res.json({ items: [], total: 0, page, pageSize });
        where.carePlanId = { in: cpIds };
      }

      const [items, total] = await Promise.all([
        (this.prisma as any).task.findMany({
          where,
          include: {
            carePlan: { select: { id: true, clientId: true, title: true } }
          },
          orderBy: [
            { status: 'asc' },
            { dueDate: 'asc' },
            { createdAt: 'desc' }
          ],
          skip,
          take: pageSize,
        }),
        (this.prisma as any).task.count({ where })
      ]);

      return res.json({ items, total, page, pageSize });
    } catch (error: any) {
      console.error('listTenantTasks error', error);
      return res.status(500).json({ error: 'Failed to list tenant tasks', details: error?.message });
    }
  }

  // Update a task
  public async updateTask(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const taskId = req.params.taskId;
      if (!taskId) return res.status(400).json({ error: 'taskId required in path' });

      const payload = req.body || {};

      // Find the task and verify ownership
      const existingTask = await (this.prisma as any).task.findUnique({
        where: { id: taskId },
        select: { id: true, tenantId: true, status: true }
      });

      if (!existingTask) {
        return res.status(404).json({ error: 'Task not found' });
      }

      if (existingTask.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: 'Access denied to this task' });
      }

      const updateData: any = {};

      if (payload.title !== undefined) updateData.title = payload.title;
      if (payload.description !== undefined) updateData.description = payload.description;
      if (payload.status !== undefined) {
        updateData.status = payload.status;
        // Auto-set completedAt when status changes to COMPLETED
        if (payload.status === 'COMPLETED' && existingTask.status !== 'COMPLETED') {
          updateData.completedAt = new Date();
        }
        // Clear completedAt if status changes away from COMPLETED
        if (payload.status !== 'COMPLETED' && existingTask.status === 'COMPLETED') {
          updateData.completedAt = null;
        }
      }
      if (payload.riskFrequency !== undefined) updateData.riskFrequency = payload.riskFrequency;
      if (payload.startDate !== undefined) updateData.startDate = this.toDateOrNull(payload.startDate);
      if (payload.dueDate !== undefined) updateData.dueDate = this.toDateOrNull(payload.dueDate);
      if (payload.additionalNotes !== undefined) updateData.additionalNotes = payload.additionalNotes;
      if (Array.isArray(payload.riskCategory)) updateData.riskCategory = payload.riskCategory;

      const updated = await (this.prisma as any).task.update({
        where: { id: taskId },
        data: updateData,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true
            }
          }
        }
      });

      return res.json(updated);
    } catch (error: any) {
      console.error('updateTask error', error);
      return res.status(500).json({ error: 'Failed to update task', details: error?.message });
    }
  }

  // Delete a task
  public async deleteTask(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const taskId = req.params.taskId;
      if (!taskId) return res.status(400).json({ error: 'taskId required in path' });

      // Find the task and verify ownership
      const existingTask = await (this.prisma as any).task.findUnique({
        where: { id: taskId },
        select: { id: true, tenantId: true }
      });

      if (!existingTask) {
        return res.status(404).json({ error: 'Task not found' });
      }

      if (existingTask.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: 'Access denied to this task' });
      }

      await (this.prisma as any).task.delete({
        where: { id: taskId }
      });

      return res.status(204).send();
    } catch (error: any) {
      console.error('deleteTask error', error);
      return res.status(500).json({ error: 'Failed to delete task', details: error?.message });
    }
  }

  // Get a single task by ID
  public async getTaskById(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const taskId = req.params.taskId;
      if (!taskId) return res.status(400).json({ error: 'taskId required in path' });

      const task = await (this.prisma as any).task.findUnique({
        where: { id: taskId },
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true
            }
          }
        }
      });

      if (!task) {
        return res.status(404).json({ error: 'Task not found' });
      }

      if (task.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: 'Access denied to this task' });
      }

      return res.json(task);
    } catch (error: any) {
      console.error('getTaskById error', error);
      return res.status(500).json({ error: 'Failed to fetch task', details: error?.message });
    }
  }
}