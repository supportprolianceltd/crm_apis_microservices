import { Request, Response } from 'express';
import { z } from 'zod';
import { PrismaClient } from '@prisma/client';
import { logger, logServiceError } from '../utils/logger';
import { 
  SearchCarersQuery,
  PaginatedResponse,
  Carer
} from '../types';
import { CarerService } from '../services/carer.service';

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
  private carerService: CarerService;

  constructor(carerService: CarerService) {
    this.carerService = carerService;
  }

  /**
   * Get carer by ID (read-only)
   */
 getCarer = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId;
      const carerId = req.params.id;
      const authToken = req.headers.authorization?.replace('Bearer ', '');

      if (!authToken) {
        res.status(401).json({ success: false, error: 'Authentication required' });
        return;
      }

      console.log('Fetching carer with ID:', carerId);
      console.log('Using auth token:', authToken.substring(0, 20) + '...');

      const carer = await this.carerService.getCarerById(authToken, carerId);
      console.log('Carer service response:', carer);

      if (!carer || carer.tenantId !== tenantId) {
        res.status(404).json({ success: false, error: 'Carer not found' });
        return;
      }

      // TODO: If you need matches, you'll need to query them separately
      // since they're stored locally but reference carer IDs

      res.json({
        success: true,
        data: carer
      });

    } catch (error) {
      console.error('getCarer error:', error);
      if (error instanceof Error) {
        console.error('Error stack:', error.stack);
      } else {
        console.error('Non-Error thrown:', error);
      }
      res.status(500).json({ 
        success: false, 
        error: 'Failed to retrieve carer',
        details: process.env.NODE_ENV === 'development' && error instanceof Error ? error.message : undefined
      });
    }
  };

  /**
   * Search carers with pagination (read-only)
   */
  searchCarers = async (req: Request, res: Response): Promise<void> => {
      try {
        const tenantId = req.user!.tenantId;
        const authToken = req.headers.authorization?.replace('Bearer ', '');
        
        if (!authToken) {
          res.status(401).json({ success: false, error: 'Authentication required' });
          return;
        }

        // Validate query parameters
        const validatedQuery = searchCarersSchema.parse(req.query);

        // Get all carers from auth service
        const allCarers = await this.carerService.getCarers(authToken, tenantId);

        // Apply filters manually since we're getting all data from auth service
        let filteredCarers = allCarers;

        if (validatedQuery.postcode) {
          filteredCarers = filteredCarers.filter(carer => 
            carer.profile?.zip_code?.includes(validatedQuery.postcode!)
          );
        }

        if (validatedQuery.skills && validatedQuery.skills.length > 0) {
          filteredCarers = filteredCarers.filter(carer =>
            validatedQuery.skills!.every(skill => 
              carer.profile?.professional_qualifications?.includes(skill)
            )
          );
        }

        if (validatedQuery.languages && validatedQuery.languages.length > 0) {
          filteredCarers = filteredCarers.filter(carer =>
            validatedQuery.languages!.some(language => 
              // You'd need to add languages to your auth service user model
              carer.languages?.includes(language)
            )
          );
        }

        if (validatedQuery.isActive !== undefined) {
          filteredCarers = filteredCarers.filter(carer => 
            carer.status === (validatedQuery.isActive ? 'active' : 'inactive')
          );
        }

        // Paginate results
        const page = validatedQuery.page || 1;
        const limit = validatedQuery.limit || 20;
        const skip = (page - 1) * limit;
        
        const paginatedCarers = filteredCarers.slice(skip, skip + limit);
        const total = filteredCarers.length;
        const totalPages = Math.ceil(total / limit);

        const response = {
          data: paginatedCarers,
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

        console.error('searchCarers error:', error);
        res.status(500).json({ success: false, error: 'Failed to search carers' });
      }
    };

  /**
   * Get carer availability (read-only)
   */
  getCarerAvailability = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId;
      const carerId = req.params.id;
      const authToken = req.headers.authorization?.replace('Bearer ', '');

      if (!authToken) {
        res.status(401).json({ success: false, error: 'Authentication required' });
        return;
      }

      const carer = await this.carerService.getCarerById(authToken, carerId);

      if (!carer || carer.tenantId !== tenantId) {
        res.status(404).json({ success: false, error: 'Carer not found' });
        return;
      }

      res.json({
        success: true,
        data: {
          id: carer.id,
          firstName: carer.first_name,
          lastName: carer.last_name,
          email: carer.email,
          isActive: carer.status === 'active',
          availability: carer.profile?.availability || null,
          maxTravelDistance: carer.profile?.max_travel_distance || null,
          skills: carer.profile?.professional_qualifications || [],
          languages: carer.languages || []
        }
      });

    } catch (error) {
      console.error('getCarerAvailability error:', error);
      res.status(500).json({ success: false, error: 'Failed to retrieve carer availability' });
    }
  };

  /**
   * Create a new carer (for testing/demo purposes)
   */
  createCarer = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user?.tenantId || '4'; // Default for demo

      const carerData = {
        tenantId,
        firstName: req.body.firstName,
        lastName: req.body.lastName,
        email: req.body.email,
        phone: req.body.phone,
        address: req.body.address,
        postcode: req.body.postcode,
        experienceYears: req.body.experienceYears || 0,
        skills: req.body.skills || [],
        isActive: req.body.isActive !== undefined ? req.body.isActive : true,
        maxTravelDistanceMeters: req.body.maxTravelDistanceMeters || 15000
      };

      const carer = await this.prisma.carer.create({
        data: carerData
      });

      logger.info('Carer created successfully', { carerId: carer.id, tenantId });

      res.status(201).json({
        success: true,
        data: carer,
        message: 'Carer created successfully'
      });

    } catch (error) {
      logServiceError('Carer', 'createCarer', error, req.body);
      res.status(500).json({
        success: false,
        error: 'Failed to create carer'
      });
    }
  };

  /**
   * Note: Carer updates and deletion are handled through
   * the auth service sync process. This controller provides
   * limited write access for testing/demo purposes.
   */


}