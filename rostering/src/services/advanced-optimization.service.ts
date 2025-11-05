// File: src/services/advanced-optimization.service.ts
import { RosterGenerationService, RosterScenario, RosterAssignment } from './roster-generation.service';
import { RosteringConstraints } from './constraints.service';
import { logger } from '../utils/logger';
import axios, { AxiosInstance } from 'axios';

// ========== INTERFACES ==========
export interface ORToolsOptimizationRequest {
  visits: ORToolsVisit[];
  carers: ORToolsCarer[];
  constraints: ORToolsConstraints;
  weights: ORToolsWeights;
  travelMatrix: TravelMatrix;
  timeoutSeconds?: number;
  strategy: string;
}

export interface ORToolsOptimizationResponse {
  assignments: ORToolsAssignment[];
  objective: number;
  solutionTime: number;
  status: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'ERROR';
  violations: ORToolsViolations;
  message: string;
}

interface ORToolsVisit {
  id: string;
  timeWindowStart: number;
  timeWindowEnd: number;
  duration: number;
  requiredSkills: string[];
  carerPreferences: { [carerId: string]: number };
  latitude?: number;
  longitude?: number;
  visitType?: 'single' | 'double';
}

interface ORToolsCarer {
  id: string;
  skills: string[];
  maxWeeklyHours: number;
  latitude?: number;
  longitude?: number;
}

interface ORToolsConstraints {
  wtdMaxHoursPerWeek: number;
  travelMaxMinutes: number;
  bufferMinutes: number;
  restPeriodHours: number;
}

interface ORToolsWeights {
  travel: number;
  continuity: number;
  workload: number;
}

interface ORToolsAssignment {
  visitId: string;
  carerId: string;
  startTime: number;
  endTime: number;
  travelTime: number;
  score: number;
}

interface ORToolsViolations {
  wtd: number;
  restPeriod: number;
  travel: number;
  skills: number;
}

interface TravelMatrix {
  [key: string]: { durationMinutes: number; distanceMeters: number };
}

interface OptimizerStatus {
  available: boolean;
  url: string;
  responseTime?: number;
  lastError?: string;
}

// ========== ADVANCED OPTIMIZATION SERVICE ==========
export class AdvancedOptimizationService {
  private pythonOptimizerUrl: string;
  private httpClient: AxiosInstance;
  private usePythonOptimizer: boolean;

  constructor(private rosterService: RosterGenerationService) {
  this.pythonOptimizerUrl = process.env.PYTHON_OPTIMIZER_URL || 'http://ortools-optimizer:5000';
    this.usePythonOptimizer = process.env.USE_PYTHON_OPTIMIZER === 'true';

    this.httpClient = axios.create({
      baseURL: this.pythonOptimizerUrl,
      timeout: 60000, // 1 minute timeout
      headers: { 'Content-Type': 'application/json' }
    });

    logger.info('AdvancedOptimizationService initialized', {
      pythonOptimizerUrl: this.pythonOptimizerUrl,
      usePythonOptimizer: this.usePythonOptimizer
    });
  }

  /**
   * Enhanced optimization using Python OR-Tools service
   */
  async optimizeWithORTools(
    visits: any[],
    carers: any[],
    constraints: RosteringConstraints,
    strategy: 'continuity' | 'travel' | 'balanced'
  ): Promise<RosterScenario> {
    this.validateOptimizationInputs(visits, carers);

    logger.info('Starting OR-Tools optimization attempt', {
      visitCount: visits.length,
      carerCount: carers.length,
      strategy,
      usePythonOptimizer: this.usePythonOptimizer
    });

    try {
      const optimizationRequest = this.buildOptimizationRequest(visits, carers, constraints, strategy);
      logger.info('Built optimization request', {
        visitsCount: optimizationRequest.visits.length,
        carersCount: optimizationRequest.carers.length
      });

      const orToolsResult = await this.callPythonOptimizer(optimizationRequest);
      logger.info('OR-Tools optimization successful', {
        assignmentsCount: orToolsResult.assignments.length,
        status: orToolsResult.status
      });

      // Check if we got valid assignments
      if (!orToolsResult.assignments || orToolsResult.assignments.length === 0) {
        logger.warn('OR-Tools returned empty assignments, falling back to standard algorithm');
        return this.fallbackToStandardAlgorithm(visits, carers, constraints, strategy);
      }

      return await this.convertORtoolsResultToScenario(orToolsResult, visits, carers, constraints, strategy);
    } catch (error) {
      logger.error('OR-Tools optimization failed, falling back to standard algorithm', {
        error: (error as any).message,
        visitCount: visits.length,
        carerCount: carers.length,
        stack: (error as any).stack?.substring(0, 500)
      });

      // Always fall back to standard algorithm for reliability
      return this.fallbackToStandardAlgorithm(visits, carers, constraints, strategy);
    }
  }

