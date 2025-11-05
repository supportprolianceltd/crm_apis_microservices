import { PrismaClient } from '@prisma/client';
import { logger } from '../utils/logger';

export interface RosteringConstraints {
  id: string;
  tenantId: string;
  name: string;
  wtdMaxHoursPerWeek: number;
  restPeriodHours: number;
  bufferMinutes: number;
  travelMaxMinutes: number;
  continuityTargetPercent: number;
  maxDailyHours?: number | null;           // 👈 allow null
  minRestBetweenVisits?: number | null;    // 👈 allow null
  maxTravelTimePerVisit?: number | null;   // 👈 allow null
  isActive?: boolean | null;               // 👈 allow null
}


export class ConstraintsService {
  constructor(private prisma: PrismaClient) {}

  /**
   * Get active constraints for a tenant
   */
  async getActiveConstraints(tenantId: string): Promise<RosteringConstraints> {
    try {
      const constraints = await this.prisma.rosteringConstraints.findFirst({
        where: {
          tenantId,
          isActive: true
        }
      });

      if (constraints) {
        return constraints;
      }

      // Create default constraints if none exist
      return await this.createDefaultConstraints(tenantId);
    } catch (error) {
      logger.error('Failed to get constraints:', error);
      // Return hardcoded defaults as fallback
      return this.getHardcodedDefaults(tenantId);
    }
  }

  /**
   * Create default constraints for a tenant
   */
  async createDefaultConstraints(tenantId: string): Promise<RosteringConstraints> {
    try {
      return await this.prisma.rosteringConstraints.create({
        data: {
          tenantId,
          name: 'Default Rules',
          wtdMaxHoursPerWeek: 48,
          restPeriodHours: 11,
          bufferMinutes: 5,
          travelMaxMinutes: 20,
          continuityTargetPercent: 85,
          maxDailyHours: 10,
          minRestBetweenVisits: 0,
          maxTravelTimePerVisit: 60,
          isActive: true,
          createdBy: 'system'
        }
      });
    } catch (error) {
      logger.error('Failed to create default constraints:', error);
      return this.getHardcodedDefaults(tenantId);
    }
  }

  /**
   * Update constraints for a tenant
   */
  async updateConstraints(
    tenantId: string, 
    updates: Partial<RosteringConstraints>
  ): Promise<RosteringConstraints> {
    try {
      const existing = await this.getActiveConstraints(tenantId);

      return await this.prisma.rosteringConstraints.update({
        where: { id: existing.id },
        data: {
          ...updates,
          updatedAt: new Date()
        }
      });
    } catch (error) {
      logger.error('Failed to update constraints:', error);
      throw new Error('Failed to update rostering constraints');
    }
  }

  /**
   * Create a new rule set
   */
  async createRuleSet(
    tenantId: string,
    name: string,
    constraints: Partial<RosteringConstraints>
  ): Promise<RosteringConstraints> {
    try {
      // Deactivate current active rules
      await this.prisma.rosteringConstraints.updateMany({
        where: { tenantId, isActive: true },
        data: { isActive: false }
      });

      // Create new active rule set
      return await this.prisma.rosteringConstraints.create({
        data: {
          tenantId,
          name,
          wtdMaxHoursPerWeek: constraints.wtdMaxHoursPerWeek || 48,
          restPeriodHours: constraints.restPeriodHours || 11,
          bufferMinutes: constraints.bufferMinutes || 5,
          travelMaxMinutes: constraints.travelMaxMinutes || 20,
          continuityTargetPercent: constraints.continuityTargetPercent || 85,
          maxDailyHours: constraints.maxDailyHours || 10,
          minRestBetweenVisits: constraints.minRestBetweenVisits || 0,
          maxTravelTimePerVisit: constraints.maxTravelTimePerVisit || 60,
          isActive: true,
          createdBy: 'coordinator'
        }
      });
    } catch (error) {
      logger.error('Failed to create rule set:', error);
      throw new Error('Failed to create new rule set');
    }
  }

  /**
   * Get all rule sets for a tenant
   */
  async getRuleSets(tenantId: string): Promise<RosteringConstraints[]> {
    return await this.prisma.rosteringConstraints.findMany({
      where: { tenantId },
      orderBy: { isActive: 'desc' }
    });
  }

  /**
   * Validate assignments against constraints
   */
  validateAssignment(
    constraints: RosteringConstraints,
    assignment: {
      carerHoursThisWeek: number;
      lastShiftEnd?: Date;
      nextShiftStart?: Date;
      travelTime: number;
    }
  ): { isValid: boolean; violations: string[] } {
    const violations: string[] = [];

    // Check WTD hours
    if (assignment.carerHoursThisWeek > constraints.wtdMaxHoursPerWeek) {
      violations.push(`Exceeds WTD maximum hours (${constraints.wtdMaxHoursPerWeek}h)`);
    }

    // Check rest period
    if (assignment.lastShiftEnd && assignment.nextShiftStart) {
      const hoursBetween = (assignment.nextShiftStart.getTime() - assignment.lastShiftEnd.getTime()) / (1000 * 60 * 60);
      if (hoursBetween < constraints.restPeriodHours) {
        violations.push(`Insufficient rest period (${hoursBetween.toFixed(1)}h < ${constraints.restPeriodHours}h)`);
      }
    }

    // Check travel time
    if (assignment.travelTime > constraints.travelMaxMinutes) {
      violations.push(`Exceeds maximum travel time (${assignment.travelTime}m > ${constraints.travelMaxMinutes}m)`);
    }

    return {
      isValid: violations.length === 0,
      violations
    };
  }

  /**
   * Hardcoded defaults as fallback
   */
  private getHardcodedDefaults(tenantId: string): RosteringConstraints {
    return {
      id: 'default',
      tenantId,
      name: 'Default Rules',
      wtdMaxHoursPerWeek: 48,
      restPeriodHours: 11,
      bufferMinutes: 5,
      travelMaxMinutes: 20,
      continuityTargetPercent: 85,
      maxDailyHours: 10,
      minRestBetweenVisits: 0,
      maxTravelTimePerVisit: 60,
      isActive: true
    };
  }
}