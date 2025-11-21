// Enum values from schema.prisma
const CARE_PLAN_STATUS = ['ACTIVE', 'INACTIVE', 'COMPLETED'];
// Allowed careType enum values (must match prisma enum `careType`)
const ALLOWED_CARE_TYPES = ['SINGLE_HANDED_CALL', 'DOUBLE_HANDED_CALL', 'SPECIALCARE'];

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

  // Generate CarerVisit rows for a care plan using its careRequirements.schedules slots
  // Window selection rules (priority):
  // 1) If careRequirements.contractStart/contractEnd provided they act as hard bounds for generation.
  // 2) If careRequirements.rollingWeeks is provided it overrides default rolling window length.
  // 3) A caller may pass an explicit rollingWeeksParam into this method (highest override).
  private async generateVisitsForCarePlan(carePlan: any, tenantId: string, rollingWeeksParam?: number) {
    try {
      if (!carePlan || !carePlan.careRequirements || !Array.isArray(carePlan.careRequirements.schedules)) return;
      // Determine rolling weeks: priority - explicit param > careRequirements.rollingWeeks > default
      const DEFAULT_ROLLING_WEEKS = 1;
      const cr = carePlan.careRequirements || {};
      const rollingWeeks = (typeof rollingWeeksParam === 'number' && rollingWeeksParam > 0)
        ? Math.floor(rollingWeeksParam)
        : (typeof cr.rollingWeeks === 'number' && cr.rollingWeeks > 0 ? Math.floor(cr.rollingWeeks) : DEFAULT_ROLLING_WEEKS);

      const schedules = (carePlan.careRequirements.schedules || []).filter((s: any) => s && s.enabled && Array.isArray(s.slots) && s.slots.length);
      if (!schedules.length) return;

      const now = new Date();
      const planStart = carePlan.startDate ? new Date(carePlan.startDate) : now;
      // Use contractStart/contractEnd from careRequirements as optional hard bounds.
      // If either contractStart or contractEnd is provided, the contract bounds take priority
      // over the rollingWeeks window (i.e. we generate only between contractStart/contractEnd
      // intersected with plan start/end and today as needed).
      const contractStart = cr.contractStart ? new Date(cr.contractStart) : null;
      const contractEnd = cr.contractEnd ? new Date(cr.contractEnd) : null;

      const hasContractBounds = Boolean(contractStart || contractEnd);

      // Pick window start: must be at least today and planStart, and contractStart if provided
      let windowStart = planStart > now ? planStart : now;
      if (contractStart && contractStart > windowStart) windowStart = contractStart;

      const planEnd = carePlan.endDate ? new Date(carePlan.endDate) : null;

      let windowEnd: Date;
      if (hasContractBounds) {
        // Use contract bounds (if provided) intersected with planEnd (if provided)
        windowEnd = contractEnd ? new Date(contractEnd) : (planEnd ? new Date(planEnd) : new Date(windowStart.getTime() + rollingWeeks * 7 * 24 * 60 * 60 * 1000));
        if (planEnd && planEnd < windowEnd) windowEnd = planEnd;
      } else {
        // No contract bounds: use rollingWeeks window (from windowStart) but do not extend past planEnd (if present)
        const windowEndCandidate = new Date(windowStart.getTime() + rollingWeeks * 7 * 24 * 60 * 60 * 1000);
        windowEnd = planEnd ? (planEnd < windowEndCandidate ? planEnd : windowEndCandidate) : windowEndCandidate;
      }

      // Map day enum to JS weekday number (0=Sunday..6=Saturday)
      const dayOfWeekMap: Record<string, number> = { SUNDAY: 0, MONDAY: 1, TUESDAY: 2, WEDNESDAY: 3, THURSDAY: 4, FRIDAY: 5, SATURDAY: 6 };

      const visitsToCreate: any[] = [];

      // Iterate each date in the window (UTC days)
      for (let cur = new Date(Date.UTC(windowStart.getUTCFullYear(), windowStart.getUTCMonth(), windowStart.getUTCDate())); cur <= windowEnd; cur.setUTCDate(cur.getUTCDate() + 1)) {
        const weekday = cur.getUTCDay();

        for (const sched of schedules) {
          const schedDay = sched.day as string;
          if (dayOfWeekMap[schedDay] !== weekday) continue;

          for (const slot of sched.slots) {
            // slot.startTime and endTime are stored as TIME mapped to Date objects (date portion is epoch)
            const slotStart = new Date(slot.startTime);
            const slotEnd = new Date(slot.endTime);

            const visitStart = new Date(Date.UTC(cur.getUTCFullYear(), cur.getUTCMonth(), cur.getUTCDate(), slotStart.getUTCHours(), slotStart.getUTCMinutes(), slotStart.getUTCSeconds()));
            const visitEnd = new Date(Date.UTC(cur.getUTCFullYear(), cur.getUTCMonth(), cur.getUTCDate(), slotEnd.getUTCHours(), slotEnd.getUTCMinutes(), slotEnd.getUTCSeconds()));

            // Only create visits that fall within windowStart..windowEnd
            if (visitEnd < windowStart || visitStart > windowEnd) continue;

            visitsToCreate.push({
              tenantId: tenantId.toString(),
              carePlanId: carePlan.id,
              startDate: visitStart,
              endDate: visitEnd,
              generatedFromCarePlan: true,
              // inherit careType from care plan when present
              careType: (carePlan.careRequirements && ALLOWED_CARE_TYPES.includes(carePlan.careRequirements.careType)) ? carePlan.careRequirements.careType : undefined,
            });
          }
        }
      }

      if (visitsToCreate.length) {
        // create in batches to avoid too-large single insert
        const BATCH = 200;
        for (let i = 0; i < visitsToCreate.length; i += BATCH) {
          const batch = visitsToCreate.slice(i, i + BATCH);
          try {
            await (this.prisma as any).carerVisit.createMany({ data: batch });
          } catch (e) {
            console.error('Failed to create carer visits batch', e);
          }
        }
      }
    } catch (e) {
      console.error('generateVisitsForCarePlan error', e);
    }
  }

  public async createCarePlan(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const payload = req.body || {};
      console.log(`Attempting to create careplan for tenant ${tenantId}`)
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
        const cr: any = { tenantId: tenantId.toString() };
        if (payload.careRequirements.careType !== undefined && payload.careRequirements.careType !== null) {
          if (typeof payload.careRequirements.careType === 'string' && ALLOWED_CARE_TYPES.includes(payload.careRequirements.careType)) {
            cr.careType = payload.careRequirements.careType;
          } else {
            // invalid careType should have been caught by validation, but guard here to avoid Prisma errors
            console.warn('Ignoring invalid careRequirements.careType value on create:', payload.careRequirements.careType);
          }
        }

        // Persist optional contract bounds and rolling window when provided
        if (payload.careRequirements.contractStart) cr.contractStart = this.toDateOrNull(payload.careRequirements.contractStart);
        if (payload.careRequirements.contractEnd) cr.contractEnd = this.toDateOrNull(payload.careRequirements.contractEnd);
        if (typeof payload.careRequirements.rollingWeeks === 'number') cr.rollingWeeks = Math.max(0, Math.floor(payload.careRequirements.rollingWeeks));

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

        // medications: filter out completely empty entries and only attach nested create when non-empty
        if (Array.isArray(payload.medicalInfo.medications) && payload.medicalInfo.medications.length) {
          const meds = payload.medicalInfo.medications
            .map((m: any) => ({ ...m, tenantId: tenantId.toString() }))
            .filter((m: any) => m && (
              (m.drugName && String(m.drugName).trim() !== '') ||
              (m.dosage && String(m.dosage).trim() !== '') ||
              (m.frequency && String(m.frequency).trim() !== '')
            ));
          if (meds.length) {
            mi.medications = { create: meds };
          } else {
            delete mi.medications;
          }
        } else {
          delete mi.medications;
        }

        // clientAllergies: only attach when non-empty
        if (Array.isArray(payload.medicalInfo.clientAllergies) && payload.medicalInfo.clientAllergies.length) {
          const allergies = payload.medicalInfo.clientAllergies
            .map((a: any) => ({ ...a, tenantId: tenantId.toString() }))
            .filter(Boolean);
          if (allergies.length) {
            mi.clientAllergies = { create: allergies };
          } else {
            delete mi.clientAllergies;
          }
        } else {
          delete mi.clientAllergies;
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
      let includeShape: any = {
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
      };

      // Optional: include carer visits for this care plan when requested via query ?includeVisits=true
      try {
        const includeVisits = String(req.query.includeVisits || '').toLowerCase();
        if (includeVisits === 'true' || includeVisits === '1') {
          includeShape.carerVisits = { include: { tasks: true } };
        }
      } catch (e) {
        // ignore and proceed without visits
      }

      // create the care plan with nested relations when present
      // Prisma client types may be out-of-date in dev; cast to any so the code compiles until `prisma generate` is run
      const created = await (this.prisma as any).carePlan.create({ data, include: includeShape });
      console.log("Careplan created successfully")

      // Generate CarerVisit instances for initial rolling window (non-blocking for caller)
      try {
        await this.generateVisitsForCarePlan(created, tenantId.toString());
      } catch (e) {
        console.error('Error generating visits for care plan', e);
      }

      return res.status(201).json(created);
    } catch (error: any) {
      console.error('createCarePlan error', error);
      // Return the raw error details for debugging (message + optional stack in non-production)
      const errPayload = error instanceof Error
        ? { message: error.message, stack: error.stack }
        : error;
      return res.status(500).json({ error: errPayload });
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
          if (cr.careType !== undefined && ALLOWED_CARE_TYPES.includes(cr.careType)) createObj.careType = cr.careType;
          if (cr.contractStart !== undefined) createObj.contractStart = this.toDateOrNull(cr.contractStart);
          if (cr.contractEnd !== undefined) createObj.contractEnd = this.toDateOrNull(cr.contractEnd);
          if (cr.rollingWeeks !== undefined) createObj.rollingWeeks = typeof cr.rollingWeeks === 'number' ? Math.max(0, Math.floor(cr.rollingWeeks)) : null;
          if (schedulesCreate.length) createObj.schedules = { create: schedulesCreate };

          const updateObj: any = {};
          if (cr.careType !== undefined && ALLOWED_CARE_TYPES.includes(cr.careType)) updateObj.careType = cr.careType;
          if (cr.contractStart !== undefined) updateObj.contractStart = this.toDateOrNull(cr.contractStart);
          if (cr.contractEnd !== undefined) updateObj.contractEnd = this.toDateOrNull(cr.contractEnd);
          if (cr.rollingWeeks !== undefined) updateObj.rollingWeeks = typeof cr.rollingWeeks === 'number' ? Math.max(0, Math.floor(cr.rollingWeeks)) : null;
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

      // If schedules or dates changed, reconcile generated visits for this care plan
      if (payload.careRequirements || payload.startDate !== undefined || payload.endDate !== undefined) {
        try {
          // delete previously generated visits for this care plan and recreate for the rolling window
          await (this.prisma as any).carerVisit.deleteMany({ where: { tenantId: tenantId.toString(), carePlanId: id, generatedFromCarePlan: true } });
          await this.generateVisitsForCarePlan(updated, tenantId.toString());
        } catch (e) {
          console.error('Failed to reconcile generated visits for care plan update', e);
        }
      }

      return res.json(updated);
    } catch (error: any) {
      console.error('updateCarePlan error', error);
      const errPayload = error instanceof Error
        ? { message: error.message, stack: error.stack }
        : error;
      return res.status(500).json({ error: errPayload });
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

  // Get a single care plan by ID
  public async getCarePlanById(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const id = req.params.id || req.params['carePlanId'];
      if (!id) return res.status(400).json({ error: 'carePlan id required in path' });

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

      const plan = await (this.prisma as any).carePlan.findUnique({ where: { id }, include: includeShape });
      if (!plan) return res.status(404).json({ error: 'Care plan not found' });
      if (plan.tenantId !== tenantId.toString()) return res.status(403).json({ error: 'Access denied to this care plan' });

      return res.json(plan);
    } catch (error: any) {
      console.error('getCarePlanById error', error);
      return res.status(500).json({ error: 'Failed to fetch care plan', details: error?.message });
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

  // Delete a care plan and related generated visits
  public async deleteCarePlan(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const id = req.params.id;
      if (!id) return res.status(400).json({ error: 'carePlan id required in path' });

      // Verify the care plan exists and belongs to this tenant
      const plan = await (this.prisma as any).carePlan.findUnique({ where: { id }, select: { id: true, tenantId: true } });
      if (!plan) return res.status(404).json({ error: 'Care plan not found' });
      if (plan.tenantId !== tenantId.toString()) return res.status(403).json({ error: 'Access denied to this care plan' });

      // Transaction: delete any CarerVisit rows linked to this care plan (including generated ones), then delete the care plan
      await (this.prisma as any).$transaction(async (tx: any) => {
        try {
          await tx.carerVisit.deleteMany({ where: { tenantId: tenantId.toString(), carePlanId: id } });
        } catch (e) {
          // log and continue - deletion of visits should not block care plan deletion
          console.error('Failed to delete carer visits for care plan', id, e);
        }

        await tx.carePlan.delete({ where: { id } });
      });

      return res.status(204).send();
    } catch (error: any) {
      console.error('deleteCarePlan error', error);
      return res.status(500).json({ error: 'Failed to delete care plan', details: getUserFriendlyError(error) });
    }
  }
}
