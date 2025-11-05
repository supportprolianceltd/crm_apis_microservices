// Enum values from schema.prisma
const CARE_PLAN_STATUS = ['ACTIVE', 'INACTIVE', 'COMPLETED'];

import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { validateCreatePayload } from '../validation/careplan.validation';

function getUserFriendlyError(error: any): string {
  if (error?.code === 'P2002') {
    return 'A record with this unique value already exists.';
  }
  if (error?.code === 'P2025') {
    return 'The requested record was not found.';
  }
  if (error?.code === 'P2003') {
    return 'Invalid reference to a related record.';
  }
  if (error?.name === 'ValidationError' || error?.isValidationError) {
    if (error.details) {
      return `Invalid data provided: ${JSON.stringify(error.details)}`;
    }
    return error.message || 'Invalid data provided.';
  }
  // Prisma 'Unknown argument' error
  if (typeof error?.message === 'string' && error.message.includes('Unknown argument')) {
    const match = error.message.match(/Unknown argument `(\w+)`/);
    if (match && match[1]) {
      return `You provided a field that does not exist in the schema: ${match[1]}. Please check your payload.`;
    }
    return 'You provided a field that does not exist in the schema. Please check your payload.';
  }
  if (error?.name === 'PrismaClientKnownRequestError' && error?.message) {
    return error.message;
  }
  if (error?.message) {
    return error.message;
  }
  return 'An unexpected error occurred. Please try again or contact support.';
}

export class CarePlanController {
  private prisma: PrismaClient;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  // Normalize day strings to Prisma DayOfWeek enum values (MONDAY..SUNDAY)
  private normalizeDay(day: string): string | null {
    if (!day || typeof day !== 'string') return null;
    const d = day.trim().toUpperCase();
    const map: Record<string, string> = {
      MONDAY: 'MONDAY', TUESDAY: 'TUESDAY', WEDNESDAY: 'WEDNESDAY', THURSDAY: 'THURSDAY', FRIDAY: 'FRIDAY', SATURDAY: 'SATURDAY', SUNDAY: 'SUNDAY',
      // allow lowercase keys
      MON: 'MONDAY', TUE: 'TUESDAY', WED: 'WEDNESDAY', THU: 'THURSDAY', FRI: 'FRIDAY', SAT: 'SATURDAY', SUN: 'SUNDAY',
    };
    // accept values like 'monday' or 'MONDAY' or 'Mon'
    if (map[d]) return map[d];
    // also allow full word lower-case
    const up = d.toUpperCase();
    if (map[up]) return map[up];
    return null;
  }

  private toDateOrNull(val: any) {
    if (!val) return null;
    const d = new Date(val);
    return isNaN(d.getTime()) ? null : d;
  }

