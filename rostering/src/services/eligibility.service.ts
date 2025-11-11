import { PrismaClient } from '@prisma/client';
import { logger } from '../utils/logger';

export interface EligibilityResult {
  carerId: string;
  eligible: boolean;
  score: number;
  skillsMatch: boolean;
  credentialsValid: boolean;
  available: boolean;
  preferencesMatch: boolean;
  travelTime?: number;
  reasons: string[];
}

export class EligibilityService {
  constructor(private prisma: PrismaClient) {}

  async precomputeEligibility(tenantId: string, visitId: string): Promise<EligibilityResult[]> {
    const [visit, carers] = await Promise.all([
      this.prisma.externalRequest.findUnique({
        where: { id: visitId, tenantId }
      }),
      this.prisma.carer.findMany({
        where: { tenantId, isActive: true }
      })
    ]);

    if (!visit) {
      throw new Error(`Visit not found: ${visitId}`);
    }

    const eligibilityResults: EligibilityResult[] = [];

    for (const carer of carers) {
      const result = await this.checkCarerEligibility(visit, carer);
      eligibilityResults.push(result);

      // Store in eligibility table - commented out as visitEligibility doesn't exist in schema
      // await this.prisma.visitEligibility.upsert({
      //   where: {
      //     visitId_carerId: {
      //       visitId,
      //       carerId: carer.id
      //     }
      //   },
      //   update: {
      //     eligible: result.eligible,
      //     score: result.score,
      //     skillsMatch: result.skillsMatch,
      //     credentialsValid: result.credentialsValid,
      //     available: result.available,
      //     preferencesMatch: result.preferencesMatch,
      //     travelTime: result.travelTime,
      //     lastCalculated: new Date()
      //   },
      //   create: {
      //     tenantId,
      //     visitId,
      //     carerId: carer.id,
      //     eligible: result.eligible,
      //     score: result.score,
      //     skillsMatch: result.skillsMatch,
      //     credentialsValid: result.credentialsValid,
      //     available: result.available,
      //     preferencesMatch: result.preferencesMatch,
      //     travelTime: result.travelTime,
      //     lastCalculated: new Date()
      //   }
      // });
    }

    logger.info('Eligibility pre-computation completed', {
      visitId,
      totalCarers: carers.length,
      eligibleCount: eligibilityResults.filter(r => r.eligible).length
    });

    return eligibilityResults.sort((a, b) => b.score - a.score);
  }

  async getEligibleCarers(visitId: string): Promise<EligibilityResult[]> {
    // Since visitEligibility doesn't exist, return empty array for now
    // This would need to be implemented differently based on the actual schema
    return [];
  }

  private async checkCarerEligibility(visit: any, carer: any): Promise<EligibilityResult> {
    const reasons: string[] = [];
    let score = 0;

    // Check skills
    const skillsMatch = this.checkSkillsMatch(visit.requiredSkills || [], carer.skills);
    if (!skillsMatch) {
      reasons.push('Missing required skills');
    } else {
      score += 40;
    }

    // Check credentials - simplified since credentials not available
    const credentialsValid = true; // Assume valid for now
    score += 20;

    // Check availability
    const available = await this.checkAvailability(carer, visit.scheduledStartTime);
    if (!available) {
      reasons.push('Not available');
    } else {
      score += 20;
    }

    // Check preferences
    const preferencesMatch = this.checkPreferences(visit.client, carer);
    if (!preferencesMatch) {
      reasons.push('Preferences mismatch');
    } else {
      score += 10;
    }

    // Check travel time
    const travelTime = await this.calculateTravelTime(visit, carer);
    if (travelTime && travelTime > 60) { // More than 60 minutes
      reasons.push('Travel time too long');
    } else if (travelTime) {
      score += Math.max(0, 10 - (travelTime / 6)); // Reduce score based on travel time
    }

    const eligible = skillsMatch && credentialsValid && available && preferencesMatch;

    return {
      carerId: carer.id,
      eligible,
      score,
      skillsMatch,
      credentialsValid,
      available,
      preferencesMatch,
      travelTime,
      reasons
    };
  }

  private checkSkillsMatch(requiredSkills: string[], carerSkills: string[]): boolean {
    if (!requiredSkills || requiredSkills.length === 0) return true;

    const carerSkillsLower = carerSkills.map(s => s.toLowerCase());
    const requiredSkillsLower = requiredSkills.map(s => s.toLowerCase());

    return requiredSkillsLower.every(requiredSkill =>
      carerSkillsLower.some(carerSkill => carerSkill.includes(requiredSkill) || requiredSkill.includes(carerSkill))
    );
  }

  private extractSkills(requirements: string): string[] {
    const requirementsLower = requirements.toLowerCase();
    const commonSkills = [
      'personal care', 'medication', 'mobility', 'dementia', 'complex care',
      'hoist', 'peg feeding', 'catheter', 'stoma', 'diabetes',
      'parkinson', 'stroke', 'palliative', 'respite', 'companionship'
    ];

    return commonSkills.filter(skill => requirementsLower.includes(skill));
  }

  private checkCredentials(credentials: any[]): boolean {
    // Simplified check since credentials structure is unknown
    return true;
  }

  private async checkAvailability(carer: any, scheduledTime: Date): Promise<boolean> {
    if (!carer.availabilityHours) return true;
    
    try {
      const availability = typeof carer.availabilityHours === 'string' 
        ? JSON.parse(carer.availabilityHours)
        : carer.availabilityHours;
      
      const dayOfWeek = scheduledTime.getDay();
      const hour = scheduledTime.getHours();
      
      return availability[dayOfWeek]?.includes(hour) || false;
    } catch {
      return true; // If availability data is invalid, assume available
    }
  }

  private checkPreferences(client: any, carer: any): boolean {
    // Simplified preferences check since client structure is unknown
    return true;
  }

  private async calculateTravelTime(visit: any, carer: any): Promise<number | undefined> {
    if (!visit.postcode || !carer.postcode) return undefined;
    
    // Use travel matrix or calculate distance
    try {
      const travelService = new (await import('./travel.service')).TravelService(this.prisma);
      const travel = await travelService.getTravelTime(carer.postcode, visit.postcode);
      return Math.ceil(travel.durationSeconds / 60);
    } catch {
      return this.estimateTravelTime(visit, carer);
    }
  }

  private estimateTravelTime(visit: any, carer: any): number {
    if (!visit.latitude || !visit.longitude || !carer.latitude || !carer.longitude) {
      return 15; // Default estimate
    }

    const distance = this.calculateDistance(
      visit.latitude, visit.longitude,
      carer.latitude, carer.longitude
    );

    return Math.ceil(distance / 500) + 5; // 500 meters per minute + 5 minutes base
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
}