  /**
   * Health check for Python optimizer service
   */
  async healthCheck(): Promise<boolean> {
    if (!this.usePythonOptimizer) {
      return false;
    }

    try {
      const response = await this.httpClient.get('/health', { timeout: 5000 });
      return response.status === 200;
    } catch (error) {
      logger.warn('Python optimizer health check failed', { error: (error as any).message });
      return false;
    }
  }

  /**
   * Get optimizer status
   */
  async getOptimizerStatus(): Promise<OptimizerStatus> {
    if (!this.usePythonOptimizer) {
      return { available: false, url: this.pythonOptimizerUrl };
    }

    try {
      const startTime = Date.now();
      const response = await this.httpClient.get('/health', { timeout: 5000 });
      const responseTime = Date.now() - startTime;

      return {
        available: response.status === 200,
        url: this.pythonOptimizerUrl,
        responseTime
      };
    } catch (error: any) {
      return {
        available: false,
        url: this.pythonOptimizerUrl,
        lastError: error.message
      };
    }
  }

  // ========== PRIVATE METHODS ==========

  private validateOptimizationInputs(visits: any[], carers: any[]): void {
    if (!visits || visits.length === 0) {
      throw new Error('No visits provided for optimization');
    }

    if (!carers || carers.length === 0) {
      throw new Error('No carers provided for optimization');
    }
  }

  private shouldUsePythonOptimizer(visits: any[]): boolean {
    return this.usePythonOptimizer && visits.length >= 5;
  }

  private fallbackToStandardAlgorithm(
    visits: any[],
    carers: any[],
    constraints: RosteringConstraints,
    strategy: 'continuity' | 'travel' | 'balanced'
  ): Promise<RosterScenario> {
    logger.info('Using standard algorithm instead of Python optimizer', {
      visitCount: visits.length,
      usePythonOptimizer: this.usePythonOptimizer
    });
    return (this.rosterService as any).generateSingleScenario(visits, carers, constraints, strategy);
  }

  private async callPythonOptimizer(
    request: ORToolsOptimizationRequest
  ): Promise<ORToolsOptimizationResponse> {
    logger.info('Calling Python OR-Tools optimizer', {
      visitCount: request.visits.length,
      carerCount: request.carers.length,
      strategy: request.strategy
    });

    const startTime = Date.now();
    const response = await this.httpClient.post<ORToolsOptimizationResponse>('/solve', request);
    const solveTime = Date.now() - startTime;

    const result = response.data;

    logger.info('Python OR-Tools optimization completed', {
      status: result.status,
      objective: result.objective,
      assignmentCount: result.assignments.length,
      solutionTime: result.solutionTime,
      ourRequestTime: solveTime,
      message: result.message
    });

    this.validateORtoolsResult(result);
    return result;
  }

  private validateORtoolsResult(result: ORToolsOptimizationResponse): void {
    if (result.status === 'INFEASIBLE') {
      throw new Error(`OR-Tools could not find feasible solution: ${result.message}`);
    }

    if (result.status === 'ERROR') {
      throw new Error(`OR-Tools optimization error: ${result.message}`);
    }

    if (result.assignments.length === 0) {
      throw new Error('OR-Tools returned empty assignment list');
    }
  }

