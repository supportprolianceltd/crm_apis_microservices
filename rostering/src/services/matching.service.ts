import { PrismaClient } from '@prisma/client';
import { GeocodingService } from './geocoding.service';
import { logger, logServiceError } from '../utils/logger';
import { 
  Carer, 
  ExternalRequest, 
  MatchingCriteria, 
  MatchResult, 
  RequestUrgency,
  MatchStatus 
} from '../types';

export class MatchingService {
  private prisma: PrismaClient;
  private geocodingService: GeocodingService;
  private carerService: any;

  constructor(prisma: PrismaClient, geocodingService: GeocodingService) {
    this.prisma = prisma;
    this.geocodingService = geocodingService;
    // instantiate CarerService for fetching external carer details
    // require here to avoid circular deps at module load time
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { CarerService } = require('./carer.service');
    this.carerService = new CarerService();
  }

  /**
   * Find matching carers for a request
   */
  async findMatches(
    requestId: string, 
    criteria: MatchingCriteria = {}
  ): Promise<MatchResult[]> {
    try {
      // Get the request with location data
      const request = await this.prisma.externalRequest.findUnique({
        where: { id: requestId },
        include: { matches: true }
      });

      if (!request) {
        throw new Error(`Request not found: ${requestId}`);
      }

      // Geocode request location if not already done
      if (!request.latitude || !request.longitude) {
        const geocoded = await this.geocodingService.geocodeAddress(
          request.address, 
          request.postcode
        );

        if (geocoded) {
          await this.prisma.externalRequest.update({
            where: { id: requestId },
            data: {
              latitude: geocoded.latitude,
              longitude: geocoded.longitude
            }
          });
          request.latitude = geocoded.latitude;
          request.longitude = geocoded.longitude;
        } else {
          logger.warn(`Failed to geocode request location: ${request.address}`);
          return [];
        }
      }

      // Find potential carers
      const potentialCarers = await this.findPotentialCarers(request, criteria);

      // Calculate matches
      const matches: MatchResult[] = [];
      for (const carer of potentialCarers) {
        const matchResult = await this.calculateMatch(request, carer, criteria);
        if (matchResult.matchScore > 0) {
          matches.push(matchResult);
        }
      }

      // Sort by match score (highest first)
      matches.sort((a, b) => b.matchScore - a.matchScore);

      logger.info(`Found ${matches.length} potential matches for request: ${requestId}`);
      return matches;

    } catch (error) {
      logServiceError('Matching', 'findMatches', error, { requestId, criteria });
      return [];
    }
  }

