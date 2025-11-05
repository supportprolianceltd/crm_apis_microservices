// File: src/services/roster-generation.service.ts
import { PrismaClient } from '@prisma/client';
import { ConstraintsService, RosteringConstraints } from './constraints.service';
import { TravelService } from './travel.service';
import { ClusteringService, ClusterVisit } from './clustering.service';
import { PairingService, DoubleHandedVisit } from './pairing.service';
import { AdvancedOptimizationService } from './advanced-optimization.service';
import { logger } from '../utils/logger';

// ========== INTERFACES ==========
export interface RosterAssignment {
  id: string;
  visitId: string;
  carerId: string;
  carerName: string;
  scheduledTime: Date;
  estimatedEndTime: Date;
  travelFromPrevious: number; // minutes
  travelToPrevious?: string; // from location
  complianceChecks: ComplianceChecks;
  visitDetails: VisitDetails;
}

export interface ComplianceChecks {
  wtdCompliant: boolean;
  restPeriodOK: boolean;
  travelTimeOK: boolean;
  skillsMatch: boolean;
  warnings: string[];
}

export interface VisitDetails {
  clientName: string;
  address: string;
  duration: number;
  requirements: string;
}

export interface RosterScenario {
  id: string;
  label: string;
  strategy: OptimizationStrategy;
  assignments: RosterAssignment[];
  metrics: ScenarioMetrics;
  score: number; // overall quality score 0-100
}

export interface ScenarioMetrics {
  totalTravel: number; // minutes
  continuityScore: number; // percentage
  violations: ViolationCounts;
  overtimeMinutes: number;
  averageCarerWorkload: number;
}

export interface ViolationCounts {
  hard: number;
  soft: number;
}

export interface OptimizationParams {
  clusterId?: string;
  dateRange: { start: Date; end: Date };
  strategy?: OptimizationStrategy;
  lockedAssignments?: string[]; // assignment IDs to preserve
  generateScenarios?: boolean; // if true, generate 3 scenarios
}

export type OptimizationStrategy = 'continuity' | 'travel' | 'balanced';

interface OptimizationWeights {
  continuity: number;
  travel: number;
  workload: number;
  skills: number;
}

interface CarerSchedule {
  carerId: string;
  assignments: RosterAssignment[];
}

// ========== MAIN SERVICE ==========
export class RosterGenerationService {
  private advancedOptimizationService: AdvancedOptimizationService;

  constructor(
    private prisma: PrismaClient,
    private constraintsService: ConstraintsService,
    private travelService: TravelService,
    private clusteringService: ClusteringService
  ) {
    this.advancedOptimizationService = new AdvancedOptimizationService(this);
  }

  /**
   * Generate optimized roster assignments
   */
// In generateRoster() method, after scenarios are sorted
async generateRoster(
  tenantId: string,
  params: OptimizationParams
): Promise<RosterScenario[]> {
  try {
    // ... existing code ...
    
    // Get visits and carers data
    const visits = await this.getVisitsForRoster(tenantId, params);
    const carers = await this.getAvailableCarers(tenantId, params);
    const constraints = await this.constraintsService.getActiveConstraints(tenantId);

    this.validateRosterInputs(visits, carers);

    const scenarios = params.generateScenarios !== false
      ? await this.generateMultipleScenarios(visits, carers, constraints, params)
      : [await this.generateSingleScenario(visits, carers, constraints, params.strategy || 'balanced')];

    // ✅ ADD THIS: Persist scenarios to database
    const savedScenarios = await this.persistScenarios(
      tenantId, 
      scenarios, 
      params
    );

    return savedScenarios;
  } catch (error) {
    logger.error('Failed to generate roster:', error);
    throw error;
  }
}

// ✅ ADD THIS METHOD
private async persistScenarios(
  tenantId: string,
  scenarios: RosterScenario[],
  params: OptimizationParams
): Promise<RosterScenario[]> {
  const savedScenarios: RosterScenario[] = [];

  for (const scenario of scenarios) {
    // Create roster record
    const roster = await this.prisma.roster.create({
      data: {
        tenantId,
        name: `${scenario.label} - ${new Date().toLocaleDateString()}`,
        description: `Auto-generated ${scenario.strategy} roster`,
        strategy: scenario.strategy.toUpperCase() as any,
        startDate: params.dateRange.start,
        endDate: params.dateRange.end,
        createdBy: 'system', // Should come from request context
        status: 'DRAFT',
        totalAssignments: scenario.assignments.length,
        totalTravelMinutes: scenario.metrics.totalTravel,
        continuityScore: scenario.metrics.continuityScore,
        qualityScore: scenario.score
      }
    });

    // Create assignment records
    const assignmentRecords = await this.prisma.assignment.createMany({
      data: scenario.assignments.map(a => ({
        tenantId,
        rosterId: roster.id,
        visitId: a.visitId,
        carerId: a.carerId,
        scheduledTime: a.scheduledTime,
        estimatedEndTime: a.estimatedEndTime,
        travelFromPrevious: a.travelFromPrevious,
        wtdCompliant: a.complianceChecks.wtdCompliant,
        restPeriodOK: a.complianceChecks.restPeriodOK,
        travelTimeOK: a.complianceChecks.travelTimeOK,
        skillsMatch: a.complianceChecks.skillsMatch,
        warnings: a.complianceChecks.warnings,
        status: 'PENDING'
      }))
    });

    // Re-fetch with relationships
    const savedRoster = await this.prisma.roster.findUnique({
      where: { id: roster.id },
      include: { assignments: true }
    });

    savedScenarios.push({
      ...scenario,
      id: roster.id // Update with actual DB ID
    });

    logger.info('Persisted scenario', {
      rosterId: roster.id,
      assignments: assignmentRecords.count,
      strategy: scenario.strategy
    });
  }

  return savedScenarios;
}
  /**
   * Generate 3 optimization scenarios with different strategies
   */
  private async generateMultipleScenarios(
    visits: ClusterVisit[],
    carers: any[],
    constraints: RosteringConstraints,
    params: OptimizationParams
  ): Promise<RosterScenario[]> {
    const strategies: OptimizationStrategy[] = ['continuity', 'travel', 'balanced'];
    
    const scenarios = await Promise.all(
      strategies.map(strategy =>
        this.generateSingleScenario(visits, carers, constraints, strategy)
      )
    );

    return scenarios.sort((a, b) => b.score - a.score);
  }