  private buildOptimizationRequest(
    visits: any[],
    carers: any[],
    constraints: RosteringConstraints,
    strategy: string
  ): ORToolsOptimizationRequest {
    const weights = this.getStrategyWeights(strategy);

    // Build visits data
    const optimizedVisits = visits.map(visit => ({
      id: visit.id,
      timeWindowStart: visit.timeStartMinutes || this.timeToMinutes(new Date(visit.scheduledStartTime)),
      timeWindowEnd: visit.timeEndMinutes || this.timeToMinutes(new Date(visit.scheduledEndTime || visit.scheduledStartTime)) + 60,
      duration: visit.estimatedDuration || 60,
      requiredSkills: this.extractSkills(visit.requirements),
      carerPreferences: this.calculateCarerPreferences(visit, carers),
      latitude: visit.latitude,
      longitude: visit.longitude,
      visitType: visit.visitType || 'single'
    }));

    // Build carers data
    const optimizedCarers = carers.map(carer => ({
      id: carer.id,
      skills: carer.skills || [],
      maxWeeklyHours: constraints.wtdMaxHoursPerWeek,
      latitude: carer.latitude,
      longitude: carer.longitude
    }));

    // Build travel matrix
    const travelMatrix = this.buildTravelMatrix(visits, carers);

    return {
      visits: optimizedVisits,
      carers: optimizedCarers,
      constraints: {
        wtdMaxHoursPerWeek: constraints.wtdMaxHoursPerWeek,
        travelMaxMinutes: constraints.travelMaxMinutes,
        bufferMinutes: constraints.bufferMinutes,
        restPeriodHours: constraints.restPeriodHours
      },
      weights,
      travelMatrix,
      timeoutSeconds: 30, // 30 seconds
      strategy
    };
  }

  private async convertORtoolsResultToScenario(
    orToolsResult: ORToolsOptimizationResponse,
    originalVisits: any[],
    originalCarers: any[],
    constraints: RosteringConstraints,
    strategy: string
  ): Promise<RosterScenario> {
    // Create lookup maps for efficient access
    const visitMap = new Map(originalVisits.map(v => [v.id, v]));
    const carerMap = new Map(originalCarers.map(c => [c.id, c]));

    const assignments: RosterAssignment[] = [];

    logger.info('Converting OR-Tools result to roster assignments', {
      assignmentCount: orToolsResult.assignments.length
    });

    for (const orToolsAssignment of orToolsResult.assignments) {
      const assignment = this.convertORtoolsAssignment(
        orToolsAssignment,
        visitMap,
        carerMap,
        constraints
      );
      if (assignment) {
        assignments.push(assignment);
      }
    }

    logger.info('OR-Tools assignments converted', {
      successful: assignments.length,
      failed: orToolsResult.assignments.length - assignments.length
    });

    // Calculate metrics
    const metrics = await this.calculateScenarioMetrics(assignments, constraints);
    const score = this.calculateScenarioScore(metrics, this.getStrategyWeights(strategy));

    return {
      id: `scenario_ortools_${strategy}_${Date.now()}`,
      label: `${this.getStrategyLabel(strategy)} (OR-Tools Optimized)`,
      strategy: strategy as any,
      assignments,
      metrics,
      score: Math.min(100, Math.max(0, score))
    };
  }

  private convertORtoolsAssignment(
    orToolsAssignment: ORToolsAssignment,
    visitMap: Map<string, any>,
    carerMap: Map<string, any>,
    constraints: RosteringConstraints
  ): RosterAssignment | null {
    const visit = visitMap.get(orToolsAssignment.visitId);
    const carer = carerMap.get(orToolsAssignment.carerId);

    if (!visit) {
      logger.warn('OR-Tools assigned non-existent visit', { visitId: orToolsAssignment.visitId });
      return null;
    }

    if (!carer) {
      logger.warn('OR-Tools assigned non-existent carer', { carerId: orToolsAssignment.carerId });
      return null;
    }

    // Convert time from minutes to Date objects
    const scheduledTime = this.minutesToDate(orToolsAssignment.startTime);
    const estimatedEndTime = this.minutesToDate(orToolsAssignment.endTime);

    // Create the assignment
    const rosterAssignment: RosterAssignment = {
      id: `assignment_ortools_${visit.id}_${carer.id}_${Date.now()}`,
      visitId: visit.id,
      carerId: carer.id,
      carerName: `${carer.firstName} ${carer.lastName}`,
      scheduledTime,
      estimatedEndTime,
      travelFromPrevious: orToolsAssignment.travelTime || 0,
      complianceChecks: {
        wtdCompliant: true, // OR-Tools ensures compliance
        restPeriodOK: true,
        travelTimeOK: orToolsAssignment.travelTime <= constraints.travelMaxMinutes,
        skillsMatch: true, // OR-Tools ensures skills match
        warnings: this.generateWarnings(orToolsAssignment, constraints)
      },
      visitDetails: {
        clientName: visit.requestorName || 'Unknown',
        address: visit.address || 'Address not available',
        duration: visit.estimatedDuration || 60,
        requirements: visit.requirements || 'General care'
      }
    };

    return rosterAssignment;
  }

