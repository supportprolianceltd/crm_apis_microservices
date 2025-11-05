import { PrismaClient } from '@prisma/client';
import { RosterGenerationService, RosterScenario } from './roster-generation.service';
import { MatchingService } from './matching.service';
import { NotificationService } from './notification.service';
import { logger } from '../utils/logger';

export interface DisruptionEvent {
  id: string;
  tenantId: string;
  type: DisruptionType;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  reportedBy: string;
  reportedAt: Date;
  
  // Affected entities
  affectedVisits: string[];
  affectedCarers: string[];
  affectedClients: string[];
  
  // Impact analysis
  impact: {
    totalVisitsAffected: number;
    clientsImpacted: number;
    carersImpacted: number;
    continuityBreaks: number;
    estimatedDelayMinutes: number;
  };
  
  // Resolution
  status: 'reported' | 'analyzing' | 'resolving' | 'resolved' | 'escalated';
  resolutionOptions?: ResolutionOption[];
  selectedResolution?: string;
  resolvedAt?: Date;
  resolvedBy?: string;
}

export type DisruptionType = 
  | 'carer_sick'
  | 'carer_unavailable'
  | 'visit_cancelled'
  | 'emergency_visit'
  | 'delay'
  | 'equipment_failure'
  | 'weather'
  | 'transport_issue'
  | 'other';

export interface ResolutionOption {
  id: string;
  strategy: 'redistribute' | 'overtime' | 'cancel' | 'reschedule';
  description: string;
  
  // Changes required
  changes: {
    reassignments: Array<{
      visitId: string;
      fromCarerId?: string;
      toCarerId: string;
      newScheduledTime?: Date;
    }>;
    cancellations: string[];
    overtimeRequired: Array<{
      carerId: string;
      additionalHours: number;
    }>;
  };
  
  // Impact assessment
  impact: {
    carersAffected: number;
    clientsAffected: number;
    continuityScore: number;
    travelTimeAdded: number;
    costImpact: number;
    complianceRisk: 'none' | 'low' | 'medium' | 'high';
  };
  
  score: number; // 0-100, higher is better
}

export class DisruptionService {
  constructor(
    private prisma: PrismaClient,
    private rosterService: RosterGenerationService,
    private matchingService: MatchingService,
    private notificationService: NotificationService
  ) {}

  /**
   * Report a new disruption
   */
  async reportDisruption(
    tenantId: string,
    data: {
      type: DisruptionType;
      description: string;
      reportedBy: string;
      affectedVisits?: string[];
      affectedCarers?: string[];
      severity?: 'low' | 'medium' | 'high' | 'critical';
    }
  ): Promise<DisruptionEvent> {
    try {
      logger.info('Reporting disruption', { tenantId, type: data.type });

      // Determine affected entities
      const affectedEntities = await this.identifyAffectedEntities(
        tenantId,
        data.type,
        data.affectedVisits || [],
        data.affectedCarers || []
      );

      // Calculate impact
      const impact = await this.calculateImpact(tenantId, affectedEntities);

      // Determine severity if not provided
      const severity = data.severity || this.determineSeverity(impact);

      // Create disruption event
      const disruption: DisruptionEvent = {
        id: `disruption_${Date.now()}`,
        tenantId,
        type: data.type,
        severity,
        description: data.description,
        reportedBy: data.reportedBy,
        reportedAt: new Date(),
        affectedVisits: affectedEntities.visits,
        affectedCarers: affectedEntities.carers,
        affectedClients: affectedEntities.clients,
        impact,
        status: 'reported'
      };

      // Store in database (requires Disruption model)
      // await this.prisma.disruption.create({ data: disruption });

      // Generate resolution options
      const resolutionOptions = await this.generateResolutionOptions(
        tenantId,
        disruption
      );
      disruption.resolutionOptions = resolutionOptions;
      disruption.status = 'analyzing';

      // Send notifications
      await this.notifyStakeholders(tenantId, disruption);

      logger.info(`Disruption reported: ${disruption.id}`, {
        type: data.type,
        severity,
        affectedVisits: affectedEntities.visits.length,
        optionsGenerated: resolutionOptions.length
      });

      return disruption;

    } catch (error) {
      logger.error('Failed to report disruption:', error);
      throw error;
    }
  }

  /**
   * Get disruption by ID
   */
  async getDisruption(disruptionId: string): Promise<DisruptionEvent | null> {
    // Would fetch from database
    // return await this.prisma.disruption.findUnique({ where: { id: disruptionId } });
    return null;
  }