  /**
   * Generate single roster scenario with given strategy
   */
  async generateSingleScenario(
    visits: ClusterVisit[],
    carers: any[],
    constraints: RosteringConstraints,
    strategy: OptimizationStrategy
  ): Promise<RosterScenario> {
    // TEMPORARILY DISABLE OR-TOOLS COMPLETELY
    logger.info('OR-Tools temporarily disabled, using standard algorithm', {
      visitCount: visits.length,
      strategy
    });

    // Use standard algorithm as primary method
    return await this.generateStandardScenario(visits, carers, constraints, strategy);
  }

  /**
   * Generate scenario using standard algorithm
   */
  private async generateStandardScenario(
    visits: ClusterVisit[],
    carers: any[],
    constraints: RosteringConstraints,
    strategy: OptimizationStrategy
  ): Promise<RosterScenario> {
    logger.info('Using standard optimization algorithm', {
      visitCount: visits.length,
      strategy,
      hasDoubleHanded: visits.some(v => v.visitType === 'double')
    });

    const weights = this.getOptimizationWeights(strategy);
    const assignments = await this.processAllVisits(visits, carers, constraints, weights);
    const metrics = await this.calculateScenarioMetrics(assignments, constraints);
    const score = this.calculateScenarioScore(metrics, weights);

    return {
      id: `scenario_${strategy}_${Date.now()}`,
      label: this.getStrategyLabel(strategy),
      strategy,
      assignments,
      metrics,
      score
    };
  }

  /**
   * Process all visits (single and double-handed)
   */
  private async processAllVisits(
    visits: ClusterVisit[],
    carers: any[],
    constraints: RosteringConstraints,
    weights: OptimizationWeights
  ): Promise<RosterAssignment[]> {
    const doubleVisits = visits.filter(v => v.visitType === 'double') as DoubleHandedVisit[];
    const singleVisits = visits.filter(v => v.visitType !== 'double');

    // Process double-handed visits first
    const doubleAssignments = await this.processDoubleHandedVisits(doubleVisits, carers, constraints);
    
    // Process single visits with remaining carers
    const availableCarers = this.getAvailableCarersAfterDoubleHanded(carers, doubleAssignments);
    const singleAssignments = await this.processSingleVisits(singleVisits, availableCarers, constraints, weights);

    return [...doubleAssignments, ...singleAssignments];
  }

  /**
   * Process double-handed visits
   */
  private async processDoubleHandedVisits(
    doubleVisits: DoubleHandedVisit[],
    carers: any[],
    constraints: RosteringConstraints
  ): Promise<RosterAssignment[]> {
    if (doubleVisits.length === 0) return [];

    const pairingService = new PairingService(this.prisma, this.travelService, this.constraintsService);
    const assignments: RosterAssignment[] = [];

    logger.info('Processing double-handed visits', { count: doubleVisits.length });

    for (const visit of doubleVisits) {
      try {
        const assignment = await this.processSingleDoubleHandedVisit(visit, carers, constraints, pairingService);
        if (assignment) {
          assignments.push(...assignment);
        }
      } catch (error) {
        logger.error('Error processing double-handed visit', {
          visitId: visit.id,
          error: (error as any).message
        });
      }
    }

    return assignments;
  }

