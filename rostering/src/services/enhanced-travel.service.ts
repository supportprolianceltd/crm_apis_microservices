import { PrismaClient } from '@prisma/client';
import axios from 'axios';
import { logger } from '../utils/logger';
import {
  TravelCalculationRequest,
  TravelCalculationResponse,
  LocationInput,
  LocationData,
  PrecisionLevel,
  GoogleDistanceMatrixResponse,
  CachedTravelData,
  WarningData,
  CoordinatesData
} from '../types/travel-matrix.types';

export class EnhancedTravelService {
  private prisma: PrismaClient;
  private googleMapsApiKey: string;
  private readonly ADDRESS_CACHE_TTL_HOURS = 1;
  private readonly POSTCODE_CACHE_TTL_HOURS = 24;

// In enhanced-travel.service.ts - update the constructor
constructor(prisma: PrismaClient) {
  this.prisma = prisma;
  this.googleMapsApiKey = process.env.GOOGLE_MAPS_API_KEY || '';
  
  console.log('🔧 [DEBUG] EnhancedTravelService initialized', {
    hasApiKey: !!this.googleMapsApiKey,
    keyLength: this.googleMapsApiKey ? this.googleMapsApiKey.length : 0,
    keyStartsWith: this.googleMapsApiKey ? this.googleMapsApiKey.substring(0, 10) + '...' : 'none'
  });
  
  if (!this.googleMapsApiKey) {
    logger.error('GOOGLE_MAPS_API_KEY not configured - travel calculations will fail');
    console.error('❌ GOOGLE_MAPS_API_KEY is missing from environment variables');
  } else {
    logger.info('Google Maps API key loaded successfully');
  }
}

  /**
   * Main entry point: Calculate travel time and distance
   */
  async calculateTravel(request: TravelCalculationRequest): Promise<TravelCalculationResponse> {
    try {
      // Validate input
      this.validateRequest(request);

      // Normalize locations and determine precision level
      const fromLocation = await this.normalizeLocation(request.from);
      const toLocation = await this.normalizeLocation(request.to);

      // Determine overall precision level
      const precisionLevel = this.determinePrecisionLevel(request.from, request.to);

      // Check cache unless force refresh
      if (!request.forceRefresh) {
        const cached = await this.getCachedResult(fromLocation, toLocation, request.mode || 'driving');
        if (cached) {
          logger.debug('Returning cached travel result', {
            from: fromLocation.address || fromLocation.postcode,
            to: toLocation.address || toLocation.postcode,
            precisionLevel: cached.precisionLevel
          });

          return this.formatResponse(cached, fromLocation, toLocation, true);
        }
      }

      // Call Google Distance Matrix API
      const googleResult = await this.callGoogleDistanceMatrix(
        fromLocation,
        toLocation,
        request.mode || 'driving'
      );

      // Cache the result
      await this.cacheResult(fromLocation, toLocation, googleResult, request.mode || 'driving', precisionLevel);

      // Format and return response
      return this.formatResponse(googleResult, fromLocation, toLocation, false);

    } catch (error: any) {
      logger.error('Travel calculation failed:', error);
      throw new Error(`Travel calculation failed: ${error.message}`);
    }
  }
  

  /**
   * Validate the request payload
   */
  private validateRequest(request: TravelCalculationRequest): void {
    if (!request.from || !request.to) {
      throw new Error('Both "from" and "to" locations are required');
    }

    // Validate 'from' location
    if (!this.hasValidLocation(request.from)) {
      throw new Error('Invalid "from" location: must provide address, postcode, or coordinates');
    }

    // Validate 'to' location
    if (!this.hasValidLocation(request.to)) {
      throw new Error('Invalid "to" location: must provide address, postcode, or coordinates');
    }

    // Validate mode
    const validModes = ['driving', 'walking', 'transit', 'bicycling'];
    if (request.mode && !validModes.includes(request.mode)) {
      throw new Error(`Invalid mode: must be one of ${validModes.join(', ')}`);
    }
  }

  /**
   * Check if location has valid data
   */
  private hasValidLocation(location: LocationInput): boolean {
    return !!(
      location.address ||
      location.postcode ||
      (location.latitude !== undefined && location.longitude !== undefined)
    );
  }

