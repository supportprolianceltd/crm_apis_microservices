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

  constructor(prisma: PrismaClient, geocodingService: GeocodingService) {
    this.prisma = prisma;
    this.geocodingService = geocodingService;
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

      // First, check if we have any carers at all for this tenant
      const totalCarers = await this.prisma.carer.count({
        where: { tenantId: request.tenantId }
      });
      logger.debug(`📊 Total carers for tenant ${request.tenantId}: ${totalCarers}`);

      if (totalCarers === 0) {
        logger.warn(`⚠️ No carers found for tenant ${request.tenantId}`);
        return [];
      }

      // Check active carers
      const activeCarers = await this.prisma.carer.count({
        where: { 
          tenantId: request.tenantId,
          isActive: true
        }
      });
      logger.debug(`✅ Active carers for tenant ${request.tenantId}: ${activeCarers}`);

      if (activeCarers === 0) {
        logger.warn(`⚠️ No active carers found for tenant ${request.tenantId}`);
        return [];
      }

      let carers: any[] = [];

      // If we have coordinates, try PostGIS distance filtering
      if (request.latitude && request.longitude) {
        logger.debug(`🌍 Request has coordinates: ${request.latitude}, ${request.longitude}`);
        
        // Check for carers with location data
        const carersWithLocation = await this.prisma.carer.count({
          where: { 
            tenantId: request.tenantId,
            isActive: true,
            latitude: { not: null },
            longitude: { not: null }
          }
        });
        logger.debug(`📍 Carers with location data: ${carersWithLocation}`);

        if (carersWithLocation > 0) {
          try {
            logger.debug(`🗺️ Attempting PostGIS distance query within ${maxDistance}m...`);
            
            // Use PostGIS with geography columns as per schema
            const sqlQuery = `
              SELECT c.*,
                     ST_Distance(c.location, ST_GeogFromText($2)) as distance_meters
              FROM carers c
              WHERE c."tenantId" = $1
                AND c."isActive" = true
                AND c.location IS NOT NULL
                AND ST_DWithin(c.location, ST_GeogFromText($2), $3)
              ORDER BY ST_Distance(c.location, ST_GeogFromText($2))
              LIMIT 50
            `;

            const pointWKT = `POINT(${request.longitude} ${request.latitude})`;
            const params = [request.tenantId, pointWKT, maxDistance];

            logger.debug(`🔧 Executing PostGIS query with params: ${JSON.stringify(params)}`);

            carers = await this.prisma.$queryRawUnsafe(sqlQuery, ...params);
            logger.debug(`✅ PostGIS query found ${carers.length} carers within ${maxDistance}m`);

          } catch (sqlError) {
            logger.error(`❌ PostGIS query failed:`, sqlError);
            logger.debug(`🔄 Falling back to coordinate-based distance calculation...`);
            
            // Fallback: Get all carers with coordinates and calculate distance in code
            const allCarersWithCoords = await this.prisma.carer.findMany({
              where: {
                tenantId: request.tenantId,
                isActive: true,
                latitude: { not: null },
                longitude: { not: null }
              }
            });

            // Calculate distances manually and filter
            carers = allCarersWithCoords.filter(carer => {
              if (!carer.latitude || !carer.longitude) return false;
              
              const distance = this.calculateDistance(
                request.latitude, request.longitude,
                carer.latitude, carer.longitude
              );
              
              // Add distance to carer object for sorting
              (carer as any).distance_meters = distance;
              
              return distance <= maxDistance;
            }).sort((a, b) => (a as any).distance_meters - (b as any).distance_meters);

            logger.debug(`📏 Manual distance calculation found ${carers.length} carers within ${maxDistance}m`);
          }
        } else {
          logger.warn(`⚠️ No carers have location data for tenant ${request.tenantId}`);
          // Fall back to all active carers
          carers = await this.prisma.carer.findMany({
            where: {
              tenantId: request.tenantId,
              isActive: true
            },
            take: 50
          });
          logger.debug(`📋 Retrieved ${carers.length} active carers (no location filtering)`);
        }
      } else {
        logger.debug(`📮 No coordinates available, getting all active carers`);
        // No coordinates - just get all active carers
        carers = await this.prisma.carer.findMany({
          where: {
            tenantId: request.tenantId,
            isActive: true,
            ...(request.postcode ? { postcode: request.postcode } : {})
          },
          take: 50
        });
        logger.debug(`📋 Retrieved ${carers.length} active carers (postcode: ${request.postcode || 'none'})`);
      }

      logger.debug(`🎯 Final result: Found ${carers.length} potential carers for request: ${request.id}`);
      return carers;

    } catch (error) {
      logger.error(`💥 findPotentialCarers error:`, error);
      logServiceError('Matching', 'findPotentialCarers', error, { requestId: request.id });
      return [];
    }
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

    // Skills matching
    if (criteria.requiredSkills && criteria.requiredSkills.length > 0) {
      const matchedSkills = criteria.requiredSkills.filter(skill => 
        carer.skills.includes(skill)
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
      const criteria: MatchingCriteria = {
        maxDistance: parseInt(process.env.DEFAULT_MATCHING_RADIUS || '5000'),
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