  /**
   * Process single double-handed visit
   */
  private async processSingleDoubleHandedVisit(
    visit: DoubleHandedVisit,
    carers: any[],
    constraints: RosteringConstraints,
    pairingService: PairingService
  ): Promise<RosterAssignment[] | null> {
    const compatiblePairs = await pairingService.findCompatiblePairs(
      visit, 
      carers, 
      constraints, 
      new Date(visit.scheduledStartTime!)
    );

    if (compatiblePairs.length > 0) {
      const bestPair = compatiblePairs[0];
      
      logger.info('Assigned double-handed visit', {
        visitId: visit.id,
        carerA: bestPair.carerA.id,
        carerB: bestPair.carerB.id,
        pairScore: bestPair.pairScore
      });

      return [
        this.createDoubleHandedAssignment(visit, bestPair.carerA, bestPair.carerB, constraints),
        this.createDoubleHandedAssignment(visit, bestPair.carerB, bestPair.carerA, constraints)
      ];
    }

    // Fallback: assign as single visit
    logger.warn('No compatible pairs found for double-handed visit, using fallback', {
      visitId: visit.id,
      requiredSkills: visit.requirements
    });
    
    return await this.createFallbackSingleAssignment(visit, carers, constraints);
  }

  /**
   * Process single visits
   */
  private async processSingleVisits(
    visits: ClusterVisit[],
    carers: any[],
    constraints: RosteringConstraints,
    weights: OptimizationWeights
  ): Promise<RosterAssignment[]> {
    if (visits.length === 0) return [];

    logger.info('Processing single visits', { 
      count: visits.length, 
      availableCarers: carers.length 
    });

    // Score each visit-carer pair
    const scoredPairs = await this.scoreAllPairs(visits, carers, constraints, weights);

    // Build assignments using greedy algorithm
    return await this.buildAssignments(scoredPairs, visits, carers, constraints);
  }

  /**
   * Score all visit-carer pairs
   */
  private async scoreAllPairs(
    visits: ClusterVisit[],
    carers: any[],
    constraints: RosteringConstraints,
    weights: OptimizationWeights
  ): Promise<Map<string, number>> {
    const scores = new Map<string, number>();
    const totalPairs = visits.length * carers.length;

    logger.info('Scoring visit-carer pairs', { totalPairs });

    let processedPairs = 0;
    const batchSize = Math.ceil(totalPairs / 10); // Log progress every 10%

    for (const visit of visits) {
      for (const carer of carers) {
        const key = `${visit.id}_${carer.id}`;
        
        // Calculate individual scores
        const continuityScore = await this.calculateContinuityScore(visit, carer);
        const travelScore = await this.calculateTravelScore(visit, carer);
        const workloadScore = await this.calculateWorkloadScore(carer, constraints);
        const skillScore = this.calculateSkillScore(visit, carer);

        // Weighted composite score
        const totalScore =
          continuityScore * weights.continuity +
          travelScore * weights.travel +
          workloadScore * weights.workload +
          skillScore * weights.skills;

        scores.set(key, totalScore);

        processedPairs++;
        if (processedPairs % batchSize === 0) {
          logger.debug('Pair scoring progress', {
            processed: processedPairs,
            total: totalPairs,
            percentage: Math.round((processedPairs / totalPairs) * 100)
          });
        }
      }
    }

    logger.info('Completed pair scoring', { totalPairs: processedPairs });
    return scores;
  }

  /**
   * Build assignments using greedy algorithm
   */
  private async buildAssignments(
    scoredPairs: Map<string, number>,
    visits: ClusterVisit[],
    carers: any[],
    constraints: RosteringConstraints
  ): Promise<RosterAssignment[]> {
    const assignments: RosterAssignment[] = [];
    const assignedVisits = new Set<string>();
    const carerSchedules = new Map<string, RosterAssignment[]>();

    // Initialize carer schedules
    carers.forEach(carer => carerSchedules.set(carer.id, []));

    // Sort visits by time (earliest first)
    const sortedVisits = [...visits].sort(
      (a, b) => a.timeStartMinutes - b.timeStartMinutes
    );

    logger.info('Building assignments', { visitCount: sortedVisits.length });

    let assignedCount = 0;
    for (const visit of sortedVisits) {
      if (assignedVisits.has(visit.id)) continue;

      // Find best eligible carer
      const bestCarer = await this.findBestCarerForVisit(
        visit,
        carers,
        carerSchedules,
        scoredPairs,
        constraints
      );

      if (!bestCarer) {
        logger.warn(`No eligible carer found for visit ${visit.id}`);
        continue;
      }

      // Create assignment
      const assignment = await this.createAssignment(
        visit,
        bestCarer,
        carerSchedules.get(bestCarer.id) || [],
        constraints
      );

      assignments.push(assignment);
      assignedVisits.add(visit.id);
      carerSchedules.get(bestCarer.id)!.push(assignment);
      assignedCount++;

      if (assignedCount % 10 === 0) {
        logger.debug('Assignment progress', {
          assigned: assignedCount,
          total: sortedVisits.length,
          percentage: Math.round((assignedCount / sortedVisits.length) * 100)
        });
      }
    }

    logger.info('Assignment building completed', {
      assigned: assignedCount,
      total: sortedVisits.length,
      successRate: Math.round((assignedCount / sortedVisits.length) * 100)
    });

    return assignments;
  }

