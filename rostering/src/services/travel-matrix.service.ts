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

export class TravelMatrixService {
  private cache = new Map<string, TravelMatrixEntry>();
  private readonly TTL_HOURS = 24;

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

  getCacheStats() {
    return {
      memoryCacheSize: this.cache.size,
      memoryCacheKeys: Array.from(this.cache.keys())
    };
  }

  private getCacheKey(fromPostcode: string, toPostcode: string): string {
    return `${fromPostcode}_${toPostcode}`.toLowerCase().replace(/\s+/g, '');
  }
}