  /**
   * Apply a resolution option
   */
  async applyResolution(
    disruptionId: string,
    resolutionId: string,
    appliedBy: string
  ): Promise<DisruptionEvent> {
    try {
      logger.info(`Applying resolution ${resolutionId} to disruption ${disruptionId}`);

      // Get disruption
      const disruption = await this.getDisruption(disruptionId);
      if (!disruption) {
        throw new Error('Disruption not found');
      }

      // Get resolution option
      const resolution = disruption.resolutionOptions?.find(r => r.id === resolutionId);
      if (!resolution) {
        throw new Error('Resolution option not found');
      }

      // Apply changes
      await this.executeResolution(disruption.tenantId, resolution);

      // Update disruption status
      disruption.status = 'resolved';
      disruption.selectedResolution = resolutionId;
      disruption.resolvedAt = new Date();
      disruption.resolvedBy = appliedBy;

      // Store update
      // await this.prisma.disruption.update({
      //   where: { id: disruptionId },
      //   data: disruption
      // });

      // Notify affected parties
      await this.notifyResolution(disruption, resolution);

      logger.info(`Resolution applied successfully: ${resolutionId}`);

      return disruption;

    } catch (error) {
      logger.error('Failed to apply resolution:', error);
      throw error;
    }
  }

  /**
   * Get active disruptions for a tenant
   */
  async getActiveDisruptions(tenantId: string): Promise<DisruptionEvent[]> {
    // Would query from database
    // return await this.prisma.disruption.findMany({
    //   where: {
    //     tenantId,
    //     status: { in: ['reported', 'analyzing', 'resolving'] }
    //   },
    //   orderBy: { reportedAt: 'desc' }
    // });
    return [];
  }

  // ========== PRIVATE HELPER METHODS ==========

  /**
   * Identify all affected entities
   */
  private async identifyAffectedEntities(
    tenantId: string,
    type: DisruptionType,
    visitIds: string[],
    carerIds: string[]
  ): Promise<{
    visits: string[];
    carers: string[];
    clients: string[];
  }> {
    const affectedVisits = new Set(visitIds);
    const affectedCarers = new Set(carerIds);
    const affectedClients = new Set<string>();

    // Type-specific logic
    switch (type) {
      case 'carer_sick':
      case 'carer_unavailable':
        // Get all visits assigned to these carers today
        for (const carerId of carerIds) {
          const carerVisits = await this.getCarerVisitsToday(tenantId, carerId);
          carerVisits.forEach(v => affectedVisits.add(v.id));
        }
        break;

      case 'visit_cancelled':
        // Just the specified visits
        break;

      case 'emergency_visit':
        // Would need to find overlapping visits
        break;
    }

    // Get clients for affected visits
    if (affectedVisits.size > 0) {
      const visits = await this.prisma.externalRequest.findMany({
        where: { id: { in: Array.from(affectedVisits) } },
        select: { id: true, requestorEmail: true }
      });

      visits.forEach(v => {
        affectedClients.add(v.requestorEmail);
      });
    }

    return {
      visits: Array.from(affectedVisits),
      carers: Array.from(affectedCarers),
      clients: Array.from(affectedClients)
    };
  }

  /**
   * Calculate impact of disruption
   */
  private async calculateImpact(
    tenantId: string,
    affectedEntities: {
      visits: string[];
      carers: string[];
      clients: string[];
    }
  ): Promise<DisruptionEvent['impact']> {
    // Calculate continuity breaks
    const continuityBreaks = await this.calculateContinuityBreaks(
      tenantId,
      affectedEntities.visits,
      affectedEntities.carers
    );

    // Estimate delay
    const estimatedDelayMinutes = affectedEntities.visits.length * 30; // Rough estimate

    return {
      totalVisitsAffected: affectedEntities.visits.length,
      clientsImpacted: affectedEntities.clients.length,
      carersImpacted: affectedEntities.carers.length,
      continuityBreaks,
      estimatedDelayMinutes
    };
  }

  /**
   * Determine severity based on impact
   */
  private determineSeverity(
    impact: DisruptionEvent['impact']
  ): 'low' | 'medium' | 'high' | 'critical' {
    if (impact.totalVisitsAffected >= 10 || impact.continuityBreaks >= 5) {
      return 'critical';
    }
    if (impact.totalVisitsAffected >= 5 || impact.continuityBreaks >= 3) {
      return 'high';
    }
    if (impact.totalVisitsAffected >= 2) {
      return 'medium';
    }
    return 'low';
  }