  /**
   * Find best carer for a visit during assignment building
   */
  private async findBestCarerForVisit(
    visit: ClusterVisit,
    carers: any[],
    carerSchedules: Map<string, RosterAssignment[]>,
    scoredPairs: Map<string, number>,
    constraints: RosteringConstraints
  ): Promise<any | null> {
    let bestCarer = null;
    let bestScore = -1;

    for (const carer of carers) {
      const key = `${visit.id}_${carer.id}`;
      const baseScore = scoredPairs.get(key) || 0;

      if (baseScore <= 0) continue;

      // Check if assignment is valid
      const isValid = await this.validateAssignment(
        visit,
        carer,
        carerSchedules.get(carer.id) || [],
        constraints
      );

      if (isValid) {
        // Apply time-based penalty for carer's current schedule
        const schedulePenalty = this.calculateSchedulePenalty(visit, carerSchedules.get(carer.id) || []);
        const adjustedScore = baseScore * (1 - schedulePenalty);

        if (adjustedScore > bestScore) {
          bestScore = adjustedScore;
          bestCarer = carer;
        }
      }
    }

    return bestCarer;
  }

  // ========== ASSIGNMENT CREATION METHODS ==========

  /**
   * Create assignment for double-handed visit
   */
  private createDoubleHandedAssignment(
    visit: DoubleHandedVisit,
    carer: any,
    partnerCarer: any,
    constraints: RosteringConstraints
  ): RosterAssignment {
    const scheduledTime = new Date(visit.scheduledStartTime!);
    const duration = visit.estimatedDuration || 60;
    const estimatedEndTime = new Date(scheduledTime.getTime() + duration * 60000);

    const complianceChecks = this.runComplianceChecks(visit, carer, [], 0, constraints);
    complianceChecks.warnings.push(`Double-handed with ${partnerCarer.firstName} ${partnerCarer.lastName}`);

    return {
      id: `assignment_double_${visit.id}_${carer.id}_${Date.now()}`,
      visitId: visit.id,
      carerId: carer.id,
      carerName: `${carer.firstName} ${carer.lastName}`,
      scheduledTime,
      estimatedEndTime,
      travelFromPrevious: 0,
      complianceChecks,
      visitDetails: {
        clientName: (visit as any).requestorName || 'Unknown',
        address: (visit as any).address || 'Address not available',
        duration,
        requirements: visit.requirements || 'Double-handed care'
      }
    };
  }

  /**
   * Create fallback single assignment when no pairs available
   */
  private async createFallbackSingleAssignment(
    visit: DoubleHandedVisit,
    carers: any[],
    constraints: RosteringConstraints
  ): Promise<RosterAssignment[] | null> {
    const bestCarer = await this.findBestCarerForSingleAssignment(visit, carers, constraints);
    
    if (!bestCarer) {
      logger.warn('No suitable carer found for fallback single assignment', { visitId: visit.id });
      return null;
    }

    const scheduledTime = new Date(visit.scheduledStartTime!);
    const duration = visit.estimatedDuration || 60;
    const estimatedEndTime = new Date(scheduledTime.getTime() + duration * 60000);

    const complianceChecks = this.runComplianceChecks(visit, bestCarer, [], 0, constraints);
    complianceChecks.warnings.push('Double-handed visit assigned as single (fallback)');

    const assignment: RosterAssignment = {
      id: `assignment_fallback_${visit.id}_${bestCarer.id}_${Date.now()}`,
      visitId: visit.id,
      carerId: bestCarer.id,
      carerName: `${bestCarer.firstName} ${bestCarer.lastName}`,
      scheduledTime,
      estimatedEndTime,
      travelFromPrevious: 0,
      complianceChecks,
      visitDetails: {
        clientName: (visit as any).requestorName || 'Unknown',
        address: (visit as any).address || 'Address not available',
        duration,
        requirements: visit.requirements || 'Double-handed care (single fallback)'
      }
    };

    logger.info('Assigned double-handed visit as single (fallback)', {
      visitId: visit.id,
      carerId: bestCarer.id
    });

    return [assignment];
  }

  /**
   * Find best carer for single assignment
   */
  private async findBestCarerForSingleAssignment(
    visit: DoubleHandedVisit,
    carers: any[],
    constraints: RosteringConstraints
  ): Promise<any | null> {
    let bestCarer = null;
    let bestScore = -1;

    for (const carer of carers) {
      const hasSkills = this.checkSkillsMatch(visit.requirements, carer.skills);
      if (!hasSkills) continue;

      const score = await this.calculateCarerScore(visit, carer, constraints);
      if (score > bestScore) {
        bestScore = score;
        bestCarer = carer;
      }
    }

    return bestCarer;
  }