  /**
   * Normalize location to standard format with coordinates
   */
  private async normalizeLocation(location: LocationInput): Promise<LocationData> {
    // Case 1: Coordinates provided directly
    if (location.latitude !== undefined && location.longitude !== undefined) {
      return {
        address: location.address,
        postcode: location.postcode || 'N/A',
        coordinates: {
          latitude: location.latitude,
          longitude: location.longitude
        }
      };
    }

    // Case 2: Address provided - use it directly (Google will geocode)
    if (location.address) {
      return {
        address: location.address,
        postcode: location.postcode || this.extractPostcodeFromAddress(location.address) || 'N/A',
        coordinates: {
          latitude: 0, // Will be filled from Google response
          longitude: 0
        }
      };
    }

    // Case 3: Only postcode provided
    if (location.postcode) {
      return {
        postcode: location.postcode,
        coordinates: {
          latitude: 0, // Will be filled from Google response
          longitude: 0
        }
      };
    }

    throw new Error('Invalid location: no address, postcode, or coordinates provided');
  }

  /**
   * Extract postcode from address string (simple regex)
   */
  private extractPostcodeFromAddress(address: string): string | null {
    // UK postcode pattern
    const ukPattern = /\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b/i;
    const match = address.match(ukPattern);
    return match ? match[0].toUpperCase() : null;
  }

  /**
   * Determine precision level based on input
   */
  private determinePrecisionLevel(from: LocationInput, to: LocationInput): PrecisionLevel {
    const hasFromCoords = from.latitude !== undefined && from.longitude !== undefined;
    const hasToCoords = to.latitude !== undefined && to.longitude !== undefined;
    const hasFromAddress = !!from.address;
    const hasToAddress = !!to.address;

    if (hasFromCoords && hasToCoords) {
      return PrecisionLevel.COORDINATES;
    }

    if (hasFromAddress && hasToAddress) {
      return PrecisionLevel.ADDRESS;
    }

    return PrecisionLevel.POSTCODE;
  }

  /**
   * Check cache for existing result
   */
  private async getCachedResult(
    from: LocationData,
    to: LocationData,
    mode: string
  ): Promise<CachedTravelData | null> {
    const now = new Date();

    try {
      // Try address-based cache first (most precise)
      if (from.address && to.address) {
        const cached = await this.prisma.travelMatrixCache.findFirst({
          where: {
            fromAddress: from.address,
            toAddress: to.address,
            mode
          }
        });

        if (cached && cached.expiresAt > now) {
          return this.mapCachedData(cached);
        }
      }

      // Fall back to postcode-based cache
      if (from.postcode && to.postcode) {
        const cached = await this.prisma.travelMatrixCache.findFirst({
          where: {
            fromPostcode: from.postcode,
            toPostcode: to.postcode,
            mode
          }
        });

        if (cached && cached.expiresAt > now) {
          return this.mapCachedData(cached);
        }
      }

      return null;
    } catch (error) {
      logger.error('Cache lookup failed:', error);
      return null;
    }
  }

  /**
   * Map database cache record to CachedTravelData
   */
  private mapCachedData(cached: any): CachedTravelData {
    return {
      distanceMeters: cached.distanceMeters ?? 0,
      durationSeconds: cached.durationSeconds ?? 0,
      trafficDurationSeconds: cached.trafficDurationSeconds ?? undefined,
      fromLatitude: cached.fromLatitude ?? 0,
      fromLongitude: cached.fromLongitude ?? 0,
      toLatitude: cached.toLatitude ?? 0,
      toLongitude: cached.toLongitude ?? 0,
      fromAddress: cached.fromAddress ?? undefined,
      toAddress: cached.toAddress ?? undefined,
      fromPostcode: cached.fromPostcode,
      toPostcode: cached.toPostcode,
      precisionLevel: cached.precisionLevel as PrecisionLevel,
      calculatedAt: cached.calculatedAt,
      expiresAt: cached.expiresAt
    };
  }

