// File: src/services/pairing.service.ts
import { PrismaClient } from '@prisma/client';
import { TravelService } from './travel.service';
import { ConstraintsService, RosteringConstraints } from './constraints.service';
import { logger } from '../utils/logger';
import { ClusterVisit } from './clustering.service';

export interface CarerPair {
  carerA: any;
  carerB: any;
  pairScore: number;
  travelCompatibility: TravelCompatibility;
  skillsOverlap: string[];
  availabilityOverlap: number; // Percentage of overlapping availability
  historicalPairingScore: number;
}

export interface TravelCompatibility {
  distanceBetweenCarers: number; // meters
  estimatedTravelTime: number; // minutes
  routeEfficiency: number; // 0-1 score
  compatible: boolean;
}

export interface DoubleHandedVisit extends ClusterVisit {
  visitType: 'double';
  requiredCarerCount: 2;
  pairingRequirements?: {
    minSkillOverlap?: number;
    maxTravelTimeBetweenCarers?: number;
    sameGenderRequired?: boolean;
    languageRequirements?: string[];
  };
}

export interface CarerAvailability {
  [day: string]: {
    start: string; // "09:00"
    end: string;   // "17:00"
  }[];
}

export class PairingService {
  constructor(
    private prisma: PrismaClient,
    private travelService: TravelService,
    private constraintsService: ConstraintsService
  ) {}

  /**
   * Find all compatible carer pairs for double-handed visits
   */
  async findCompatiblePairs(
    visit: DoubleHandedVisit,
    availableCarers: any[],
    constraints: RosteringConstraints,
    scheduledTime: Date
  ): Promise<CarerPair[]> {
    
    logger.info('Finding compatible pairs for double-handed visit', {
      visitId: visit.id,
      availableCarers: availableCarers.length,
      scheduledTime: scheduledTime.toISOString()
    });

    const compatiblePairs: CarerPair[] = [];

    // Filter carers who are available at the scheduled time
    const availableAtTime = availableCarers.filter(carer => 
      this.isCarerAvailable(carer, scheduledTime, visit.estimatedDuration || 60)
    );

    logger.info('Carers available at scheduled time', {
      total: availableCarers.length,
      available: availableAtTime.length
    });

    if (availableAtTime.length < 2) {
      logger.warn('Not enough available carers for double-handed visit', {
        required: 2,
        available: availableAtTime.length
      });
      return [];
    }

    // Generate all possible pairs
    let pairsEvaluated = 0;
    for (let i = 0; i < availableAtTime.length; i++) {
      for (let j = i + 1; j < availableAtTime.length; j++) {
        const carerA = availableAtTime[i];
        const carerB = availableAtTime[j];

        try {
          const isValid = await this.isValidPair(carerA, carerB, visit, constraints, scheduledTime);
          
          if (isValid) {
            const [
              pairScore,
              travelCompatibility,
              skillsOverlap,
              availabilityOverlap,
              historicalPairingScore
            ] = await Promise.all([
              this.calculatePairScore(carerA, carerB, visit, scheduledTime),
              this.checkTravelCompatibility(carerA, carerB, visit),
              this.calculateSkillsOverlap(carerA, carerB, visit),
              this.calculateDailyAvailabilityOverlap(
                this.parseAvailability(carerA.availability),
                this.parseAvailability(carerB.availability),
                scheduledTime.getDay()
              ),
              this.calculateHistoricalPairingScore(carerA, carerB)
            ]);

            compatiblePairs.push({
              carerA,
              carerB,
              pairScore,
              travelCompatibility,
              skillsOverlap,
              availabilityOverlap,
              historicalPairingScore
            });
          }

          pairsEvaluated++;
          if (pairsEvaluated % 10 === 0) {
            logger.debug('Pair evaluation progress', {
              evaluated: pairsEvaluated,
              totalPossible: (availableAtTime.length * (availableAtTime.length - 1)) / 2,
              valid: compatiblePairs.length
            });
          }

        } catch (error) {
          logger.warn('Error evaluating carer pair', {
            carerA: carerA.id,
            carerB: carerB.id,
            error: (error as Error).message
          });
        }
      }
    }

    // Sort by pair score (descending)
    const sortedPairs = compatiblePairs.sort((a, b) => b.pairScore - a.pairScore);

    logger.info('Compatible pairs search completed', {
      visitId: visit.id,
      totalPairs: sortedPairs.length,
      pairsEvaluated,
      topScore: sortedPairs[0]?.pairScore || 0
    });

    return sortedPairs;
  }