  /**
   * Create roster assignment
   */
  private async createAssignment(
    visit: ClusterVisit,
    carer: any,
    previousAssignments: RosterAssignment[],
    constraints: RosteringConstraints
  ): Promise<RosterAssignment> {
    const scheduledTime = new Date(visit.scheduledStartTime!);
    const duration = visit.estimatedDuration || 60;
    const estimatedEndTime = new Date(scheduledTime.getTime() + duration * 60000);

    // Calculate travel from previous visit
    let travelFromPrevious = 0;
    let travelToPrevious = undefined;

    if (previousAssignments.length > 0) {
      const lastAssignment = previousAssignments[previousAssignments.length - 1];
      
      // Get travel time
      const lastVisit = await this.prisma.externalRequest.findUnique({
        where: { id: lastAssignment.visitId }
      });

      if (lastVisit && lastVisit.postcode && visit.postcode) {
        try {
          const travel = await this.travelService.getTravelTime(
            lastVisit.postcode,
            visit.postcode
          );
          travelFromPrevious = Math.ceil(travel.durationSeconds / 60);
          travelToPrevious = lastVisit.address;
        } catch (error) {
          logger.warn('Failed to calculate travel time, using estimate', {
            from: lastVisit.postcode,
            to: visit.postcode,
            error: (error as any).message
          });
          // Fallback: estimate travel time based on distance
          travelFromPrevious = this.estimateTravelTime(lastVisit, visit);
        }
      }
    }

    // Run compliance checks
    const complianceChecks = this.runComplianceChecks(
      visit,
      carer,
      previousAssignments,
      travelFromPrevious,
      constraints
    );

    return {
      id: `assignment_${visit.id}_${carer.id}_${Date.now()}`,
      visitId: visit.id,
      carerId: carer.id,
      carerName: `${carer.firstName} ${carer.lastName}`,
      scheduledTime,
      estimatedEndTime,
      travelFromPrevious,
      travelToPrevious,
      complianceChecks,
      visitDetails: {
        clientName: (visit as any).requestorName || 'Unknown',
        address: (visit as any).address || 'Address not available',
        duration,
        requirements: visit.requirements || 'General care'
      }
    };
  }

  // ========== SCORING AND VALIDATION METHODS ==========

  /**
   * Calculate carer score for a visit
   */
  private async calculateCarerScore(
    visit: ClusterVisit, 
    carer: any, 
    constraints: RosteringConstraints
  ): Promise<number> {
    const continuityScore = await this.calculateContinuityScore(visit, carer);
    const travelScore = await this.calculateTravelScore(visit, carer);
    const workloadScore = await this.calculateWorkloadScore(carer, constraints);
    const skillScore = this.calculateSkillScore(visit, carer);

    return (continuityScore * 0.3) + (travelScore * 0.3) + (workloadScore * 0.2) + (skillScore * 0.2);
  }

  /**
   * Calculate continuity score
   */
  private async calculateContinuityScore(visit: ClusterVisit, carer: any): Promise<number> {
    // Check if this carer has visited this client before
    const hasHistory = visit.matches?.some(m => 
      m.carerId === carer.id && m.response === 'ACCEPTED'
    );
    return hasHistory ? 1.0 : 0.3;
  }

  /**
   * Calculate travel score
   */
  private async calculateTravelScore(visit: ClusterVisit, carer: any): Promise<number> {
    if (!visit.latitude || !visit.longitude || !carer.latitude || !carer.longitude) {
      return 0.5;
    }

    const distance = this.haversineDistance(
      visit.latitude, visit.longitude,
      carer.latitude, carer.longitude
    );

    // Score inversely proportional to distance (closer = better)
    const maxDistance = carer.maxTravelDistance || 10000;
    return Math.max(0, 1 - (distance / maxDistance));
  }

  /**
   * Calculate workload score
   */
  private async calculateWorkloadScore(carer: any, constraints: RosteringConstraints): Promise<number> {
    // Fetch current workload for the week
    const weekStart = new Date();
    weekStart.setHours(0, 0, 0, 0);
    weekStart.setDate(weekStart.getDate() - weekStart.getDay()); // Start of week (Sunday)
    
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 7);

    const currentAssignments = await this.prisma.assignment.count({
      where: {
        carerId: carer.id,
        scheduledTime: {
          gte: weekStart,
          lt: weekEnd
        },
        status: { in: ['ACCEPTED', 'COMPLETED'] }
      }
    });

    // Score based on how much capacity remains
    const avgVisitsPerWeek = 20; // Assume ~20 visits per week capacity
    const capacityUsed = currentAssignments / avgVisitsPerWeek;
    
