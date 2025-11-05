import { PrismaClient } from '@prisma/client';
import axios from 'axios';
import { logger } from '../utils/logger';

export interface TravelResult {
  distanceMeters: number;
  durationSeconds: number;
  trafficDurationSeconds?: number;
  fromPostcode: string;
  toPostcode: string;
}

export class TravelService {
  private prisma: PrismaClient;
  private googleMapsApiKey: string;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
    this.googleMapsApiKey = process.env.GOOGLE_MAPS_API_KEY || 'AIzaSyBuhePcYzdwa59sqBUJrE1ouknCp9mKk8k';
  }

  /**
   * Get travel time between two postcodes
   */
  async getTravelTime(
    fromPostcode: string,
    toPostcode: string,
    mode: string = 'driving'
  ): Promise<TravelResult> {
    try {
      // Check cache first
      const cached = await this.getCachedTravelTime(fromPostcode, toPostcode, mode);
        if (cached && this.isCacheValid(cached.calculatedAt)) {
        logger.debug(`Using cached travel time for ${fromPostcode} -> ${toPostcode}`);
        return {
            distanceMeters: cached.distanceMeters ?? 0,       // ✅ use ?? instead of ||
            durationSeconds: cached.durationSeconds ?? 0,     // ✅ use ?? instead of ||
            trafficDurationSeconds: cached.trafficDurationSeconds ?? undefined, // ✅ ensure consistent type
            fromPostcode,
            toPostcode
        };
        }


      // Get from Google Maps API
      const apiResult = await this.getGoogleMapsTravelTime(fromPostcode, toPostcode, mode);
      
      // Cache the result
      await this.cacheTravelTime(fromPostcode, toPostcode, mode, apiResult);

      return {
        ...apiResult,
        fromPostcode,
        toPostcode
      };

    } catch (error) {
      logger.error('Failed to get travel time:', error);
      // Fallback to straight-line distance
      return this.getFallbackTravelTime(fromPostcode, toPostcode);
    }
  }

  /**
   * Get cached travel time
   */
  private async getCachedTravelTime(
    fromPostcode: string,
    toPostcode: string,
    mode: string
  ) {
    return await this.prisma.travelMatrixCache.findUnique({
      where: {
        fromPostcode_toPostcode_mode: {
          fromPostcode,
          toPostcode,
          mode
        }
      }
    });
  }

  /**
   * Check if cache is still valid (1 hour)
   */
  private isCacheValid(calculatedAt: Date): boolean {
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    return calculatedAt > oneHourAgo;
  }

  /**
   * Get travel time from Google Maps API
   */
  private async getGoogleMapsTravelTime(
    fromPostcode: string,
    toPostcode: string,
    mode: string
  ): Promise<{ distanceMeters: number; durationSeconds: number; trafficDurationSeconds?: number }> {
    try {
      const response = await axios.get('https://maps.googleapis.com/maps/api/distancematrix/json', {
        params: {
          origins: fromPostcode,
          destinations: toPostcode,
          mode,
          key: this.googleMapsApiKey,
          units: 'metric'
        },
        timeout: 10000
      });

      if (response.data.status !== 'OK') {
        throw new Error(`Google Maps API error: ${response.data.status}`);
      }

      const element = response.data.rows[0]?.elements[0];
      if (!element || element.status !== 'OK') {
        throw new Error(`No route found for ${fromPostcode} -> ${toPostcode}`);
      }

        return {
        distanceMeters: element.distance?.value ?? 0,
        durationSeconds: element.duration?.value ?? 0,
        trafficDurationSeconds: element.duration_in_traffic?.value ?? undefined
        };

    } catch (error) {
      logger.error('Google Maps API failed:', error);
      throw error;
    }
  }

  /**
   * Cache travel time result
   */
  private async cacheTravelTime(
    fromPostcode: string,
    toPostcode: string,
    mode: string,
    result: { distanceMeters: number; durationSeconds: number; trafficDurationSeconds?: number }
  ) {
    try {
        await this.prisma.travelMatrixCache.upsert({
        where: {
            fromPostcode_toPostcode_mode: {
            fromPostcode,
            toPostcode,
            mode
            }
        },
        update: {
            distanceMeters: result.distanceMeters ?? 0,
            durationSeconds: result.durationSeconds ?? 0,
            trafficDurationSeconds: result.trafficDurationSeconds ?? null,
            calculatedAt: new Date()
        },
        create: {
            fromPostcode,
            toPostcode,
            mode,
            distanceMeters: result.distanceMeters ?? 0,
            durationSeconds: result.durationSeconds ?? 0,
            trafficDurationSeconds: result.trafficDurationSeconds ?? null
        }
        });

    } catch (error) {
      logger.error('Failed to cache travel time:', error);
    }
  }

  /**
   * Fallback to straight-line distance calculation
   */
  private async getFallbackTravelTime(
    fromPostcode: string,
    toPostcode: string
  ): Promise<TravelResult> {
    // Simple fallback: assume 1.4x straight-line distance at 30 km/h
    const straightLineDistance = await this.calculateStraightLineDistance(fromPostcode, toPostcode);
    const travelDistance = straightLineDistance * 1.4; // Account for road network
    const durationSeconds = (travelDistance / 30) * 3600; // 30 km/h average speed

    return {
      distanceMeters: Math.round(travelDistance * 1000), // km to meters
      durationSeconds: Math.round(durationSeconds),
      fromPostcode,
      toPostcode
    };
  }

  /**
   * Calculate straight-line distance between postcodes
   */
  private async calculateStraightLineDistance(fromPostcode: string, toPostcode: string): Promise<number> {
    // This would need proper postcode coordinate lookup
    // For now, return a reasonable default
    return 5; // 5 km default
  }

  /**
   * Batch get travel times for multiple pairs
   */
  async getBatchTravelTimes(
    pairs: Array<{ fromPostcode: string; toPostcode: string }>,
    mode: string = 'driving'
  ): Promise<TravelResult[]> {
    const results: TravelResult[] = [];

    for (const pair of pairs) {
      try {
        const result = await this.getTravelTime(pair.fromPostcode, pair.toPostcode, mode);
        results.push(result);
      } catch (error) {
        logger.error(`Failed to get travel time for ${pair.fromPostcode} -> ${pair.toPostcode}:`, error);
        // Add fallback result
        results.push(await this.getFallbackTravelTime(pair.fromPostcode, pair.toPostcode));
      }
    }

    return results;
  }
}