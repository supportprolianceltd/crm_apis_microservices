import { PrismaClient } from '@prisma/client';
import { logger, logServiceError } from '../utils/logger';
import { GeocodingService } from './geocoding.service';

interface AuthServiceUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  status: string;
  is_active: boolean;
  job_role: string;
  tenant: string;
  profile: {
    id: number;
    user: number;
    work_phone?: string;
    personal_phone?: string;
    gender?: string;
    street?: string;
    city?: string;
    state?: string;
    country?: string;
    zip_code?: string;
    department?: string;
    employee_id?: string;
    professional_qualifications?: Array<{
      id?: number;
      name?: string;
      title?: string;
      institution?: string;
      date_obtained?: string;
    }>;
    employment_details?: any[];
    education_details?: any[];
  } | null;
}

interface AuthServiceResponse {
  status: string;
  message: string;
  data: AuthServiceUser[];
}

export class AuthSyncService {
  private prisma: PrismaClient;
  private geocodingService: GeocodingService;
  private authServiceUrl: string;

  constructor(prisma: PrismaClient, geocodingService: GeocodingService) {
    this.prisma = prisma;
    this.geocodingService = geocodingService;
    this.authServiceUrl = process.env.AUTH_SERVICE_URL || 'https://server1.prolianceltd.com';
  }