  /**
   * Find potential carers based on basic criteria
   */
  private async findPotentialCarers(
    request: any, // Use any temporarily to avoid enum conflicts 
    criteria: MatchingCriteria
  ): Promise<any[]> {
    try {
      const maxDistance = criteria.maxDistance || 
                         parseInt(process.env.DEFAULT_MATCHING_RADIUS || '5000');

      logger.debug(`🔍 Searching for carers for tenant: ${request.tenantId}`);

      // We no longer rely on a local `carer` table. Instead, find candidate carer IDs
      // from `cluster_assignments` and then enrich each carer via the external CarerService.
      let candidateCarerIds: string[] = [];

      if (request.latitude && request.longitude) {
        logger.debug(`🌍 Request has coordinates: ${request.latitude}, ${request.longitude}`);

        try {
          // Find assignments whose cluster center is within maxDistance of the request
          const rows = await this.prisma.$queryRaw<any[]>`
            SELECT DISTINCT ca."carerId", ca."clusterId", c.latitude as cluster_lat, c.longitude as cluster_lng
            FROM cluster_assignments ca
            JOIN clusters c ON c.id = ca."clusterId"
            WHERE ca."tenantId" = ${request.tenantId}
              AND c."regionCenter" IS NOT NULL
              AND ST_DWithin(c."regionCenter"::geography, ST_SetSRID(ST_MakePoint(${request.longitude}, ${request.latitude}), 4326)::geography, ${maxDistance})
            LIMIT 500
          `;

          candidateCarerIds = rows.map(r => r.carerId).filter((v, i, a) => a.indexOf(v) === i);
          logger.debug(`🔎 Found ${candidateCarerIds.length} candidate carers from cluster_assignments`);
        } catch (sqlError) {
          logger.error('❌ cluster_assignments spatial query failed:', sqlError);
          logger.debug('🔄 Falling back to retrieving recent assignments...');
          const rows = await (this.prisma as any).clusterAssignment.findMany({ where: { tenantId: request.tenantId }, take: 500, select: { carerId: true } });
          candidateCarerIds = rows.map((r: any) => r.carerId);
        }
      } else {
        // No coords: get recent assignments for tenant
        const rows = await (this.prisma as any).clusterAssignment.findMany({ where: { tenantId: request.tenantId }, take: 500, select: { carerId: true } });
        candidateCarerIds = rows.map((r: any) => r.carerId);
      }

      if (candidateCarerIds.length === 0) {
        logger.warn(`⚠️ No candidate carer assignments found for tenant ${request.tenantId}`);
        return [];
      }

      // Limit the number of external lookups to a reasonable amount
      const limitedIds = candidateCarerIds.slice(0, 200);

      // Fetch carer details from external service in parallel
      const carersFromExternal = await Promise.all(limitedIds.map(async (carerId) => {
        try {
          const carer = await this.carerService.getCarerById(undefined, carerId);
          return carer ? { ...carer } : null;
        } catch (err) {
          logger.error(`Failed to fetch carer ${carerId} from auth service:`, err);
          return null;
        }
      }));

      // Map external carer objects into the shape expected by matching logic
      const carers: any[] = carersFromExternal.filter(Boolean).map((c: any) => ({
        id: c.id?.toString() ?? c.user_id ?? c.auth_user_id ?? null,
        latitude: c.latitude ?? c.location?.lat ?? c.profile?.location?.lat ?? null,
        longitude: c.longitude ?? c.location?.lng ?? c.profile?.location?.lng ?? null,
        skills: c.profile?.skill_details ?? c.profile?.professional_qualifications ?? c.skills ?? [],
        languages: c.profile?.languages ?? c.languages ?? [],
        maxTravelDistance: c.profile?.maxTravelDistance ?? c.maxTravelDistance ?? c.profile?.max_travel_distance ?? 10000,
        isActive: (c.status ? c.status === 'active' : true),
        experience: c.profile?.experience_years ?? c.experience ?? 0,
        employmentDetails: c.profile?.employment_details ?? []
      })).filter(carer => carer.id !== null);

      logger.debug(`🎯 Final result: Found ${carers.length} potential carers for request: ${request.id}`);
      return carers;

    } catch (error) {
      logger.error(`💥 findPotentialCarers error:`, error);
      logServiceError('Matching', 'findPotentialCarers', error, { requestId: request.id });
      return [];
    }
  }

  /**
   * Check if carer is employed during the request time
   */
  private checkEmploymentStatus(carer: any, requestTime: Date | null): { isEmployed: boolean; reason: string } {
    if (!requestTime) {
      return { isEmployed: true, reason: '' };
    }

    const employmentDetails = carer.employmentDetails || [];
    if (employmentDetails.length === 0) {
      return { isEmployed: true, reason: '' }; // Assume employed if no details
    }

    for (const employment of employmentDetails) {
      const startDate = employment.employment_start_date ? new Date(employment.employment_start_date) : null;
      const endDate = employment.employment_end_date ? new Date(employment.employment_end_date) : null;

      // Check if request time is within employment period
      const isAfterStart = !startDate || requestTime >= startDate;
      const isBeforeEnd = !endDate || requestTime <= endDate;

      if (isAfterStart && isBeforeEnd) {
        return { isEmployed: true, reason: '' };
      }
    }

    return {
      isEmployed: false,
      reason: `Not employed during request time (${requestTime.toISOString().split('T')[0]})`
    };
  }

