import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { format } from 'date-fns';
import { TravelService } from '../services/travel.service';

export class TaskController {
  private prisma: PrismaClient;
  private travelService: TravelService;

  // Map careType enum to assignment capacity (null means unlimited)
  private careTypeCapacity(ct?: string | null): number | null {
    if (!ct) return null;
    switch (ct) {
      case 'SINGLE_HANDED_CALL':
        return 1;
      case 'DOUBLE_HANDED_CALL':
        return 2;
      case 'SPECIALCARE':
        return null;
      default:
        return null;
    }
  }

  // Patch a visit (partial update) - supports updating careType with required switch reason/comment
  public async updateVisit(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId) ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const visitId = req.params.visitId;
      if (!visitId) return res.status(400).json({ error: 'visitId required in path' });

      const payload = req.body || {};

      const existing = await (this.prisma as any).carerVisit.findUnique({ where: { id: visitId } });
      if (!existing) return res.status(404).json({ error: 'Visit not found' });
      if (existing.tenantId !== tenantId.toString()) return res.status(403).json({ error: 'Access denied to this visit' });

      const updateData: any = {};

      // Only allow updating careType, startDate, endDate for now
      if (payload.startDate !== undefined) updateData.startDate = this.toDateOrNull(payload.startDate);
      if (payload.endDate !== undefined) updateData.endDate = this.toDateOrNull(payload.endDate);

      // Handle careType change with validation for switchReason/switchComment
      if (payload.careType !== undefined) {
        const newCareType = payload.careType as string | null;
        const oldCareType = existing.careType as string | null;
        if (newCareType !== oldCareType) {
          // require switchReason and switchComment
          const switchReason = payload.switchReason as string | undefined;
          const switchComment = payload.switchComment as string | undefined;
          if (!switchReason || typeof switchReason !== 'string') {
            return res.status(400).json({ error: 'switchReason is required when changing careType' });
          }
          if (!switchComment || typeof switchComment !== 'string') {
            return res.status(400).json({ error: 'switchComment is required when changing careType' });
          }
          updateData.careType = newCareType;
          updateData.switchReason = switchReason;
          updateData.switchComment = switchComment;
        }
      }

      if (Object.keys(updateData).length === 0) return res.status(400).json({ error: 'No updatable fields provided' });

      const updated = await (this.prisma as any).carerVisit.update({ where: { id: visitId }, data: updateData });

      // NOTE: visit-level actions (care type changes) are no longer written to client_visit_logs.
      // Only task-level actions (TASK_COMPLETED) are recorded in that table per product decision.

