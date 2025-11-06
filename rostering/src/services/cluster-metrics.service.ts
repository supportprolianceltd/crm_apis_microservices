import { PrismaClient } from '@prisma/client';
import { logger } from '../utils/logger';

export interface ClusterMetrics {
  clusterId: string;
  calculatedAt: Date;
  totalVisits: number;
  totalHours: number;
  averageDistance: number;
  totalTravelTime: number;
  skillCoverage: number;
  continuityRisk: number;
  requiredSkills: string[];
}

export class ClusterMetricsService {
  constructor(private prisma: PrismaClient) {}

  async calculateClusterMetrics(clusterId: string): Promise<ClusterMetrics> {
    // ✅ FIX 1: Get cluster with visits and carers in single query
    const cluster = await this.prisma.cluster.findUnique({
      where: { id: clusterId },
      include: {
        visits: {  // ✅ Direct visits relation
          include: {
            assignments: {
              include: { carer: true }
            }
          }
        },
        carers: true  // ✅ Include carers directly
      }
    });

    if (!cluster) {
      throw new Error(`Cluster not found: ${clusterId}`);
    }

    // ✅ FIX 2: Use visits and carers directly
    const visits = cluster.visits;
    const carers = cluster.carers;

    // Calculate metrics
    const totalVisits = visits.length;
    const totalHours = this.calculateTotalHours(visits);
    const averageDistance = await this.calculateAverageDistance(visits);
    const totalTravelTime = await this.calculateTotalTravelTime(visits);
    const skillCoverage = this.calculateSkillCoverage(visits, carers);
    const continuityRisk = await this.calculateContinuityRisk(visits);
    const requiredSkills = this.extractRequiredSkills(visits);

    const metrics: ClusterMetrics = {
      clusterId,
      calculatedAt: new Date(),
      totalVisits,
      totalHours,
      averageDistance,
      totalTravelTime,
      skillCoverage,
      continuityRisk,
      requiredSkills
    };

    // Store metrics
    await this.prisma.clusterMetrics.create({
      data: {
        tenantId: cluster.tenantId,
        clusterId,
        calculatedAt: new Date(),
        totalVisits,
        totalHours,
        averageDistance,
        totalTravelTime,
        skillCoverage,
        continuityRisk,
        requiredSkills
      }
    });

    logger.info('Cluster metrics calculated', {
      clusterId,
      totalVisits,
      skillCoverage: `${Math.round(skillCoverage * 100)}%`,
      continuityRisk: `${Math.round(continuityRisk * 100)}%`
    });

    return metrics;
  }

  async getClusterMetrics(clusterId: string, hoursBack: number = 24): Promise<ClusterMetrics | null> {
    const cutoff = new Date(Date.now() - hoursBack * 60 * 60 * 1000);

    const metrics = await this.prisma.clusterMetrics.findFirst({
      where: {
        clusterId,
        calculatedAt: { gt: cutoff }
      },
      orderBy: { calculatedAt: 'desc' }
    });

    if (!metrics) {
      return null;
    }

    return {
      clusterId: metrics.clusterId,
      calculatedAt: metrics.calculatedAt,
      totalVisits: metrics.totalVisits,
      totalHours: metrics.totalHours,
      averageDistance: metrics.averageDistance,
      totalTravelTime: metrics.totalTravelTime,
      skillCoverage: metrics.skillCoverage,
      continuityRisk: metrics.continuityRisk,
      requiredSkills: metrics.requiredSkills
    };
  }

  // ✅ FIX 4: Add proper typing to private methods
  private calculateTotalHours(visits: Array<{ estimatedDuration: number | null }>): number {
    return visits.reduce((total, visit) => {
      return total + (visit.estimatedDuration || 60) / 60;
    }, 0);
  }

  private async calculateAverageDistance(
    visits: Array<{ latitude: number | null; longitude: number | null }>
  ): Promise<number> {
    if (visits.length < 2) return 0;

    let totalDistance = 0;
    let pairCount = 0;

    for (let i = 0; i < visits.length; i++) {
      const v1 = visits[i];
      if (!v1.latitude || !v1.longitude) continue;

      for (let j = i + 1; j < visits.length; j++) {
        const v2 = visits[j];
        if (!v2.latitude || !v2.longitude) continue;

        const distance = this.calculateHaversineDistance(
          v1.latitude, v1.longitude,
          v2.latitude, v2.longitude
        );
        totalDistance += distance;
        pairCount++;
      }
    }

    return pairCount > 0 ? totalDistance / pairCount : 0;
  }

  private async calculateTotalTravelTime(visits: Array<any>): Promise<number> {
    // Simplified calculation - in reality would use travel matrix
    return visits.length * 15; // Assume 15 minutes average travel per visit
  }

  private calculateSkillCoverage(
    visits: Array<{ requirements: string | null }>,
    carers: Array<{ skills: string[] }>
  ): number {
    if (visits.length === 0) return 1;

    const allRequiredSkills = new Set<string>();
    const carerSkills = new Set<string>();

    // Collect all required skills
    visits.forEach(visit => {
      if (visit.requirements) {
        const skills = this.extractSkills(visit.requirements);
        skills.forEach(skill => allRequiredSkills.add(skill));
      }
    });

    // Collect all carer skills
    carers.forEach(carer => {
      carer.skills.forEach(skill => carerSkills.add(skill.toLowerCase()));
    });

    if (allRequiredSkills.size === 0) return 1;

    // Check coverage
    let coveredSkills = 0;
    allRequiredSkills.forEach(skill => {
      if (carerSkills.has(skill.toLowerCase())) {
        coveredSkills++;
      }
    });

    return coveredSkills / allRequiredSkills.size;
  }

  private async calculateContinuityRisk(
    visits: Array<{ 
      assignments: Array<{ carerId: string }>;
      externalRequest?: { 
        matches?: Array<{ response: string; carerId: string }> 
      } 
    }>
  ): Promise<number> {
    if (visits.length === 0) return 0;

    let riskCount = 0;

    for (const visit of visits) {
      // Get matches from external request
      const matches = visit.externalRequest?.matches || [];
      const assignedCarerId = visit.assignments[0]?.carerId;

      const hasContinuity = matches.some(match => 
        match.response === 'ACCEPTED' && match.carerId === assignedCarerId
      );

      if (!hasContinuity && assignedCarerId) {
        riskCount++;
      }
    }

    return riskCount / visits.length;
  }

  private extractRequiredSkills(visits: Array<{ requirements: string | null }>): string[] {
    const skills = new Set<string>();
    
    visits.forEach(visit => {
      if (visit.requirements) {
        const visitSkills = this.extractSkills(visit.requirements);
        visitSkills.forEach(skill => skills.add(skill));
      }
    });

    return Array.from(skills);
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

  private calculateHaversineDistance(
    lat1: number, 
    lon1: number, 
    lat2: number, 
    lon2: number
  ): number {
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