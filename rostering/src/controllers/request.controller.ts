import { Request, Response } from 'express';
import { z } from 'zod';
import { PrismaClient } from '@prisma/client';
import { GeocodingService } from '../services/geocoding.service';
import { MatchingService } from '../services/matching.service';
import { logger, logServiceError } from '../utils/logger';
import { 
  CreateRequestPayload, 
  UpdateRequestPayload, 
  SearchRequestsQuery,
  PaginatedResponse,
  ExternalRequest
} from '../types';

// Validation schemas
const createRequestSchema = z.object({
  subject: z.string().min(1, 'Subject is required'),
  content: z.string().min(1, 'Content is required'),
  requestorEmail: z.string().email('Valid email is required'),
  requestorName: z.string().optional(),
  requestorPhone: z.string().optional(),
  address: z.string().min(1, 'Address is required'),
  postcode: z.string().optional(),
  urgency: z.enum(['LOW', 'MEDIUM', 'HIGH', 'URGENT']).optional(),
  requirements: z.string().optional(),
  estimatedDuration: z.number().int().positive().optional(),
  scheduledStartTime: z.string().datetime().optional(),
  scheduledEndTime: z.string().datetime().optional(),
  notes: z.string().optional()
});

const updateRequestSchema = createRequestSchema.partial().omit({ 
  subject: true, 
  content: true, 
  requestorEmail: true 
}).extend({
  status: z.enum(['PENDING', 'PROCESSING', 'MATCHED', 'ASSIGNED', 'COMPLETED', 'CANCELLED', 'FAILED']).optional()
});

const searchRequestsSchema = z.object({
  status: z.enum(['PENDING', 'PROCESSING', 'MATCHED', 'ASSIGNED', 'COMPLETED', 'CANCELLED', 'FAILED']).optional(),
  urgency: z.enum(['LOW', 'MEDIUM', 'HIGH', 'URGENT']).optional(),
  postcode: z.string().optional(),
  dateFrom: z.string().datetime().optional(),
  dateTo: z.string().datetime().optional(),
  requestorEmail: z.string().email().optional(),
  page: z.number().int().positive().optional(),
  limit: z.number().int().positive().max(100).optional()
});

export class RequestController {
  private prisma: PrismaClient;
  private geocodingService: GeocodingService;
  private matchingService: MatchingService;

  constructor(
    prisma: PrismaClient, 
    geocodingService: GeocodingService, 
    matchingService: MatchingService
  ) {
    this.prisma = prisma;
    this.geocodingService = geocodingService;
    this.matchingService = matchingService;
  }

  /**
   * Create a new request
   */
  createRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      
      // Validate request body
      const validatedData = createRequestSchema.parse(req.body);

      // Geocode the address
      const geocoded = await this.geocodingService.geocodeAddress(
        validatedData.address, 
        validatedData.postcode
      );

      // Create the request
      const request = await this.prisma.externalRequest.create({
        data: {
          tenantId,
          subject: validatedData.subject,
          content: validatedData.content,
          requestorEmail: validatedData.requestorEmail,
          requestorName: validatedData.requestorName,
          requestorPhone: validatedData.requestorPhone,
          address: validatedData.address,
          postcode: validatedData.postcode || '',
          latitude: geocoded?.latitude,
          longitude: geocoded?.longitude,
          urgency: validatedData.urgency || 'MEDIUM',
          requirements: validatedData.requirements,
          estimatedDuration: validatedData.estimatedDuration,
          scheduledStartTime: validatedData.scheduledStartTime ? new Date(validatedData.scheduledStartTime) : undefined,
          scheduledEndTime: validatedData.scheduledEndTime ? new Date(validatedData.scheduledEndTime) : undefined,
          notes: validatedData.notes,
          status: 'PENDING'
        }
      });

      // Start auto-matching in the background
      this.matchingService.autoMatchRequest(request.id).catch(error => 
        logServiceError('Request', 'autoMatch', error, { requestId: request.id })
      );

      logger.info(`Created request: ${request.id}`, { tenantId, requestId: request.id });