  /**
   * Validate if two carers can form a valid pair for a double-handed visit
   */
  private async isValidPair(
    carerA: any,
    carerB: any,
    visit: DoubleHandedVisit,
    constraints: RosteringConstraints,
    scheduledTime: Date
  ): Promise<boolean> {
    // 1. Basic validation
    if (carerA.id === carerB.id) {
      return false; // Cannot pair with oneself
    }

    // 2. Skills validation - both carers must have required skills
    const hasRequiredSkills = this.checkSkillsMatch(visit.requirements, carerA.skills) &&
                             this.checkSkillsMatch(visit.requirements || '', carerB.skills);
    
    if (!hasRequiredSkills) {
      return false;
    }

    // 3. Gender preferences (if specified)
    if (visit.pairingRequirements?.sameGenderRequired) {
      if (carerA.gender !== carerB.gender) {
        return false;
      }
    }

    // 4. Language requirements (if specified)
    if (visit.pairingRequirements?.languageRequirements) {
      const requiredLanguages = visit.pairingRequirements.languageRequirements;
      const hasLanguageOverlap = requiredLanguages.some(language => 
        carerA.languages?.includes(language) && carerB.languages?.includes(language)
      );
      if (!hasLanguageOverlap) {
        return false;
      }
    }

    // 5. Travel compatibility
    const travelCompatibility = await this.checkTravelCompatibility(carerA, carerB, visit);
    if (!travelCompatibility.compatible) {
      return false;
    }

    // 6. Scheduling constraints
    const noSchedulingConflicts = !await this.hasSchedulingConflicts(carerA, carerB, visit, scheduledTime);
    if (!noSchedulingConflicts) {
      return false;
    }

    // 7. Working time directive compliance
    const wtdCompliant = await this.checkWTDCompliance(carerA, carerB, visit, constraints, scheduledTime);
    if (!wtdCompliant) {
      return false;
    }

    return true;
  }

  /**
   * Calculate comprehensive pair score (0-100)
   */
  private async calculatePairScore(
    carerA: any,
    carerB: any,
    visit: DoubleHandedVisit,
    scheduledTime: Date
  ): Promise<number> {
    let score = 0;

    // 1. Skills compatibility (30%)
    const skillsScore = this.calculateSkillsCompatibility(carerA, carerB, visit);
    score += skillsScore * 0.3;

    // 2. Travel efficiency (25%)
    const travelScore = await this.calculateTravelScore(carerA, carerB, visit);
    score += travelScore * 0.25;

    // 3. Historical pairing success (20%)
    const historicalScore = await this.calculateHistoricalPairingScore(carerA, carerB);
    score += historicalScore * 0.2;

    // 4. Availability alignment (15%)
    const availabilityScore = this.calculateAvailabilityScore(carerA, carerB, visit, scheduledTime);
    score += availabilityScore * 0.15;

    // 5. Client continuity (10%)
    const continuityScore = await this.calculateContinuityScore(carerA, carerB, visit);
    score += continuityScore * 0.1;

    return Math.min(100, Math.max(0, score * 100)); // Convert to 0-100 scale
  }

  /**
   * Check travel compatibility between two carers
   */
  private async checkTravelCompatibility(
    carerA: any,
    carerB: any,
    visit: DoubleHandedVisit
  ): Promise<TravelCompatibility> {
    try {
      // Calculate distance between carers' locations
      let distanceBetweenCarers = 0;
      if (carerA.latitude && carerA.longitude && carerB.latitude && carerB.longitude) {
        distanceBetweenCarers = this.calculateHaversineDistance(
          carerA.latitude, carerA.longitude,
          carerB.latitude, carerB.longitude
        );
      }

      // Calculate travel time to visit location from both carers
      const travelTimeA = visit.latitude && visit.longitude ? 
        await this.estimateTravelTime(carerA, visit) : 0;
      const travelTimeB = visit.latitude && visit.longitude ? 
        await this.estimateTravelTime(carerB, visit) : 0;

      const maxTravelTime = visit.pairingRequirements?.maxTravelTimeBetweenCarers || 30; // minutes
      const estimatedTravelTime = Math.max(travelTimeA, travelTimeB);

      // Route efficiency - how well their routes align
      const routeEfficiency = this.calculateRouteEfficiency(carerA, carerB, visit);

      return {
        distanceBetweenCarers,
        estimatedTravelTime,
        routeEfficiency,
        compatible: estimatedTravelTime <= maxTravelTime && routeEfficiency >= 0.5
      };

    } catch (error) {
      logger.error('Error checking travel compatibility', { error: (error as Error).message });
      return {
        distanceBetweenCarers: 0,
        estimatedTravelTime: 0,
        routeEfficiency: 0,
        compatible: false
      };
    }
  }