  /**
   * Calculate distance between two points in meters using Haversine formula
   */
  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371000; // Earth's radius in meters
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  }

  /**
   * Calculate match score between request and carer
   */
  private async calculateMatch(
    request: any, // Use any temporarily to avoid enum conflicts
    carer: any, // Use any temporarily to avoid type conflicts
    criteria: MatchingCriteria
  ): Promise<MatchResult> {
    const reasoning: string[] = [];
    let score = 0;

    // Calculate distance
    let distance = 0;
    if (request.latitude && request.longitude && carer.latitude && carer.longitude) {
      distance = await this.geocodingService.calculateDistance(
        request.latitude, request.longitude,
        carer.latitude, carer.longitude
      );
    }

    // Distance scoring (closer = higher score)
    const maxDistance = carer.maxTravelDistance || 10000;
    if (distance <= maxDistance) {
      const distanceScore = Math.max(0, 100 - (distance / maxDistance) * 50);
      score += distanceScore * 0.4; // 40% weight
      reasoning.push(`Distance: ${Math.round(distance)}m (${Math.round(distanceScore)} pts)`);
    } else {
      reasoning.push(`Distance: ${Math.round(distance)}m (exceeds max travel distance)`);
      return { carer, distance, matchScore: 0, reasoning };
    }

    // Check employment status
    const employmentCheck = this.checkEmploymentStatus(carer, request.scheduledStartTime);
    if (!employmentCheck.isEmployed) {
      reasoning.push(employmentCheck.reason);
      return { carer, distance, matchScore: 0, reasoning };
    }

    // Skills matching
    if (criteria.requiredSkills && criteria.requiredSkills.length > 0) {
      const matchedSkills = criteria.requiredSkills.filter(skill =>
        carer.skills.some((carerSkill: any) =>
          typeof carerSkill === 'string'
            ? carerSkill.toLowerCase().includes(skill.toLowerCase()) || skill.toLowerCase().includes(carerSkill.toLowerCase())
            : carerSkill.skill_name?.toLowerCase().includes(skill.toLowerCase()) || skill.toLowerCase().includes(carerSkill.skill_name?.toLowerCase())
        )
      );
      const skillsScore = (matchedSkills.length / criteria.requiredSkills.length) * 100;
      score += skillsScore * 0.3; // 30% weight
      reasoning.push(`Skills: ${matchedSkills.length}/${criteria.requiredSkills.length} matched (${Math.round(skillsScore)} pts)`);
    }

    // Language matching
    if (criteria.preferredLanguages && criteria.preferredLanguages.length > 0) {
      const matchedLanguages = criteria.preferredLanguages.filter(lang => 
        carer.languages.includes(lang)
      );
      if (matchedLanguages.length > 0) {
        const langScore = Math.min(100, (matchedLanguages.length / criteria.preferredLanguages.length) * 100);
        score += langScore * 0.1; // 10% weight
        reasoning.push(`Languages: ${matchedLanguages.join(', ')} (${Math.round(langScore)} pts)`);
      }
    }

    // Urgency bonus
    if (request.urgency === RequestUrgency.URGENT) {
      score += 20;
      reasoning.push('Urgent request bonus (+20 pts)');
    } else if (request.urgency === RequestUrgency.HIGH) {
      score += 10;
      reasoning.push('High priority bonus (+10 pts)');
    }

    // Experience bonus
    if (carer.experience && carer.experience > 2) {
      const expBonus = Math.min(20, carer.experience * 2);
      score += expBonus * 0.1;
      reasoning.push(`Experience: ${carer.experience} years (+${Math.round(expBonus * 0.1)} pts)`);
    }

    // Availability check (simplified - could be more sophisticated)
    if (criteria.availabilityRequired && carer.availabilityHours) {
      // This would need more complex logic based on the actual availability structure
      score += 10;
      reasoning.push('Availability confirmed (+10 pts)');
    }

    // Ensure score is between 0 and 100
    score = Math.max(0, Math.min(100, score));

    return {
      carer,
      distance,
      matchScore: Math.round(score),
      reasoning
    };
  }

  /**
   * Create matches in the database
   */
  async createMatches(requestId: string, matches: MatchResult[]): Promise<string[]> {
    try {
      const request = await this.prisma.externalRequest.findUnique({
        where: { id: requestId }
      });

      if (!request) {
        throw new Error(`Request not found: ${requestId}`);
      }

      const matchIds: string[] = [];

      for (const match of matches) {
        // Check if match already exists
        const existing = await this.prisma.requestCarerMatch.findUnique({
          where: {
            requestId_carerId: {
              requestId,
              carerId: match.carer.id
            }
          }
        });

        if (!existing) {
          const created = await this.prisma.requestCarerMatch.create({
            data: {
              tenantId: request.tenantId,
              requestId,
              carerId: match.carer.id,
              distance: match.distance,
              matchScore: match.matchScore,
              status: MatchStatus.PENDING
            }
          });
          matchIds.push(created.id);
        }
      }

      // Update request status
      await this.prisma.externalRequest.update({
        where: { id: requestId },
        data: { 
          status: 'MATCHED',
          processedAt: new Date()
        }
      });

      logger.info(`Created ${matchIds.length} matches for request: ${requestId}`);
      return matchIds;

    } catch (error) {
      logServiceError('Matching', 'createMatches', error, { requestId });
      return [];
    }
  }

  /**
   * Auto-match requests with carers
   */
  async autoMatchRequest(requestId: string): Promise<boolean> {
    try {
      // Get the request to extract requiredSkills
      const request = await this.prisma.externalRequest.findUnique({
        where: { id: requestId },
        select: { requiredSkills: true }
      });

      const criteria: MatchingCriteria = {
        maxDistance: parseInt(process.env.DEFAULT_MATCHING_RADIUS || '5000'),
        requiredSkills: request?.requiredSkills || [],
        availabilityRequired: false
      };

      const matches = await this.findMatches(requestId, criteria);
      
      if (matches.length === 0) {
        logger.info(`No matches found for request: ${requestId}`);
        return false;
      }

      // Take only the top 5 matches to avoid overwhelming carers
      const topMatches = matches.slice(0, 5);
      const matchIds = await this.createMatches(requestId, topMatches);

      return matchIds.length > 0;

    } catch (error) {
      logServiceError('Matching', 'autoMatchRequest', error, { requestId });
      return false;
    }
  }

  /**
   * Get match statistics
   */
  async getMatchStatistics(tenantId: string, dateFrom?: Date, dateTo?: Date): Promise<any> {
    try {
      const dateFilter = {
        ...(dateFrom ? { gte: dateFrom } : {}),
        ...(dateTo ? { lte: dateTo } : {})
      };

      const stats = await this.prisma.requestCarerMatch.groupBy({
        by: ['status'],
        where: {
          tenantId,
          ...(dateFrom || dateTo ? { createdAt: dateFilter } : {})
        },
        _count: {
          id: true
        },
        _avg: {
          matchScore: true,
          distance: true
        }
      });

      const totalRequests = await this.prisma.externalRequest.count({
        where: {
          tenantId,
          ...(dateFrom || dateTo ? { createdAt: dateFilter } : {})
        }
      });

      const matchedRequests = await this.prisma.externalRequest.count({
        where: {
          tenantId,
          status: 'MATCHED',
          ...(dateFrom || dateTo ? { createdAt: dateFilter } : {})
        }
      });

      return {
        totalRequests,
        matchedRequests,
        matchRate: totalRequests > 0 ? (matchedRequests / totalRequests) * 100 : 0,
        matchesByStatus: stats.reduce((acc, stat) => {
          acc[stat.status] = {
            count: stat._count.id,
            avgScore: stat._avg.matchScore,
            avgDistance: stat._avg.distance
          };
          return acc;
        }, {} as any)
      };

    } catch (error) {
      logServiceError('Matching', 'getMatchStatistics', error, { tenantId });
      return {
        totalRequests: 0,
        matchedRequests: 0,
        matchRate: 0,
        matchesByStatus: {}
      };
    }
  }
}

export default MatchingService;