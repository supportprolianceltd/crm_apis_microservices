import { PrismaClient, RosteringConstraints as PrismaRosteringConstraints } from '@prisma/client';
import { logger } from '../utils/logger';

// Use the generated Prisma type instead of custom interface
export type RosteringConstraints = PrismaRosteringConstraints;

export interface UpdateUserInfo {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
}

export interface ManualChangeValidation {
  isValid: boolean;
  hardBlocks: string[];
  softWarnings: string[];
  affectedAssignments?: string[];
}

export class ConstraintsService {
  constructor(private prisma: PrismaClient) {}


   /**
   * ✅ NEW: Validate manual roster change before applying
   */
  async validateManualChange(
    tenantId: string,
    change: {
      assignmentId?: string;
      visitId: string;
      newCarerId: string;
      newScheduledTime?: Date;
    }
  ): Promise<ManualChangeValidation> {
    const constraints = await this.getActiveConstraints(tenantId);
    const validation: ManualChangeValidation = {
      isValid: true,
      hardBlocks: [],
      softWarnings: []
    };

    // 1. Get carer details
    const carer = await this.prisma.carer.findUnique({
      where: { id: change.newCarerId }
    });

    if (!carer) {
      validation.isValid = false;
      validation.hardBlocks.push('Carer not found');
      return validation;
    }

    // 2. Get visit details
    const visit = await this.prisma.externalRequest.findUnique({
      where: { id: change.visitId }
    });

    if (!visit) {
      validation.isValid = false;
      validation.hardBlocks.push('Visit not found');
      return validation;
    }

    // 3. Check skills match
    const hasSkills = this.checkSkillsMatch(visit.requirements, carer.skills);
    if (!hasSkills) {
      validation.isValid = false;
      validation.hardBlocks.push(
        `Carer lacks required skills: ${visit.requirements}`
      );
    }

    // 4. Check WTD compliance
    const scheduledTime = change.newScheduledTime || visit.scheduledStartTime!;
    const weekStart = this.getWeekStart(scheduledTime);
    const weekEnd = this.getWeekEnd(weekStart);

    const carerWeeklyHours = await this.getCarerWeeklyHours(
      change.newCarerId,
      weekStart,
      weekEnd
    );

    const visitHours = (visit.estimatedDuration || 60) / 60;
    const totalHours = carerWeeklyHours + visitHours;

    if (totalHours > constraints.wtdMaxHoursPerWeek) {
      validation.isValid = false;
      validation.hardBlocks.push(
        `WTD violation: ${totalHours.toFixed(1)}h exceeds ${constraints.wtdMaxHoursPerWeek}h limit`
      );
    } else if (totalHours > constraints.wtdMaxHoursPerWeek * 0.9) {
      validation.softWarnings.push(
        `Approaching WTD limit: ${totalHours.toFixed(1)}h / ${constraints.wtdMaxHoursPerWeek}h`
      );
    }

    // 5. Check time conflicts
    const conflicts = await this.checkTimeConflicts(
      change.newCarerId,
      scheduledTime,
      new Date(scheduledTime.getTime() + (visit.estimatedDuration || 60) * 60000)
    );

    if (conflicts.length > 0) {
      validation.isValid = false;
      validation.hardBlocks.push(
        `Time conflict with ${conflicts.length} existing assignment(s)`
      );
      validation.affectedAssignments = conflicts.map(c => c.id);
    }

    // 6. Check rest period
    const restViolation = await this.checkRestPeriodViolation(
      change.newCarerId,
      scheduledTime,
      constraints.restPeriodHours
    );

    if (restViolation) {
      validation.isValid = false;
      validation.hardBlocks.push(
        `Rest period violation: Less than ${constraints.restPeriodHours}h since last shift`
      );
    }

    // 7. Check travel time
    const travelViolation = await this.checkTravelTimeViolation(
      change.newCarerId,
      visit,
      constraints.travelMaxMinutes
    );

    if (travelViolation.exceeds) {
      validation.softWarnings.push(
        `Travel time ${travelViolation.actualMinutes}min exceeds recommended ${constraints.travelMaxMinutes}min`
      );
    }

    return validation;
  }

  // ✅ Helper methods
  private checkSkillsMatch(requirements: string | null, carerSkills: string[]): boolean {
    if (!requirements) return true;
    const reqLower = requirements.toLowerCase();
    return carerSkills.some(skill => reqLower.includes(skill.toLowerCase()));
  }

