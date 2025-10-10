import { Request, Response } from 'express';
import { z } from 'zod';
import { PrismaClient } from '@prisma/client';
import { logger, logServiceError } from '../utils/logger';
import { 
  SearchCarersQuery,
  PaginatedResponse,
  Carer
} from '../types';

// Validation schemas
const searchCarersSchema = z.object({
  postcode: z.string().optional(),
  skills: z.array(z.string()).optional(),
  languages: z.array(z.string()).optional(),
  maxDistance: z.number().int().positive().optional(),
  isActive: z.boolean().optional(),
  page: z.number().int().positive().optional(),
  limit: z.number().int().positive().max(100).optional()
});

export class CarerController {
  private prisma: PrismaClient;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  /**
   * Get carer by ID (read-only)
   */
  getCarer = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId;
      const carerId = req.params.id;

      const carer = await this.prisma.carer.findFirst({
        where: {
          id: carerId,
          tenantId
        },
        include: {
          matches: {
            include: {
              request: {
                select: {
                  id: true,
                  subject: true,
                  urgency: true,
                  status: true,
                  address: true,
                  createdAt: true
                }
              }
            },
            orderBy: {
              createdAt: 'desc'
            },
            take: 10 // Recent matches only
          }
        }
      });

      if (!carer) {
        res.status(404).json({
          success: false,
          error: 'Carer not found'
        });
        return;
      }

      res.json({
        success: true,
        data: carer
      });

    } catch (error) {
      logServiceError('Carer', 'getCarer', error, { carerId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve carer'
      });
    }
  };

  /**
   * Search carers with pagination (read-only)
   */
  searchCarers = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId;
      
      // Validate query parameters
      const validatedQuery = searchCarersSchema.parse(req.query);

      const page = validatedQuery.page || 1;
      const limit = validatedQuery.limit || 20;
      const skip = (page - 1) * limit;

      // Build where clause
      const whereClause: any = {
        tenantId,
        ...(validatedQuery.isActive !== undefined && { isActive: validatedQuery.isActive }),
        ...(validatedQuery.postcode && { postcode: { contains: validatedQuery.postcode, mode: 'insensitive' } })
      };

      // Add skill filtering if specified
      if (validatedQuery.skills && validatedQuery.skills.length > 0) {
        whereClause.skills = {
          hasEvery: validatedQuery.skills
        };
      }

      // Add language filtering if specified
      if (validatedQuery.languages && validatedQuery.languages.length > 0) {
        whereClause.languages = {
          hasSome: validatedQuery.languages
        };
      }

      // Get total count and data
      const [total, carers] = await Promise.all([
        this.prisma.carer.count({ where: whereClause }),
        this.prisma.carer.findMany({
          where: whereClause,
          skip,
          take: limit,
          orderBy: [
            { isActive: 'desc' },
            { createdAt: 'desc' }
          ],
          include: {
            matches: {
              select: {
                id: true,
                status: true,
                matchScore: true,
                distance: true,
                createdAt: true
              },
              orderBy: {
                createdAt: 'desc'
              },
              take: 3 // Only include recent matches in list view
            }
          }
        })
      ]);

      const totalPages = Math.ceil(total / limit);

      const response: PaginatedResponse<any> = {
        data: carers, // Remove type assertion since Prisma types don't match exactly
        pagination: {
          page,
          limit,
          total,
          pages: totalPages,
          hasNext: page < totalPages,
          hasPrev: page > 1
        }
      };

      res.json({
        success: true,
        ...response
      });

    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({
          success: false,
          error: 'Validation error',
          details: error.errors
        });
        return;
      }

      logServiceError('Carer', 'searchCarers', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to search carers'
      });
    }
  };

  /**
   * Get carer availability (read-only)
   */
  getCarerAvailability = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId;
      const carerId = req.params.id;

      const carer = await this.prisma.carer.findFirst({
        where: {
          id: carerId,
          tenantId
        },
        select: {
          id: true,
          firstName: true,
          lastName: true,
          email: true,
          isActive: true,
          availabilityHours: true,
          maxTravelDistance: true,
          skills: true,
          languages: true
        }
      });

      if (!carer) {
        res.status(404).json({
          success: false,
          error: 'Carer not found'
        });
        return;
      }

      res.json({
        success: true,
        data: {
          ...carer,
          availability: carer.availabilityHours || null
        }
      });

    } catch (error) {
      logServiceError('Carer', 'getCarerAvailability', error, { carerId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve carer availability'
      });
    }
  };

  /**
   * Note: Carer creation, updates, and deletion are handled through 
   * the auth service sync process. This controller only provides 
   * read-only access to synced carer data.
   */


}