  public async createCarePlan(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const payload = req.body || {};
      const errors = validateCreatePayload(payload);
      if (errors.length) return res.status(400).json({ errors });

      // Build the create data with optional nested creates
      const data: any = {
        tenantId: tenantId.toString(),
        clientId: payload.clientId,
        title: payload.title,
      };

      if (payload.description !== undefined) data.description = payload.description;
      if (payload.startDate) data.startDate = this.toDateOrNull(payload.startDate);
      if (payload.endDate) data.endDate = this.toDateOrNull(payload.endDate);
      if (payload.status) data.status = payload.status;

      // Helper to attach nested create if present
      const attachNested = (key: string, value: any) => {
        if (value === undefined || value === null) return;
        data[key] = { create: value };
      };

      // Simple one-to-one nested objects
      attachNested('riskAssessment', payload.riskAssessment ? { ...payload.riskAssessment, tenantId: tenantId.toString() } : undefined);
      attachNested('personalCare', payload.personalCare ? { ...payload.personalCare, tenantId: tenantId.toString() } : undefined);
      attachNested('everydayActivityPlan', payload.everydayActivityPlan ? { ...payload.everydayActivityPlan, tenantId: tenantId.toString() } : undefined);
      attachNested('fallsAndMobility', payload.fallsAndMobility ? { ...payload.fallsAndMobility, tenantId: tenantId.toString() } : undefined);
      attachNested('psychologicalInfo', payload.psychologicalInfo ? { ...payload.psychologicalInfo, tenantId: tenantId.toString() } : undefined);
      attachNested('foodHydration', payload.foodHydration ? { ...payload.foodHydration, tenantId: tenantId.toString() } : undefined);
      attachNested('routine', payload.routine ? { ...payload.routine, tenantId: tenantId.toString() } : undefined);
      attachNested('cultureValues', payload.cultureValues ? { ...payload.cultureValues, tenantId: tenantId.toString() } : undefined);
      attachNested('bodyMap', payload.bodyMap ? { ...payload.bodyMap, tenantId: tenantId.toString() } : undefined);
      attachNested('legalRequirement', payload.legalRequirement ? { ...payload.legalRequirement, tenantId: tenantId.toString() } : undefined);
      // careRequirements needs special handling so we can persist normalized AgreedCareSchedule + AgreedCareSlot rows
      if (payload.careRequirements) {
        const cr: any = { tenantId: tenantId.toString(), careType: payload.careRequirements.careType };

        // Build schedules if provided. Support either an array `schedules` or an object `agreedCareVisits` keyed by day name.
        const schedulesCreate: any[] = [];

        const pushSlot = (slot: any, idx: number) => {
          if (!slot) return null;
          return {
            startTime: slot.startTime ?? slot.start ?? slot.from ?? slot.start_time ?? slot.startTimeString ?? slot.start_time_string ?? slot.startTime,
            endTime: slot.endTime ?? slot.end ?? slot.to ?? slot.end_time ?? slot.endTimeString ?? slot.end_time_string ?? slot.endTime,
            externalId: slot.externalId ?? slot.id ?? slot.clientId ?? null,
            position: typeof slot.position === 'number' ? slot.position : idx,
          };
        };

        if (Array.isArray(payload.careRequirements.schedules) && payload.careRequirements.schedules.length) {
          for (const s of payload.careRequirements.schedules) {
            const dayEnum = this.normalizeDay(s.day || s.name || s.dayOfWeek || (s.day && String(s.day)));
            if (!dayEnum) continue;
            const slots = Array.isArray(s.slots) ? s.slots.map((sl: any, i: number) => pushSlot(sl, i)) : [];
            schedulesCreate.push({
              tenantId: tenantId.toString(),
              day: dayEnum,
              enabled: s.enabled === undefined ? true : !!s.enabled,
              lunchStart: s.lunchStart ?? s.lunch_start ?? null,
              lunchEnd: s.lunchEnd ?? s.lunch_end ?? null,
              slots: slots.length ? { create: slots } : undefined,
            });
          }
        } else if (payload.careRequirements.agreedCareVisits && typeof payload.careRequirements.agreedCareVisits === 'object') {
          // agreedCareVisits may be an object keyed by day names
          for (const [dayKey, dayVal] of Object.entries(payload.careRequirements.agreedCareVisits)) {
            const dayEnum = this.normalizeDay(dayKey);
            if (!dayEnum) continue;
            const s = dayVal as any;
            const slots = Array.isArray(s.slots) ? s.slots.map((sl: any, i: number) => pushSlot(sl, i)) : [];
            schedulesCreate.push({
              tenantId: tenantId.toString(),
              day: dayEnum,
              enabled: s.enabled === undefined ? true : !!s.enabled,
              lunchStart: s.lunchStart ?? s.lunch_start ?? null,
              lunchEnd: s.lunchEnd ?? s.lunch_end ?? null,
              slots: slots.length ? { create: slots } : undefined,
            });
          }
        }

        if (schedulesCreate.length) {
          cr.schedules = { create: schedulesCreate };
        }

        data.careRequirements = { create: cr };
      }

      // Medical information is nested and may include arrays
      if (payload.medicalInfo) {
        const mi: any = { ...payload.medicalInfo, tenantId: tenantId.toString() };
        if (Array.isArray(payload.medicalInfo.medications) && payload.medicalInfo.medications.length) {
          mi.medications = { create: payload.medicalInfo.medications.map((m: any) => ({ ...m, tenantId: tenantId.toString() })) };
        }
        if (Array.isArray(payload.medicalInfo.clientAllergies) && payload.medicalInfo.clientAllergies.length) {
          mi.clientAllergies = { create: payload.medicalInfo.clientAllergies.map((a: any) => ({ ...a, tenantId: tenantId.toString() })) };
        }
        data.medicalInfo = { create: mi };
      }

      // MovingHandling may include IntakeLog array
      if (payload.movingHandling) {
        const mh: any = { ...payload.movingHandling, tenantId: tenantId.toString() };
        if (Array.isArray(payload.movingHandling.IntakeLog) && payload.movingHandling.IntakeLog.length) {
          mh.IntakeLog = { create: payload.movingHandling.IntakeLog.map((i: any) => ({ ...i, tenantId: tenantId.toString() })) };
        }
        data.movingHandling = { create: mh };
      }

      // carers (CarePlanCarer) - array of carerId strings or objects
      if (Array.isArray(payload.carers) && payload.carers.length) {
        const carersCreate = payload.carers.map((c: any) => {
          if (typeof c === 'string') return { tenantId: tenantId.toString(), carerId: c };
          return { tenantId: tenantId.toString(), carerId: c.carerId, ...('role' in c ? { role: c.role } : {}) };
        });
        data.carers = { create: carersCreate };
      }

      // include shape for returning full nested relations
      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: { include: { schedules: { include: { slots: true } } } },
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      // create the care plan with nested relations when present
      // Prisma client types may be out-of-date in dev; cast to any so the code compiles until `prisma generate` is run
      const created = await (this.prisma as any).carePlan.create({ data, include: includeShape });

      return res.status(201).json(created);
    } catch (error: any) {
      console.error('createCarePlan error', error);
      return res.status(500).json({ error: getUserFriendlyError(error) });
    }
  }

  // Update an existing care plan and optionally upsert careRequirements + schedules/slots
  public async updateCarePlan(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const id = req.params.id;
      if (!id) return res.status(400).json({ error: 'carePlan id required in path' });

      const payload = req.body || {};

      // Build top-level carePlan update data
      const updateData: any = {};
      if (payload.title !== undefined) updateData.title = payload.title;
      if (payload.description !== undefined) updateData.description = payload.description;
      if (payload.startDate !== undefined) updateData.startDate = this.toDateOrNull(payload.startDate);
      if (payload.endDate !== undefined) updateData.endDate = this.toDateOrNull(payload.endDate);
      if (payload.status !== undefined) updateData.status = payload.status;

      // Helper to build schedulesCreate (same shape as create endpoint)
      const buildSchedulesCreate = (careReq: any) => {
        const schedulesCreate: any[] = [];
        const pushSlot = (slot: any, idx: number) => {
          if (!slot) return null;
          return {
            startTime: slot.startTime ?? slot.start ?? slot.from ?? slot.start_time ?? slot.startTimeString ?? slot.start_time_string ?? slot.startTime,
            endTime: slot.endTime ?? slot.end ?? slot.to ?? slot.end_time ?? slot.endTimeString ?? slot.end_time_string ?? slot.endTime,
            externalId: slot.externalId ?? slot.id ?? slot.clientId ?? null,
            position: typeof slot.position === 'number' ? slot.position : idx,
          };
        };

        if (!careReq) return schedulesCreate;

        if (Array.isArray(careReq.schedules) && careReq.schedules.length) {
          for (const s of careReq.schedules) {
            const dayEnum = this.normalizeDay(s.day || s.name || s.dayOfWeek || (s.day && String(s.day)));
            if (!dayEnum) continue;
            const slots = Array.isArray(s.slots) ? s.slots.map((sl: any, i: number) => pushSlot(sl, i)).filter(Boolean) : [];
            schedulesCreate.push({
              tenantId: tenantId.toString(),
              day: dayEnum,
              enabled: s.enabled === undefined ? true : !!s.enabled,
              lunchStart: s.lunchStart ?? s.lunch_start ?? null,
              lunchEnd: s.lunchEnd ?? s.lunch_end ?? null,
              slots: slots.length ? { create: slots } : undefined,
            });
          }
        } else if (careReq.agreedCareVisits && typeof careReq.agreedCareVisits === 'object') {
          for (const [dayKey, dayVal] of Object.entries(careReq.agreedCareVisits)) {
            const dayEnum = this.normalizeDay(dayKey);
            if (!dayEnum) continue;
            const s = dayVal as any;
            const slots = Array.isArray(s.slots) ? s.slots.map((sl: any, i: number) => pushSlot(sl, i)).filter(Boolean) : [];
            schedulesCreate.push({
              tenantId: tenantId.toString(),
              day: dayEnum,
              enabled: s.enabled === undefined ? true : !!s.enabled,
              lunchStart: s.lunchStart ?? s.lunch_start ?? null,
              lunchEnd: s.lunchEnd ?? s.lunch_end ?? null,
              slots: slots.length ? { create: slots } : undefined,
            });
          }
        }

        return schedulesCreate;
      };

      // Run updates in a transaction: update carePlan, upsert careRequirements and replace schedules if provided, and replace carers if provided
      await this.prisma.$transaction(async (tx) => {
        if (Object.keys(updateData).length) {
          await tx.carePlan.update({ where: { id }, data: updateData });
        }

        if (payload.careRequirements) {
          const cr = payload.careRequirements;
          const schedulesCreate = buildSchedulesCreate(cr);

          const createObj: any = {
            tenantId: tenantId.toString(),
            carePlanId: id,
          };
          if (cr.careType !== undefined) createObj.careType = cr.careType;
          if (schedulesCreate.length) createObj.schedules = { create: schedulesCreate };

          const updateObj: any = {};
          if (cr.careType !== undefined) updateObj.careType = cr.careType;
          if (schedulesCreate.length) updateObj.schedules = { deleteMany: {}, create: schedulesCreate };

          await tx.careRequirements.upsert({
            where: { carePlanId: id },
            create: createObj,
            update: updateObj,
          });
        }

        if (Array.isArray(payload.carers)) {
          // replace existing carers for this care plan
          await tx.carePlanCarer.deleteMany({ where: { tenantId: tenantId.toString(), carePlanId: id } });
          if (payload.carers.length) {
            const carersCreate = payload.carers.map((c: any) => (typeof c === 'string' ? { tenantId: tenantId.toString(), carePlanId: id, carerId: c } : { tenantId: tenantId.toString(), carePlanId: id, carerId: c.carerId, ...('role' in c ? { role: c.role } : {}) }));
            // use createMany where possible for efficiency
            try {
              await tx.carePlanCarer.createMany({ data: carersCreate });
            } catch (e) {
              // fallback to individual creates (handles DBs that may not support createMany with certain datatypes)
              for (const rc of carersCreate) await tx.carePlanCarer.create({ data: rc });
            }
          }
        }
      });

      // return updated care plan with nested schedules/slots
      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: { include: { schedules: { include: { slots: true } } } },
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      const updated = await (this.prisma as any).carePlan.findUnique({ where: { id }, include: includeShape });
      return res.json(updated);
    } catch (error: any) {
      console.error('updateCarePlan error', error);
      return res.status(500).json({ error: getUserFriendlyError(error) });
    }
  }

  // Get all care plans for a tenant (with optional pagination)
  public async listCarePlans(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const page = parseInt((req.query.page as string) || '1', 10);
      const pageSize = parseInt((req.query.pageSize as string) || '50', 10);
      const skip = (Math.max(page, 1) - 1) * pageSize;

      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: { include: { schedules: { include: { slots: true } } } },
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      const [items, total] = await Promise.all([
        (this.prisma as any).carePlan.findMany({
          where: { tenantId: tenantId.toString() },
          skip,
          take: pageSize,
          orderBy: { createdAt: 'desc' },
          include: includeShape,
        }),
        (this.prisma as any).carePlan.count({ where: { tenantId: tenantId.toString() } }),
      ]);

      return res.json({ items, total, page, pageSize });
    } catch (error: any) {
      console.error('listCarePlans error', error);
      return res.status(500).json({ error: 'Failed to list care plans', details: error?.message });
    }
  }

  // Get care plans for a specific clientId
  public async getCarePlansByClient(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const clientId = req.params.clientId;
      if (!clientId) return res.status(400).json({ error: 'clientId required in path' });

      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: { include: { schedules: { include: { slots: true } } } },
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      const plans = await (this.prisma as any).carePlan.findMany({
        where: { tenantId: tenantId.toString(), clientId },
        orderBy: { createdAt: 'desc' },
        include: includeShape,
      });

      return res.json(plans);
    } catch (error: any) {
      console.error('getCarePlansByClient error', error);
      return res.status(500).json({ error: 'Failed to fetch care plans for client', details: error?.message });
    }
  }

  // Get care plans by carerId (find carePlanIds from CarePlanCarer)
  public async getCarePlansByCarer(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const carerId = req.params.carerId;
      if (!carerId) return res.status(400).json({ error: 'carerId required in path' });

      const links = await (this.prisma as any).carePlanCarer.findMany({
        where: { tenantId: tenantId.toString(), carerId },
        select: { carePlanId: true },
      });

      const carePlanIds = links.map((l: any) => l.carePlanId);
      if (!carePlanIds.length) return res.json([]);

      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: { include: { schedules: { include: { slots: true } } } },
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      const plans = await (this.prisma as any).carePlan.findMany({
        where: { id: { in: carePlanIds }, tenantId: tenantId.toString() },
        orderBy: { createdAt: 'desc' },
        include: includeShape,
      });

      return res.json(plans);
    } catch (error: any) {
      console.error('getCarePlansByCarer error', error);
      return res.status(500).json({ error: 'Failed to fetch care plans by carer', details: error?.message });
    }
  }
}