  private getWeekStart(date: Date): Date {
    const weekStart = new Date(date);
    weekStart.setDate(date.getDate() - date.getDay());
    weekStart.setHours(0, 0, 0, 0);
    return weekStart;
  }

  private getWeekEnd(weekStart: Date): Date {
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 7);
    return weekEnd;
  }

  private async getCarerWeeklyHours(
    carerId: string,
    weekStart: Date,
    weekEnd: Date
  ): Promise<number> {
    const assignments = await this.prisma.assignment.findMany({
      where: {
        carerId,
        scheduledTime: { gte: weekStart, lt: weekEnd },
        status: { in: ['PENDING', 'ACCEPTED', 'COMPLETED'] }
      },
      include: { visit: true }
    });

    return assignments.reduce((total, a) => {
      return total + ((a.visit.estimatedDuration || 60) / 60);
    }, 0);
  }

  private async checkTimeConflicts(
    carerId: string,
    startTime: Date,
    endTime: Date
  ) {
    return await this.prisma.assignment.findMany({
      where: {
        carerId,
        status: { in: ['PENDING', 'ACCEPTED'] },
        OR: [
          { scheduledTime: { lt: endTime, gte: startTime } },
          { estimatedEndTime: { gt: startTime, lte: endTime } }
        ]
      }
    });
  }

  private async checkRestPeriodViolation(
    carerId: string,
    proposedTime: Date,
    restPeriodHours: number
  ): Promise<boolean> {
    const lastAssignment = await this.prisma.assignment.findFirst({
      where: {
        carerId,
        estimatedEndTime: { lt: proposedTime },
        status: { in: ['ACCEPTED', 'COMPLETED'] }
      },
      orderBy: { estimatedEndTime: 'desc' }
    });

    if (!lastAssignment) return false;

    const hoursSinceLastShift = 
      (proposedTime.getTime() - lastAssignment.estimatedEndTime.getTime()) / 
      (1000 * 60 * 60);

    return hoursSinceLastShift < restPeriodHours;
  }

  private async checkTravelTimeViolation(
    carerId: string,
    visit: any,
    maxTravelMinutes: number
  ): Promise<{ exceeds: boolean; actualMinutes: number }> {
    // Get carer's location
    const carer = await this.prisma.carer.findUnique({
      where: { id: carerId }
    });

    if (!carer?.latitude || !visit?.latitude) {
      return { exceeds: false, actualMinutes: 0 };
    }

    // Simple Haversine distance estimate
    const distance = this.calculateDistance(
      carer.latitude, carer.longitude || 0,
      visit.latitude, visit.longitude || 0
    );

    const estimatedMinutes = Math.ceil(distance / 500) + 10; // 500m/min + 10min base

    return {
      exceeds: estimatedMinutes > maxTravelMinutes,
      actualMinutes: estimatedMinutes
    };
  }

  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371e3;
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c;
  }
  

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
    updates: Partial<RosteringConstraints>,
    updatedByUser?: UpdateUserInfo
  ): Promise<RosteringConstraints> {
    try {
      const existing = await this.getActiveConstraints(tenantId);

      const updateData: any = {
        ...updates,
        updatedAt: new Date(),
      };

      // Only add user tracking fields if user info is provided
      if (updatedByUser) {
        updateData.updatedBy = updatedByUser.id;
        updateData.updatedByEmail = updatedByUser.email;
        updateData.updatedByFirstName = updatedByUser.firstName || null;
        updateData.updatedByLastName = updatedByUser.lastName || null;

        logger.debug('Updating constraints with user info', {
          userId: updatedByUser.id,
          email: updatedByUser.email,
          firstName: updatedByUser.firstName,
          lastName: updatedByUser.lastName
        });
      } else {
        // Set default values for tracking fields when no user info provided
        updateData.updatedBy = null;
        updateData.updatedByEmail = null;
        updateData.updatedByFirstName = null;
        updateData.updatedByLastName = null;
        logger.warn('Updating constraints without user info');
      }

      const result = await this.prisma.rosteringConstraints.update({
        where: { id: existing.id },
        data: updateData
      });

      logger.info('Constraints updated successfully', {
        constraintId: result.id,
        tenantId: result.tenantId
      });

      return result;
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
      isActive: true,
      createdBy: 'system',
      updatedBy: null,
      updatedByEmail: null,
      updatedByFirstName: null,
      updatedByLastName: null,
      createdAt: new Date(),
      updatedAt: new Date()
    };
  }
}