  /**
   * Generate resolution options
   */
  private async generateResolutionOptions(
    tenantId: string,
    disruption: DisruptionEvent
  ): Promise<ResolutionOption[]> {
    const options: ResolutionOption[] = [];

    // Option 1: Redistribute to available carers
    const redistributeOption = await this.generateRedistributeOption(
      tenantId,
      disruption
    );
    if (redistributeOption) {
      options.push(redistributeOption);
    }

    // Option 2: Use overtime from existing carers
    const overtimeOption = await this.generateOvertimeOption(
      tenantId,
      disruption
    );
    if (overtimeOption) {
      options.push(overtimeOption);
    }

    // Option 3: Cancel non-critical visits
    if (disruption.severity === 'critical') {
      const cancelOption = await this.generateCancelOption(
        tenantId,
        disruption
      );
      if (cancelOption) {
        options.push(cancelOption);
      }
    }

    // Sort by score
    return options.sort((a, b) => b.score - a.score);
  }

  /**
   * Generate redistribute resolution option
   */
  private async generateRedistributeOption(
    tenantId: string,
    disruption: DisruptionEvent
  ): Promise<ResolutionOption | null> {
    try {
      // Get affected visits
      const visits = await this.prisma.externalRequest.findMany({
        where: { id: { in: disruption.affectedVisits } },
        include: { matches: true }
      });

      // Find available carers
      const reassignments: ResolutionOption['changes']['reassignments'] = [];
      let totalTravelAdded = 0;
      let continuityScore = 100;

      for (const visit of visits) {
        // Find best available carer
        const eligibleCarers = await this.findAvailableCarersForVisit(
          tenantId,
          visit.id,
          new Date(visit.scheduledStartTime!)
        );

        if (eligibleCarers.length > 0) {
          const bestCarer = eligibleCarers[0];
          
          reassignments.push({
            visitId: visit.id,
            fromCarerId: undefined,
            toCarerId: bestCarer.id
          });

          // Estimate travel time (simplified)
          totalTravelAdded += 15; // Assume 15 min average

          // Check continuity
          const hadHistory = visit.matches.some(m => m.carerId === bestCarer.id);
          if (!hadHistory) {
            continuityScore -= 10;
          }
        }
      }

      if (reassignments.length === 0) {
        return null;
      }

      const score = this.calculateResolutionScore({
        carersAffected: reassignments.length,
        clientsAffected: disruption.affectedClients.length,
        continuityScore,
        travelTimeAdded: totalTravelAdded,
        costImpact: totalTravelAdded * 0.5, // Rough cost estimate
        complianceRisk: 'low'
      });

      return {
        id: `res_redistribute_${Date.now()}`,
        strategy: 'redistribute',
        description: `Redistribute ${reassignments.length} visits to available carers`,
        changes: {
          reassignments,
          cancellations: [],
          overtimeRequired: []
        },
        impact: {
          carersAffected: reassignments.length,
          clientsAffected: disruption.affectedClients.length,
          continuityScore,
          travelTimeAdded: totalTravelAdded,
          costImpact: totalTravelAdded * 0.5,
          complianceRisk: 'low'
        },
        score
      };

    } catch (error) {
      logger.error('Failed to generate redistribute option:', error);
      return null;
    }
  }

  /**
   * Generate overtime resolution option
   */
  private async generateOvertimeOption(
    tenantId: string,
    disruption: DisruptionEvent
  ): Promise<ResolutionOption | null> {
    // Simplified implementation
    return {
      id: `res_overtime_${Date.now()}`,
      strategy: 'overtime',
      description: 'Use overtime from existing carers',
      changes: {
        reassignments: [],
        cancellations: [],
        overtimeRequired: []
      },
      impact: {
        carersAffected: 0,
        clientsAffected: 0,
        continuityScore: 100,
        travelTimeAdded: 0,
        costImpact: 50,
        complianceRisk: 'medium'
      },
      score: 70
    };
  }

