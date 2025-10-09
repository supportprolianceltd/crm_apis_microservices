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

  private validateCreatePayload(body: any) {
    const errors: string[] = [];
    if (!body) errors.push('body required');
    if (!body.carePlanId || typeof body.carePlanId !== 'string') errors.push('carePlanId is required and must be a string');
    if (!body.relatedTable || typeof body.relatedTable !== 'string') errors.push('relatedTable is required and must be a string');
    if (!body.relatedId || typeof body.relatedId !== 'string') errors.push('relatedId is required and must be a string');
    if (!body.title || typeof body.title !== 'string') errors.push('title is required and must be a string');
    
    if (body.relatedTable && !this.validRelatedTables.includes(body.relatedTable)) {
      errors.push(`relatedTable must be one of: ${this.validRelatedTables.join(', ')}`);
    }
    
    if (body.status && !['PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ON_HOLD'].includes(body.status)) {
      errors.push('status must be one of: PENDING, IN_PROGRESS, COMPLETED, CANCELLED, ON_HOLD');
    }
    
    if (body.priority && !['LOW', 'MEDIUM', 'HIGH', 'URGENT'].includes(body.priority)) {
      errors.push('priority must be one of: LOW, MEDIUM, HIGH, URGENT');
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
      const carePlan = await (this.prisma as any).carePlan.findUnique({
        where: { id: payload.carePlanId },
        select: { id: true, tenantId: true, clientId: true }
      });

      if (!carePlan) {
        return res.status(404).json({ error: 'Care plan not found' });
      }

      if (carePlan.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: 'Access denied to this care plan' });
      }

      const data: any = {
        tenantId: tenantId.toString(),
        carePlanId: payload.carePlanId,
        relatedTable: payload.relatedTable,
        relatedId: payload.relatedId,
        title: payload.title,
      };

      if (payload.description !== undefined) data.description = payload.description;
      if (payload.status) data.status = payload.status;
      if (payload.priority) data.priority = payload.priority;
      if (payload.dueDate) data.dueDate = this.toDateOrNull(payload.dueDate);
      if (payload.notes !== undefined) data.notes = payload.notes;
      if (payload.createdBy) data.createdBy = payload.createdBy;
      if (Array.isArray(payload.attachments)) data.attachments = payload.attachments;

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
      const priority = req.query.priority as string;

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId
      };

      if (relatedTable) where.relatedTable = relatedTable;
      if (status) where.status = status;
      if (priority) where.priority = priority;

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
          { priority: 'desc' },
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
          { priority: 'desc' },
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
          { priority: 'desc' },
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
          { priority: 'desc' },
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
      if (payload.priority !== undefined) updateData.priority = payload.priority;
      if (payload.dueDate !== undefined) updateData.dueDate = this.toDateOrNull(payload.dueDate);
      if (payload.notes !== undefined) updateData.notes = payload.notes;
      if (Array.isArray(payload.attachments)) updateData.attachments = payload.attachments;

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