      res.status(201).json({
        success: true,
        data: request,
        message: 'Request created successfully'
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

      logServiceError('Request', 'createRequest', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to create request',
        message: 'Internal server error'
      });
    }
  };

  /**
   * Get request by ID
   */
  getRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const requestId = req.params.id;

      const request = await this.prisma.externalRequest.findFirst({
        where: {
          id: requestId,
          tenantId
        },
        include: {
          matches: {
            include: {
              carer: true
            },
            orderBy: {
              matchScore: 'desc'
            }
          }
        }
      });

      if (!request) {
        res.status(404).json({
          success: false,
          error: 'Request not found'
        });
        return;
      }

      res.json({
        success: true,
        data: request
      });

    } catch (error) {
      logServiceError('Request', 'getRequest', error, { requestId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve request'
      });
    }
  };

  /**
   * Update request
   */
  updateRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const requestId = req.params.id;

      // Validate request body
      const validatedData = updateRequestSchema.parse(req.body);

      // Check if request exists and belongs to tenant
      const existingRequest = await this.prisma.externalRequest.findFirst({
        where: {
          id: requestId,
          tenantId
        }
      });

      if (!existingRequest) {
        res.status(404).json({
          success: false,
          error: 'Request not found'
        });
        return;
      }

      // Prepare update data
      const updateData: any = {
        ...validatedData,
        scheduledStartTime: validatedData.scheduledStartTime ? new Date(validatedData.scheduledStartTime) : undefined,
        scheduledEndTime: validatedData.scheduledEndTime ? new Date(validatedData.scheduledEndTime) : undefined,
        updatedAt: new Date()
      };

      // If address changed, re-geocode
      if (validatedData.address && validatedData.address !== existingRequest.address) {
        const geocoded = await this.geocodingService.geocodeAddress(
          validatedData.address, 
          validatedData.postcode
        );

        if (geocoded) {
          updateData.latitude = geocoded.latitude;
          updateData.longitude = geocoded.longitude;
          updateData.location = `POINT(${geocoded.longitude} ${geocoded.latitude})`;
        }
      }

      // Update the request
      const updatedRequest = await this.prisma.externalRequest.update({
        where: { id: requestId },
        data: updateData
      });

      logger.info(`Updated request: ${requestId}`, { tenantId, requestId });

      res.json({
        success: true,
        data: updatedRequest,
        message: 'Request updated successfully'
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

      logServiceError('Request', 'updateRequest', error, { requestId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to update request'
      });
    }
  };

  /**
   * List all requests for a tenant (simplified version of searchRequests)
   */
  listRequests = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const page = parseInt(req.query.page as string) || 1;
      const limit = Math.min(parseInt(req.query.limit as string) || 20, 100);
      const skip = (page - 1) * limit;

      // Get total count and data
      const [total, requests] = await Promise.all([
        this.prisma.externalRequest.count({ where: { tenantId } }),
        this.prisma.externalRequest.findMany({
          where: { tenantId },
          skip,
          take: limit,
          orderBy: {
            createdAt: 'desc'
          },
          include: {
            matches: {
              select: {
                id: true,
                status: true,
                matchScore: true,
                distance: true,
                carer: {
                  select: {
                    id: true,
                    email: true,
                    firstName: true,
                    lastName: true
                  }
                }
              },
              orderBy: {
                matchScore: 'desc'
              },
              take: 5 // Show top 5 matches
            }
          }
        })
      ]);

      const totalPages = Math.ceil(total / limit);

      const response: PaginatedResponse<ExternalRequest> = {
        data: requests as any,
        pagination: {
          page,
          limit,
          total,
          pages: totalPages,
          hasNext: page < totalPages,
          hasPrev: page > 1
        }
      };

      res.json(response);

    } catch (error) {
      logServiceError('RequestController', 'listRequests', error, { 
        tenantId: req.user?.tenantId 
      });
      res.status(500).json({
        success: false,
        error: 'Failed to list requests',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  };

  /**
   * Search requests with pagination
   */
  searchRequests = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      
      // Validate query parameters
      const validatedQuery = searchRequestsSchema.parse(req.query);

      const page = validatedQuery.page || 1;
      const limit = validatedQuery.limit || 20;
      const skip = (page - 1) * limit;

      // Build where clause
      const whereClause: any = {
        tenantId,
        ...(validatedQuery.status && { status: validatedQuery.status }),
        ...(validatedQuery.urgency && { urgency: validatedQuery.urgency }),
        ...(validatedQuery.postcode && { postcode: { contains: validatedQuery.postcode, mode: 'insensitive' } }),
        ...(validatedQuery.requestorEmail && { requestorEmail: { contains: validatedQuery.requestorEmail, mode: 'insensitive' } })
      };

      // Add date filtering
      if (validatedQuery.dateFrom || validatedQuery.dateTo) {
        whereClause.createdAt = {};
        if (validatedQuery.dateFrom) {
          whereClause.createdAt.gte = new Date(validatedQuery.dateFrom);
        }
        if (validatedQuery.dateTo) {
          whereClause.createdAt.lte = new Date(validatedQuery.dateTo);
        }
      }

      // Get total count and data
      const [total, requests] = await Promise.all([
        this.prisma.externalRequest.count({ where: whereClause }),
        this.prisma.externalRequest.findMany({
          where: whereClause,
          skip,
          take: limit,
          orderBy: {
            createdAt: 'desc'
          },
          include: {
            matches: {
              select: {
                id: true,
                status: true,
                matchScore: true,
                distance: true
              },
              orderBy: {
                matchScore: 'desc'
              },
              take: 3 // Only include top 3 matches in list view
            }
          }
        })
      ]);

      const totalPages = Math.ceil(total / limit);

      const response: PaginatedResponse<ExternalRequest> = {
        data: requests as ExternalRequest[],
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

      logServiceError('Request', 'searchRequests', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to search requests'
      });
    }
  };

  /**
   * Delete request
   */
  deleteRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const requestId = req.params.id;

      // Check if request exists and belongs to tenant
      const existingRequest = await this.prisma.externalRequest.findFirst({
        where: {
          id: requestId,
          tenantId
        }
      });

      if (!existingRequest) {
        res.status(404).json({
          success: false,
          error: 'Request not found'
        });
        return;
      }

      // Delete the request (cascades to matches)
      await this.prisma.externalRequest.delete({
        where: { id: requestId }
      });

      logger.info(`Deleted request: ${requestId}`, { tenantId, requestId });

      res.json({
        success: true,
        message: 'Request deleted successfully'
      });

    } catch (error) {
      logServiceError('Request', 'deleteRequest', error, { requestId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to delete request'
      });
    }
  };

  /**
   * Trigger manual matching for a request
   */
  triggerMatching = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId.toString();
      const requestId = req.params.id;

      // Check if request exists and belongs to tenant
      const existingRequest = await this.prisma.externalRequest.findFirst({
        where: {
          id: requestId,
          tenantId
        }
      });

      if (!existingRequest) {
        res.status(404).json({
          success: false,
          error: 'Request not found'
        });
        return;
      }

      // Trigger matching
      const success = await this.matchingService.autoMatchRequest(requestId);

      if (success) {
        res.json({
          success: true,
          message: 'Matching completed successfully'
        });
      } else {
        res.status(400).json({
          success: false,
          error: 'No matches found or matching failed'
        });
      }

    } catch (error) {
      logServiceError('Request', 'triggerMatching', error, { requestId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to trigger matching'
      });
    }
  };
}