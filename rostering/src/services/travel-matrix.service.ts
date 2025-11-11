import { PrismaClient } from '@prisma/client';
import { logger } from '../utils/logger';

export interface TravelMatrixEntry {
  fromPostcode: string;
  toPostcode: string;
  durationMinutes: number;
  distanceMeters: number;
  lastUpdated: Date;
  expiresAt: Date;
}

export interface ClientToClusterDistanceEntry {
  clientPostcode: string;
  clusterId: string;
  distanceKm: number;
  lastUpdated: Date;
  expiresAt: Date;
}

export class TravelMatrixService {
  private cache = new Map<string, TravelMatrixEntry>();
  private clientClusterCache = new Map<string, ClientToClusterDistanceEntry>();
  private readonly TTL_HOURS = 24;
  private readonly CLIENT_CLUSTER_TTL_DAYS = 7; // Client to cluster distances change less frequently

  constructor(private prisma: PrismaClient) {}

  async getTravelTime(fromPostcode: string, toPostcode: string): Promise<TravelMatrixEntry | null> {
    const key = this.getCacheKey(fromPostcode, toPostcode);
    
    // Check memory cache first
    const cached = this.cache.get(key);
    if (cached && cached.expiresAt > new Date()) {
      return cached;
    }

    // Check database cache
    const dbEntry = await this.prisma.travelMatrix.findFirst({
      where: {
        fromPostcode,
        toPostcode,
        expiresAt: { gt: new Date() }
      }
    });

    if (dbEntry) {
      const entry: TravelMatrixEntry = {
        fromPostcode: dbEntry.fromPostcode,
        toPostcode: dbEntry.toPostcode,
        durationMinutes: dbEntry.durationMinutes,
        distanceMeters: dbEntry.distanceMeters,
        lastUpdated: dbEntry.lastUpdated,
        expiresAt: dbEntry.expiresAt
      };
      
      this.cache.set(key, entry);
      return entry;
    }

    return null;
  }

  async setTravelTime(
    fromPostcode: string, 
    toPostcode: string, 
    durationMinutes: number, 
    distanceMeters: number
  ): Promise<void> {
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + this.TTL_HOURS);

    const entry: TravelMatrixEntry = {
      fromPostcode,
      toPostcode,
      durationMinutes,
      distanceMeters,
      lastUpdated: new Date(),
      expiresAt
    };

    const key = this.getCacheKey(fromPostcode, toPostcode);
    this.cache.set(key, entry);

    await this.prisma.travelMatrix.upsert({
      where: {
        fromPostcode_toPostcode: {
          fromPostcode,
          toPostcode
        }
      },
      update: {
        durationMinutes,
        distanceMeters,
        lastUpdated: new Date(),
        expiresAt
      },
      create: {
        fromPostcode,
        toPostcode,
        durationMinutes,
        distanceMeters,
        lastUpdated: new Date(),
        expiresAt
      }
    });

