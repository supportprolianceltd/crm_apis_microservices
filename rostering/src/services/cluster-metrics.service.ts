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
    const cluster = await this.prisma.cluster.findUnique({
      where: { id: clusterId },
      include: {
        requests: {
          include: {
            assignments: {
              include: { carer: true }
            },
            matches: true
          }
        },
        carers: true
      }
    });

    if (!cluster) {
      throw new Error(`Cluster not found: ${clusterId}`);
    }

    const visits = cluster.requests;
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

  private calculateTotalHours(visits: any[]): number {
    return visits.reduce((total, visit) => {
      return total + (visit.estimatedDuration || 60) / 60;
    }, 0);
  }

  private async calculateAverageDistance(visits: any[]): Promise<number> {
    if (visits.length < 2) return 0;

    let totalDistance = 0;
    let pairCount = 0;

    for (let i = 0; i < visits.length; i++) {
      for (let j = i + 1; j < visits.length; j++) {
        const distance = this.calculateHaversineDistance(
          visits[i].latitude, visits[i].longitude,
          visits[j].latitude, visits[j].longitude
        );
        totalDistance += distance;
        pairCount++;
      }
    }

    return pairCount > 0 ? totalDistance / pairCount : 0;
  }

  private async calculateTotalTravelTime(visits: any[]): Promise<number> {
    // Simplified calculation - in reality would use travel matrix
    return visits.length * 15; // Assume 15 minutes average travel per visit
  }

  private calculateSkillCoverage(visits: any[], carers: any[]): number {
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
      carer.skills.forEach((skill: string) => carerSkills.add(skill.toLowerCase()));
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

  private async calculateContinuityRisk(visits: any[]): Promise<number> {
    if (visits.length === 0) return 0;

    let riskCount = 0;

    for (const visit of visits) {
      const hasContinuity = visit.matches.some((match: any) => 
        match.response === 'ACCEPTED' && match.carerId === visit.assignments[0]?.carerId
      );

      if (!hasContinuity) {
        riskCount++;
      }
    }

    return riskCount / visits.length;
  }

  private extractRequiredSkills(visits: any[]): string[] {
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

  private calculateHaversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
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