  /**
   * Call Google Distance Matrix API
   */
  private async callGoogleDistanceMatrix(
    from: LocationData,
    to: LocationData,
    mode: string
  ): Promise<CachedTravelData> {
    try {
      // Build origin and destination strings
      const origin = this.buildLocationString(from);
      const destination = this.buildLocationString(to);

      logger.debug('Calling Google Distance Matrix API', { origin, destination, mode });

      const response = await axios.get<GoogleDistanceMatrixResponse>(
        'https://maps.googleapis.com/maps/api/distancematrix/json',
        {
          params: {
            origins: origin,
            destinations: destination,
            mode,
            key: this.googleMapsApiKey,
            units: 'metric',
            departure_time: 'now' // Get traffic data
          },
          timeout: 10000
        }
      );

      if (response.data.status !== 'OK') {
        throw new Error(`Google Maps API error: ${response.data.status} - ${response.data.error_message || 'Unknown error'}`);
      }

      const element = response.data.rows[0]?.elements[0];
      if (!element || element.status !== 'OK') {
        throw new Error(`No route found between locations. Status: ${element?.status || 'UNKNOWN'}`);
      }

      // Extract geocoded addresses from Google response
      const fromGeocoded = response.data.origin_addresses[0];
      const toGeocoded = response.data.destination_addresses[0];

      // Extract coordinates from geocoded addresses (we'll need to parse or make another call)
      // For now, use provided coordinates or set to 0
      const fromCoords = this.extractCoordinates(from);
      const toCoords = this.extractCoordinates(to);

      return {
        distanceMeters: element.distance?.value ?? 0,
        durationSeconds: element.duration?.value ?? 0,
        trafficDurationSeconds: element.duration_in_traffic?.value ?? undefined,
        fromLatitude: fromCoords.latitude,
        fromLongitude: fromCoords.longitude,
        toLatitude: toCoords.latitude,
        toLongitude: toCoords.longitude,
        fromAddress: from.address ?? fromGeocoded,
        toAddress: to.address ?? toGeocoded,
        fromPostcode: from.postcode || 'N/A',
        toPostcode: to.postcode || 'N/A',
        precisionLevel: from.address && to.address ? PrecisionLevel.ADDRESS : PrecisionLevel.POSTCODE,
        calculatedAt: new Date(),
        expiresAt: this.calculateExpiryDate(from.address && to.address ? PrecisionLevel.ADDRESS : PrecisionLevel.POSTCODE)
      };

    } catch (error: any) {
      if (axios.isAxiosError(error)) {
        logger.error('Google Maps API request failed:', {
          message: error.message,
          response: error.response?.data
        });
        throw new Error(`Google Maps API failed: ${error.message}`);
      }
      throw error;
    }
  }

  /**
   * Extract coordinates from location data
   */
  private extractCoordinates(location: LocationData): CoordinatesData {
    if (location.coordinates && location.coordinates.latitude !== 0) {
      return location.coordinates;
    }
    // Return zero coordinates - will need geocoding
    return { latitude: 0, longitude: 0 };
  }

  /**
   * Build location string for Google API
   */
  private buildLocationString(location: LocationData): string {
    // Priority: coordinates > address > postcode
    if (location.coordinates && location.coordinates.latitude !== 0) {
      return `${location.coordinates.latitude},${location.coordinates.longitude}`;
    }

    if (location.address) {
      return location.address;
    }

    if (location.postcode) {
      return location.postcode;
    }

    throw new Error('Cannot build location string: no valid data');
  }

  /**
   * Calculate expiry date based on precision level
   */
  private calculateExpiryDate(precisionLevel: PrecisionLevel): Date {
    const expiresAt = new Date();
    
    if (precisionLevel === PrecisionLevel.ADDRESS || precisionLevel === PrecisionLevel.COORDINATES) {
      // 1 hour for address-level precision
      expiresAt.setHours(expiresAt.getHours() + this.ADDRESS_CACHE_TTL_HOURS);
    } else {
      // 24 hours for postcode-level precision
      expiresAt.setHours(expiresAt.getHours() + this.POSTCODE_CACHE_TTL_HOURS);
    }

    return expiresAt;
  }