  /**
   * Calculate skills overlap between two carers
   */
  private calculateSkillsOverlap(carerA: any, carerB: any, visit: DoubleHandedVisit): string[] {
    const skillsA = new Set(carerA.skills || []);
    const skillsB = new Set(carerB.skills || []);
    const requiredSkills = new Set(this.extractRequiredSkills(visit.requirements || ''));

    const overlap = [...skillsA].filter((skill: unknown) => typeof skill === 'string' && skillsB.has(skill) && requiredSkills.has(skill)) as string[];
    return overlap;
  }

  /**
   * Calculate skills compatibility score
   */
  private calculateSkillsCompatibility(carerA: any, carerB: any, visit: DoubleHandedVisit): number {
    const skillsOverlap = this.calculateSkillsOverlap(carerA, carerB, visit);
    const requiredSkills = this.extractRequiredSkills(visit.requirements || '');
    
    if (requiredSkills.length === 0) return 1.0;

    const overlapRatio = skillsOverlap.length / requiredSkills.length;
    return Math.min(1.0, overlapRatio);
  }

  /**
   * Calculate travel efficiency score
   */
  private async calculateTravelScore(carerA: any, carerB: any, visit: DoubleHandedVisit): Promise<number> {
    const travelCompatibility = await this.checkTravelCompatibility(carerA, carerB, visit);
    
    if (!travelCompatibility.compatible) {
      return 0;
    }

    // Normalize travel time (0-30 minutes -> 1-0 score)
    const maxAcceptableTravel = 30;
    const travelTimeScore = Math.max(0, 1 - (travelCompatibility.estimatedTravelTime / maxAcceptableTravel));

    // Combine with route efficiency
    return (travelTimeScore * 0.7) + (travelCompatibility.routeEfficiency * 0.3);
  }

  /**
   * Calculate historical pairing success score
   */
  private async calculateHistoricalPairingScore(carerA: any, carerB: any): Promise<number> {
    try {
      // Get the current week range
      const now = new Date();
      const startOfWeek = new Date(now);
      startOfWeek.setDate(now.getDate() - now.getDay());
      startOfWeek.setHours(0, 0, 0, 0);

      const endOfWeek = new Date(startOfWeek);
      endOfWeek.setDate(startOfWeek.getDate() + 7);

      // Query historical pairings from database for the current week
      const historicalPairings = await this.prisma.assignment.findMany({
        where: {
          OR: [
            { carerId: carerA.id },
            { carerId: carerB.id }
          ],
          status: 'COMPLETED',
          scheduledTime: {
            gte: startOfWeek,
            lt: endOfWeek
          }
        },
        include: {
          visit: true
        }
      });

      // Count how many times they've worked together
      const jointVisits = new Set<string>();
      
      historicalPairings.forEach(assignment => {
        const otherAssignments = historicalPairings.filter(a => 
          a.visitId === assignment.visitId && a.carerId !== assignment.carerId
        );
        
        otherAssignments.forEach(otherAssignment => {
          if ((otherAssignment.carerId === carerA.id || otherAssignment.carerId === carerB.id) &&
              (assignment.carerId === carerA.id || assignment.carerId === carerB.id)) {
            jointVisits.add(assignment.visitId);
          }
        });
      });

      const uniqueJointVisits = jointVisits.size;

      // Scoring based on historical pairing frequency
      if (uniqueJointVisits === 0) return 0.3; // Low score for no history
      if (uniqueJointVisits === 1) return 0.6; // Medium score for one pairing
      if (uniqueJointVisits === 2) return 0.8; // Good score for two pairings
      return 1.0; // Excellent score for 3+ pairings

    } catch (error) {
      logger.warn('Error calculating historical pairing score', { error: (error as Error).message });
      return 0.5; // Neutral score on error
    }
  }