    logger.debug('Travel matrix updated', { fromPostcode, toPostcode, durationMinutes });
  }

  async batchUpdateTravelTimes(updates: Array<{
    fromPostcode: string;
    toPostcode: string;
    durationMinutes: number;
    distanceMeters: number;
  }>): Promise<void> {
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + this.TTL_HOURS);

    await this.prisma.$transaction(async (tx) => {
      for (const update of updates) {
        await tx.travelMatrix.upsert({
          where: {
            fromPostcode_toPostcode: {
              fromPostcode: update.fromPostcode,
              toPostcode: update.toPostcode
            }
          },
          update: {
            durationMinutes: update.durationMinutes,
            distanceMeters: update.distanceMeters,
            lastUpdated: new Date(),
            expiresAt
          },
          create: {
            fromPostcode: update.fromPostcode,
            toPostcode: update.toPostcode,
            durationMinutes: update.durationMinutes,
            distanceMeters: update.distanceMeters,
            lastUpdated: new Date(),
            expiresAt
          }
        });

        const key = this.getCacheKey(update.fromPostcode, update.toPostcode);
        this.cache.set(key, {
          ...update,
          lastUpdated: new Date(),
          expiresAt
        });
      }
    });

    logger.info('Batch travel matrix update completed', { count: updates.length });
  }

  async cleanupExpiredEntries(): Promise<number> {
    const result = await this.prisma.travelMatrix.deleteMany({
      where: {
        expiresAt: { lt: new Date() }
      }
    });

    const now = new Date();
    for (const [key, entry] of this.cache.entries()) {
      if (entry.expiresAt < now) {
        this.cache.delete(key);
      }
    }

    logger.info('Expired travel matrix entries cleaned up', { count: result.count });
    return result.count;
  }

  /**
   * Get cached client-to-cluster distance
   */
  async getClientToClusterDistance(clientPostcode: string, clusterId: string): Promise<ClientToClusterDistanceEntry | null> {
    const key = this.getClientClusterCacheKey(clientPostcode, clusterId);

    // Check memory cache first
    const cached = this.clientClusterCache.get(key);
    if (cached && cached.expiresAt > new Date()) {
      return cached;
    }

    // Check database cache
    const dbEntry = await this.prisma.clientClusterDistance.findFirst({
      where: {
        clientPostcode,
        clusterId,
        expiresAt: { gt: new Date() }
      }
    });

    if (dbEntry) {
      const entry: ClientToClusterDistanceEntry = {
        clientPostcode: dbEntry.clientPostcode,
        clusterId: dbEntry.clusterId,
        distanceKm: dbEntry.distanceKm,
        lastUpdated: dbEntry.lastUpdated,
        expiresAt: dbEntry.expiresAt
      };

      this.clientClusterCache.set(key, entry);
      return entry;
    }

    return null;
  }

  /**
   * Set client-to-cluster distance in cache
   */
  async setClientToClusterDistance(
    clientPostcode: string,
    clusterId: string,
    distanceKm: number
  ): Promise<void> {
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + this.CLIENT_CLUSTER_TTL_DAYS);

    const entry: ClientToClusterDistanceEntry = {
      clientPostcode,
      clusterId,
      distanceKm,
      lastUpdated: new Date(),
      expiresAt
    };

    const key = this.getClientClusterCacheKey(clientPostcode, clusterId);
    this.clientClusterCache.set(key, entry);

    await this.prisma.clientClusterDistance.upsert({
      where: {
        clientPostcode_clusterId: {
          clientPostcode,
          clusterId
        }
      },
      update: {
        distanceKm,
        lastUpdated: new Date(),
        expiresAt
      },
      create: {
        clientPostcode,
        clusterId,
        distanceKm,
        lastUpdated: new Date(),
        expiresAt
      }
    });

    logger.debug('Client-cluster distance cached', { clientPostcode, clusterId, distanceKm });
  }

  /**
   * Batch update client-to-cluster distances
   */
  async batchUpdateClientClusterDistances(updates: Array<{
    clientPostcode: string;
    clusterId: string;
    distanceKm: number;
  }>): Promise<void> {
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + this.CLIENT_CLUSTER_TTL_DAYS);

    await this.prisma.$transaction(async (tx) => {
      for (const update of updates) {
        await tx.clientClusterDistance.upsert({
          where: {
            clientPostcode_clusterId: {
              clientPostcode: update.clientPostcode,
              clusterId: update.clusterId
            }
          },
          update: {
            distanceKm: update.distanceKm,
            lastUpdated: new Date(),
            expiresAt
          },
          create: {
            clientPostcode: update.clientPostcode,
            clusterId: update.clusterId,
            distanceKm: update.distanceKm,
            lastUpdated: new Date(),
            expiresAt
          }
        });

        const key = this.getClientClusterCacheKey(update.clientPostcode, update.clusterId);
        this.clientClusterCache.set(key, {
          ...update,
          lastUpdated: new Date(),
          expiresAt
        });
      }
    });

    logger.info('Batch client-cluster distance update completed', { count: updates.length });
  }

  /**
   * Clean up expired client-cluster distance entries
   */
  async cleanupExpiredClientClusterEntries(): Promise<number> {
    const result = await this.prisma.clientClusterDistance.deleteMany({
      where: {
        expiresAt: { lt: new Date() }
      }
    });

    const now = new Date();
    for (const [key, entry] of this.clientClusterCache.entries()) {
      if (entry.expiresAt < now) {
        this.clientClusterCache.delete(key);
      }
    }

    logger.info('Expired client-cluster distance entries cleaned up', { count: result.count });
    return result.count;
  }

  getCacheStats() {
    return {
      memoryCacheSize: this.cache.size,
      memoryCacheKeys: Array.from(this.cache.keys()),
      clientClusterCacheSize: this.clientClusterCache.size,
      clientClusterCacheKeys: Array.from(this.clientClusterCache.keys())
    };
  }

  private getCacheKey(fromPostcode: string, toPostcode: string): string {
    return `${fromPostcode}_${toPostcode}`.toLowerCase().replace(/\s+/g, '');
  }

  private getClientClusterCacheKey(clientPostcode: string, clusterId: string): string {
    return `${clientPostcode}_${clusterId}`.toLowerCase().replace(/\s+/g, '');
  }
}