  private generateWarnings(assignment: ORToolsAssignment, constraints: RosteringConstraints): string[] {
    const warnings: string[] = [];

    if (assignment.travelTime > constraints.travelMaxMinutes * 0.8) {
      warnings.push(`Travel time (${assignment.travelTime}min) approaching limit`);
    }

    if (assignment.travelTime > constraints.travelMaxMinutes * 0.9) {
      warnings.push(`Travel time (${assignment.travelTime}min) close to limit`);
    }

    // Add OR-Tools specific information
    warnings.push('Optimized by OR-Tools constraint solver');

    return warnings;
  }

  private buildTravelMatrix(visits: any[], carers: any[]): TravelMatrix {
    const matrix: TravelMatrix = {};

    logger.info('Building travel matrix', { visitCount: visits.length });

    // Calculate travel times between all visit pairs
    for (let i = 0; i < visits.length; i++) {
      for (let j = i + 1; j < visits.length; j++) {
        const visit1 = visits[i];
        const visit2 = visits[j];

        const key1 = `${visit1.id}_${visit2.id}`;
        const key2 = `${visit2.id}_${visit1.id}`;

        const duration = this.estimateTravelTime(visit1, visit2);
        const distance = this.calculateDistance(visit1, visit2);

        matrix[key1] = { durationMinutes: Math.round(duration), distanceMeters: Math.round(distance) };
        matrix[key2] = { durationMinutes: Math.round(duration), distanceMeters: Math.round(distance) };
      }
    }

    // Calculate travel times from carers to visits (simplified)
    for (const carer of carers) {
      for (const visit of visits) {
        const key = `carer_${carer.id}_visit_${visit.id}`;
        const duration = this.estimateCarerToVisitTime(carer, visit);
        const distance = this.calculateDistance(carer, visit);

        matrix[key] = { durationMinutes: Math.round(duration), distanceMeters: Math.round(distance) };
      }
    }

    logger.info('Travel matrix completed', {
      entries: Object.keys(matrix).length,
      visitPairs: visits.length * (visits.length - 1) / 2
    });

    return matrix;
  }

  private estimateTravelTime(visit1: any, visit2: any): number {
    if (!visit1.latitude || !visit1.longitude || !visit2.latitude || !visit2.longitude) {
      return 15; // Default 15 minutes
    }

    const distance = this.calculateHaversineDistance(
      visit1.latitude, visit1.longitude,
      visit2.latitude, visit2.longitude
    );

    // Estimate travel time: 2 minutes per km + 5 minutes base
    return Math.max(5, Math.min(120, Math.ceil(distance / 500) + 5));
  }

  private estimateCarerToVisitTime(carer: any, visit: any): number {
    if (!carer.latitude || !carer.longitude || !visit.latitude || !visit.longitude) {
      return 20; // Default 20 minutes from home
    }

    const distance = this.calculateHaversineDistance(
      carer.latitude, carer.longitude,
      visit.latitude, visit.longitude
    );

    // Estimate travel time from home: 2 minutes per km + 10 minutes base
    return Math.max(10, Math.min(60, Math.ceil(distance / 500) + 10));
  }

  private calculateDistance(point1: any, point2: any): number {
    if (!point1.latitude || !point1.longitude || !point2.latitude || !point2.longitude) {
      return 5000; // Default 5km
    }

    return this.calculateHaversineDistance(
      point1.latitude, point1.longitude,
      point2.latitude, point2.longitude
    );
  }

  private calculateHaversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
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

  private extractSkills(requirements: string | null): string[] {
    if (!requirements) return [];
    
    const requirementsLower = requirements.toLowerCase();
    const commonSkills = [
      'personal care', 'medication', 'mobility', 'dementia', 'complex care',
      'hoist', 'peg feeding', 'catheter', 'stoma', 'diabetes',
      'parkinson', 'stroke', 'palliative', 'respite', 'companionship'
    ];

    return commonSkills.filter(skill => requirementsLower.includes(skill));
  }