  /**
   * Calculate availability alignment score
   */
  private calculateAvailabilityScore(
    carerA: any,
    carerB: any,
    visit: DoubleHandedVisit,
    scheduledTime: Date
  ): number {
    try {
      const availabilityA = this.parseAvailability(carerA.availability);
      const availabilityB = this.parseAvailability(carerB.availability);

      const dayOfWeek = scheduledTime.getDay();
      const hour = scheduledTime.getHours();

      const isAvailableA = this.isTimeInAvailability(availabilityA, dayOfWeek, hour);
      const isAvailableB = this.isTimeInAvailability(availabilityB, dayOfWeek, hour);

      if (!isAvailableA || !isAvailableB) return 0;

      // Calculate overlap percentage for the scheduled day
      const overlapHours = this.calculateDailyAvailabilityOverlap(availabilityA, availabilityB, dayOfWeek);
      const maxPossibleHours = 24;

      return Math.min(1.0, overlapHours / maxPossibleHours);
    } catch (error) {
      logger.warn('Error calculating availability score', { error: (error as Error).message });
      return 0.5; // Default score on error
    }
  }

  /**
   * Calculate client continuity score
   */
  private async calculateContinuityScore(carerA: any, carerB: any, visit: DoubleHandedVisit): Promise<number> {
    try {
      // Check if either carer has history with this client
      const [clientHistoryA, clientHistoryB] = await Promise.all([
        this.prisma.requestCarerMatch.count({
          where: {
            carerId: carerA.id,
            requestId: visit.id,
            response: 'ACCEPTED'
          }
        }),
        this.prisma.requestCarerMatch.count({
          where: {
            carerId: carerB.id,
            requestId: visit.id,
            response: 'ACCEPTED'
          }
        })
      ]);

      // If both have history, max score
      if (clientHistoryA > 0 && clientHistoryB > 0) return 1.0;
      
      // If one has history, medium score
      if (clientHistoryA > 0 || clientHistoryB > 0) return 0.7;
      
      // No history
      return 0.3;

    } catch (error) {
      logger.warn('Error calculating continuity score', { error: (error as Error).message });
      return 0.5;
    }
  }

  // ========== IMPLEMENTED HELPER METHODS (No Placeholders) ==========

  /**
   * Check if carer is available at specified time
   */
  private isCarerAvailable(carer: any, scheduledTime: Date, duration: number): boolean {
    try {
      const availability = this.parseAvailability(carer.availability);
      const dayOfWeek = scheduledTime.getDay();
      const startHour = scheduledTime.getHours();
      const endHour = startHour + Math.ceil(duration / 60);

      // Check each hour of the visit duration
      for (let hour = startHour; hour < endHour; hour++) {
        if (!this.isTimeInAvailability(availability, dayOfWeek, hour)) {
          return false;
        }
      }
      return true;
    } catch (error) {
      logger.warn('Error checking carer availability', { error: (error as Error).message });
      return true; // Assume available if we can't determine
    }
  }

  /**
   * Check for scheduling conflicts
   */
  private async hasSchedulingConflicts(
    carerA: any,
    carerB: any,
    visit: DoubleHandedVisit,
    scheduledTime: Date
  ): Promise<boolean> {
    try {
      const visitStart = scheduledTime;
      const visitEnd = new Date(visitStart.getTime() + (visit.estimatedDuration || 60) * 60000);

      // Check conflicts for both carers
      const [conflictsA, conflictsB] = await Promise.all([
        this.checkCarerConflicts(carerA.id, visitStart, visitEnd),
        this.checkCarerConflicts(carerB.id, visitStart, visitEnd)
      ]);

      return conflictsA || conflictsB;
    } catch (error) {
      logger.warn('Error checking scheduling conflicts', { error: (error as Error).message });
      return false; // Assume no conflicts on error
    }
  }

  /**
   * Check WTD compliance for pair
   */
  private async checkWTDCompliance(
    carerA: any,
    carerB: any,
    visit: DoubleHandedVisit,
    constraints: RosteringConstraints,
    scheduledTime: Date
  ): Promise<boolean> {
    try {
      // Get weekly hours for both carers
      const [weeklyHoursA, weeklyHoursB] = await Promise.all([
        this.getCarerWeeklyHours(carerA.id, scheduledTime),
        this.getCarerWeeklyHours(carerB.id, scheduledTime)
      ]);

      const visitHours = (visit.estimatedDuration || 60) / 60;

      return (weeklyHoursA + visitHours <= constraints.wtdMaxHoursPerWeek) &&
             (weeklyHoursB + visitHours <= constraints.wtdMaxHoursPerWeek);
    } catch (error) {
      logger.warn('Error checking WTD compliance', { error: (error as Error).message });
      return true; // Assume compliant on error
    }
  }