  /**
   * Generate cancel resolution option
   */
  private async generateCancelOption(
    tenantId: string,
    disruption: DisruptionEvent
  ): Promise<ResolutionOption | null> {
    // Would prioritize canceling low-priority visits
    return {
      id: `res_cancel_${Date.now()}`,
      strategy: 'cancel',
      description: 'Cancel non-critical visits',
      changes: {
        reassignments: [],
        cancellations: disruption.affectedVisits,
        overtimeRequired: []
      },
      impact: {
        carersAffected: 0,
        clientsAffected: disruption.affectedClients.length,
        continuityScore: 0,
        travelTimeAdded: 0,
        costImpact: 0,
        complianceRisk: 'high'
      },
      score: 40
    };
  }

  /**
   * Execute a resolution
   */
  private async executeResolution(
    tenantId: string,
    resolution: ResolutionOption
  ): Promise<void> {
    // Apply reassignments
    for (const reassignment of resolution.changes.reassignments) {
      // Would update assignment in database
      logger.info(`Reassigning visit ${reassignment.visitId} to carer ${reassignment.toCarerId}`);
    }

    // Apply cancellations
    for (const visitId of resolution.changes.cancellations) {
      // Would cancel visit in database
      logger.info(`Cancelling visit ${visitId}`);
    }

    // Record overtime
    for (const overtime of resolution.changes.overtimeRequired) {
      logger.info(`Recording ${overtime.additionalHours}h overtime for carer ${overtime.carerId}`);
    }
  }

  /**
   * Notify stakeholders of disruption
   */
  private async notifyStakeholders(
    tenantId: string,
    disruption: DisruptionEvent
  ): Promise<void> {
    // Notify coordinators
    await this.notificationService.sendNotification({
      event_type: 'disruption_reported',
      recipient_type: 'push',
      recipient: 'coordinators',
      tenant_id: tenantId,
      data: {
        disruptionId: disruption.id,
        type: disruption.type,
        description: disruption.description
      }
    });

    // Notify affected carers
    for (const carerId of disruption.affectedCarers) {
      await this.notificationService.sendNotification({
        event_type: 'schedule_update',
        recipient_type: 'push',
        recipient: carerId,
        tenant_id: tenantId,
        data: {
          disruptionId: disruption.id,
          message: 'Your schedule has been affected by a disruption'
        }
      });
    }
  }

  /**
   * Notify resolution applied
   */
  private async notifyResolution(
    disruption: DisruptionEvent,
    resolution: ResolutionOption
  ): Promise<void> {
    // Notify coordinators
    await this.notificationService.sendNotification({
      event_type: 'disruption_resolved',
      recipient_type: 'push',
      recipient: 'coordinators',
      tenant_id: disruption.tenantId,
      data: {
        disruptionId: disruption.id,
        resolutionId: resolution.id,
        type: disruption.type,
        description: resolution.description
      }
    });

    // Notify affected carers with new assignments
    for (const reassignment of resolution.changes.reassignments) {
      await this.notificationService.sendNotification({
        event_type: 'new_assignment',
        recipient_type: 'push',
        recipient: reassignment.toCarerId,
        tenant_id: disruption.tenantId,
        data: {
          visitId: reassignment.visitId,
          message: 'You have been assigned a new visit'
        }
      });
    }
  }

  // ========== UTILITY METHODS ==========

  private async getCarerVisitsToday(tenantId: string, carerId: string): Promise<any[]> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    return await this.prisma.externalRequest.findMany({
      where: {
        tenantId,
        scheduledStartTime: {
          gte: today,
          lt: tomorrow
        },
        matches: {
          some: {
            carerId,
            status: 'ACCEPTED'
          }
        }
      }
    });
  }

  private async calculateContinuityBreaks(
    tenantId: string,
    visitIds: string[],
    carerIds: string[]
  ): Promise<number> {
    // Simplified - would check historical assignments
    return Math.floor(visitIds.length * 0.3);
  }

  private async findAvailableCarersForVisit(
    tenantId: string,
    visitId: string,
    timeSlot: Date
  ): Promise<any[]> {
    // Simplified - would check carer availability
    return await this.prisma.carer.findMany({
      where: { tenantId, isActive: true },
      take: 5
    });
  }

  private calculateResolutionScore(impact: ResolutionOption['impact']): number {
    let score = 100;

    score -= impact.carersAffected * 5;
    score -= impact.clientsAffected * 3;
    score += (impact.continuityScore - 50) * 0.5;
    score -= impact.travelTimeAdded * 0.1;
    score -= impact.costImpact * 0.2;

    const riskPenalty = {
      none: 0,
      low: 5,
      medium: 15,
      high: 30
    };
    score -= riskPenalty[impact.complianceRisk];

    return Math.max(0, Math.min(100, score));
  }
}