  /**
   * Fetch all carers/staff from auth service for a tenant
   */
  async syncCarersFromAuthService(tenantId: string, authToken: string): Promise<number> {
    try {
      logger.info(`Starting carer sync for tenant: ${tenantId}`);

      // Get all users from auth service
      const response = await fetch(`${this.authServiceUrl}/api/user/tenant-users`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Auth service request failed: ${response.status} - ${response.statusText}`);
      }

      const authData = await response.json() as AuthServiceResponse;
      const allUsers = authData.data || [];

      if (!Array.isArray(allUsers)) {
        throw new Error('Invalid response format from auth service');
      }

      // Filter for carers only
      const carers = allUsers.filter(user => user.role === 'carer' && user.is_active === true);

      logger.info(`Found ${carers.length} carers in auth service for tenant ${tenantId}`);

      let syncedCount = 0;
      const authUserIds = new Set<string>();

      // Process each carer
      for (const authCarer of carers) {
        try {
          await this.upsertCarerFromAuth(authCarer, tenantId);
          authUserIds.add(authCarer.id.toString());
          syncedCount++;
        } catch (error) {
          logger.error(`Failed to sync carer ${authCarer.email}:`, error);
        }
      }

      // Deactivate carers that are no longer in auth service
      if (authUserIds.size > 0) {
        await this.prisma.carer.updateMany({
          where: {
            tenantId: tenantId.toString(),
            authUserId: {
              notIn: Array.from(authUserIds)
            }
          },
          data: {
            isActive: false,
            updatedAt: new Date()
          }
        });
      }

      logger.info(`Successfully synced ${syncedCount} carers for tenant ${tenantId}`);
      return syncedCount;

    } catch (error) {
      logServiceError('AuthSync', 'syncCarersFromAuthService', error, { tenantId });
      throw error;
    }
  }

  /**
   * Create or update a single carer from auth service data
   */
  private async upsertCarerFromAuth(authCarer: AuthServiceUser, tenantId: string): Promise<void> {
    try {
      // Extract profile data with proper typing
      const profile = authCarer.profile as {
        street?: string;
        city?: string;
        state?: string;
        country?: string;
        zip_code?: string;
        work_phone?: string;
        personal_phone?: string;
        professional_qualifications?: Array<{
          name?: string;
          title?: string;
        }>;
      } | null;
      
      // Build full address from auth carer profile data
      const addressParts = [
        profile?.street,
        profile?.city,
        profile?.state,
        profile?.country
      ].filter(Boolean);
      
      const fullAddress = addressParts.join(', ');
      const postcode = profile?.zip_code || '';

      // Geocode the address
      let latitude: number | undefined;
      let longitude: number | undefined;
      
      if (fullAddress) {
        try {
          const geocoded = await this.geocodingService.geocodeAddress(
            fullAddress, 
            postcode, 
            profile?.country || 'Nigeria' // Pass country for geocoding
          );
          if (geocoded) {
            latitude = geocoded.latitude;
            longitude = geocoded.longitude;
          }
        } catch (geocodeError) {
          logger.warn(`Failed to geocode address for carer ${authCarer.email}: ${fullAddress}`);
        }
      }

      // Extract professional qualifications as skills
      const skills = profile?.professional_qualifications?.map((qual: any) => qual.name || qual.title).filter(Boolean) || [];
      
      // Determine languages (default to English)
      const languages = ['English']; // Could be enhanced based on profile data

      // Extract country for geocoding
      const country = profile?.country || 'Nigeria'; // Default to Nigeria

      // Upsert carer record
      const carerData = {
        tenantId: tenantId.toString(), // Ensure tenantId is string
        authUserId: authCarer.id.toString(),
        email: authCarer.email,
        firstName: authCarer.first_name || '',
        lastName: authCarer.last_name || '',
        phone: profile?.work_phone || profile?.personal_phone || '',
        address: fullAddress,
        postcode,
        country, // Save country for future geocoding
        latitude,
        longitude,
        maxTravelDistance: 15000, // Default 15km travel distance
        availabilityHours: undefined, // Could be enhanced based on profile data
        skills,
        languages,
        qualification: profile?.professional_qualifications?.[0]?.name || '',
        experience: 0, // Could be calculated from employment_details
        hourlyRate: null, // Could be extracted from profile if available
        isActive: authCarer.is_active !== false && authCarer.status === 'active',
        updatedAt: new Date()
      };

      const carer = await this.prisma.carer.upsert({
        where: {
          tenantId_email: {
            tenantId: tenantId.toString(), // Ensure tenantId is string
            email: authCarer.email
          }
        },
        update: carerData,
        create: carerData
      });

      // Update PostGIS location if we have coordinates
      if (latitude && longitude) {
        await this.prisma.$executeRaw`
          UPDATE carers 
          SET location = ST_GeogFromText(${`POINT(${longitude} ${latitude})`})
          WHERE id = ${carer.id}
        `;
      }

      logger.debug(`Synced carer: ${authCarer.email} (${authCarer.id})`);

    } catch (error) {
      logServiceError('AuthSync', 'upsertCarerFromAuth', error, { 
        carerId: authCarer.id, 
        email: authCarer.email 
      });
      throw error;
    }
  }

  /**
   * Sync a single carer when they're updated in auth service
   */
  async syncSingleCarer(carerId: string, tenantId: string, authToken: string): Promise<void> {
    try {
      logger.info(`Syncing single carer: ${carerId} for tenant: ${tenantId}`);

      // Get all users and find the specific carer
      const response = await fetch(`${this.authServiceUrl}/api/user/tenant-users`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Auth service request failed: ${response.status} - ${response.statusText}`);
      }

      const authData = await response.json() as AuthServiceResponse;
      const allUsers = authData.data || [];

      // Find the specific carer
      const authCarer = allUsers.find((user: AuthServiceUser) => 
        user.id.toString() === carerId && user.role === 'carer'
      );

      if (!authCarer) {
        throw new Error('Carer not found in auth service or user is not a carer');
      }

      await this.upsertCarerFromAuth(authCarer, tenantId);
      logger.info(`Successfully synced single carer ${carerId} for tenant ${tenantId}`);

    } catch (error) {
      logServiceError('AuthSync', 'syncSingleCarer', error, { carerId, tenantId });
      throw error;
    }
  }

  /**
   * Get carer count comparison between auth service and local database
   */
  async getCarerSyncStatus(tenantId: string, authToken: string): Promise<{
    authServiceCount: number;
    localCount: number;
    lastSyncTime?: Date;
  }> {
    try {
      // Get all users from auth service
      const response = await fetch(`${this.authServiceUrl}/api/user/tenant-users`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Auth service request failed: ${response.status}`);
      }

      const authData = await response.json() as AuthServiceResponse;
      const allUsers = authData.data || [];
      const authCarers = allUsers.filter((user: AuthServiceUser) => user.role === 'carer');

      const authServiceCount = authCarers.length;

      // Get local count
      const localCount = await this.prisma.carer.count({
        where: {
          tenantId,
          isActive: true
        }
      });

      // Get last sync time (approximate from most recent carer update)
      const lastUpdatedCarer = await this.prisma.carer.findFirst({
        where: { tenantId },
        orderBy: { updatedAt: 'desc' },
        select: { updatedAt: true }
      });

      return {
        authServiceCount,
        localCount,
        lastSyncTime: lastUpdatedCarer?.updatedAt
      };

    } catch (error) {
      logServiceError('AuthSync', 'getCarerSyncStatus', error, { tenantId });
      throw error;
    }
  }

  /**
   * Check if a carer exists in auth service (for validation)
   */
  async validateCarerExists(carerId: string, tenantId: string, authToken: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.authServiceUrl}/api/user/tenant-users`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        return false;
      }

      const authData = await response.json() as AuthServiceResponse;
      const allUsers = authData.data || [];

      const carer = allUsers.find((user: AuthServiceUser) => 
        user.id.toString() === carerId && 
        user.role === 'carer' && 
        user.is_active
      );

      return !!carer;

    } catch (error) {
      logServiceError('AuthSync', 'validateCarerExists', error, { carerId, tenantId });
      return false;
    }
  }
}

export default AuthSyncService;