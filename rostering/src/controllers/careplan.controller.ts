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
      attachNested('careRequirements', payload.careRequirements ? { ...payload.careRequirements, tenantId: tenantId.toString() } : undefined);

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
        careRequirements: true,
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
        careRequirements: true,
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
        careRequirements: true,
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
        careRequirements: true,
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