    return Math.max(0, 1 - capacityUsed);
  }

  /**
   * Calculate skill score
   */
  private calculateSkillScore(visit: ClusterVisit, carer: any): number {
    return this.checkSkillsMatch(visit.requirements, carer.skills) ? 1.0 : 0.0;
  }

  /**
   * Validate assignment against constraints
   */
  private async validateAssignment(
    visit: ClusterVisit,
    carer: any,
    existingAssignments: RosterAssignment[],
    constraints: RosteringConstraints
  ): Promise<boolean> {
    // Check skills
    const hasSkills = this.checkSkillsMatch(visit.requirements, carer.skills);
    if (!hasSkills) return false;

    // Check time conflicts
    const visitStart = new Date(visit.scheduledStartTime!);
    const visitEnd = new Date(
      visitStart.getTime() + (visit.estimatedDuration || 60) * 60000
    );

    for (const assignment of existingAssignments) {
      const assignmentStart = new Date(assignment.scheduledTime);
      const assignmentEnd = new Date(assignment.estimatedEndTime);

      // Check for overlap (including travel time buffer)
      const bufferMs = constraints.bufferMinutes * 60000;
      if (visitStart.getTime() < assignmentEnd.getTime() + bufferMs && 
          visitEnd.getTime() + bufferMs > assignmentStart.getTime()) {
        return false;
      }
    }

    // Check WTD hours
    const totalHours = this.calculateTotalHours(existingAssignments);
    const visitHours = (visit.estimatedDuration || 60) / 60;
    if (totalHours + visitHours > constraints.wtdMaxHoursPerWeek) {
      return false;
    }

    // Check rest period
    if (existingAssignments.length > 0) {
      const lastAssignment = existingAssignments[existingAssignments.length - 1];
      const lastEnd = new Date(lastAssignment.estimatedEndTime);
      const hoursSinceLastShift = (visitStart.getTime() - lastEnd.getTime()) / (1000 * 60 * 60);
      
      if (hoursSinceLastShift < constraints.restPeriodHours) {
        return false;
      }
    }

    return true;
  }

  /**
   * Calculate schedule penalty based on carer's current assignments
   */
  private calculateSchedulePenalty(visit: ClusterVisit, existingAssignments: RosterAssignment[]): number {
    if (existingAssignments.length === 0) return 0;

    const visitStart = new Date(visit.scheduledStartTime!);
    let penalty = 0;

    // Penalize based on how many assignments the carer already has
    penalty += Math.min(0.3, existingAssignments.length * 0.05);

    // Penalize based on proximity to other assignments
    for (const assignment of existingAssignments) {
      const assignmentTime = new Date(assignment.scheduledTime);
      const timeDiff = Math.abs(visitStart.getTime() - assignmentTime.getTime()) / (1000 * 60 * 60); // hours

      if (timeDiff < 2) {
        penalty += 0.2; // Heavy penalty for assignments within 2 hours
      } else if (timeDiff < 4) {
        penalty += 0.1; // Moderate penalty for assignments within 4 hours
      }
    }

    return Math.min(0.5, penalty); // Cap penalty at 50%
  }

  /**
   * Run compliance checks for assignment
   */
  private runComplianceChecks(
    visit: ClusterVisit,
    carer: any,
    previousAssignments: RosterAssignment[],
    travelTime: number,
    constraints: RosteringConstraints
  ): ComplianceChecks {
    const warnings: string[] = [];
    let wtdCompliant = true;
    let restPeriodOK = true;
    let travelTimeOK = true;
    let skillsMatch = true;

    // Check WTD
    const totalHours = this.calculateTotalHours(previousAssignments);
    const visitHours = (visit.estimatedDuration || 60) / 60;
    if (totalHours + visitHours > constraints.wtdMaxHoursPerWeek * 0.9) {
      warnings.push('Approaching WTD limit');
    }
    if (totalHours + visitHours > constraints.wtdMaxHoursPerWeek) {
      wtdCompliant = false;
      warnings.push(`Exceeds WTD maximum hours: ${totalHours + visitHours}h > ${constraints.wtdMaxHoursPerWeek}h`);
    }

    // Check travel time
    if (travelTime > constraints.travelMaxMinutes) {
      travelTimeOK = false;
      warnings.push(`Travel time ${travelTime}min exceeds limit ${constraints.travelMaxMinutes}min`);
    } else if (travelTime > constraints.travelMaxMinutes * 0.8) {
      warnings.push(`Travel time ${travelTime}min approaching limit`);
    }

    // Check skills
    skillsMatch = this.checkSkillsMatch(visit.requirements, carer.skills);
    if (!skillsMatch) {
      warnings.push('Skills mismatch');
    }

    // Check rest period
    if (previousAssignments.length > 0) {
      const lastAssignment = previousAssignments[previousAssignments.length - 1];
      const lastEnd = new Date(lastAssignment.estimatedEndTime);
      const visitStart = new Date(visit.scheduledStartTime!);
      const hoursSinceLastShift = (visitStart.getTime() - lastEnd.getTime()) / (1000 * 60 * 60);
      
      if (hoursSinceLastShift < constraints.restPeriodHours) {
        restPeriodOK = false;
        warnings.push(`Rest period violation: ${hoursSinceLastShift.toFixed(1)}h < ${constraints.restPeriodHours}h`);
      } else if (hoursSinceLastShift < constraints.restPeriodHours + 1) {
        warnings.push(`Rest period tight: ${hoursSinceLastShift.toFixed(1)}h since last shift`);
      }
    }

    return {
      wtdCompliant,
      restPeriodOK,
      travelTimeOK,
      skillsMatch,
      warnings
    };
  }

  // ========== METRICS AND SCORING METHODS ==========

  /**
   * Calculate scenario metrics
   */
  private async calculateScenarioMetrics(
    assignments: RosterAssignment[],
    constraints: RosteringConstraints
  ): Promise<ScenarioMetrics> {
    const totalTravel = assignments.reduce(
      (sum, a) => sum + a.travelFromPrevious,
      0
    );

    const violations = {
      hard: assignments.filter(a => 
        !a.complianceChecks.wtdCompliant || 
        !a.complianceChecks.restPeriodOK ||
        !a.complianceChecks.skillsMatch
      ).length,
      soft: assignments.filter(a => 
        !a.complianceChecks.travelTimeOK ||
        a.complianceChecks.warnings.length > 0
      ).length
    };

    const overtimeMinutes = this.calculateOvertime(assignments, constraints);
    const continuityScore = await this.calculateOverallContinuity(assignments);

    // Calculate workload balance
    const carerWorkloads = new Map<string, number>();
    assignments.forEach(a => {
      const current = carerWorkloads.get(a.carerId) || 0;
      const duration = a.visitDetails.duration;
      carerWorkloads.set(a.carerId, current + duration);
    });

    const workloads = Array.from(carerWorkloads.values());
    const averageCarerWorkload = workloads.length > 0 ? 
      workloads.reduce((sum, w) => sum + w, 0) / workloads.length : 0;

    // Calculate workload balance score (lower std dev = better balance)
    const workloadVariance = workloads.length > 0 ?
      workloads.reduce((sum, w) => sum + Math.pow(w - averageCarerWorkload, 2), 0) / workloads.length : 0;

    logger.info('Scenario metrics calculated', {
      totalTravel,
      continuityScore,
      violations: `${violations.hard} hard, ${violations.soft} soft`,
      overtimeMinutes,
      averageCarerWorkload: Math.round(averageCarerWorkload),
      workloadVariance: Math.round(workloadVariance)
    });

    return {
      totalTravel,
      continuityScore,
      violations,
      overtimeMinutes,
      averageCarerWorkload
    };
  }

  /**
   * Calculate scenario score (0-100)
   */
  private calculateScenarioScore(
    metrics: ScenarioMetrics,
    weights: OptimizationWeights
  ): number {
    let score = 100;

    // Penalize travel time (normalize to 0-20 penalty)
    const travelPenalty = Math.min(metrics.totalTravel / 10, 20);
    score -= travelPenalty * weights.travel;

    // Reward continuity
    score += (metrics.continuityScore / 100) * 30 * weights.continuity;

    // Penalize violations
    score -= metrics.violations.hard * 15;
    score -= metrics.violations.soft * 5;

    // Penalize overtime
    score -= (metrics.overtimeMinutes / 60) * 10;

    // Penalize workload imbalance
    const workloadPenalty = Math.min(metrics.averageCarerWorkload / 10, 10);
    score -= workloadPenalty * weights.workload;

    return Math.max(0, Math.min(100, score));
  }

  /**
   * Calculate overall continuity score
   */
  private async calculateOverallContinuity(assignments: RosterAssignment[]): Promise<number> {
    if (assignments.length === 0) return 0;

    const visitIds = assignments.map(a => a.visitId);
    
    const historicalMatches = await this.prisma.requestCarerMatch.findMany({
      where: {
        requestId: { in: visitIds },
        status: 'ACCEPTED'
      }
    });

    let continuityCount = 0;
    assignments.forEach(assignment => {
      const hasHistory = historicalMatches.some(
        m => m.requestId === assignment.visitId && m.carerId === assignment.carerId
      );
      if (hasHistory) continuityCount++;
    });

    const continuityScore = (continuityCount / assignments.length) * 100;
    
    logger.debug('Continuity score calculated', {
      assignments: assignments.length,
      continuityCount,
      continuityScore: Math.round(continuityScore)
    });

    return continuityScore;
  }

  // ========== DATA ACCESS METHODS ==========