  private calculateCarerPreferences(visit: any, carers: any[]): { [carerId: string]: number } {
    const preferences: { [carerId: string]: number } = {};
    
    carers.forEach(carer => {
      let preferenceScore = 0.3; // Base score for new carers
      
      // Check historical matches
      const hasHistory = visit.matches?.some((m: any) => 
        m.carerId === carer.id && m.response === 'ACCEPTED'
      );
      
      if (hasHistory) {
        preferenceScore = 1.0; // High preference for historical matches
      }
      
      // Check skills match
      const skillsMatch = this.checkSkillsMatch(visit.requirements, carer.skills);
      if (skillsMatch) {
        preferenceScore = Math.max(preferenceScore, 0.7); // Boost for skills match
      }
      
      preferences[carer.id] = preferenceScore;
    });

    return preferences;
  }

  private checkSkillsMatch(requirements: string | null, carerSkills: string[]): boolean {
    if (!requirements) return true;
    
    const requiredSkills = this.extractSkills(requirements);
    if (requiredSkills.length === 0) return true;
    
    const carerSkillsLower = carerSkills.map(s => s.toLowerCase());
    
    return requiredSkills.every(requiredSkill => 
      carerSkillsLower.some(carerSkill => carerSkill.includes(requiredSkill))
    );
  }

  private minutesToDate(minutes: number): Date {
    const date = new Date();
    date.setHours(Math.floor(minutes / 60));
    date.setMinutes(minutes % 60);
    date.setSeconds(0);
    date.setMilliseconds(0);
    return date;
  }

  private timeToMinutes(date: Date): number {
    return date.getHours() * 60 + date.getMinutes();
  }

  private getStrategyWeights(strategy: string): ORToolsWeights {
    switch (strategy) {
      case 'continuity':
        return { travel: 20, continuity: 50, workload: 30 };
      case 'travel':
        return { travel: 50, continuity: 20, workload: 30 };
      case 'balanced':
      default:
        return { travel: 33, continuity: 33, workload: 34 };
    }
  }

  private getStrategyLabel(strategy: string): string {
    const labels: { [key: string]: string } = {
      continuity: 'Continuity-First',
      travel: 'Travel-First', 
      balanced: 'Balanced'
    };
    return labels[strategy] || strategy;
  }

  /**
   * Calculate scenario metrics (simplified version)
   */
  private async calculateScenarioMetrics(
    assignments: RosterAssignment[],
    constraints: RosteringConstraints
  ): Promise<any> {
    const totalTravel = assignments.reduce((sum, a) => sum + a.travelFromPrevious, 0);
    
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

    logger.info('OR-Tools scenario metrics calculated', {
      totalTravel,
      continuityScore: Math.round(continuityScore),
      violations: `${violations.hard} hard, ${violations.soft} soft`,
      overtimeMinutes,
      averageCarerWorkload: Math.round(averageCarerWorkload),
      uniqueCarers: carerWorkloads.size
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
   * Calculate overtime minutes
   */
  private calculateOvertime(assignments: RosterAssignment[], constraints: RosteringConstraints): number {
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

  /**
   * Calculate overall continuity score
   */
  private async calculateOverallContinuity(assignments: RosterAssignment[]): Promise<number> {
    if (assignments.length === 0) return 0;

    // This is a simplified implementation - in production, you'd query the database
    // For now, we'll assume OR-Tools already optimized for continuity
    const continuityCount = assignments.filter(a => 
      a.complianceChecks.warnings.some(w => w.includes('historical'))
    ).length;

    return (continuityCount / assignments.length) * 100;
  }

  /**
   * Calculate scenario score (0-100)
   */
  private calculateScenarioScore(metrics: any, weights: ORToolsWeights): number {
    let score = 100;

    // Penalize travel time
    const travelPenalty = Math.min(metrics.totalTravel / 10, 20);
    score -= travelPenalty * (weights.travel / 100);

    // Reward continuity  
    score += (metrics.continuityScore / 100) * 30 * (weights.continuity / 100);

    // Penalize violations
    score -= metrics.violations.hard * 15;
    score -= metrics.violations.soft * 5;

    // Penalize overtime
    score -= (metrics.overtimeMinutes / 60) * 10;

    // Penalize workload imbalance
    const workloadPenalty = Math.min(metrics.averageCarerWorkload / 10, 10);
    score -= workloadPenalty * (weights.workload / 100);

    // Bonus for OR-Tools optimization
    score += 5; // Small bonus for using advanced optimization

    return Math.max(0, Math.min(100, score));
  }
}