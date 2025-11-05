// File: src/services/double-handed.service.ts
import { RosteringConstraints } from './constraints.service';
import { ClusterVisit } from './clustering.service';
import { CarerPair } from './pairing.service';
import { logger } from '../utils/logger';

export class DoubleHandedService {
  
  /**
   * Find compatible carer pairs for double-handed calls
   */
  async findCompatiblePairs(
    visit: ClusterVisit,
    availableCarers: any[],
    constraints: RosteringConstraints
  ): Promise<CarerPair[]> {

    if (visit.visitType !== 'double') {
      return [];
    }

    const compatiblePairs: CarerPair[] = [];

    for (let i = 0; i < availableCarers.length; i++) {
      for (let j = i + 1; j < availableCarers.length; j++) {
        const carerA = availableCarers[i];
        const carerB = availableCarers[j];

        if (this.isValidPair(carerA, carerB, visit, constraints)) {
          compatiblePairs.push({
            carerA,
            carerB,
            pairScore: this.calculatePairScore(carerA, carerB, visit),
            travelCompatibility: await this.checkTravelCompatibility(carerA, carerB, visit),
            skillsOverlap: [],
            availabilityOverlap: 0,
            historicalPairingScore: 0
          });
        }
      }
    }

    return compatiblePairs.sort((a, b) => b.pairScore - a.pairScore);
  }

  private isValidPair(
    carerA: any,
    carerB: any,
    visit: ClusterVisit,
    constraints: RosteringConstraints
  ): boolean {
    // Both carers must have required skills
    const hasSkills = this.checkSkillsMatch(visit.requirements, carerA.skills) &&
                     this.checkSkillsMatch(visit.requirements, carerB.skills);

    // Carers cannot be the same person
    const differentCarers = carerA.id !== carerB.id;

    // Check if carers can work together (no conflicts)
    const noConflicts = !this.hasSchedulingConflicts(carerA, carerB, visit);

    return hasSkills && differentCarers && noConflicts;
  }

  private calculatePairScore(carerA: any, carerB: any, visit: ClusterVisit): number {
    let score = 0;

    // Skills match (40%)
    score += this.calculateSkillsScore(carerA, carerB, visit) * 0.4;

    // Historical pairing success (30%)
    score += this.calculatePairingHistoryScore(carerA, carerB) * 0.3;

    // Geographic compatibility (20%)
    score += this.calculateTravelScore(carerA, carerB, visit) * 0.2;

    // Availability alignment (10%)
    score += this.calculateAvailabilityScore(carerA, carerB, visit) * 0.1;

    return score;
  }

  // Placeholder methods - implement as needed
  private checkSkillsMatch(requirements: string | null, carerSkills: string[]): boolean {
    if (!requirements) return true;
    const reqLower = requirements.toLowerCase();
    const carerSkillsLower = carerSkills.map(s => s.toLowerCase());
    return carerSkillsLower.some(skill => reqLower.includes(skill));
  }

  private hasSchedulingConflicts(carerA: any, carerB: any, visit: ClusterVisit): boolean {
    // Placeholder implementation
    return false;
  }

  private calculateSkillsScore(carerA: any, carerB: any, visit: ClusterVisit): number {
    const hasSkillsA = this.checkSkillsMatch(visit.requirements, carerA.skills);
    const hasSkillsB = this.checkSkillsMatch(visit.requirements, carerB.skills);
    return (hasSkillsA && hasSkillsB) ? 1.0 : 0.0;
  }

  private calculatePairingHistoryScore(carerA: any, carerB: any): number {
    // Placeholder implementation
    return 0.5;
  }

  private calculateTravelScore(carerA: any, carerB: any, visit: ClusterVisit): number {
    // Placeholder implementation
    return 0.5;
  }

  private calculateAvailabilityScore(carerA: any, carerB: any, visit: ClusterVisit): number {
    // Placeholder implementation
    return 0.5;
  }

  private async checkTravelCompatibility(carerA: any, carerB: any, visit: ClusterVisit): Promise<any> {
    // Placeholder implementation
    return {
      distanceBetweenCarers: 0,
      estimatedTravelTime: 0,
      routeEfficiency: 0.5,
      compatible: true
    };
  }
}