private async getVisitsForRoster(
  tenantId: string,
  params: OptimizationParams
): Promise<ClusterVisit[]> {
  const whereClause: any = {
    tenantId,
    status: 'APPROVED',
    sendToRostering: true,
    scheduledStartTime: {
      gte: params.dateRange.start,
      lte: params.dateRange.end
    }
  };

  if (params.clusterId) {
    whereClause.clusterId = params.clusterId;
  }

  const visits = await this.prisma.externalRequest.findMany({
    where: whereClause,
    include: {
      matches: {
        include: { carer: true }
      }
    }
  });

  const clusterVisits: ClusterVisit[] = visits.map(v => ({
    id: v.id,
    tenantId: v.tenantId,
    scheduledStartTime: v.scheduledStartTime,
    scheduledEndTime: v.scheduledEndTime,
    status: v.status,
    timeStartMinutes: this.timeToMinutes(new Date(v.scheduledStartTime!)),
    timeEndMinutes: this.timeToMinutes(new Date(v.scheduledEndTime!)),
    dayOfWeek: new Date(v.scheduledStartTime!).getDay(),
    eligibleCarers: [],
    latitude: v.latitude ?? null,
    longitude: v.longitude ?? null,
    postcode: v.postcode ?? null,
    requirements: v.requirements ?? null,
    estimatedDuration: v.estimatedDuration ?? null,
    matches: v.matches?.map(m => ({
      response: m.response || 'UNKNOWN',
      carerId: m.carerId
    })) || []
  } as ClusterVisit));

  return clusterVisits;
  }

  private async getAvailableCarers(tenantId: string, params: OptimizationParams) {
    const carers = await this.prisma.carer.findMany({
      where: {
        tenantId,
        isActive: true
      }
    });

    logger.info('Retrieved available carers', {
      tenantId,
      total: carers.length,
      withCoordinates: carers.filter(c => c.latitude && c.longitude).length
    });

    return carers;
  }

  // ========== HELPER METHODS ==========

  private validateRosterInputs(visits: ClusterVisit[], carers: any[]): void {
    if (visits.length === 0) {
      throw new Error('No visits to schedule');
    }
    if (carers.length === 0) {
      throw new Error('No available carers found');
    }
  }

  private getOptimizationWeights(strategy: OptimizationStrategy): OptimizationWeights {
    const weights: { [key in OptimizationStrategy]: OptimizationWeights } = {
      continuity: { continuity: 0.5, travel: 0.2, workload: 0.2, skills: 0.1 },
      travel: { continuity: 0.2, travel: 0.5, workload: 0.2, skills: 0.1 },
      balanced: { continuity: 0.3, travel: 0.3, workload: 0.3, skills: 0.1 }
    };
    return weights[strategy];
  }

  private getStrategyLabel(strategy: OptimizationStrategy): string {
    const labels: { [key in OptimizationStrategy]: string } = {
      continuity: 'Continuity-First (same carers)',
      travel: 'Travel-First (minimize drive time)',
      balanced: 'Balanced (recommended)'
    };
    return labels[strategy];
  }

  private getAvailableCarersAfterDoubleHanded(
    carers: any[], 
    doubleAssignments: RosterAssignment[]
  ): any[] {
    const assignedCarerIds = new Set(doubleAssignments.map(a => a.carerId));
    const availableCarers = carers.filter(carer => !assignedCarerIds.has(carer.id));
    
    logger.info('Carers after double-handed assignments', {
      total: carers.length,
      assigned: assignedCarerIds.size,
      available: availableCarers.length
    });
    
    return availableCarers;
  }

  /**
   * Determine if visit is single or double-handed based on requirements
   */
  private determineVisitType(visit: any): 'single' | 'double' {
    const requirements = (visit.requirements || '').toLowerCase();
    
    // Double-handed if requires two carers or specific complex care
    const doubleHandedIndicators = [
      'double', 'two carers', 'two person', 'hoist', 'complex lift',
      'mobility transfer', 'bariatric', 'fall recovery'
    ];

    return doubleHandedIndicators.some(indicator => requirements.includes(indicator)) 
      ? 'double' 
      : 'single';
  }

  private checkSkillsMatch(requirements: string | null, carerSkills: string[]): boolean {
    if (!requirements) return true;
    
    const reqLower = requirements.toLowerCase();
    const carerSkillsLower = carerSkills.map(s => s.toLowerCase());
    
    // Check if any carer skill matches the requirements
    return carerSkillsLower.some(skill => reqLower.includes(skill));
  }

  private calculateTotalHours(assignments: RosterAssignment[]): number {
    return assignments.reduce((sum, a) => {
      const duration = a.visitDetails.duration;
      return sum + duration / 60;
    }, 0);
  }

  private calculateOvertime(
    assignments: RosterAssignment[],
    constraints: RosteringConstraints
  ): number {
    const carerHours = new Map<string, number>();
    
    assignments.forEach(a => {
      const current = carerHours.get(a.carerId) || 0;
      carerHours.set(a.carerId, current + a.visitDetails.duration / 60);
    });

    let overtime = 0;
    carerHours.forEach(hours => {
      if (hours > constraints.wtdMaxHoursPerWeek) {
        overtime += (hours - constraints.wtdMaxHoursPerWeek) * 60;
      }
    });

    return overtime;
  }

  private timeToMinutes(date: Date): number {
    return date.getHours() * 60 + date.getMinutes();
  }

  /**
   * Estimate travel time between two visits
   */
  private estimateTravelTime(visit1: any, visit2: any): number {
    if (!visit1.latitude || !visit1.longitude || !visit2.latitude || !visit2.longitude) {
      return 15; // Default 15 minutes
    }

    const distance = this.haversineDistance(
      visit1.latitude, visit1.longitude,
      visit2.latitude, visit2.longitude
    );

    // Estimate travel time: 500 meters per minute + 5 minutes base
    return Math.max(5, Math.min(60, Math.ceil(distance / 500) + 5));
  }

  /**
   * Calculate Haversine distance between two points
   */
  private haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371e3; // Earth radius in meters
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
}