  /**
   * Cache the result in database
   */
  private async cacheResult(
    from: LocationData,
    to: LocationData,
    result: CachedTravelData,
    mode: string,
    precisionLevel: PrecisionLevel
  ): Promise<void> {
    try {
      const expiresAt = this.calculateExpiryDate(precisionLevel);

      // Prepare cache data
      const cacheData = {
        fromAddress: from.address ?? null,
        fromPostcode: from.postcode || 'N/A',
        toAddress: to.address ?? null,
        toPostcode: to.postcode || 'N/A',
        fromLatitude: result.fromLatitude,
        fromLongitude: result.fromLongitude,
        toLatitude: result.toLatitude,
        toLongitude: result.toLongitude,
        distanceMeters: result.distanceMeters,
        durationSeconds: result.durationSeconds,
        trafficDurationSeconds: result.trafficDurationSeconds ?? null,
        mode,
        precisionLevel,
        calculatedAt: new Date(),
        expiresAt
      };

      // Use address-based key if available, otherwise postcode-based
      if (from.address && to.address) {
        const existing = await this.prisma.travelMatrixCache.findFirst({
          where: {
            fromAddress: from.address,
            toAddress: to.address,
            mode
          }
        });

        if (existing) {
          await this.prisma.travelMatrixCache.update({
            where: { id: existing.id },
            data: cacheData
          });
        } else {
          await this.prisma.travelMatrixCache.create({
            data: cacheData
          });
        }
      } else {
        const existing = await this.prisma.travelMatrixCache.findFirst({
          where: {
            fromPostcode: from.postcode || 'N/A',
            toPostcode: to.postcode || 'N/A',
            mode
          }
        });

        if (existing) {
          await this.prisma.travelMatrixCache.update({
            where: { id: existing.id },
            data: cacheData
          });
        } else {
          await this.prisma.travelMatrixCache.create({
            data: cacheData
          });
        }
      }

      logger.debug('Travel result cached', {
        from: from.address || from.postcode,
        to: to.address || to.postcode,
        precisionLevel,
        expiresAt
      });

    } catch (error) {
      logger.error('Failed to cache travel result:', error);
      // Don't throw - caching failure shouldn't break the request
    }
  }

  /**
   * Format response for API
   */
  private formatResponse(
    data: CachedTravelData,
    from: LocationData,
    to: LocationData,
    cached: boolean
  ): TravelCalculationResponse {
    const warnings: WarningData[] = [];

    // Add warning for postcode-only precision
    if (data.precisionLevel === PrecisionLevel.POSTCODE) {
      warnings.push({
        type: 'APPROXIMATE_LOCATION',
        message: 'Using postcode centroid - actual distance may vary by ±200-500m',
        severity: 'info'
      });
    }

    return {
      distance: {
        meters: data.distanceMeters,
        kilometers: parseFloat((data.distanceMeters / 1000).toFixed(2)),
        text: `${(data.distanceMeters / 1000).toFixed(1)} km`
      },
      duration: {
        seconds: data.durationSeconds,
        minutes: Math.round(data.durationSeconds / 60),
        text: `${Math.round(data.durationSeconds / 60)} mins`
      },
      trafficDuration: data.trafficDurationSeconds ? {
        seconds: data.trafficDurationSeconds,
        minutes: Math.round(data.trafficDurationSeconds / 60),
        text: `${Math.round(data.trafficDurationSeconds / 60)} mins`
      } : undefined,
      from: {
        address: from.address,
        postcode: from.postcode,
        geocoded: data.fromAddress,
        coordinates: {
          latitude: data.fromLatitude,
          longitude: data.fromLongitude
        }
      },
      to: {
        address: to.address,
        postcode: to.postcode,
        geocoded: data.toAddress,
        coordinates: {
          latitude: data.toLatitude,
          longitude: data.toLongitude
        }
      },
      mode: 'driving',
      precisionLevel: data.precisionLevel,
      cached,
      calculatedAt: data.calculatedAt,
      expiresAt: data.expiresAt,
      warnings
    };
  }

  /**
   * Cleanup expired cache entries
   */
  async cleanupExpiredCache(): Promise<number> {
    try {
      const now = new Date();
      const result = await this.prisma.travelMatrixCache.deleteMany({
        where: {
          expiresAt: { lt: now }
        }
      });

      logger.info('Expired travel cache entries cleaned up', { count: result.count });
      return result.count;
    } catch (error) {
      logger.error('Failed to cleanup expired cache:', error);
      return 0;
    }
  }

  /**
   * Get cache statistics
   */
  async getCacheStats() {
    try {
      const now = new Date();
      const total = await this.prisma.travelMatrixCache.count();
      const addressLevel = await this.prisma.travelMatrixCache.count({
        where: { precisionLevel: PrecisionLevel.ADDRESS }
      });
      const postcodeLevel = await this.prisma.travelMatrixCache.count({
        where: { precisionLevel: PrecisionLevel.POSTCODE }
      });
      const coordinateLevel = await this.prisma.travelMatrixCache.count({
        where: { precisionLevel: PrecisionLevel.COORDINATES }
      });
      const expired = await this.prisma.travelMatrixCache.count({
        where: { expiresAt: { lt: now } }
      });

      return {
        total,
        byPrecision: {
          address: addressLevel,
          postcode: postcodeLevel,
          coordinates: coordinateLevel
        },
        expired,
        active: total - expired
      };
    } catch (error) {
      logger.error('Failed to get cache stats:', error);
      return null;
    }
  }
}