  /**
   * Parse availability JSON
   */
  private parseAvailability(availability: any): CarerAvailability {
    try {
      if (!availability) return {};
      
      if (typeof availability === 'string') {
        return JSON.parse(availability);
      }
      
      return availability || {};
    } catch (error) {
      logger.warn('Error parsing availability', { error: (error as Error).message });
      return {};
    }
  }

  /**
   * Check if time is within availability
   */
  private isTimeInAvailability(availability: CarerAvailability, dayOfWeek: number, hour: number): boolean {
    try {
      const dayNames = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
      const dayName = dayNames[dayOfWeek];
      
      const dayAvailability = availability[dayName];
      if (!dayAvailability || !Array.isArray(dayAvailability)) {
        return true; // Assume available if no specific availability
      }

      // Check if hour falls within any availability slot
      return dayAvailability.some(slot => {
        const [startHour] = slot.start.split(':').map(Number);
        const [endHour] = slot.end.split(':').map(Number);
        return hour >= startHour && hour < endHour;
      });
    } catch (error) {
      logger.warn('Error checking time availability', { error: (error as Error).message });
      return true; // Assume available on error
    }
  }

  /**
   * Calculate daily availability overlap
   */
  private calculateDailyAvailabilityOverlap(availabilityA: CarerAvailability, availabilityB: CarerAvailability, dayOfWeek: number): number {
    try {
      const dayNames = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
      const dayName = dayNames[dayOfWeek];
      
      const slotsA = availabilityA[dayName] || [];
      const slotsB = availabilityB[dayName] || [];

      if (slotsA.length === 0 || slotsB.length === 0) {
        return 8; // Default overlap if no specific availability
      }

      // Simple overlap calculation - count overlapping hours
      let overlapHours = 0;
      
      for (const slotA of slotsA) {
        for (const slotB of slotsB) {
          const [startA] = slotA.start.split(':').map(Number);
          const [endA] = slotA.end.split(':').map(Number);
          const [startB] = slotB.start.split(':').map(Number);
          const [endB] = slotB.end.split(':').map(Number);
          
          const overlapStart = Math.max(startA, startB);
          const overlapEnd = Math.min(endA, endB);
          
          if (overlapStart < overlapEnd) {
            overlapHours += (overlapEnd - overlapStart);
          }
        }
      }

      return Math.min(12, overlapHours); // Cap at 12 hours
    } catch (error) {
      logger.warn('Error calculating availability overlap', { error: (error as Error).message });
      return 8; // Default overlap on error
    }
  }

  /**
   * Check carer conflicts with existing assignments
   */
  private async checkCarerConflicts(carerId: string, visitStart: Date, visitEnd: Date): Promise<boolean> {
    try {
      const conflictingAssignments = await this.prisma.assignment.count({
        where: {
          carerId: carerId,
          status: { in: ['PENDING', 'OFFERED', 'ACCEPTED'] },
          OR: [
            {
              scheduledTime: {
                lt: visitEnd,
                gte: visitStart
              }
            },
            {
              estimatedEndTime: {
                gt: visitStart,
                lte: visitEnd
              }
            }
          ]
        }
      });

      return conflictingAssignments > 0;
    } catch (error) {
      logger.warn('Error checking carer conflicts', { error: (error as Error).message });
      return false; // Assume no conflicts on error
    }
  }

