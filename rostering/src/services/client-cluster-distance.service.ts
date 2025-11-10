import { PrismaClient } from '@prisma/client';
import { logger, logServiceError } from '../utils/logger';

export interface ClusterSuggestion {
  clusterId: string;
  clusterName: string;
  distanceKm: number;
  centroidCoordinates: {
    latitude: number;
    longitude: number;
  };
  score: number;
  reasoning: string[];
  availableCarers: number;
  timeCompatibility: number;
  skillMatch: number;
}

export interface ClientClusterSuggestionResult {
  clientId: string;
  clientName: string;
  clientPostcode: string;
  clientCoordinates: {
    latitude: number;
    longitude: number;
  };
  suggestions: ClusterSuggestion[];
  topSuggestion?: ClusterSuggestion;
}

export class ClientClusterDistanceService {
  constructor(private prisma: PrismaClient) {}

  /**
   * Calculate distance between two coordinates using Haversine formula
   */
  private calculateDistance(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number
  ): number {
    const R = 6371; // Earth's radius in kilometers
    const dLat = this.toRadians(lat2 - lat1);
    const dLon = this.toRadians(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRadians(lat1)) *
        Math.cos(this.toRadians(lat2)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  private toRadians(degrees: number): number {
    return degrees * (Math.PI / 180);
  }

  /**
   * Get or calculate distance between client postcode and cluster
   */
  async getClientClusterDistance(
    clientPostcode: string,
    clusterId: string
  ): Promise<number> {
    try {
      // Check cache first
      const cached = await (this.prisma as any).clientClusterDistance.findUnique({
        where: {
          clientPostcode_clusterId: {
            clientPostcode: clientPostcode.toUpperCase(),
            clusterId
          }
        }
      });

      if (cached && cached.expiresAt > new Date()) {
        return cached.distanceKm;
      }

      // Calculate new distance
      const cluster = await this.prisma.cluster.findUnique({
        where: { id: clusterId },
        select: { latitude: true, longitude: true }
      });

      if (!cluster?.latitude || !cluster?.longitude) {
        throw new Error(`Cluster ${clusterId} has no coordinates`);
      }

      // Get client coordinates (would need geocoding service)
      const clientCoordinates = await this.geocodePostcode(clientPostcode);
      const distance = this.calculateDistance(
        clientCoordinates.latitude,
        clientCoordinates.longitude,
        cluster.latitude,
        cluster.longitude
      );

      // Cache the result
      await (this.prisma as any).clientClusterDistance.upsert({
        where: {
          clientPostcode_clusterId: {
            clientPostcode: clientPostcode.toUpperCase(),
            clusterId
          }
        },
        update: {
          distanceKm: distance,
          lastUpdated: new Date(),
          expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) // 7 days
        },
        create: {
          clientPostcode: clientPostcode.toUpperCase(),
          clusterId,
          distanceKm: distance,
          lastUpdated: new Date(),
          expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
        }
      });

      return distance;
    } catch (error) {
      logServiceError('ClientClusterDistance', 'getClientClusterDistance', error, {
        clientPostcode,
        clusterId
      });
      throw error;
    }
  }

  /**
   * Get intelligent cluster suggestions for a client
   */
  async getClusterSuggestions(
    clientId: string,
    tenantId: string,
    options: {
      maxSuggestions?: number;
      maxDistanceKm?: number;
      includeInactiveClusters?: boolean;
    } = {}
  ): Promise<ClientClusterSuggestionResult> {
    try {
      const {
        maxSuggestions = 3,
        maxDistanceKm = 50,
        includeInactiveClusters = false
      } = options;

      // Get client details
      const client = await this.prisma.externalRequest.findFirst({
        where: {
          id: clientId,
          tenantId
        },
        select: {
          id: true,
          subject: true,
          postcode: true,
          latitude: true,
          longitude: true,
          requirements: true,
          requiredSkills: true,
          scheduledStartTime: true,
          scheduledEndTime: true
        }
      });

      if (!client) {
        throw new Error(`Client ${clientId} not found`);
      }

      if (!client.postcode) {
        throw new Error(`Client ${clientId} has no postcode`);
      }

      // Get client coordinates
      const clientCoordinates = client.latitude && client.longitude
        ? { latitude: client.latitude, longitude: client.longitude }
        : await this.geocodePostcode(client.postcode);

      // Get all active clusters for tenant
      const clusters = await this.prisma.cluster.findMany({
        where: {
          tenantId,
          ...(includeInactiveClusters ? {} : {
            activeRequestCount: { gt: 0 }
          })
        },
        select: {
          id: true,
          name: true,
          latitude: true,
          longitude: true,
          activeCarerCount: true,
          totalCarerCount: true,
          radiusMeters: true
        }
      });

      // Calculate distances and scores for each cluster
      const suggestions: ClusterSuggestion[] = [];

      for (const cluster of clusters) {
        if (!cluster.latitude || !cluster.longitude) continue;

        const distance = this.calculateDistance(
          clientCoordinates.latitude,
          clientCoordinates.longitude,
          cluster.latitude,
          cluster.longitude
        );

        // Skip clusters beyond max distance
        if (distance > maxDistanceKm) continue;

        // Calculate score based on multiple factors
        const score = await this.calculateClusterScore(
          client,
          cluster,
          distance,
          tenantId
        );

        suggestions.push({
          clusterId: cluster.id,
          clusterName: cluster.name,
          distanceKm: distance,
          centroidCoordinates: {
            latitude: cluster.latitude,
            longitude: cluster.longitude
          },
          score: score.total,
          reasoning: score.reasoning,
          availableCarers: cluster.activeCarerCount,
          timeCompatibility: score.timeCompatibility,
          skillMatch: score.skillMatch
        });
      }

      // Sort by score (descending)
      suggestions.sort((a, b) => b.score - a.score);

      // Take top suggestions
      const topSuggestions = suggestions.slice(0, maxSuggestions);

      return {
        clientId: client.id,
        clientName: client.subject,
        clientPostcode: client.postcode,
        clientCoordinates,
        suggestions: topSuggestions,
        topSuggestion: topSuggestions[0]
      };
    } catch (error) {
      logServiceError('ClientClusterDistance', 'getClusterSuggestions', error, {
        clientId,
        tenantId,
        options
      });
      throw error;
    }
  }

  /**
   * Calculate comprehensive score for cluster suitability
   */
  private async calculateClusterScore(
    client: any,
    cluster: any,
    distance: number,
    tenantId: string
  ): Promise<{
    total: number;
    distance: number;
    skillMatch: number;
    timeCompatibility: number;
    carerAvailability: number;
    reasoning: string[];
  }> {
    const reasoning: string[] = [];

    // Distance score (0-50 points)
    let distanceScore = 0;
    if (distance <= 2) {
      distanceScore = 50;
      reasoning.push('Within 2km - excellent proximity');
    } else if (distance <= 5) {
      distanceScore = 30;
      reasoning.push('Within 5km - good proximity');
    } else if (distance <= 10) {
      distanceScore = 10;
      reasoning.push('Within 10km - acceptable distance');
    } else {
      distanceScore = 5;
      reasoning.push('Over 10km - consider alternatives');
    }

    // Skill match score (0-30 points)
    const skillMatch = await this.calculateSkillMatchScore(client, cluster, tenantId);
    if (skillMatch >= 0.8) {
      reasoning.push('Excellent skill coverage available');
    } else if (skillMatch >= 0.6) {
      reasoning.push('Good skill coverage available');
    } else if (skillMatch >= 0.4) {
      reasoning.push('Limited skill coverage - may need additional training');
    } else {
      reasoning.push('Poor skill coverage - not recommended');
    }

    // Time compatibility score (0-20 points)
    const timeCompatibility = this.calculateTimeCompatibilityScore(client, cluster);
    if (timeCompatibility >= 0.8) {
      reasoning.push('Time windows align well');
    } else if (timeCompatibility >= 0.6) {
      reasoning.push('Time windows partially compatible');
    } else {
      reasoning.push('Time windows may conflict');
    }

    // Carer availability score (0-10 points)
    const carerAvailability = Math.min(cluster.activeCarerCount / 5, 1) * 10;
    if (cluster.activeCarerCount >= 3) {
      reasoning.push('Good carer availability');
    } else if (cluster.activeCarerCount >= 1) {
      reasoning.push('Limited carer availability');
    } else {
      reasoning.push('No active carers - urgent attention needed');
    }

    const total = distanceScore + (skillMatch * 30) + (timeCompatibility * 20) + carerAvailability;

    return {
      total,
      distance: distanceScore,
      skillMatch: skillMatch * 30,
      timeCompatibility: timeCompatibility * 20,
      carerAvailability,
      reasoning
    };
  }

  /**
   * Calculate skill match score (0-1)
   */
  private async calculateSkillMatchScore(
    client: any,
    cluster: any,
    tenantId: string
  ): Promise<number> {
    if (!client.requiredSkills || client.requiredSkills.length === 0) {
      return 1; // No specific skills required
    }

    // Get carers in cluster
    const carers = await this.prisma.clusterAssignment.findMany({
      where: { clusterId: cluster.id },
      include: {
        cluster: {
          include: {
            carers: {
              where: { isActive: true },
              select: { skills: true }
            }
          }
        }
      }
    });

    if (carers.length === 0) return 0;

    let totalMatchScore = 0;
    for (const carer of carers) {
      // This would need to be implemented based on your carer data structure
      // For now, return a placeholder
      totalMatchScore += 0.8; // Placeholder
    }

    return totalMatchScore / carers.length;
  }

  /**
   * Calculate time compatibility score (0-1)
   */
  private calculateTimeCompatibilityScore(client: any, cluster: any): number {
    // Placeholder implementation - would need cluster operating hours
    return 0.8;
  }

  /**
   * Geocode postcode to coordinates
   */
  private async geocodePostcode(postcode: string): Promise<{ latitude: number; longitude: number }> {
    // This would integrate with your geocoding service
    // For now, return placeholder coordinates
    return {
      latitude: 51.5074, // London coordinates as placeholder
      longitude: -0.1278
    };
  }

  /**
   * Batch process multiple clients
   */
  async getBatchClusterSuggestions(
    clientIds: string[],
    tenantId: string,
    options: {
      maxSuggestions?: number;
      maxDistanceKm?: number;
      includeInactiveClusters?: boolean;
    } = {}
  ): Promise<ClientClusterSuggestionResult[]> {
    const results: ClientClusterSuggestionResult[] = [];

    for (const clientId of clientIds) {
      try {
        const result = await this.getClusterSuggestions(clientId, tenantId, options);
        results.push(result);
      } catch (error) {
        logger.error(`Failed to get suggestions for client ${clientId}:`, error);
        // Continue with other clients
      }
    }

    return results;
  }

  /**
   * Clean up expired cache entries
   */
  async cleanupExpiredCache(): Promise<number> {
    try {
      const result = await (this.prisma as any).clientClusterDistance.deleteMany({
        where: {
          expiresAt: { lt: new Date() }
        }
      });

      logger.info(`Cleaned up ${result.count} expired client-cluster distance cache entries`);
      return result.count;
    } catch (error) {
      logServiceError('ClientClusterDistance', 'cleanupExpiredCache', error);
      return 0;
    }
  }
}