      return res.json(updated);
    } catch (error: any) {
      console.error('updateVisit error', error);
      return res.status(500).json({ error: 'Failed to update visit', details: error?.message });
    }
  }

  // Valid table names that tasks can be related to
  private validRelatedTables = [
    "RiskAssessment",
    "PersonalCare",
    "EverydayActivityPlan",
    "FallsAndMobility",
    "MedicalInformation",
    "PsychologicalInformation",
    "FoodNutritionHydration",
    "RoutinePreference",
    "CultureValues",
    "BodyMap",
    "MovingHandling",
    "LegalRequirement",
    "CareRequirements",
  ];

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
    this.travelService = new TravelService(prisma);
  }

  // Mark overdue tasks as MISSED when dueDate has passed and write client_visit_logs entries
  private async markOverdueTasks(tenantId: string) {
    if (!tenantId) return;
    try {
      const now = new Date();

      // Find candidate tasks
      const candidates: any[] = await (this.prisma as any).task.findMany({
        where: {
          tenantId: tenantId.toString(),
          dueDate: { lt: now },
          status: { in: ['PENDING', 'IN_PROGRESS'] },
        },
        select: { id: true, tenantId: true, carerVisitId: true, status: true },
      });

      if (!candidates || candidates.length === 0) return;

      const nowIso = now.toISOString();
      const logs = candidates
        .filter((t: any) => t.carerVisitId)
        .map((t: any) => ({
          tenantId: t.tenantId,
          visitId: t.carerVisitId,
          action: 'TASK_MISSED',
          taskId: t.id,
          performedById: 'system',
          details: JSON.stringify({ taskId: t.id, previousStatus: t.status, markedAt: nowIso }),
        }));

      try {
        const taskIds = candidates.map((t: any) => t.id);
        await (this.prisma as any).$transaction(async (tx: any) => {
          if (logs.length > 0) {
            try {
              await tx.clientVisitLog.createMany({ data: logs, skipDuplicates: true });
            } catch (e) {
              for (const l of logs) {
                try { await tx.clientVisitLog.create({ data: l }); } catch (err) { /* ignore */ }
              }
            }
          }

          await tx.task.updateMany({ where: { id: { in: taskIds } }, data: { status: 'MISSED' } });
        });

        console.debug(`Marked ${candidates.length} overdue tasks as MISSED for tenant ${tenantId} and wrote ${logs.length} client_visit_logs`);
      } catch (e) {
        console.error('Failed to mark overdue tasks (transaction)', e);
      }
    } catch (e) {
      console.error('Failed to mark overdue tasks', e);
    }
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
    if (typeof hhmm !== "string") return null;
    const parts = hhmm.split(":");
    if (parts.length < 2) return null;
    const hh = parseInt(parts[0], 10);
    const mm = parseInt(parts[1], 10);
    if (isNaN(hh) || isNaN(mm) || hh < 0 || hh > 23 || mm < 0 || mm > 59)
      return null;
    return hh * 60 + mm;
  }

  // Map JS Date to DayOfWeek enum string used in DB (MONDAY..SUNDAY)
  private dayOfWeekString(d: Date): string {
    const dow = d.getDay(); // 0 = Sunday, 1 = Monday ...
    switch (dow) {
      case 1:
        return "MONDAY";
      case 2:
        return "TUESDAY";
      case 3:
        return "WEDNESDAY";
      case 4:
        return "THURSDAY";
      case 5:
        return "FRIDAY";
      case 6:
        return "SATURDAY";
      default:
        return "SUNDAY";
    }
  }

  // Check whether a given start (and optional end) Date falls within any agreed slot for that day.
  // schedules: array of AgreedCareSchedule objects, each containing `day` and `slots` array with startTime/endTime strings.
  private isWithinAgreedSlots(
    start: Date,
    end: Date | null,
    schedules: any[] | undefined
  ) {
    // If there are no schedules, treat as unrestricted
    if (!schedules || !Array.isArray(schedules) || schedules.length === 0)
      return { ok: true };

    const dayStr = this.dayOfWeekString(start);
    const matching = schedules.find(
      (s: any) =>
        s && s.day === dayStr && (s.enabled === undefined || s.enabled)
    );
    if (!matching) {
      // Build allowed days summary
      const daysWithSlots = schedules
        .filter(
          (s: any) =>
            s &&
            (s.enabled === undefined || s.enabled) &&
            Array.isArray(s.slots) &&
            s.slots.length
        )
        .map(
          (s: any) =>
            s.day +
            ":" +
            (s.slots || [])
              .map((sl: any) => `${sl.startTime}-${sl.endTime}`)
              .join(",")
        )
        .slice(0, 10);
      return {
        ok: false,
        reason: `No agreed windows for ${dayStr}`,
        allowed: daysWithSlots,
      };
    }

    const slots = Array.isArray(matching.slots) ? matching.slots : [];
    if (slots.length === 0)
      return {
        ok: false,
        reason: `No slots defined for ${dayStr}`,
        allowed: [],
      };

    const startMinutes = start.getHours() * 60 + start.getMinutes();
    let endMinutes: number | null = null;
    if (end) {
      if (
        end.getDate() !== start.getDate() ||
        end.getMonth() !== start.getMonth() ||
        end.getFullYear() !== start.getFullYear()
      ) {
        return {
          ok: false,
          reason:
            "Task spans multiple days which is not supported by agreed slots",
        };
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

    return {
      ok: false,
      reason: `Requested time not within any agreed slots for ${dayStr}`,
      allowed: allowedSlots,
    };
  }

  private validateCreatePayload(body: any) {
    const errors: string[] = [];
    if (!body) errors.push("body required");
    if (!body.carePlanId || typeof body.carePlanId !== "string")
      errors.push("carePlanId is required and must be a string");
    if (!body.relatedTable || typeof body.relatedTable !== "string")
      errors.push("relatedTable is required and must be a string");
    if (!body.relatedId || typeof body.relatedId !== "string")
      errors.push("relatedId is required and must be a string");
    if (!body.title || typeof body.title !== "string")
      errors.push("title is required and must be a string");
    if (!body.description || typeof body.description !== "string")
      errors.push("description is required and must be a string");
    if (!body.riskFrequency || typeof body.riskFrequency !== "string")
      errors.push("riskFrequency is required and must be a string");

    if (
      body.relatedTable &&
      !this.validRelatedTables.includes(body.relatedTable)
    ) {
      errors.push(
        `relatedTable must be one of: ${this.validRelatedTables.join(", ")}`
      );
    }

    if (
      body.status &&
      !["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED", "ON_HOLD"].includes(
        body.status
      )
    ) {
      errors.push(
        "status must be one of: PENDING, IN_PROGRESS, COMPLETED, CANCELLED, ON_HOLD"
      );
    }

    if (body.riskCategory && !Array.isArray(body.riskCategory)) {
      errors.push("riskCategory must be an array of strings");
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
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      // Ensure overdue tasks are marked as MISSED before returning tasks for a client
      await this.markOverdueTasks(tenantId.toString());

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
                include: { slots: true },
              },
            },
          },
        },
      });

      if (!carePlan) {
        return res.status(404).json({ error: "Care plan not found" });
      }

      if (carePlan.tenantId !== tenantId.toString()) {
        return res
          .status(403)
          .json({ error: "Access denied to this care plan" });
      }

      // If start/due times are provided, validate against the client's agreed care schedule slots
      if (payload.startDate) {
        const start = new Date(payload.startDate);
        if (isNaN(start.getTime()))
          return res.status(400).json({ error: "Invalid startDate" });
        const end = payload.dueDate ? new Date(payload.dueDate) : null;
        if (end && isNaN(end.getTime()))
          return res.status(400).json({ error: "Invalid dueDate" });

        const schedules = carePlan.careRequirements
          ? Array.isArray(carePlan.careRequirements.schedules)
            ? carePlan.careRequirements.schedules
            : []
          : [];
        const check = this.isWithinAgreedSlots(start, end, schedules);
        if (!check.ok) {
          return res
            .status(400)
            .json({
              success: false,
              error: "Outside agreed care windows",
              details: check,
            });
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
      if (payload.startDate)
        data.startDate = this.toDateOrNull(payload.startDate);
      if (payload.dueDate) data.dueDate = this.toDateOrNull(payload.dueDate);
      if (payload.additionalNotes !== undefined)
        data.additionalNotes = payload.additionalNotes;
      if (payload.createdBy) data.createdBy = payload.createdBy;
      if (Array.isArray(payload.riskCategory))
        data.riskCategory = payload.riskCategory;

      const created = await (this.prisma as any).task.create({
        data,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true,
            },
          },
        },
      });

      // If caller requested pushToVisit, attach task to an existing CarerVisit that fully contains the task window
      if (payload.pushToVisit) {
        const taskStart: Date | null = data.startDate ? new Date(data.startDate) : created.startDate ? new Date(created.startDate) : null;
        const taskEnd: Date | null = data.dueDate ? new Date(data.dueDate) : created.dueDate ? new Date(created.dueDate) : null;

        if (!taskStart) {
          // cannot match a visit without a start time
          return res.status(400).json({ error: 'pushToVisit requires task.startDate to be provided' });
        }

        const visitWhere: any = {
          tenantId: tenantId.toString(),
          carePlanId: payload.carePlanId,
          startDate: { lte: taskStart },
        };
        if (taskEnd) {
          visitWhere.endDate = { gte: taskEnd };
        } else {
          // if no end date, require visit endDate >= taskStart
          visitWhere.endDate = { gte: taskStart };
        }

        const matched = await (this.prisma as any).carerVisit.findFirst({
          where: visitWhere,
          orderBy: { startDate: 'asc' },
        });

        if (!matched) {
          // Per policy: tasks don't create visits. Fail fast and ask caller to ensure visits exist on care plan
          return res.status(400).json({ error: 'No matching visit found for the provided task times; please select a time from the visit window.' });
        }

        const updated = await (this.prisma as any).task.update({
          where: { id: created.id },
          data: { carerVisitId: matched.id, pushToVisit: true },
          include: { carePlan: { select: { id: true, clientId: true, title: true } } },
        });

        return res.status(201).json(updated);
      }

      return res.status(201).json(created);
    } catch (error: any) {
      console.error("createTask error", error);
      return res
        .status(500)
        .json({ error: "Failed to create task", details: error?.message });
    }
  }

  // Get tasks for a specific care plan
  public async getTasksByCarePlan(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      // Ensure overdue tasks are marked as MISSED before returning filtered tasks
      await this.markOverdueTasks(tenantId.toString());

      // Ensure overdue tasks are marked as MISSED before returning a task
      await this.markOverdueTasks(tenantId.toString());

      const carePlanId = req.params.carePlanId;
      if (!carePlanId)
        return res.status(400).json({ error: "carePlanId required in path" });

      // Optional filters from query params
      const relatedTable = req.query.relatedTable as string;
      const status = req.query.status as string;

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId,
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
              title: true,
            },
          },
        },
        orderBy: [{ status: "asc" }, { dueDate: "asc" }, { createdAt: "desc" }],
      });

      return res.json(tasks);
    } catch (error: any) {
      console.error("getTasksByCarePlan error", error);
      return res
        .status(500)
        .json({ error: "Failed to fetch tasks", details: error?.message });
    }
  }

  // Get tasks for a specific client (across all their care plans)
  public async getTasksByClient(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      // Ensure overdue tasks are marked as MISSED before returning tasks for a carer
      await this.markOverdueTasks(tenantId.toString());

      const clientId = req.params.clientId;
      if (!clientId)
        return res.status(400).json({ error: "clientId required in path" });

      // Optional filters from query params
      const relatedTable = req.query.relatedTable as string;
      const status = req.query.status as string;

      // First find all care plans for this client
      const carePlans = await (this.prisma as any).carePlan.findMany({
        where: {
          tenantId: tenantId.toString(),
          clientId,
        },
        select: { id: true },
      });

      const carePlanIds = carePlans.map((cp: any) => cp.id);
      if (!carePlanIds.length) return res.json([]);

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId: { in: carePlanIds },
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
              title: true,
            },
          },
        },
        orderBy: [{ status: "asc" }, { dueDate: "asc" }, { createdAt: "desc" }],
      });

      return res.json(tasks);
    } catch (error: any) {
      console.error("getTasksByClient error", error);
      return res
        .status(500)
        .json({
          error: "Failed to fetch tasks for client",
          details: error?.message,
        });
    }
  }

  // Get CarerVisits for a specific client (across all their care plans)
  public async getVisitsByClient(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const clientId = req.params.clientId;
      if (!clientId) return res.status(400).json({ error: "clientId required in path" });

      const page = parseInt((req.query.page as string) || "1", 10);
      const pageSize = parseInt((req.query.pageSize as string) || "50", 10);
      const skip = (Math.max(page, 1) - 1) * pageSize;

      // First find all care plans for this client
      const carePlans = await (this.prisma as any).carePlan.findMany({
        where: {
          tenantId: tenantId.toString(),
          clientId,
        },
        select: { id: true },
      });

      const carePlanIds = carePlans.map((cp: any) => cp.id);
      if (!carePlanIds.length) return res.json({ items: [], total: 0, page, pageSize });

      const where: any = { tenantId: tenantId.toString() };

      // If caller provided a specific carePlanId, use it (but ensure it's one of the client's care plans)
      const qCarePlanId = req.query.carePlanId as string | undefined;
      if (qCarePlanId) {
        if (!carePlanIds.includes(qCarePlanId)) {
          return res.json({ items: [], total: 0, page, pageSize });
        }
        where.carePlanId = qCarePlanId;
      } else {
        where.carePlanId = { in: carePlanIds };
      }

      // Optional filter to only return visits that have tasks
      const hasTasks = (req.query.hasTasks as string | undefined) ?? undefined;
      if (hasTasks === 'true') where.tasks = { some: {} };

      // Optional date range filters (ISO strings) to find visits overlapping a range
      const startParam = req.query.startDate as string | undefined;
      const endParam = req.query.endDate as string | undefined;
      let rangeStart: Date | null = null;
      let rangeEnd: Date | null = null;
      if (startParam) {
        const d = new Date(startParam);
        if (!isNaN(d.getTime())) rangeStart = d;
      }
      if (endParam) {
        const d = new Date(endParam);
        if (!isNaN(d.getTime())) rangeEnd = d;
      }
      if (rangeStart || rangeEnd) {
        const overlapConditions: any[] = [];
        if (rangeEnd) {
          overlapConditions.push({ startDate: { lt: rangeEnd } });
        }
        if (rangeStart) {
          overlapConditions.push({ OR: [{ endDate: null }, { endDate: { gte: rangeStart } }] });
        }
        if (overlapConditions.length === 1) Object.assign(where, overlapConditions[0]);
        else if (overlapConditions.length > 1) where.AND = overlapConditions;
      }

      const [items, total] = await Promise.all([
        (this.prisma as any).carerVisit.findMany({
          where,
          include: {
            tasks: {
              include: { carePlan: { select: { id: true, clientId: true, title: true } } },
            },
            assignees: true,
          },
          orderBy: { startDate: 'asc' },
          skip,
          take: pageSize,
        }),
        (this.prisma as any).carerVisit.count({ where }),
      ]);

      const authToken = req.headers.authorization || '';
      const enrichedItems = await this.enrichVisitsWithDistance(items, authToken);
      return res.json({ items: enrichedItems, total, page, pageSize });
    } catch (error: any) {
      console.error('getVisitsByClient error', error);
      return res.status(500).json({ error: 'Failed to fetch visits for client', details: error?.message });
    }
  }

  // Get tasks for a specific client and related table (e.g., all RiskAssessment tasks for client)
  public async getTasksByClientAndTable(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const clientId = req.params.clientId;
      const relatedTable = req.params.relatedTable;

      if (!clientId)
        return res.status(400).json({ error: "clientId required in path" });
      if (!relatedTable)
        return res.status(400).json({ error: "relatedTable required in path" });

      // Validate relatedTable
      if (!this.validRelatedTables.includes(relatedTable)) {
        return res.status(400).json({
          error: `Invalid relatedTable. Must be one of: ${this.validRelatedTables.join(", ")}`,
        });
      }

      // Optional status filter from query params
      const status = req.query.status as string;

      // First find all care plans for this client
      const carePlans = await (this.prisma as any).carePlan.findMany({
        where: {
          tenantId: tenantId.toString(),
          clientId,
        },
        select: { id: true },
      });

      const carePlanIds = carePlans.map((cp: any) => cp.id);
      if (!carePlanIds.length) return res.json([]);

      const where: any = {
        tenantId: tenantId.toString(),
        carePlanId: { in: carePlanIds },
        relatedTable,
      };

      if (status) where.status = status;

      const tasks = await (this.prisma as any).task.findMany({
        where,
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true,
            },
          },
        },
        orderBy: [{ status: "asc" }, { dueDate: "asc" }, { createdAt: "desc" }],
      });

      return res.json({
        clientId,
        relatedTable,
        tasks,
      });
    } catch (error: any) {
      console.error("getTasksByClientAndTable error", error);
      return res
        .status(500)
        .json({
          error: "Failed to fetch tasks for client and table",
          details: error?.message,
        });
    }
  }

  // Get tasks assigned to a carer
  public async getTasksByCarer(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const carerId = req.params.carerId;
      if (!carerId)
        return res.status(400).json({ error: "carerId required in path" });

      // Optional filters from query params
      const relatedTable = req.query.relatedTable as string;
      const status = req.query.status as string;

      // Query tasks by carerId on the task model
      const where: any = {
        tenantId: tenantId.toString(),
        carerId: carerId,
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
              title: true,
            },
          },
        },
        orderBy: [{ status: "asc" }, { dueDate: "asc" }, { createdAt: "desc" }],
      });

      return res.json(tasks);
    } catch (error: any) {
      console.error("getTasksByCarer error", error);
      return res
        .status(500)
        .json({
          error: "Failed to fetch tasks for carer",
          details: error?.message,
        });
    }
  }

  // Helper method to enrich visits with distance information for all assignees
  private async enrichVisitsWithDistance(visits: any[], authToken: string): Promise<any[]> {
    const authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://auth-service:8001';

    return await Promise.all(visits.map(async (visit: any) => {
      // Fetch client details (postcode and name)
      let clientPostcode: string | null = null;
      let clientName: string | null = null;
      if (visit.clientId) {
        try {
          const clientResponse = await fetch(`${authServiceUrl}/api/user/clients/${visit.clientId}/`, {
            headers: { 'Authorization': authToken }
          });
          if (clientResponse.ok) {
            const clientData: any = await clientResponse.json();
            clientPostcode = clientData.profile?.postcode || clientData.profile?.zip_code || null;
            clientName = `${clientData.first_name || ''} ${clientData.last_name || ''}`.trim() || null;
          }
        } catch (e) {
          console.error(`Failed to fetch client ${visit.clientId}:`, e);
        }
      }

      // Enrich each assignee with distance
      if (visit.assignees && Array.isArray(visit.assignees)) {
        visit.assignees = await Promise.all(visit.assignees.map(async (assignee: any) => {
          if (!clientPostcode) {
            return { ...assignee, distance: "client has no zip code" };
          }

          // Fetch carer postcode
          let carerPostcode: string | null = null;
          try {
            const carerResponse = await fetch(`${authServiceUrl}/api/user/users/${assignee.carerId}/`, {
              headers: { 'Authorization': authToken }
            });
            if (carerResponse.ok) {
              const carerData: any = await carerResponse.json();
              carerPostcode = carerData.profile?.zip_code || carerData.profile?.postcode || null;
            }
          } catch (e) {
            console.error(`Failed to fetch carer ${assignee.carerId}:`, e);
          }

          if (!carerPostcode) {
            return { ...assignee, distance: "can't find zip code" };
          }

          // Calculate distance
          try {
            const travelResult = await this.travelService.getTravelTime(carerPostcode, clientPostcode, 'driving');
            return {
              ...assignee,
              distanceMeters: travelResult.distanceMeters,
              distance: `${(travelResult.distanceMeters / 1609.34).toFixed(1)} mi`,
              durationSeconds: travelResult.durationSeconds,
              duration: `${Math.round(travelResult.durationSeconds / 60)} mins`
            };
          } catch (e: any) {
            console.error(`Failed to calculate distance for assignee ${assignee.carerId}:`, e.message);
            return { ...assignee, distance: e.message };
          }
        }));
      }

      return {
        ...visit,
        client_name: clientName
      };
    }));
  }

  // Get carer visits (carerVisit records) and optionally filter by date, day of week or range
  // Query params:
  // - date=YYYY-MM-DD (returns visits which have tasks that overlap that date)
  // - day=MONDAY|TUESDAY|... (returns visits which have tasks with startDate on that weekday)
  // - startDate, endDate (ISO datetimes) to filter tasks overlapping the range
  public async getCarerVisits(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res.status(403).json({ error: "tenantId missing from auth context" });

      // Ensure overdue tasks are marked as MISSED before returning carer visits/tasks
      await this.markOverdueTasks(tenantId.toString());

      const carerId = req.params.carerId;
      if (!carerId) return res.status(400).json({ error: "carerId required in path" });

      const dateParam = req.query.date as string | undefined; // YYYY-MM-DD
      const dayParam = (req.query.day as string | undefined)?.toUpperCase(); // MONDAY...
      const startParam = req.query.startDate as string | undefined; // ISO
      const endParam = req.query.endDate as string | undefined; // ISO

      // Fetch carerVisits with tasks (we'll filter tasks in JS for flexibility)
      const visits = await (this.prisma as any).carerVisit.findMany({
        where: { tenantId: tenantId.toString(), carerId },
        include: {
          tasks: {
            include: {
              carePlan: { select: { id: true, clientId: true, title: true } },
            },
          },
          assignees: true,
        },
        orderBy: { createdAt: "desc" },
      });

      // If no temporal filter provided, enrich and return all visits
      if (!dateParam && !dayParam && !startParam && !endParam) {
        const authToken = req.headers.authorization || '';
        const enrichedVisits = await this.enrichVisitsWithDistance(visits, authToken);
        return res.json(enrichedVisits);
      }

      // Helpers to build range
      const parseDateOnly = (d: string) => {
        // treat as YYYY-MM-DD in UTC
        const dt = new Date(d + "T00:00:00Z");
        if (isNaN(dt.getTime())) return null;
        return dt;
      };

      const dayOfWeekMap: Record<string, number> = {
        SUNDAY: 0,
        MONDAY: 1,
        TUESDAY: 2,
        WEDNESDAY: 3,
        THURSDAY: 4,
        FRIDAY: 5,
        SATURDAY: 6,
      };

      let rangeStart: Date | null = null;
      let rangeEnd: Date | null = null;

      if (dateParam) {
        const ds = parseDateOnly(dateParam);
        if (!ds) return res.status(400).json({ error: "Invalid date param, expected YYYY-MM-DD" });
        rangeStart = ds;
        rangeEnd = new Date(Date.UTC(ds.getUTCFullYear(), ds.getUTCMonth(), ds.getUTCDate() + 1));
      } else if (startParam || endParam) {
        rangeStart = startParam ? new Date(startParam) : null;
        rangeEnd = endParam ? new Date(endParam) : null;
        if ((rangeStart && isNaN(rangeStart.getTime())) || (rangeEnd && isNaN(rangeEnd.getTime()))) {
          return res.status(400).json({ error: "Invalid startDate or endDate param" });
        }
      }

      const targetDay: number | null = dayParam ? (dayOfWeekMap[dayParam] ?? null) : null;

      // Filter visits by tasks overlapping the requested filter(s)
      const filtered = visits
        .map((v: any) => {
          const matchingTasks = (v.tasks || []).filter((t: any) => {
            const s: Date | null = t.startDate ? new Date(t.startDate) : null;
            const e: Date | null = t.dueDate ? new Date(t.dueDate) : null;

            // If date/range provided, check overlap: task.start < rangeEnd && (task.due == null || task.due >= rangeStart)
            if (rangeStart && rangeEnd) {
              // overlapping intervals: (s < rangeEnd) && (e == null || e >= rangeStart)
              if (s && !(s < rangeEnd)) return false;
              if (e && !(e >= rangeStart)) return false;
              // if both s and e are missing, cannot match
              if (!s && !e) return false;
              return true;
            }

            // If only start/end range partially provided
            if (rangeStart && !rangeEnd) {
              // match tasks that end >= rangeStart or start >= rangeStart
              if (e && e >= rangeStart) return true;
              if (s && s >= rangeStart) return true;
              return false;
            }
            if (!rangeStart && rangeEnd) {
              if (s && s < rangeEnd) return true;
              return false;
            }

            // If day-of-week filter requested, check startDate weekday
            if (targetDay !== null) {
              if (!s) return false;
              // use UTC weekday to keep behaviour consistent across hosts
              const wd = s.getUTCDay();
              return wd === targetDay;
            }

            return false;
          });

          return { ...v, tasks: matchingTasks };
        })
        .filter((v: any) => v.tasks && v.tasks.length > 0);

      const authToken = req.headers.authorization || '';
      const enrichedFiltered = await this.enrichVisitsWithDistance(filtered, authToken);
      return res.json(enrichedFiltered);
    } catch (error: any) {
      console.error("getCarerVisits error", error);
      return res.status(500).json({ error: "Failed to fetch carer visits", details: error?.message });
    }
  }

  // Get a single CarerVisit by ID
  public async getVisitById(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res.status(403).json({ error: "tenantId missing from auth context" });

      const visitId = req.params.visitId;
      if (!visitId) return res.status(400).json({ error: "visitId required in path" });

      const visit = await (this.prisma as any).carerVisit.findUnique({
        where: { id: visitId },
        include: {
          tasks: { include: { carePlan: { select: { id: true, clientId: true, title: true } } } },
          assignees: true,
        },
      });

      if (!visit) return res.status(404).json({ error: "Visit not found" });
      if (visit.tenantId !== tenantId.toString()) return res.status(403).json({ error: "Access denied to this visit" });

      // Enrich assignees with distance information
      const authToken = req.headers.authorization || '';
      const authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://auth-service:8001';

      // Fetch client details (postcode and name)
      let clientPostcode: string | null = null;
      let clientName: string | null = null;
      if (visit.clientId) {
        try {
          const clientResponse = await fetch(`${authServiceUrl}/api/user/clients/${visit.clientId}/`, {
            headers: { 'Authorization': authToken }
          });
          if (clientResponse.ok) {
            const clientData: any = await clientResponse.json();
            clientPostcode = clientData.profile?.postcode || clientData.profile?.zip_code || null;
            clientName = `${clientData.first_name || ''} ${clientData.last_name || ''}`.trim() || null;
          }
        } catch (e) {
          console.error(`Failed to fetch client ${visit.clientId}:`, e);
        }
      }

      // Enrich each assignee with distance
      if (visit.assignees && Array.isArray(visit.assignees)) {
        visit.assignees = await Promise.all(visit.assignees.map(async (assignee: any) => {
          if (!clientPostcode) {
            return { ...assignee, distance: "client has no zip code" };
          }

          // Fetch carer postcode
          let carerPostcode: string | null = null;
          try {
            const carerResponse = await fetch(`${authServiceUrl}/api/user/users/${assignee.carerId}/`, {
              headers: { 'Authorization': authToken }
            });
            if (carerResponse.ok) {
              const carerData: any = await carerResponse.json();
              carerPostcode = carerData.profile?.zip_code || carerData.profile?.postcode || null;
            }
          } catch (e) {
            console.error(`Failed to fetch carer ${assignee.carerId}:`, e);
          }

          if (!carerPostcode) {
            return { ...assignee, distance: "can't find zip code" };
          }

          // Calculate distance
          try {
            const travelResult = await this.travelService.getTravelTime(carerPostcode, clientPostcode, 'driving');
            return {
              ...assignee,
              distanceMeters: travelResult.distanceMeters,
              distance: `${(travelResult.distanceMeters / 1609.34).toFixed(1)} mi`,
              durationSeconds: travelResult.durationSeconds,
              duration: `${Math.round(travelResult.durationSeconds / 60)} mins`
            };
          } catch (e: any) {
            console.error(`Failed to calculate distance for assignee ${assignee.carerId}:`, e.message);
            return { ...assignee, distance: e.message };
          }
        }));
      }

      return res.json({
        ...visit,
        client_name: clientName
      });
    } catch (error: any) {
      console.error("getVisitById error", error);
      return res.status(500).json({ error: "Failed to fetch visit", details: error?.message });
    }
  }

  // Delete a CarerVisit by ID. This will disassociate any tasks that reference the visit
  // (set task.carerVisitId = null) and then delete the visit. Tenant ownership is enforced.
  public async deleteVisit(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res.status(403).json({ error: "tenantId missing from auth context" });

      const visitId = req.params.visitId;
      if (!visitId) return res.status(400).json({ error: "visitId required in path" });

      const existing = await (this.prisma as any).carerVisit.findUnique({ where: { id: visitId }, select: { id: true, tenantId: true } });
      if (!existing) return res.status(404).json({ error: "Visit not found" });
      if (existing.tenantId !== tenantId.toString()) return res.status(403).json({ error: "Access denied to this visit" });

      await this.prisma.$transaction(async (tx: any) => {
        // detach tasks from this visit
        try {
          await tx.task.updateMany({ where: { carerVisitId: visitId }, data: { carerVisitId: null } });
        } catch (e) {
          console.error('Failed to detach tasks from visit', visitId, e);
          // continue - we still attempt to delete the visit
        }

        await tx.carerVisit.delete({ where: { id: visitId } });
      });

      return res.status(204).send();
    } catch (error: any) {
      console.error('deleteVisit error', error);
      return res.status(500).json({ error: 'Failed to delete visit', details: error?.message });
    }
  }

  // List all tasks for the requesting tenant with optional pagination and filters
  public async listTenantTasks(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      // Ensure overdue tasks are marked as MISSED before returning lists
      await this.markOverdueTasks(tenantId.toString());

      const page = parseInt((req.query.page as string) || "1", 10);
      const pageSize = parseInt((req.query.pageSize as string) || "50", 10);
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
        const cps = await (this.prisma as any).carePlan.findMany({
          where: { tenantId: tenantId.toString(), clientId },
          select: { id: true },
        });
        const cpIds = cps.map((c: any) => c.id);
        if (!cpIds.length)
          return res.json({ items: [], total: 0, page, pageSize });
        where.carePlanId = { in: cpIds };
      }

      const [items, total] = await Promise.all([
        (this.prisma as any).task.findMany({
          where,
          include: {
            carePlan: { select: { id: true, clientId: true, title: true } },
          },
          orderBy: [
            { status: "asc" },
            { dueDate: "asc" },
            { createdAt: "desc" },
          ],
          skip,
          take: pageSize,
        }),
        (this.prisma as any).task.count({ where }),
      ]);

      return res.json({ items, total, page, pageSize });
    } catch (error: any) {
      console.error("listTenantTasks error", error);
      return res
        .status(500)
        .json({
          error: "Failed to list tenant tasks",
          details: error?.message,
        });
    }
  }

  // Update a task
  public async updateTask(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const taskId = req.params.taskId;
      if (!taskId)
        return res.status(400).json({ error: "taskId required in path" });

      const payload = req.body || {};

      // Find the task and verify ownership
      const existingTask = await (this.prisma as any).task.findUnique({
        where: { id: taskId },
        select: { id: true, tenantId: true, status: true },
      });

      if (!existingTask) {
        return res.status(404).json({ error: "Task not found" });
      }

      if (existingTask.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: "Access denied to this task" });
      }

      // Load full task including related visit and its assignees so we can enforce
      // that only carers assigned to the visit may change the task status.
      const fullTask = await (this.prisma as any).task.findUnique({
        where: { id: taskId },
        include: { carerVisit: { include: { assignees: true } } },
      });

      const updateData: any = {};

      if (payload.title !== undefined) updateData.title = payload.title;
      if (payload.description !== undefined)
        updateData.description = payload.description;

      if (payload.status !== undefined) {
        // If the task is linked to a visit with assignees, only allow status
        // changes by one of those assignees. If no visit attached, allow change.
        if (fullTask && fullTask.carerVisitId) {
          const assignees = Array.isArray(fullTask.carerVisit?.assignees)
            ? fullTask.carerVisit.assignees.map((a: any) => String(a.carerId))
            : [];

          if (assignees.length > 0) {
            const callerRaw = (req.user as any)?.id ?? (req.user as any)?.carerId ?? null;
            const callerId = callerRaw !== undefined && callerRaw !== null ? String(callerRaw) : null;
            if (!callerId || !assignees.includes(callerId)) {
              return res.status(403).json({ error: 'Only assignees of the related visit may change task status' });
            }
          }
        }

        // If caller is attempting to start the task (mark IN_PROGRESS), ensure
        // the related visit has already been clocked in.
        if (payload.status === 'COMPLETED' && fullTask && fullTask.carerVisitId) {
          const visitClockIn = fullTask.carerVisit?.clockInAt ?? null;
          if (!visitClockIn) {
            return res.status(400).json({ error: 'Cannot start task before the related visit has been clocked in' });
          }
        }

        updateData.status = payload.status;
        // Auto-set completedAt when status changes to COMPLETED
        if (
          payload.status === "COMPLETED" &&
          existingTask.status !== "COMPLETED"
        ) {
          updateData.completedAt = new Date();
        }
        // Clear completedAt if status changes away from COMPLETED
        if (
          payload.status !== "COMPLETED" &&
          existingTask.status === "COMPLETED"
        ) {
          updateData.completedAt = null;
        }
      }

      if (payload.riskFrequency !== undefined)
        updateData.riskFrequency = payload.riskFrequency;
      if (payload.startDate !== undefined)
        updateData.startDate = this.toDateOrNull(payload.startDate);
      if (payload.dueDate !== undefined)
        updateData.dueDate = this.toDateOrNull(payload.dueDate);
      if (payload.additionalNotes !== undefined)
        updateData.additionalNotes = payload.additionalNotes;
      if (Array.isArray(payload.riskCategory))
        updateData.riskCategory = payload.riskCategory;

      let updated: any = null;

      // If we have update fields, apply them. If not (e.g. caller only sent pushToVisit), fetch the existing task so we can continue.
      if (Object.keys(updateData).length > 0) {
        updated = await (this.prisma as any).task.update({
          where: { id: taskId },
          data: updateData,
          include: {
            carePlan: {
              select: {
                id: true,
                clientId: true,
                title: true,
              },
            },
          },
        });
      } else {
        updated = await (this.prisma as any).task.findUnique({
          where: { id: taskId },
          include: { carePlan: { select: { id: true, clientId: true, title: true } } },
        });
        if (!updated) return res.status(404).json({ error: 'Task not found after update' });
      }

      // If caller requested pushToVisit on update, attempt to attach to an existing CarerVisit
      if (payload && payload.pushToVisit) {
        // Use the task values (may have been updated above)
        const taskStart: Date | null = updated.startDate ? new Date(updated.startDate) : null;
        const taskEnd: Date | null = updated.dueDate ? new Date(updated.dueDate) : null;

        if (!taskStart) {
          return res.status(400).json({ error: 'pushToVisit requires task.startDate to be set' });
        }

        const visitWhere: any = {
          tenantId: tenantId.toString(),
          carePlanId: updated.carePlanId,
          startDate: { lte: taskStart },
        };
        if (taskEnd) visitWhere.endDate = { gte: taskEnd };
        else visitWhere.endDate = { gte: taskStart };

        const matched = await (this.prisma as any).carerVisit.findFirst({ where: visitWhere, orderBy: { startDate: 'asc' } });
        if (!matched) {
          return res.status(400).json({ error: 'No matching visit found for the provided task times; create visits via care plan schedules or admin.' });
        }

        const attached = await (this.prisma as any).task.update({
          where: { id: taskId },
          data: { carerVisitId: matched.id, pushToVisit: true },
          include: { carePlan: { select: { id: true, clientId: true, title: true } } },
        });

        // If task was marked completed during this update, write a visit log for the related visit
        try {
          if (payload.status === 'COMPLETED' && existingTask.status !== 'COMPLETED' && attached.carerVisitId) {
            const performer = (req.user as any)?.id ?? (req.user as any)?.carerId ?? req.body?.performedById ?? 'system';
            await (this.prisma as any).clientVisitLog.create({ data: {
              tenantId: tenantId.toString(), visitId: attached.carerVisitId, action: 'TASK_COMPLETED', performedById: performer, details: JSON.stringify({ taskId: attached.id })
            }});
          }
        } catch (e) {
          console.error('Failed to write client visit log (task completed)', e);
        }

        return res.json(attached);
      }

      try {
        if (payload.status === 'COMPLETED' && existingTask.status !== 'COMPLETED' && updated.carerVisitId) {
          const performer = (req.user as any)?.id ?? (req.user as any)?.carerId ?? req.body?.performedById ?? 'system';
          await (this.prisma as any).clientVisitLog.create({ data: {
            tenantId: tenantId.toString(), visitId: updated.carerVisitId, action: 'TASK_COMPLETED', performedById: performer, details: JSON.stringify({ taskId: updated.id })
          }});
        }
      } catch (e) {
        console.error('Failed to write client visit log (task completed)', e);
      }

      return res.json(updated);
    } catch (error: any) {
      console.error("updateTask error", error);
      return res
        .status(500)
        .json({ error: "Failed to update task", details: error?.message });
    }
  }

  // Delete a task
  public async deleteTask(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const taskId = req.params.taskId;
      if (!taskId)
        return res.status(400).json({ error: "taskId required in path" });

      // Find the task and verify ownership
      const existingTask = await (this.prisma as any).task.findUnique({
        where: { id: taskId },
        select: { id: true, tenantId: true },
      });

      if (!existingTask) {
        return res.status(404).json({ error: "Task not found" });
      }

      if (existingTask.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: "Access denied to this task" });
      }

      await (this.prisma as any).task.delete({
        where: { id: taskId },
      });

      return res.status(204).send();
    } catch (error: any) {
      console.error("deleteTask error", error);
      return res
        .status(500)
        .json({ error: "Failed to delete task", details: error?.message });
    }
  }

  // Get a single task by ID
  public async getTaskById(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const taskId = req.params.taskId;
      if (!taskId)
        return res.status(400).json({ error: "taskId required in path" });

      const task = await (this.prisma as any).task.findUnique({
        where: { id: taskId },
        include: {
          carePlan: {
            select: {
              id: true,
              clientId: true,
              title: true,
            },
          },
        },
      });

      if (!task) {
        return res.status(404).json({ error: "Task not found" });
      }

      if (task.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: "Access denied to this task" });
      }

      return res.json(task);
    } catch (error: any) {
      console.error("getTaskById error", error);
      return res
        .status(500)
        .json({ error: "Failed to fetch task", details: error?.message });
    }
  }

  // Assign task to carer
  public async assignTaskToCarer(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const taskId = req.params.taskId;
      if (!taskId)
        return res.status(400).json({ error: "taskId required in path" });

      const { carerId, carerVisitId } = req.body || {};
      if (!carerId || typeof carerId !== "string") {
        return res
          .status(400)
          .json({ error: "carerId is required in body and must be a string" });
      }

      // Fetch task and verify tenant ownership
      const existingTask = await this.prisma.task.findUnique({
        where: { id: taskId },
        select: { id: true, tenantId: true },
      });

      if (!existingTask)
        return res.status(404).json({ error: "Task not found" });
      if (existingTask.tenantId !== tenantId.toString())
        return res.status(403).json({ error: "Access denied to this task" });

      // Prepare base update - directly update carerId on task
      const baseUpdate: any = {
        carerId: carerId, // This is the direct carer assignment on Task model
      };

      // Use a transaction to handle carer visit assignment
      const result = await this.prisma.$transaction(async (prismaTx) => {
        let cv: any = null;

        // If an explicit carerVisitId was supplied, verify it exists and belongs to tenant/carer
        if (carerVisitId && typeof carerVisitId === "string") {
          try {
            const found = await prismaTx.carerVisit.findUnique({
              where: { id: carerVisitId },
            });
            if (
              found &&
              found.tenantId === tenantId.toString() &&
              found.carerId === carerId
            ) {
              cv = found;
            }
          } catch (e) {
            // ignore and fall through to find-or-create
            cv = null;
          }
        }

        // If no valid carerVisit found yet, try to find any carerVisit for this tenant+carer
        if (!cv) {
          try {
            cv = await prismaTx.carerVisit.findFirst({
              where: {
                tenantId: tenantId.toString(),
                carerId,
              },
              orderBy: { createdAt: "desc" },
            });
          } catch (e) {
            cv = null;
          }
        }

        // If still not found, create a new carerVisit
        if (!cv) {
          cv = await prismaTx.carerVisit.create({
            data: {
              tenantId: tenantId.toString(),
              carerId,
            },
          });
        }

        // Enforce per-visit capacity using CarerVisitAssignee join table
        // Ensure the assignee doesn't already exist
        const already = await prismaTx.carerVisitAssignee.findFirst({ where: { carerVisitId: cv.id, carerId } });
        if (!already) {
          // Determine effective careType: visit.careType (if present) else fallback to carePlan.careRequirements.careType
          let effectiveCareType: string | null = null;
          if (cv.careType) effectiveCareType = cv.careType;
          else if (cv.carePlanId) {
            try {
              const cp = await prismaTx.carePlan.findUnique({ where: { id: cv.carePlanId }, include: { careRequirements: true } });
              if (cp && cp.careRequirements && cp.careRequirements.careType) effectiveCareType = cp.careRequirements.careType;
            } catch (e) {
              // ignore
            }
          }

          const cap = this.careTypeCapacity(effectiveCareType);
          if (typeof cap === 'number') {
            const existingCount = await prismaTx.carerVisitAssignee.count({ where: { tenantId: tenantId.toString(), carerVisitId: cv.id } });
            if (existingCount >= cap) {
              throw new Error(`Visit assignment limit reached for careType=${effectiveCareType}`);
            }
          }

          await prismaTx.carerVisitAssignee.create({ data: { tenantId: tenantId.toString(), carerVisitId: cv.id, carerId } });
          // For backward compatibility, populate carerId on the carerVisit if this is the first assignee
          const totalAfter = await prismaTx.carerVisitAssignee.count({ where: { tenantId: tenantId.toString(), carerVisitId: cv.id } });
          if (!cv.carerId && totalAfter === 1) {
            await prismaTx.carerVisit.update({ where: { id: cv.id }, data: { carerId, assignedAt: new Date() } });
          }
        }

        // Attach the carerVisit id to the task and update carerId
        const updateData: any = { ...baseUpdate, carerVisitId: cv.id };
        const updated = await prismaTx.task.update({ where: { id: taskId }, data: updateData });

        return { updated, carerVisit: cv };
      });

      return res.json(result.updated);
    } catch (error: any) {
      console.error("assignTaskToCarer error", error);
      return res
        .status(500)
        .json({
          error: "Failed to assign carer to task",
          details: error?.message,
        });
    }
  }

  // Assign a carer to an existing CarerVisit (visit-level assignment)
  // Optionally propagate the carerId to all tasks attached to that visit (propagate=true by default)
  public async assignCarerToVisit(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const visitId = req.params.visitId;
      if (!visitId)
        return res.status(400).json({ error: "visitId required in path" });

      const { carerId, propagate } = req.body || {};
      if (!carerId || typeof carerId !== "string") {
        return res
          .status(400)
          .json({ error: "carerId is required in body and must be a string" });
      }

      // Default propagate to true unless explicitly false
      const shouldPropagate = propagate === undefined ? true : !!propagate;

      // Fetch the visit and verify ownership
      const existingVisit = await this.prisma.carerVisit.findUnique({
        where: { id: visitId },
        select: { id: true, tenantId: true, startDate: true, endDate: true },
      });

      if (!existingVisit) return res.status(404).json({ error: "Visit not found" });
      if (existingVisit.tenantId !== tenantId.toString())
        return res.status(403).json({ error: "Access denied to this visit" });

      // Check for time conflicts with existing visits for this carer
      if (existingVisit.startDate && existingVisit.endDate) {
        const conflictingVisits = await this.prisma.carerVisit.findMany({
          where: {
            tenantId: tenantId.toString(),
            carerId: carerId,
            id: { not: visitId }, // Exclude the current visit
            OR: [
              // New visit starts during existing visit
              {
                startDate: { lte: existingVisit.startDate },
                endDate: { gt: existingVisit.startDate }
              },
              // New visit ends during existing visit
              {
                startDate: { lt: existingVisit.endDate },
                endDate: { gte: existingVisit.endDate }
              },
              // New visit completely encompasses existing visit
              {
                startDate: { gte: existingVisit.startDate },
                endDate: { lte: existingVisit.endDate }
              }
            ]
          },
          select: { id: true, startDate: true, endDate: true }
        });

        if (conflictingVisits.length > 0) {
          const conflictDetails = conflictingVisits.map(v => 
            `Visit ${v.id}: ${v.startDate?.toISOString()} - ${v.endDate?.toISOString()}`
          ).join('; ');
          return res.status(409).json({ 
            error: "Carer has conflicting visits scheduled", 
            conflicts: conflictDetails 
          });
        }
      }

      // Transaction: create assignee while enforcing capacity, optionally propagate to tasks
      try {
        const result = await this.prisma.$transaction(async (prismaTx) => {
          const visit = await prismaTx.carerVisit.findUnique({ where: { id: visitId } });
          if (!visit) throw new Error('Visit not found in transaction');

          // Determine effective careType
          let effectiveCareType: string | null = null;
          if (visit.careType) effectiveCareType = visit.careType;
          else if (visit.carePlanId) {
            try {
              const cp = await prismaTx.carePlan.findUnique({ where: { id: visit.carePlanId }, include: { careRequirements: true } });
              if (cp && cp.careRequirements && cp.careRequirements.careType) effectiveCareType = cp.careRequirements.careType;
            } catch (e) {
              // ignore
            }
          }

          const cap = this.careTypeCapacity(effectiveCareType);

          // if cap is a number, check current assignee count
          if (typeof cap === 'number') {
            const existingCount = await prismaTx.carerVisitAssignee.count({ where: { tenantId: tenantId.toString(), carerVisitId: visitId } });
            const alreadyAssigned = await prismaTx.carerVisitAssignee.findFirst({ where: { carerVisitId: visitId, carerId } });
            if (!alreadyAssigned && existingCount >= cap) {
              throw new Error(`Visit assignment limit reached for careType=${effectiveCareType}`);
            }
          }

          // Create assignee if not already assigned
          const alreadyAssigned = await prismaTx.carerVisitAssignee.findFirst({ where: { carerVisitId: visitId, carerId } });
          if (!alreadyAssigned) {
            await prismaTx.carerVisitAssignee.create({ data: { tenantId: tenantId.toString(), carerVisitId: visitId, carerId } });
          }

          // Optionally update denormalized carerId on visit when first assignee
          const totalCount = await prismaTx.carerVisitAssignee.count({ where: { tenantId: tenantId.toString(), carerVisitId: visitId } });
          let updatedVisit: any = visit;
          if (!visit.carerId && totalCount === 1) {
            updatedVisit = await prismaTx.carerVisit.update({ where: { id: visitId }, data: { carerId, assignedAt: new Date() } });
          }

          let tasksUpdated = 0;
          if (shouldPropagate) {
            const upd = await prismaTx.task.updateMany({ where: { carerVisitId: visitId }, data: { carerId } });
            tasksUpdated = upd.count || 0;
          }

          return { updatedVisit, tasksUpdated };
        });

        return res.json(result);
      } catch (err: any) {
        console.error('assignCarerToVisit transaction error', err);
        return res.status(400).json({ error: err?.message || 'Failed to assign carer to visit' });
      }
    } catch (error: any) {
      console.error("assignCarerToVisit error", error);
      return res
        .status(500)
        .json({ error: "Failed to assign carer to visit", details: error?.message });
    }
  }

  // Assign multiple carers to an existing CarerVisit in one request
  // Body: { carerIds: string[], propagate?: boolean }
  public async assignCarersToVisit(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const visitId = req.params.visitId;
      if (!visitId)
        return res.status(400).json({ error: "visitId required in path" });

      const { carerIds, propagate } = req.body || {};
      if (!Array.isArray(carerIds) || carerIds.some((c: any) => typeof c !== 'string')) {
        return res.status(400).json({ error: 'carerIds must be an array of strings' });
      }

      const uniqueCarerIds = Array.from(new Set(carerIds));
      if (uniqueCarerIds.length === 0) return res.status(400).json({ error: 'carerIds cannot be empty' });

      const shouldPropagate = propagate === undefined ? true : !!propagate;

      // Fetch the visit and verify ownership
      const existingVisit = await this.prisma.carerVisit.findUnique({ 
        where: { id: visitId }, 
        select: { id: true, tenantId: true, carerId: true, careType: true, carePlanId: true, startDate: true, endDate: true } 
      });
      if (!existingVisit) return res.status(404).json({ error: 'Visit not found' });
      if (existingVisit.tenantId !== tenantId.toString()) return res.status(403).json({ error: 'Access denied to this visit' });

      // Check for time conflicts with existing visits for each carer
      if (existingVisit.startDate && existingVisit.endDate) {
        for (const carerId of uniqueCarerIds) {
          const conflictingVisits = await this.prisma.carerVisit.findMany({
            where: {
              tenantId: tenantId.toString(),
              carerId: carerId,
              id: { not: visitId }, // Exclude the current visit
              OR: [
                // New visit starts during existing visit
                {
                  startDate: { lte: existingVisit.startDate },
                  endDate: { gt: existingVisit.startDate }
                },
                // New visit ends during existing visit
                {
                  startDate: { lt: existingVisit.endDate },
                  endDate: { gte: existingVisit.endDate }
                },
                // New visit completely encompasses existing visit
                {
                  startDate: { gte: existingVisit.startDate },
                  endDate: { lte: existingVisit.endDate }
                }
              ]
            },
            select: { id: true, startDate: true, endDate: true }
          });

          if (conflictingVisits.length > 0) {
            const conflictDetails = conflictingVisits.map(v => 
              `Visit ${v.id}: ${v.startDate?.toISOString()} - ${v.endDate?.toISOString()}`
            ).join('; ');
            return res.status(409).json({ 
              error: `Carer ${carerId} has conflicting visits scheduled`, 
              conflicts: conflictDetails 
            });
          }
        }
      }

      try {
        const result = await this.prisma.$transaction(async (prismaTx) => {
          const visit = await prismaTx.carerVisit.findUnique({ where: { id: visitId } });
          if (!visit) throw new Error('Visit not found in transaction');

          // Determine effective careType
          let effectiveCareType: string | null = null;
          if (visit.careType) effectiveCareType = visit.careType;
          else if (visit.carePlanId) {
            try {
              const cp = await prismaTx.carePlan.findUnique({ where: { id: visit.carePlanId }, include: { careRequirements: true } });
              if (cp && cp.careRequirements && cp.careRequirements.careType) effectiveCareType = cp.careRequirements.careType;
            } catch (e) {
              // ignore
            }
          }

          const cap = this.careTypeCapacity(effectiveCareType);

          // Find already assigned carers among requested list
          const alreadyAssignedRecords = await prismaTx.carerVisitAssignee.findMany({ where: { carerVisitId: visitId, carerId: { in: uniqueCarerIds } }, select: { carerId: true } });
          const alreadyLinkedIds = alreadyAssignedRecords.map((r: any) => r.carerId);

          const newIds = uniqueCarerIds.filter((id) => !alreadyLinkedIds.includes(id));

          // If cap is numeric, ensure adding these doesn't exceed capacity
          if (typeof cap === 'number') {
            const existingCount = await prismaTx.carerVisitAssignee.count({ where: { tenantId: tenantId.toString(), carerVisitId: visitId } });
            if (existingCount + newIds.length > cap) {
              throw new Error(`Visit assignment limit reached for careType=${effectiveCareType}. Available slots=${Math.max(0, cap - existingCount)}`);
            }
          }

          // Create new assignees
          const createData = newIds.map((cid) => ({ tenantId: tenantId.toString(), carerVisitId: visitId, carerId: cid }));
          if (createData.length > 0) {
            try {
              await prismaTx.carerVisitAssignee.createMany({ data: createData, skipDuplicates: true });
            } catch (e) {
              // fallback to individual creates if createMany not supported
              for (const d of createData) {
                try { await prismaTx.carerVisitAssignee.create({ data: d }); } catch (err) { /* ignore duplicates */ }
              }
            }
          }

          // Update denormalized carerId on visit if previously null and now has exactly one assignee
          const totalAfter = await prismaTx.carerVisitAssignee.count({ where: { tenantId: tenantId.toString(), carerVisitId: visitId } });
          let updatedVisit: any = visit;
          if (!visit.carerId && totalAfter === 1) {
            // choose the single assignee as carerId
            const single = (await prismaTx.carerVisitAssignee.findFirst({ where: { carerVisitId: visitId } })) as any;
            if (single) {
              updatedVisit = await prismaTx.carerVisit.update({ where: { id: visitId }, data: { carerId: single.carerId, assignedAt: new Date() } });
            }
          }

          let tasksUpdated = 0;
          if (shouldPropagate) {
            const upd = await prismaTx.task.updateMany({ where: { carerVisitId: visitId }, data: { carerId: updatedVisit.carerId || undefined } });
            tasksUpdated = upd.count || 0;
          }

          return { createdIds: newIds, alreadyLinkedIds, totalAfter, updatedVisit, tasksUpdated };
        });

        return res.json(result);
      } catch (err: any) {
        console.error('assignCarersToVisit transaction error', err);
        return res.status(400).json({ error: err?.message || 'Failed to assign carers to visit' });
      }
    } catch (error: any) {
      console.error('assignCarersToVisit error', error);
      return res.status(500).json({ error: 'Failed to assign carers to visit', details: error?.message });
    }
  }

  // Clock in to a visit: set status to STARTED and record clockInAt timestamp
  public async clockInVisit(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId) ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const visitId = req.params.visitId;
      if (!visitId) return res.status(400).json({ error: 'visitId required in path' });

      const existing = await (this.prisma as any).carerVisit.findUnique({ where: { id: visitId }, include: { assignees: true } });
      if (!existing) return res.status(404).json({ error: 'Visit not found' });
      if (existing.tenantId !== tenantId.toString()) return res.status(403).json({ error: 'Access denied to this visit' });

      // No auth checks: allow any authenticated user to clock in. Record who attempted.
      const userObj = (req.user as any) || {};
      const callerRole = userObj.role as string | undefined;
      const callerUserId = userObj.id ? String(userObj.id) : null;
      const assigneeIds = Array.isArray(existing.assignees) ? existing.assignees.map((a: any) => a.carerId) : [];

      // Only allow callers who are assigned to this visit to clock in.
      if (!callerUserId || assigneeIds.length === 0 || !assigneeIds.includes(callerUserId)) {
        return res.status(403).json({ error: 'Only assignees of this visit may clock in' });
      }

      // Prevent clock-in before the visit's calendar day.
      // Users may clock in anytime on the same day of the visit (including before the scheduled time),
      // but not on earlier calendar days.
      try {
        const now = new Date();
        const scheduledStart = existing.startDate ? new Date(existing.startDate) : null;
        if (scheduledStart) {
          const visitDayStart = new Date(scheduledStart);
          visitDayStart.setHours(0, 0, 0, 0);
          if (now.getTime() < visitDayStart.getTime()) {
            return res.status(400).json({ error: 'Cannot clock in before the day of the visit' });
          }
        }
      } catch (e) {
        // If anything goes wrong with the check, log and continue to avoid blocking legitimate clock-ins.
        console.warn('visit day check failed', e);
      }

      const updated = await (this.prisma as any).carerVisit.update({
        where: { id: visitId },
        data: { status: 'IN_PROGRESS', clockInAt: new Date() },
        include: { tasks: { include: { carePlan: { select: { id: true, clientId: true, title: true } } } }, assignees: true },
      });

      // Update/create attendance row: determine early/late entry relative to scheduled start
      try {
        const actingCarerId = (req.user as any)?.id ? String((req.user as any).id) : null;
        const staffId = actingCarerId ? String(actingCarerId) : 'unknown';

        const clockInAt = updated.clockInAt ? new Date(updated.clockInAt) : new Date();
        const scheduledStart = existing.startDate ? new Date(existing.startDate) : null;

        let entryStatus: any = null;
        if (scheduledStart) {
          // before or on scheduled start => early entry, otherwise late entry
          entryStatus = (clockInAt.getTime() <= scheduledStart.getTime()) ? 'EARLY_ENTRY' : 'LATE_ENTRY';
        }

        // Find attendance record for same day (UTC day of clockIn)
        const dayStart = new Date(Date.UTC(clockInAt.getUTCFullYear(), clockInAt.getUTCMonth(), clockInAt.getUTCDate(), 0, 0, 0, 0));
        const dayEnd = new Date(dayStart);
        dayEnd.setUTCDate(dayStart.getUTCDate() + 1);

        const existingAttendance = await (this.prisma as any).attendance.findFirst({
          where: {
            tenantId: tenantId.toString(),
            staffId,
            OR: [
              { carerVisitId: visitId },
              { clockInAt: { gte: dayStart, lt: dayEnd } },
              { clockOutAt: { gte: dayStart, lt: dayEnd } },
            ],
          },
        });

        if (existingAttendance) {
          await (this.prisma as any).attendance.update({ where: { id: existingAttendance.id }, data: { clockInAt: clockInAt, entryStatus, carerVisitId: visitId } });
        } else {
          await (this.prisma as any).attendance.create({ data: { tenantId: tenantId.toString(), staffId, carerVisitId: visitId, clockInAt: clockInAt, entryStatus } });
        }
      } catch (e) {
        console.error('Failed to write attendance on clockIn', e);
      }

      return res.json(updated);
    } catch (error: any) {
      console.error('clockInVisit error', error);
      return res.status(500).json({ error: 'Failed to clock in to visit', details: error?.message });
    }
  }

  // Clock out of a visit: set status to COMPLETED, record clockOutAt and optional note
  public async clockOutVisit(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId) ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const visitId = req.params.visitId;
      if (!visitId) return res.status(400).json({ error: 'visitId required in path' });

      const note = req.body?.note ?? req.body?.clockOutNote ?? null;

      const existing = await (this.prisma as any).carerVisit.findUnique({ where: { id: visitId }, include: { assignees: true } });
      if (!existing) return res.status(404).json({ error: 'Visit not found' });
      if (existing.tenantId !== tenantId.toString()) return res.status(403).json({ error: 'Access denied to this visit' });

      // No auth checks: allow any authenticated user to clock out. Record who attempted.
      const userObj = (req.user as any) || {};
      const callerRole = userObj.role as string | undefined;
      const callerUserId = userObj.id ? String(userObj.id) : null;
      const assigneeIds = Array.isArray(existing.assignees) ? existing.assignees.map((a: any) => a.carerId) : [];
      console.log('[clockOutVisit] attempt', { userId: callerUserId, role: callerRole, visitId, assigneesCount: assigneeIds.length });

      const updated = await (this.prisma as any).carerVisit.update({
        where: { id: visitId },
        data: { status: 'COMPLETED', clockOutAt: new Date(), clockOutNote: note ?? undefined },
        include: { tasks: { include: { carePlan: { select: { id: true, clientId: true, title: true } } } }, assignees: true },
      });

      // Update/create attendance row: determine early/late exit relative to scheduled end
      try {
        const actingCarerId = (req.user as any)?.id ? String((req.user as any).id) : null;
        const staffId = actingCarerId ? String(actingCarerId) : 'unknown';

        const clockOutAt = updated.clockOutAt ? new Date(updated.clockOutAt) : new Date();
        const scheduledEnd = existing.endDate ? new Date(existing.endDate) : null;

        let exitStatus: any = null;
        if (scheduledEnd) {
          // on/after scheduled end => late exit, otherwise early exit
          exitStatus = (clockOutAt.getTime() >= scheduledEnd.getTime()) ? 'LATE_EXIT' : 'EARLY_EXIT';
        }

        // Find attendance record for same day (UTC day of clockOut)
        const dayStart = new Date(Date.UTC(clockOutAt.getUTCFullYear(), clockOutAt.getUTCMonth(), clockOutAt.getUTCDate(), 0, 0, 0, 0));
        const dayEnd = new Date(dayStart);
        dayEnd.setUTCDate(dayStart.getUTCDate() + 1);

        const existingAttendance = await (this.prisma as any).attendance.findFirst({
          where: {
            tenantId: tenantId.toString(),
            staffId,
            OR: [
              { carerVisitId: visitId },
              { clockInAt: { gte: dayStart, lt: dayEnd } },
              { clockOutAt: { gte: dayStart, lt: dayEnd } },
            ],
          },
        });

        if (existingAttendance) {
          await (this.prisma as any).attendance.update({ where: { id: existingAttendance.id }, data: { clockOutAt: clockOutAt, exitStatus, carerVisitId: visitId } });
        } else {
          await (this.prisma as any).attendance.create({ data: { tenantId: tenantId.toString(), staffId, carerVisitId: visitId, clockOutAt: clockOutAt, exitStatus } });
        }
      } catch (e) {
        console.error('Failed to write attendance on clockOut', e);
      }

      return res.json(updated);
    } catch (error: any) {
      console.error('clockOutVisit error', error);
      return res.status(500).json({ error: 'Failed to clock out of visit', details: error?.message });
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

      const mapStatus = (s: string | null | undefined) => {
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
      };

      const formatDateTime = (d: Date | null | undefined) => {
        if (!d) return null;
        try {
          // e.g. "12 January 2025 at 4:03am"
          return format(d, "d LLLL yyyy 'at' h:mma").replace('AM', 'am').replace('PM', 'pm');
        } catch (e) {
          return d.toISOString();
        }
      };

      const simplified = tasks.map(t => {
        const date = t.completedAt ?? t.dueDate ?? t.updatedAt ?? t.createdAt;
        return {
          task: t.title,
          status: mapStatus(t.status),
          dateTime: formatDateTime(date),
          comment: t.additionalNotes ?? null,
          taskId: t.id,
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

  // List all CarerVisits for a tenant with pagination and optional carerId filter
  public async listTenantVisits(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId)
        return res
          .status(403)
          .json({ error: "tenantId missing from auth context" });

      const page = parseInt((req.query.page as string) || "1", 10);
      const pageSize = parseInt((req.query.pageSize as string) || "50", 10);
      const skip = (Math.max(page, 1) - 1) * pageSize;

      const carerId = req.query.carerId as string | undefined;

      const where: any = { tenantId: tenantId.toString() };
      if (carerId) where.carerId = carerId;

      // Optional filter to return only visits which have tasks attached
      const hasTasks = (req.query.hasTasks as string | undefined) ?? undefined;
      if (hasTasks === 'true') {
        // Prisma relation filter: only visits that have at least one related task
        where.tasks = { some: {} };
      }

      // Optional carePlanId filter (filter visits that belong to a specific care plan)
      const qCarePlanId = req.query.carePlanId as string | undefined;
      if (qCarePlanId) where.carePlanId = qCarePlanId;

      // Optional date range filters (ISO strings)
      const startParam = req.query.startDate as string | undefined;
      const endParam = req.query.endDate as string | undefined;
      let rangeStart: Date | null = null;
      let rangeEnd: Date | null = null;
      if (startParam) {
        const d = new Date(startParam);
        if (!isNaN(d.getTime())) rangeStart = d;
      }
      if (endParam) {
        const d = new Date(endParam);
        if (!isNaN(d.getTime())) rangeEnd = d;
      }

      // If either range value is provided, filter visits that overlap the interval
      if (rangeStart || rangeEnd) {
        const overlapConditions: any[] = [];
        if (rangeEnd) {
          // visit.startDate < rangeEnd
          overlapConditions.push({ startDate: { lt: rangeEnd } });
        }
        if (rangeStart) {
          // visit.endDate is null OR visit.endDate >= rangeStart
          overlapConditions.push({ OR: [{ endDate: null }, { endDate: { gte: rangeStart } }] });
        }
        if (overlapConditions.length === 1) {
          // single condition
          Object.assign(where, overlapConditions[0]);
        } else if (overlapConditions.length > 1) {
          where.AND = overlapConditions;
        }
      }

      const [items, total] = await Promise.all([
        (this.prisma as any).carerVisit.findMany({
          where,
          include: {
            tasks: {
              include: {
                carePlan: { select: { id: true, clientId: true, title: true } },
              },
            },
            assignees: true,
          },
          orderBy: [{ createdAt: "desc" }, {id: "desc"}],
          skip,
          take: pageSize,
        }),
        (this.prisma as any).carerVisit.count({ where }),
      ]);

      const authToken = req.headers.authorization || '';
      const enrichedItems = await this.enrichVisitsWithDistance(items, authToken);
      return res.json({ items: enrichedItems, total, page, pageSize });
    } catch (error: any) {
      console.error("listTenantVisits error", error);
      return res
        .status(500)
        .json({ error: "Failed to list tenant visits", details: error?.message });
    }
  }
}