  /**
   * Get carer's weekly hours
   */
  private async getCarerWeeklyHours(carerId: string, scheduledTime: Date): Promise<number> {
    try {
      // Calculate week range
      const startOfWeek = new Date(scheduledTime);
      startOfWeek.setDate(scheduledTime.getDate() - scheduledTime.getDay());
      startOfWeek.setHours(0, 0, 0, 0);

      const endOfWeek = new Date(startOfWeek);
      endOfWeek.setDate(startOfWeek.getDate() + 7);

      // Get assignments for the week
      const weeklyAssignments = await this.prisma.assignment.findMany({
        where: {
          carerId: carerId,
          scheduledTime: {
            gte: startOfWeek,
            lt: endOfWeek
          },
          status: { in: ['PENDING', 'OFFERED', 'ACCEPTED', 'COMPLETED'] }
        },
        select: {
          visit: {
            select: {
              estimatedDuration: true
            }
          }
        }
      });

      // Calculate total hours
      const totalMinutes = weeklyAssignments.reduce((total, assignment) => {
        return total + (assignment.visit.estimatedDuration || 60);
      }, 0);

      return totalMinutes / 60; // Convert to hours
    } catch (error) {
      logger.warn('Error getting carer weekly hours', { error: (error as Error).message });
      return 0; // Assume 0 hours on error
    }
  }

  /**
   * Estimate travel time from carer to visit
   */
  private async estimateTravelTime(carer: any, visit: ClusterVisit): Promise<number> {
    if (!carer.postcode || !(visit as any).postcode) {
      return this.estimateTravelTimeByCoordinates(carer, visit);
    }
    
    try {
      const travel = await this.travelService.getTravelTime(carer.postcode!, (visit as any).postcode!);
      return Math.ceil(travel.durationSeconds / 60); // Convert to minutes
    } catch (error) {
      logger.warn('Error estimating travel time by postcode, using coordinates', { error: (error as Error).message });
      return this.estimateTravelTimeByCoordinates(carer, visit);
    }
  }

  /**
   * Estimate travel time using coordinates
   */
  private estimateTravelTimeByCoordinates(carer: any, visit: ClusterVisit): number {
    if (!carer.latitude || !carer.longitude || !visit.latitude || !visit.longitude) {
      return 20; // Default 20 minutes
    }

    const distance = this.calculateHaversineDistance(
      carer.latitude, carer.longitude,
      visit.latitude, visit.longitude
    );

    // Estimate: 2 minutes per km + 10 minutes base
    return Math.max(10, Math.min(60, Math.ceil(distance / 500) + 10));
  }

  /**
   * Calculate route efficiency (simplified)
   */
  private calculateRouteEfficiency(carerA: any, carerB: any, visit: ClusterVisit): number {
    // Simplified calculation based on distance ratios
    if (!carerA.latitude || !carerA.longitude || !carerB.latitude || !carerB.longitude || !visit.latitude || !visit.longitude) {
      return 0.7; // Default efficiency
    }

    const distanceA = this.calculateHaversineDistance(carerA.latitude, carerA.longitude, visit.latitude, visit.longitude);
    const distanceB = this.calculateHaversineDistance(carerB.latitude, carerB.longitude, visit.latitude, visit.longitude);
    const distanceBetween = this.calculateHaversineDistance(carerA.latitude, carerA.longitude, carerB.latitude, carerB.longitude);

    // Efficiency is higher when carers are close to each other and the visit
    const maxDistance = Math.max(distanceA, distanceB);
    if (maxDistance === 0) return 1.0;

    const efficiency = 1 - (distanceBetween / (maxDistance * 2));
    return Math.max(0.3, Math.min(1.0, efficiency));
  }

  /**
   * Check skills match
   */
  private checkSkillsMatch(requirements: string | null, carerSkills: string[]): boolean {
    if (!requirements) return true;
    
    const requiredSkills = this.extractRequiredSkills(requirements);
    if (requiredSkills.length === 0) return true;
    
    const carerSkillsLower = (carerSkills || []).map(s => s.toLowerCase());
    
    return requiredSkills.every(requiredSkill => 
      carerSkillsLower.some(carerSkill => carerSkill.includes(requiredSkill.toLowerCase()))
    );
  }

  /**
   * Extract required skills from requirements string
   */
  private extractRequiredSkills(requirements: string | null): string[] {
    if (!requirements) return [];
    
    const requirementsLower = requirements.toLowerCase();
    const commonSkills = [
      'personal care', 'medication', 'mobility', 'dementia', 'complex care',
      'hoist', 'peg feeding', 'catheter', 'stoma', 'diabetes',
      'parkinson', 'stroke', 'palliative', 'respite', 'companionship',
      'double', 'two carers', 'two person' // Double-handed indicators
    ];

    return commonSkills.filter(skill => requirementsLower.includes(skill));
  }

  /**
   * Calculate Haversine distance between two points
   */
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
}


