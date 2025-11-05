import { PrismaClient } from '@prisma/client';
import axios from 'axios';
import { logger, logServiceError } from '../utils/logger';
import { GeocodingResult, ServiceError } from '../types';

export class GeocodingService {
  private prisma: PrismaClient;
  private nominatimUrl: string;
  private requestCache: Map<string, Promise<GeocodingResult | null>> = new Map();

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
    this.nominatimUrl = process.env.NOMINATIM_URL || 'https://nominatim.openstreetmap.org';
  }

  /**
   * Geocode an address with caching
   */
  async geocodeAddress(address: string, postcode?: string, country?: string): Promise<GeocodingResult | null> {
    try {
      const normalizedAddress = this.normalizeAddress(address, postcode);
      
      // Check cache first
      const cached = await this.getCachedResult(normalizedAddress);
      if (cached) {
        logger.debug(`Geocoding cache hit for: ${normalizedAddress}`);
        return cached;
      }

      // Check if there's an ongoing request for the same address
      const ongoingRequest = this.requestCache.get(normalizedAddress);
      if (ongoingRequest) {
        logger.debug(`Using ongoing geocoding request for: ${normalizedAddress}`);
        return await ongoingRequest;
      }

      // Start new geocoding request with country
      const geocodingPromise = this.performGeocoding(normalizedAddress, country);
      this.requestCache.set(normalizedAddress, geocodingPromise);

      try {
        const result = await geocodingPromise;
        
        // Cache the result
        if (result) {
          await this.cacheResult(normalizedAddress, result);
        }

        return result;
      } finally {
        // Clean up the request cache
        this.requestCache.delete(normalizedAddress);
      }

    } catch (error) {
      logServiceError('Geocoding', 'geocodeAddress', error, { address, postcode });
      return null;
    }
  }

  /**
   * Perform actual geocoding using Nominatim API with fallback strategies
   */
  private async performGeocoding(address: string, country?: string): Promise<GeocodingResult | null> {
    try {
      // Map country names to ISO country codes for Nominatim
      const countryCodeMap: { [key: string]: string } = {
        'Nigeria': 'ng',
        'United Kingdom': 'gb',
        'UK': 'gb',
        'England': 'gb',
        'Scotland': 'gb',
        'Wales': 'gb',
        'Northern Ireland': 'gb',
        'Ghana': 'gh',
        'Kenya': 'ke',
        'South Africa': 'za',
        'United States': 'us',
        'USA': 'us',
        'Canada': 'ca'
      };

      // Get country code, default to no restriction if country not recognized
      const countryCode = country ? countryCodeMap[country] || null : null;

      // Try multiple query formats for better geocoding success
      const queryVariations = this.buildQueryVariations(address);
      
      for (const query of queryVariations) {
        const searchParams = new URLSearchParams({
          q: query,
          format: 'json',
          limit: '1',
          addressdetails: '1'
        });

        // Only add country code if we have a valid one
        if (countryCode) {
          searchParams.append('countrycodes', countryCode);
        }

        const response = await axios.get(`${this.nominatimUrl}/search`, {
          params: searchParams,
          timeout: 10000,
          headers: {
            'User-Agent': 'CRM-Rostering-Service/1.0'
          }
        });

        if (response.data && response.data.length > 0) {
          const result = response.data[0];
          const geocodingResult: GeocodingResult = {
            latitude: parseFloat(result.lat),
            longitude: parseFloat(result.lon),
            confidence: this.calculateConfidence(result),
            address: result.display_name,
            source: 'nominatim'
          };

          logger.debug(`Geocoded address: ${address} -> ${geocodingResult.latitude}, ${geocodingResult.longitude}`);
          return geocodingResult;
        }
      }

      logger.warn(`No geocoding results for address: ${address}`);
      return null;

    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.code === 'ECONNABORTED') {
          logger.warn(`Geocoding timeout for address: ${address}`);
        } else if (error.response?.status === 429) {
          logger.warn(`Geocoding rate limit exceeded for address: ${address}`);
          // Could implement exponential backoff here
        } else {
          logger.error(`Geocoding API error for address: ${address}`, error.response?.data);
        }
      } else {
        logServiceError('Geocoding', 'performGeocoding', error, { address });
      }
      return null;
    }
  }

  /**
   * Build multiple query variations for better geocoding success
   */
  private buildQueryVariations(address: string): string[] {
    const variations: string[] = [];
    
    // Extract postcode if present
    const postcodeMatch = address.match(/\b\d{5,6}\b/); // Match 5-6 digit postcodes
    const postcode = postcodeMatch ? postcodeMatch[0] : null;
    
    if (postcode) {
      // Remove postcode from original address
      const addressWithoutPostcode = address.replace(/,?\s*\b\d{5,6}\b/, '').replace(/,\s*$/, '').trim();
      
      // Variation 1: Postcode first (works best for Nigeria)
      variations.push(`${postcode} ${addressWithoutPostcode}`);
      
      // Variation 2: Original format (with postcode at end)
      variations.push(address);
      
      // Variation 3: Without postcode entirely
      variations.push(addressWithoutPostcode);
    } else {
      // No postcode found, use original address
      variations.push(address);
    }
    
    return variations;
  }

  /**
   * Get cached geocoding result
   */
  private async getCachedResult(address: string): Promise<GeocodingResult | null> {
    try {
      const cached = await this.prisma.geocodingCache.findUnique({
        where: { address }
      });

      if (cached) {
        return {
          latitude: cached.latitude,
          longitude: cached.longitude,
          confidence: cached.confidence || undefined,
          address: cached.address || address,
          source: cached.source
        };
      }

      return null;
    } catch (error) {
      logServiceError('Geocoding', 'getCachedResult', error, { address });
      return null;
    }
  }

  /**
   * Cache geocoding result
   */
  private async cacheResult(address: string, result: GeocodingResult): Promise<void> {
    try {
      // Check if record already exists
      const existing = await this.prisma.geocodingCache.findUnique({
        where: { address }
      });

      if (existing) {
        // Update existing record
        await this.prisma.geocodingCache.update({
          where: { address },
          data: {
            latitude: result.latitude,
            longitude: result.longitude,
            confidence: result.confidence,
            source: result.source,
            updatedAt: new Date()
          }
        });
      } else {
        // Create new record using raw SQL to handle PostGIS location field
        await this.prisma.$executeRaw`
          INSERT INTO geocoding_cache (id, address, latitude, longitude, location, confidence, source, "createdAt", "updatedAt")
          VALUES (
            gen_random_uuid(),
            ${address},
            ${result.latitude},
            ${result.longitude},
            ST_GeogFromText(${`POINT(${result.longitude} ${result.latitude})`}),
            ${result.confidence || null},
            ${result.source},
            NOW(),
            NOW()
          )
        `;
      }

      logger.debug(`Cached geocoding result for: ${address}`);
    } catch (error) {
      logServiceError('Geocoding', 'cacheResult', error, { address, result });
    }
  }

  /**
   * Normalize address for consistent caching
   */
  private normalizeAddress(address: string, postcode?: string): string {
    let normalized = address.trim().toLowerCase();
    
    if (postcode) {
      // Add postcode if not already included
      const postcodePattern = /[a-z]{1,2}\d{1,2}[a-z]?\s*\d[a-z]{2}/i;
      if (!postcodePattern.test(normalized)) {
        normalized += `, ${postcode.trim().toLowerCase()}`;
      }
    }

    // Remove extra whitespace
    normalized = normalized.replace(/\s+/g, ' ');
    
    return normalized;
  }

  /**
   * Calculate confidence score based on Nominatim result
   */
  private calculateConfidence(result: any): number {
    // Basic confidence calculation based on place rank and importance
    const importance = parseFloat(result.importance || '0');
    const placeRank = parseInt(result.place_rank || '30');
    
    // Higher importance and lower place rank = higher confidence
    let confidence = importance * 100;
    confidence = confidence - (placeRank - 1) * 2;
    
    // Normalize to 0-100 range
    confidence = Math.max(0, Math.min(100, confidence));
    
    return Math.round(confidence);
  }

  /**
   * Extract postcode from address string
   */
  private extractPostcode(address: string): string | null {
    const postcodePattern = /([a-z]{1,2}\d{1,2}[a-z]?\s*\d[a-z]{2})/i;
    const match = address.match(postcodePattern);
    return match ? match[1].toUpperCase() : null;
  }

  /**
   * Batch geocode multiple addresses
   */
  async geocodeAddresses(addresses: Array<{ address: string; postcode?: string }>): Promise<Array<GeocodingResult | null>> {
    const promises = addresses.map(({ address, postcode }) => 
      this.geocodeAddress(address, postcode)
    );
    
    return Promise.all(promises);
  }

  /**
   * Calculate distance between two points using PostGIS
   */
  async calculateDistance(
    lat1: number, 
    lon1: number, 
    lat2: number, 
    lon2: number
  ): Promise<number> {
    try {
      const result = await this.prisma.$queryRaw<Array<{ distance: number }>>`
        SELECT ST_Distance(
          ST_GeogFromText(${`POINT(${lon1} ${lat1})`}),
          ST_GeogFromText(${`POINT(${lon2} ${lat2})`})
        ) as distance
      `;

      return result[0]?.distance || 0;
    } catch (error) {
      logServiceError('Geocoding', 'calculateDistance', error, { lat1, lon1, lat2, lon2 });
      // Fallback to Haversine formula if PostGIS fails
      return this.haversineDistance(lat1, lon1, lat2, lon2);
    }
  }

  /**
   * Fallback distance calculation using Haversine formula
   */
  private haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371000; // Earth's radius in meters
    const dLat = this.toRadians(lat2 - lat1);
    const dLon = this.toRadians(lon2 - lon1);
    const a = 
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) * 
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  private toRadians(degrees: number): number {
    return degrees * (Math.PI / 180);
  }
}

