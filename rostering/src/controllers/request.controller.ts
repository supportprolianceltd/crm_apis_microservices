import { Request, Response } from 'express';
import { z } from 'zod';
import { PrismaClient, RequestStatus, MatchStatus, Prisma } from '@prisma/client';
import { GeocodingService } from '../services/geocoding.service';
import { MatchingService } from '../services/matching.service';
import { ClusteringService } from '../services/clustering.service';
import { ConstraintsService } from '../services/constraints.service';
import { TravelService } from '../services/travel.service';
import { CarerService } from '../services/carer.service';
import { logger, logServiceError } from '../utils/logger';
import { generateUniqueRequestId, generateUniqueVisitId } from '../utils/idGenerator';
import {
  CreateRequestPayload,
  UpdateRequestPayload,
  SearchRequestsQuery,
  PaginatedResponse,
  ExternalRequest
} from '../types';

// Validation schemas (unchanged)
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
  requiredSkills: z.array(z.string()).optional(),
  estimatedDuration: z.number().int().positive().optional(),
  scheduledStartTime: z.string().datetime().optional(),
  scheduledEndTime: z.string().datetime().optional(),
  recurrencePattern: z.string().nullable().optional(),
  notes: z.string().optional(),
  availabilityRequirements: z.any().optional(),
  requestTypes: z.string().optional()
});

const updateRequestSchema = createRequestSchema.partial().omit({}).extend({
  status: z.enum(['PENDING', 'PROCESSING', 'MATCHED', 'APPROVED', 'COMPLETED', 'DECLINED', 'FAILED']).optional(),
  sendToRostering: z.union([z.boolean(), z.string()]).optional()
});

const searchRequestsSchema = z.object({
  status: z.enum(['PENDING', 'PROCESSING', 'MATCHED', 'APPROVED', 'COMPLETED', 'DECLINED', 'FAILED']).optional(),
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
  private clusteringService: ClusteringService;
  private carerService: CarerService;

  constructor(
    prisma: PrismaClient,
    geocodingService: GeocodingService,
    matchingService: MatchingService
  ) {
    this.prisma = prisma;
    this.geocodingService = geocodingService;
    this.matchingService = matchingService;
    this.carerService = new CarerService();
    const constraintsService = new ConstraintsService(prisma);
    const travelService = new TravelService(prisma);
    this.clusteringService = new ClusteringService(prisma, constraintsService, travelService);
  }

  /**
   * Create a new request with creator tracking
   */
// Import the ID generator

  /**
   * Create a new request publicly (no authentication required)
   * Tenant ID is encoded in the request body
   */
  createPublicRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      // Validate request body (same schema as authenticated version)
      const validatedData = createRequestSchema.parse(req.body);

      // Extract tenantId from request body (required for public endpoint)
      const tenantId = req.body.tenantId;
      if (!tenantId || typeof tenantId !== 'string') {
        res.status(400).json({
          success: false,
          error: 'Tenant ID is required in request body'
        });
        return;
      }

      // Generate unique request ID
      const requestId = await generateUniqueRequestId(async (id: string) => {
        const existing = await this.prisma.externalRequest.findUnique({
          where: { id },
          select: { id: true }
        });
        return !!existing;
      });

      // Geocode the address
      const geocoded = await this.geocodingService.geocodeAddress(
        validatedData.address,
        validatedData.postcode
      );

      let clusterId: string | undefined;
      let cluster: any = null;

      // Find or create cluster if we have coordinates
      if (process.env.AUTO_ASSIGN_REQUESTS === 'true' && geocoded?.latitude && geocoded?.longitude) {
        try {
          cluster = await this.clusteringService.findOrCreateClusterForLocation(
            tenantId,
            geocoded.latitude,
            geocoded.longitude
          );
          clusterId = cluster?.id;
        } catch (error) {
          logger.warn('Failed to assign cluster, continuing without cluster', { error });
        }
      }

      // Create the request with public access (no user tracking)
      const createData: any = {
        id: requestId, // Use our custom generated ID
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
        requiredSkills: validatedData.requiredSkills || [],
        estimatedDuration: validatedData.estimatedDuration,
        scheduledStartTime: validatedData.scheduledStartTime ? new Date(validatedData.scheduledStartTime) : undefined,
        scheduledEndTime: validatedData.scheduledEndTime ? new Date(validatedData.scheduledEndTime) : undefined,
        recurrencePattern: validatedData.recurrencePattern,
        notes: validatedData.notes,
        availabilityRequirements: validatedData.availabilityRequirements,
        requestTypes: validatedData.requestTypes,
        status: RequestStatus.PENDING,
        sendToRostering: false
        // Note: No creator tracking for public requests
      };

      // If we have a cluster, connect the relation
      if (clusterId) {
        createData.cluster = { connect: { id: clusterId } };
      }

      const request = await this.prisma.externalRequest.create({
        data: createData
      });

      // Update PostGIS location field using raw SQL
      if (geocoded?.latitude && geocoded?.longitude) {
        try {
          await this.prisma.$executeRaw`
            UPDATE external_requests
            SET location = ST_SetSRID(ST_MakePoint(${geocoded.longitude}, ${geocoded.latitude}), 4326)::geography
            WHERE id = ${request.id}
          `;
        } catch (error) {
          logger.warn('Failed to set PostGIS location', { error, requestId: request.id });
        }
      }

      // Update cluster stats if assigned to a cluster
      if (clusterId) {
        this.clusteringService.updateClusterStats(clusterId).catch(error =>
          logger.warn('Failed to update cluster stats', { error, clusterId })
        );
      }

      // Start auto-matching in the background
      this.matchingService.autoMatchRequest(request.id).catch(error =>
        logServiceError('Request', 'autoMatch', error, { requestId: request.id })
      );

      logger.info(`Created public request: ${request.id}`, {
        tenantId,
        requestId: request.id,
        clusterId: clusterId || 'none',
        clusterName: cluster?.name || 'none'
      });

      res.status(201).json({
        success: true,
        data: request,
        cluster: cluster ? {
          id: cluster.id,
          name: cluster.name,
          location: `${cluster.latitude}, ${cluster.longitude}`
        } : null,
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
      logServiceError('Request', 'createPublicRequest', error, { tenantId: req.body?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to create request',
        message: 'Internal server error'
      });
    }
  };

  /**
   * Create a new request with creator tracking and custom ID
   */
  createRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
    
      // Validate request body
      const validatedData = createRequestSchema.parse(req.body);
      
      // Generate unique request ID
      const requestId = await generateUniqueRequestId(async (id: string) => {
        const existing = await this.prisma.externalRequest.findUnique({
          where: { id },
          select: { id: true }
        });
        return !!existing;
      });
      
      // Geocode the address
      const geocoded = await this.geocodingService.geocodeAddress(
        validatedData.address,
        validatedData.postcode
      );

      let clusterId: string | undefined;
      let cluster: any = null;
      
      // Find or create cluster if we have coordinates
      if (process.env.AUTO_ASSIGN_REQUESTS === 'true' && geocoded?.latitude && geocoded?.longitude) {
        try {
          cluster = await this.clusteringService.findOrCreateClusterForLocation(
            tenantId,
            geocoded.latitude,
            geocoded.longitude
          );
          clusterId = cluster?.id;
        } catch (error) {
          logger.warn('Failed to assign cluster, continuing without cluster', { error });
        }
      }

      // Create the request with creator information and custom ID
      const createData: any = {
        id: requestId, // Use our custom generated ID
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
        requiredSkills: validatedData.requiredSkills || [],
        estimatedDuration: validatedData.estimatedDuration,
        scheduledStartTime: validatedData.scheduledStartTime ? new Date(validatedData.scheduledStartTime) : undefined,
        scheduledEndTime: validatedData.scheduledEndTime ? new Date(validatedData.scheduledEndTime) : undefined,
        recurrencePattern: validatedData.recurrencePattern,
        notes: validatedData.notes,
        availabilityRequirements: validatedData.availabilityRequirements,
        requestTypes: validatedData.requestTypes,
        status: RequestStatus.PENDING,
        sendToRostering: false,
        // Track creator information
        createdBy: user?.id,
        createdByEmail: user?.email,
        createdByFirstName: user?.firstName || user?.first_name,
        createdByLastName: user?.lastName || user?.last_name
      };

      // If we have a cluster, connect the relation
      if (clusterId) {
        createData.cluster = { connect: { id: clusterId } };
      }

      const request = await this.prisma.externalRequest.create({
        data: createData
      });

      // Update PostGIS location field using raw SQL
      if (geocoded?.latitude && geocoded?.longitude) {
        try {
          await this.prisma.$executeRaw`
            UPDATE external_requests
            SET location = ST_SetSRID(ST_MakePoint(${geocoded.longitude}, ${geocoded.latitude}), 4326)::geography
            WHERE id = ${request.id}
          `;
        } catch (error) {
          logger.warn('Failed to set PostGIS location', { error, requestId: request.id });
        }
      }

      // Update cluster stats if assigned to a cluster
      if (clusterId) {
        this.clusteringService.updateClusterStats(clusterId).catch(error =>
          logger.warn('Failed to update cluster stats', { error, clusterId })
        );
      }

      // Start auto-matching in the background
      this.matchingService.autoMatchRequest(request.id).catch(error =>
        logServiceError('Request', 'autoMatch', error, { requestId: request.id })
      );

      logger.info(`Created request: ${request.id}`, {
        tenantId,
        requestId: request.id,
        clusterId: clusterId || 'none',
        clusterName: cluster?.name || 'none',
        createdBy: user?.email
      });

      res.status(201).json({
        success: true,
        data: request,
        cluster: cluster ? {
          id: cluster.id,
          name: cluster.name,
          location: `${cluster.latitude}, ${cluster.longitude}`
        } : null,
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
   * Get requests for current tenant by status
   */
  getRequestsByStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const statusParam = (req.params.status || '').toUpperCase();

      const validStatuses = Object.values(RequestStatus) as string[];
      if (!validStatuses.includes(statusParam)) {
        res.status(400).json({ success: false, error: 'Invalid status', valid: validStatuses });
        return;
      }

      const requests = await this.prisma.externalRequest.findMany({
        where: {
          tenantId,
          status: statusParam as unknown as RequestStatus
        },
        orderBy: { createdAt: 'desc' },
        include: {
          matches: {
            select: {
              id: true,
              status: true,
              matchScore: true,
              distance: true,
              carerId: true
            },
            orderBy: { matchScore: 'desc' },
            take: 5
          }
        }
      });

      // Enrich matches with external carer details
      try {
        const { CarerService } = require('../services/carer.service');
        const carerService = new CarerService();
        const authToken = req.headers?.authorization?.split?.(' ')?.[1];

        await Promise.all(requests.map(async (r: any) => {
          if (!r.matches || r.matches.length === 0) return;
          await Promise.all(r.matches.map(async (m: any) => {
            try {
              const carer = await carerService.getCarerById(authToken, m.carerId);
              m.carer = carer ? {
                id: carer.id,
                email: carer.email,
                firstName: carer.firstName || carer.profile?.firstName,
                lastName: carer.lastName || carer.profile?.lastName
              } : null;
            } catch (err) {
              m.carer = null;
            }
          }));
        }));
      } catch (err) {
        logger.warn('Failed to enrich matches with carer data', { err });
      }

      res.json({ success: true, data: requests });
    } catch (error) {
      logServiceError('Request', 'getRequestsByStatus', error, { status: req.params.status, tenantId: req.user?.tenantId });
      res.status(500).json({ success: false, error: 'Failed to get requests by status' });
    }
  };

  /**
   * Get request by ID
   */
  getRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const requestId = req.params.id;

      const request = await this.prisma.externalRequest.findFirst({
        where: {
          id: requestId,
          tenantId
        },
        include: {
          matches: {
            select: {
              id: true,
              status: true,
              matchScore: true,
              distance: true,
              carerId: true
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

      // Enrich matches with carer details
      try {
        const { CarerService } = require('../services/carer.service');
        const carerService = new CarerService();
        const authToken = req.headers?.authorization?.split?.(' ')?.[1];

        if (request.matches && request.matches.length > 0) {
          await Promise.all(request.matches.map(async (m: any) => {
            try {
              const carer = await carerService.getCarerById(authToken, m.carerId);
              m.carer = carer ? {
                id: carer.id,
                email: carer.email,
                firstName: carer.firstName || carer.profile?.firstName,
                lastName: carer.lastName || carer.profile?.lastName
              } : null;
            } catch (err) {
              m.carer = null;
            }
          }));
        }
      } catch (err) {
        logger.warn('Failed to enrich request matches with carer data', { err });
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
 /**
 * Update request - Fixed to handle missing schema fields gracefully
 */
updateRequest = async (req: Request, res: Response): Promise<void> => {
  try {
    const user = (req as any).user;
    const tenantId = user?.tenantId?.toString();
    const requestId = req.params.id;

    const validatedData = updateRequestSchema.parse(req.body);

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

    const updateData: any = {
      ...validatedData,
      requiredSkills: validatedData.requiredSkills || [],
      scheduledStartTime: validatedData.scheduledStartTime ? new Date(validatedData.scheduledStartTime) : undefined,
      scheduledEndTime: validatedData.scheduledEndTime ? new Date(validatedData.scheduledEndTime) : undefined,
      updatedAt: new Date()
    };

    // Handle sendToRostering flag conversion from string to boolean
    if (typeof validatedData.sendToRostering === 'string') {
      const lower = validatedData.sendToRostering.trim().toLowerCase();
      updateData.sendToRostering = lower === 'true';
    }

    // Only add update tracking if the fields exist in the schema
    // This prevents errors if migrations haven't been run yet
    try {
      updateData.updatedBy = user?.id;
      updateData.updatedByEmail = user?.email;
      updateData.updatedByFirstName = user?.firstName || user?.first_name;
      updateData.updatedByLastName = user?.lastName || user?.last_name;
    } catch (error) {
      // Silently ignore if update tracking fields don't exist yet
      logger.debug('Update tracking fields not available in schema', { error });
    }

    // If address changed, re-geocode
    if (validatedData.address && validatedData.address !== existingRequest.address) {
      const geocoded = await this.geocodingService.geocodeAddress(
        validatedData.address, 
        validatedData.postcode
      );

      if (geocoded) {
        updateData.latitude = geocoded.latitude;
        updateData.longitude = geocoded.longitude;
      }
    }

    const updatedRequest = await this.prisma.externalRequest.update({
      where: { id: requestId },
      data: updateData
    });

    // Update PostGIS location if coordinates changed
    if (validatedData.address && updatedRequest.latitude && updatedRequest.longitude) {
      try {
        await this.prisma.$executeRaw`
          UPDATE external_requests 
          SET location = ST_SetSRID(ST_MakePoint(${updatedRequest.longitude}, ${updatedRequest.latitude}), 4326)::geography
          WHERE id = ${requestId}
        `;
      } catch (error) {
        logger.warn('Failed to update PostGIS location', { error, requestId });
      }
    }

    logger.info(`Updated request: ${requestId}`, { 
      tenantId, 
      requestId,
      updatedBy: user?.email,
      fieldsUpdated: Object.keys(validatedData)
    });

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
      error: 'Failed to update request',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};
  /**
   * List all requests for a tenant
   */
  listRequests = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const page = parseInt(req.query.page as string) || 1;
      const limit = Math.min(parseInt(req.query.limit as string) || 20, 100);
      const skip = (page - 1) * limit;

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
                carerId: true
              },
              orderBy: {
                matchScore: 'desc'
              },
              take: 5
            }
          }
        })
      ]);

      // Enrich results with external carer information
      try {
        const { CarerService } = require('../services/carer.service');
        const carerService = new CarerService();
        const authToken = req.headers?.authorization?.split?.(' ')?.[1];

        await Promise.all(requests.map(async (r: any) => {
          if (!r.matches || r.matches.length === 0) return;
          await Promise.all(r.matches.map(async (m: any) => {
            try {
              const carer = await carerService.getCarerById(authToken, m.carerId);
              m.carer = carer ? {
                id: carer.id,
                email: carer.email,
                firstName: carer.firstName || carer.profile?.firstName,
                lastName: carer.lastName || carer.profile?.lastName
              } : null;
            } catch (err) {
              m.carer = null;
            }
          }));
        }));
      } catch (err) {
        logger.warn('Failed to enrich listRequests matches with carer data', { err });
      }

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
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      
      const validatedQuery = searchRequestsSchema.parse(req.query);

      const page = validatedQuery.page || 1;
      const limit = validatedQuery.limit || 20;
      const skip = (page - 1) * limit;

      const whereClause: any = {
        tenantId,
        ...(validatedQuery.status && { status: validatedQuery.status }),
        ...(validatedQuery.urgency && { urgency: validatedQuery.urgency }),
        ...(validatedQuery.postcode && { postcode: { contains: validatedQuery.postcode, mode: 'insensitive' } }),
        ...(validatedQuery.requestorEmail && { requestorEmail: { contains: validatedQuery.requestorEmail, mode: 'insensitive' } })
      };

      if (validatedQuery.dateFrom || validatedQuery.dateTo) {
        whereClause.createdAt = {};
        if (validatedQuery.dateFrom) {
          whereClause.createdAt.gte = new Date(validatedQuery.dateFrom);
        }
        if (validatedQuery.dateTo) {
          whereClause.createdAt.lte = new Date(validatedQuery.dateTo);
        }
      }

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
              take: 3
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
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const requestId = req.params.id;

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
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const requestId = req.params.id;

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

  /**
   * Approve a request with approver tracking
   */
  approveRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const requestId = req.params.id;

      const existingRequest = await this.prisma.externalRequest.findFirst({
        where: { id: requestId, tenantId }
      });

      if (!existingRequest) {
        res.status(404).json({ success: false, error: 'Request not found' });
        return;
      }

      if (existingRequest.status === RequestStatus.DECLINED || existingRequest.status === RequestStatus.COMPLETED) {
        res.status(400).json({ success: false, error: `Cannot approve a request with status ${existingRequest.status}` });
        return;
      }

      const { sendToRostering } = req.body as { sendToRostering?: boolean | string };

      const updateData: any = {
        status: RequestStatus.APPROVED,
        processedAt: new Date(),
        approvedAt: new Date(),
        updatedAt: new Date(),
        // NEW: Track approver information
        approvedBy: user?.id,
        approvedByEmail: user?.email,
        approvedByFirstName: user?.firstName || user?.first_name,
        approvedByLastName: user?.lastName || user?.last_name
      };

      // Handle sendToRostering flag
      if (typeof sendToRostering === 'boolean') {
        updateData.sendToRostering = sendToRostering;
      } else if (typeof sendToRostering === 'string') {
        const lower = sendToRostering.trim().toLowerCase();
        if (lower === 'true') updateData.sendToRostering = true;
        else if (lower === 'false') updateData.sendToRostering = false;
      }

      const updated = await this.prisma.externalRequest.update({
        where: { id: requestId },
        data: updateData
      });

      // Create a Visit record for the approved request only if it has a scheduled start time
      let visit = null;
      if (existingRequest.scheduledStartTime) {
        // Generate unique visit ID using the visit generator
        const visitId = await generateUniqueVisitId(async (id: string) => {
          const existing = await this.prisma.visit.findUnique({
            where: { id },
            select: { id: true }
          });
          return !!existing;
        });

        visit = await this.prisma.visit.create({
           data: {
             id: visitId, // Use generated readable ID
             tenantId: existingRequest.tenantId,
             externalRequestId: existingRequest.id,
             subject: existingRequest.subject,
             content: existingRequest.content,
             requestorEmail: existingRequest.requestorEmail,
             requestorName: existingRequest.requestorName,
             requestorPhone: existingRequest.requestorPhone,
             address: existingRequest.address,
             postcode: existingRequest.postcode,
             latitude: existingRequest.latitude,
             longitude: existingRequest.longitude,
             scheduledStartTime: existingRequest.scheduledStartTime,
             scheduledEndTime: existingRequest.scheduledEndTime,
             estimatedDuration: existingRequest.estimatedDuration,
             recurrencePattern: (existingRequest as any).recurrencePattern,
             urgency: existingRequest.urgency,
             requirements: existingRequest.requirements,
             requiredSkills: (existingRequest as any).requiredSkills || [],
             notes: existingRequest.notes,
             availabilityRequirements: (existingRequest as any).availabilityRequirements,
             status: 'SCHEDULED',
             clusterId: existingRequest.clusterId,
             createdBy: user?.id,
             createdByEmail: user?.email
           }
         });
      }

      // Kick off matching again in background
      this.matchingService.autoMatchRequest(requestId).catch(error =>
        logServiceError('Request', 'autoMatchAfterApprove', error, { requestId })
      );

      logger.info(`Approved request ${requestId}`, { 
        tenantId, 
        requestId,
        approvedBy: user?.email
      });

      res.json({ 
        success: true, 
        data: updated, 
        message: 'Request approved and set to processing' 
      });

    } catch (error) {
      console.error('Approve request error:', error);
      logServiceError('Request', 'approveRequest', error, { requestId: req.params.id });
      res.status(500).json({ success: false, error: 'Failed to approve request' });
    }
  };


  /**
     * Check request feasibility - which carers can handle this request (WITH BATCHING)
     */
    checkRequestFeasibility = async (req: Request, res: Response): Promise<void> => {
      try {
        const user = (req as any).user;
        const tenantId = user?.tenantId?.toString();
        const requestId = req.params.id;
        const { includeScheduleCheck } = req.query as { includeScheduleCheck?: string };

        const existingRequest = await this.prisma.externalRequest.findFirst({
          where: { id: requestId, tenantId }
        });

        if (!existingRequest) {
          res.status(404).json({ success: false, error: 'Request not found' });
          return;
        }

        if (!existingRequest.scheduledStartTime) {
          res.status(400).json({
            success: false,
            error: 'Request must have scheduled start time for feasibility check'
          });
          return;
        }

        // Get all carers from auth service
        const authToken = req.headers?.authorization?.split?.(' ')?.[1];
        if (!authToken) {
          res.status(401).json({ success: false, error: 'Authorization token required' });
          return;
        }

        let allCarers: any[] = [];
        try {
          logger.info('Fetching carers from auth service');
          allCarers = await this.carerService.getCarers(authToken, tenantId);
          logger.info(`Fetched ${allCarers.length} carers from auth service`);
        } catch (error) {
          logger.error('Failed to fetch carers from auth service', {
            error: error instanceof Error ? error.message : String(error),
            tenantId
          });
          res.status(500).json({
            success: false,
            error: 'Failed to fetch carer data from auth service',
            details: error instanceof Error ? error.message : 'Unknown error'
          });
          return;
        }

        // STEP 1: Pre-filter with cheap checks
        const preFilteredCarers = this.preFilterCarers(allCarers, existingRequest);
        logger.info(`Pre-filtered to ${preFilteredCarers.length} carers from ${allCarers.length} total`);

        // STEP 2: Process in batches to avoid overwhelming the system
        const BATCH_SIZE = 20;
        const eligibleCarers: any[] = [];
        const ineligibleCarers: any[] = [];
        
        for (let i = 0; i < preFilteredCarers.length; i += BATCH_SIZE) {
          const batch = preFilteredCarers.slice(i, i + BATCH_SIZE);
          
          const batchResults = await Promise.all(
            batch.map(carer => this.checkCarerEligibilityWithScore(carer, existingRequest, authToken))
          );
          
          // Separate eligible and ineligible
          batchResults.forEach(result => {
            if (result.overallEligible) {
              eligibleCarers.push(result);
            } else {
              ineligibleCarers.push(result);
            }
          });
          
          // Early exit if we have enough eligible carers (10+)
          if (eligibleCarers.length >= 10) {
            logger.info(`Early exit: Found ${eligibleCarers.length} eligible carers`);
            break;
          }
        }

        // STEP 3: Sort by score
        eligibleCarers.sort((a, b) => b.score - a.score);
        ineligibleCarers.sort((a, b) => b.score - a.score);

        // STEP 4: Collect alternative suggestions
        const alternativeOptions: any[] = [];
        [...eligibleCarers, ...ineligibleCarers].forEach(result => {
          if (result.availability.suggestions && result.availability.suggestions.length > 0) {
            result.availability.suggestions.forEach((suggestion: any) => {
              alternativeOptions.push({
                carerId: result.carerId,
                carerName: result.carerName,
                email: result.email,
                score: result.score,
                skillsMatch: result.skillsMatch,
                day: suggestion.day,
                date: suggestion.date,
                startTime: suggestion.startTime,
                endTime: suggestion.endTime,
                duration: suggestion.duration,
                isPrimaryTime: false
              });
            });
          }
        });

        // Sort alternatives by date and score
        alternativeOptions.sort((a, b) => {
          const dateCompare = a.date.localeCompare(b.date);
          if (dateCompare !== 0) return dateCompare;
          return b.score - a.score;
        });

        res.json({
          success: true,
          data: {
            requestId,
            requestDetails: {
              subject: existingRequest.subject,
              scheduledStartTime: existingRequest.scheduledStartTime,
              scheduledEndTime: existingRequest.scheduledEndTime,
              estimatedDuration: existingRequest.estimatedDuration,
              requiredSkills: (existingRequest as any).requiredSkills || [],
              requirements: existingRequest.requirements
            },
            summary: {
              totalCarers: allCarers.length,
              preFilteredCarers: preFilteredCarers.length,
              eligibleCarers: eligibleCarers.length,
              ineligibleCarers: ineligibleCarers.length,
              alternativeOptions: alternativeOptions.length,
              checkedSchedule: includeScheduleCheck === 'true',
              scoringUsed: true
            },
            eligibleCarers: eligibleCarers.slice(0, 20), // Top 20
            ineligibleCarers: ineligibleCarers.slice(0, 10), // Top 10 ineligible
            alternativeOptions: alternativeOptions.slice(0, 20) // Top 20 alternatives
          },
          message: `Found ${eligibleCarers.length} eligible carers with scores (max 100 points). Pre-filtered ${allCarers.length} to ${preFilteredCarers.length} candidates.`
        });

      } catch (error) {
        logServiceError('Request', 'checkRequestFeasibility', error, { requestId: req.params.id });
        res.status(500).json({
          success: false,
          error: 'Failed to check request feasibility'
        });
      }
    };

  /**
   * Helper method to check if carer skills match requirements
   */
  private checkSkillsMatch(carerSkills: any[], requiredSkills: string[], requirements: string) {
    // Extract skill names from skill_details objects or handle string arrays for backward compatibility
    const carerSkillNames = carerSkills.map(skill =>
      typeof skill === 'string' ? skill : skill.skill_name || ''
    ).filter(name => name.trim() !== '');

    const carerSkillsLower = carerSkillNames.map(s => s.toLowerCase());
    const requiredSkillsLower = requiredSkills.map(s => s.toLowerCase());
    const requirementsLower = requirements.toLowerCase();

    // Check required skills
    const missingSkills = requiredSkillsLower.filter(skill =>
      !carerSkillsLower.some(carerSkill => carerSkill.includes(skill) || skill.includes(carerSkill))
    );

    const matchingSkills = requiredSkillsLower.filter(skill =>
      carerSkillsLower.some(carerSkill => carerSkill.includes(skill) || skill.includes(carerSkill))
    );

    // Check requirements text for skill keywords
    const skillKeywords = [
      'personal care', 'medication', 'mobility', 'dementia', 'complex care',
      'hoist', 'peg feeding', 'catheter', 'stoma', 'diabetes',
      'parkinson', 'stroke', 'palliative', 'respite', 'companionship'
    ];

    const requirementsMatch = skillKeywords.some(keyword =>
      requirementsLower.includes(keyword) &&
      carerSkillsLower.some(carerSkill => carerSkill.includes(keyword))
    );

    // Relaxed matching: require at least one skill match if skills are required, otherwise allow if no requirements
    const hasSomeRequired = requiredSkills.length === 0 || matchingSkills.length > 0;

    return {
      hasSomeRequired,
      missingSkills,
      matchingSkills,
      requirementsMatch: !requirements || requirementsMatch
    };
  }

  /**
   * Helper method to check basic availability (time windows)
   */
  private checkBasicAvailability(carer: any, requestStart: Date, requestEnd: Date) {
    // This is a simplified check - in reality you'd check against working hours
    // For now, assume carers are available during typical working hours
    const requestHour = requestStart.getHours();
    const isWorkingHour = requestHour >= 8 && requestHour <= 18; // 8 AM to 6 PM

    // Check for obvious conflicts (this is simplified)
    const conflicts = [];
    if (!isWorkingHour) {
      conflicts.push(`Request time (${requestHour}:00) is outside typical working hours (8:00-18:00)`);
    }

    // Check if it's a weekend (simplified)
    const dayOfWeek = requestStart.getDay();
    if (dayOfWeek === 0 || dayOfWeek === 6) {
      conflicts.push('Request is on a weekend');
    }

    return {
      isAvailable: conflicts.length === 0,
      conflicts
    };
  }

  /**
   * Helper method to check for schedule conflicts with existing assignments
   */
  private checkScheduleConflicts(existingAssignments: any[], requestStart: Date, requestEnd: Date) {
    const conflicts = [];

    for (const assignment of existingAssignments) {
      const assignmentStart = new Date(assignment.scheduledTime);
      const assignmentEnd = new Date(assignment.estimatedEndTime);

      // Check for overlap
      if (requestStart < assignmentEnd && requestEnd > assignmentStart) {
        conflicts.push({
          assignmentId: assignment.id,
          visitId: assignment.visitId,
          conflictStart: assignmentStart,
          conflictEnd: assignmentEnd,
          overlapMinutes: Math.min(requestEnd.getTime(), assignmentEnd.getTime()) -
                         Math.max(requestStart.getTime(), assignmentStart.getTime())
        });
      }
    }

    return conflicts;
  }


  /**
   * Check if carer is employed during the request time
   */
  private checkEmploymentStatus(carer: any, requestTime: Date): { isEmployed: boolean; reason: string } {
    const employmentDetails = carer.profile?.employment_details || [];
    if (employmentDetails.length === 0) {
      return { isEmployed: true, reason: '' }; // Assume employed if no details
    }

    for (const employment of employmentDetails) {
      const startDate = employment.employment_start_date ? new Date(employment.employment_start_date) : null;
      const endDate = employment.employment_end_date ? new Date(employment.employment_end_date) : null;

      // Check if request time is within employment period
      const isAfterStart = !startDate || requestTime >= startDate;
      const isBeforeEnd = !endDate || requestTime <= endDate;

      if (isAfterStart && isBeforeEnd) {
        return { isEmployed: true, reason: '' };
      }
    }

    return {
      isEmployed: false,
      reason: `Not employed during request time (${requestTime.toISOString().split('T')[0]})`
    };
  }

  /**
   * Check carer availability based on profile availability data and suggest alternatives
   */
  private checkCarerAvailability(carer: any, requestStart: Date, requestEnd: Date, availabilityRequirements?: any) {
    const carerAvailability = carer.profile?.availability || {};

    // Get the day of the week for the request
    const daysOfWeek = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const requestDay = daysOfWeek[requestStart.getDay()].toLowerCase();

    // Check if carer has availability for this day
    const dayAvailability = carerAvailability[requestDay];
    const hasAvailabilityForRequestDay = !!dayAvailability;

    let isAvailable = false;
    const conflicts: string[] = [];
    const suggestions: any[] = [];

    // Check primary availability match
    if (hasAvailabilityForRequestDay) {
      const availabilityResult = this.checkSpecificDayAvailability(dayAvailability, requestStart, requestEnd, requestDay);
      isAvailable = availabilityResult.isAvailable;
      if (!isAvailable) {
        conflicts.push(...availabilityResult.conflicts);
      }
    } else {
      conflicts.push(`No availability configured for ${requestDay}`);
    }

    // Generate suggestions for other available days
    const requestDurationHours = (requestEnd.getTime() - requestStart.getTime()) / (1000 * 60 * 60);

    for (const [dayName, dayAvail] of Object.entries(carerAvailability)) {
      if (!dayAvail || dayName === requestDay) continue;

      try {
        const suggestion = this.generateTimeSuggestion(dayAvail, dayName, requestDurationHours, requestStart);
        if (suggestion) {
          suggestions.push(suggestion);
        }
      } catch (error) {
        // Skip invalid availability formats
        continue;
      }
    }

    return {
      isAvailable,
      conflicts,
      suggestions: suggestions.slice(0, 3), // Limit to top 3 suggestions
      availableHours: carerAvailability
    };
  }

  /**
   * Check availability for a specific day
   */
  private checkSpecificDayAvailability(dayAvailability: any, requestStart: Date, requestEnd: Date, requestDay: string) {
    // Handle new object format: { start: "08:00", end: "14:00", available: true }
    if (typeof dayAvailability === 'object' && dayAvailability.available !== false) {
      const startTime = dayAvailability.start;
      const endTime = dayAvailability.end;

      if (!startTime || !endTime) {
        return {
          isAvailable: false,
          conflicts: [`Invalid availability object for ${requestDay}: missing start or end time`]
        };
      }

      // Parse time strings (e.g., "08:00", "14:00")
      const [startHourStr, startMinStr] = startTime.split(':');
      const [endHourStr, endMinStr] = endTime.split(':');

      const startHour24 = parseInt(startHourStr);
      const endHour24 = parseInt(endHourStr);

      if (isNaN(startHour24) || isNaN(endHour24)) {
        return {
          isAvailable: false,
          conflicts: [`Invalid time format for ${requestDay}: ${startTime} - ${endTime}`]
        };
      }

      // Get request times in hours (ignore minutes for simplicity)
      const requestStartHour = requestStart.getHours();
      const requestEndHour = requestEnd.getHours();

      // Check if request falls within availability
      const isAvailable = requestStartHour >= startHour24 && requestEndHour <= endHour24;

      const conflicts = [];
      if (!isAvailable) {
        conflicts.push(`Request time (${requestStartHour}:00-${requestEndHour}:00) is outside carer availability (${startHour24}:00-${endHour24}:00) on ${requestDay}`);
      }

      return { isAvailable, conflicts };
    }

    // Fallback: Handle old string format (e.g., "8am-6pm") for backward compatibility
    if (typeof dayAvailability === 'string') {
      const timeRangeMatch = dayAvailability.match(/(\d+)(am|pm)-(\d+)(am|pm)/i);
      if (!timeRangeMatch) {
        return {
          isAvailable: false,
          conflicts: [`Invalid availability format for ${requestDay}: ${dayAvailability}`]
        };
      }

      const [, startHour, startPeriod, endHour, endPeriod] = timeRangeMatch;
      let startHour24 = parseInt(startHour);
      let endHour24 = parseInt(endHour);

      // Convert to 24-hour format
      if (startPeriod.toLowerCase() === 'pm' && startHour24 !== 12) startHour24 += 12;
      if (startPeriod.toLowerCase() === 'am' && startHour24 === 12) startHour24 = 0;
      if (endPeriod.toLowerCase() === 'pm' && endHour24 !== 12) endHour24 += 12;
      if (endPeriod.toLowerCase() === 'am' && endHour24 === 12) endHour24 = 0;

      // Get request times in hours
      const requestStartHour = requestStart.getHours();
      const requestEndHour = requestEnd.getHours();

      // Check if request falls within availability
      const isAvailable = requestStartHour >= startHour24 && requestEndHour <= endHour24;

      const conflicts = [];
      if (!isAvailable) {
        conflicts.push(`Request time (${requestStartHour}:00-${requestEndHour}:00) is outside carer availability (${startHour24}:00-${endHour24}:00) on ${requestDay}`);
      }

      return { isAvailable, conflicts };
    }

    // If neither object nor string format
    return {
      isAvailable: false,
      conflicts: [`Unsupported availability format for ${requestDay}`]
    };
  }

  /**
   * Generate time suggestions based on carer's availability
   */
  private generateTimeSuggestion(dayAvailability: any, dayName: string, requestDurationHours: number, originalRequestStart: Date) {
    let startHour24: number, endHour24: number;

    // Parse availability based on format
    if (typeof dayAvailability === 'object' && dayAvailability.available !== false) {
      const [startHourStr] = (dayAvailability.start || '').split(':');
      const [endHourStr] = (dayAvailability.end || '').split(':');
      startHour24 = parseInt(startHourStr);
      endHour24 = parseInt(endHourStr);
    } else if (typeof dayAvailability === 'string') {
      const timeRangeMatch = dayAvailability.match(/(\d+)(am|pm)-(\d+)(am|pm)/i);
      if (!timeRangeMatch) return null;

      const [, startHour, startPeriod, endHour, endPeriod] = timeRangeMatch;
      startHour24 = parseInt(startHour);
      endHour24 = parseInt(endHour);

      // Convert to 24-hour format
      if (startPeriod.toLowerCase() === 'pm' && startHour24 !== 12) startHour24 += 12;
      if (startPeriod.toLowerCase() === 'am' && startHour24 === 12) startHour24 = 0;
      if (endPeriod.toLowerCase() === 'pm' && endHour24 !== 12) endHour24 += 12;
      if (endPeriod.toLowerCase() === 'am' && endHour24 === 12) endHour24 = 0;
    } else {
      return null;
    }

    if (isNaN(startHour24) || isNaN(endHour24)) return null;

    // Calculate available duration
    const availableDuration = endHour24 - startHour24;
    if (availableDuration < requestDurationHours) return null; // Not enough time

    // Find the next occurrence of this day
    const daysOfWeek = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const targetDayIndex = daysOfWeek.indexOf(dayName);
    const currentDayIndex = originalRequestStart.getDay();

    let daysAhead = targetDayIndex - currentDayIndex;
    if (daysAhead <= 0) daysAhead += 7; // Next week if same day or past

    const suggestedDate = new Date(originalRequestStart);
    suggestedDate.setDate(suggestedDate.getDate() + daysAhead);

    // Suggest the earliest possible time in their availability window
    const suggestedStart = new Date(suggestedDate);
    suggestedStart.setHours(startHour24, 0, 0, 0);

    const suggestedEnd = new Date(suggestedStart);
    suggestedEnd.setHours(suggestedStart.getHours() + requestDurationHours);

    // Make sure it fits within their availability
    if (suggestedEnd.getHours() > endHour24) {
      suggestedStart.setHours(endHour24 - requestDurationHours, 0, 0, 0);
      suggestedEnd.setHours(endHour24, 0, 0, 0);
    }

    return {
      day: dayName,
      date: suggestedDate.toISOString().split('T')[0],
      startTime: `${suggestedStart.getHours().toString().padStart(2, '0')}:00`,
      endTime: `${suggestedEnd.getHours().toString().padStart(2, '0')}:00`,
      duration: requestDurationHours
    };
  }

  /**
    * Decline a request
    */
  declineRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const requestId = req.params.id;

      const existingRequest = await this.prisma.externalRequest.findFirst({
        where: { id: requestId, tenantId }
      });

      if (!existingRequest) {
        res.status(404).json({ success: false, error: 'Request not found' });
        return;
      }

      if (existingRequest.status === RequestStatus.DECLINED || existingRequest.status === RequestStatus.COMPLETED) {
        res.status(400).json({ success: false, error: `Cannot decline a request with status ${existingRequest.status}` });
        return;
      }

      const { reason } = req.body as { reason?: string };

      const updated = await this.prisma.$transaction(async (tx: Prisma.TransactionClient) => {
        await tx.requestCarerMatch.updateMany({
          where: { requestId },
          data: { status: MatchStatus.DECLINED }
        });

        const notes = [existingRequest.notes, reason ? `Decline reason: ${reason}` : null].filter(Boolean).join('\n');

        const u = await tx.externalRequest.update({
          where: { id: requestId },
          data: {
            status: RequestStatus.DECLINED,
            processedAt: new Date(),
            notes: notes || undefined,
            updatedAt: new Date()
          }
        });

        return u;
      });

      logger.info(`Declined request ${requestId}`, { tenantId, requestId });

      res.json({ success: true, data: updated, message: 'Request declined and cancelled' });

    } catch (error) {
      logServiceError('Request', 'declineRequest', error, { requestId: req.params.id });
      res.status(500).json({ success: false, error: 'Failed to decline request' });
    }
  };

  /**
 * Pre-filter carers with cheap checks before detailed eligibility
 */
private preFilterCarers(carers: any[], visit: any): any[] {
  return carers.filter(carer => {
    // 1. Quick employment check
    const employmentCheck = this.checkEmploymentStatus(carer, visit.scheduledStartTime);
    if (!employmentCheck.isEmployed) {
      return false;
    }
    
    // 2. Quick geographic check (if cluster-based)
    if (visit.clusterId && carer.profile?.clusterId) {
      // Only include carers from same or nearby clusters
      // For now, we'll be permissive since we don't have distance data
      // In production, you'd check cluster distance here
      return true;
    }
    
    return true;
  });
}

/**
 * Check individual carer eligibility with scoring
 */
private async checkCarerEligibilityWithScore(
  carer: any, 
  visit: any,
  authToken: string
): Promise<any> {
  let score = 0;
  
  // 0. Employment status (blocking)
  const employmentCheck = this.checkEmploymentStatus(carer, visit.scheduledStartTime);
  if (!employmentCheck.isEmployed) {
    return {
      carerId: carer.id,
      carerName: `${carer.first_name || 'Unknown'} ${carer.last_name || 'Carer'}`,
      email: carer.email,
      overallEligible: false,
      score: 0,
      employment: employmentCheck,
      skillsMatch: { hasSomeRequired: false, missingSkills: [], matchingSkills: [], requirementsMatch: false },
      availability: { isAvailable: false, conflicts: ['Not employed during visit time'], suggestions: [] }
    };
  }
  
  // 1. Skills match (40 points)
  const carerSkills = carer.profile?.skill_details || [];
  const requiredSkills = (visit as any).requiredSkills || [];
  const requirements = visit.requirements || '';
  const skillsMatch = this.checkSkillsMatch(carerSkills, requiredSkills, requirements);
  
  if (skillsMatch.hasSomeRequired) {
    score += 40;
  }
  
  // 2. Availability check (20 points)
  const requestStartTime = visit.scheduledStartTime!;
  const requestEndTime = visit.scheduledEndTime ||
    new Date(requestStartTime.getTime() + (visit.estimatedDuration || 60) * 60 * 1000);
  const availabilityRequirements = (visit as any).availabilityRequirements;
  
  const availabilityCheck = this.checkCarerAvailability(
    carer,
    requestStartTime,
    requestEndTime,
    availabilityRequirements
  );
  
  if (availabilityCheck.isAvailable) {
    score += 20;
  }
  
  // 3. Cluster proximity (15 points)
  let clusterBonus = 0;
  if (visit.clusterId && carer.profile?.clusterId) {
    if (visit.clusterId === carer.profile.clusterId) {
      clusterBonus = 15; // Same cluster
      score += clusterBonus;
    }
    // TODO: Add nearby cluster bonus using cluster distance calculation
  }
  
  // 4. Continuity of care (10 points) - check if carer has served this client before
  const continuityBonus = await this.calculateContinuityBonus(carer.id, visit);
  score += continuityBonus;
  
  // 5. Workload balancing (deduct up to 20 points for overload)
  const weeklyHours = await this.getCarerWeeklyHours(carer.id, visit.scheduledStartTime);
  const workloadPenalty = this.calculateWorkloadPenalty(weeklyHours);
  score -= workloadPenalty;
  
  const overallEligible = employmentCheck.isEmployed && 
                          skillsMatch.hasSomeRequired && 
                          availabilityCheck.isAvailable;
  
  return {
    carerId: carer.id,
    carerName: `${carer.first_name || 'Unknown'} ${carer.last_name || 'Carer'}`,
    email: carer.email,
    employment: employmentCheck,
    skills: carerSkills,
    skillsMatch,
    availability: availabilityCheck,
    cluster: {
      carerId: carer.id,
      carerClusterId: carer.profile?.clusterId,
      visitClusterId: visit.clusterId,
      sameCluster: visit.clusterId === carer.profile?.clusterId,
      bonus: clusterBonus
    },
    continuity: {
      bonus: continuityBonus,
      previousVisits: continuityBonus > 0 ? Math.floor(continuityBonus / 5) : 0
    },
    workload: {
      currentWeeklyHours: weeklyHours,
      utilizationPercent: (weeklyHours / 48) * 100,
      penalty: workloadPenalty
    },
    score,
    overallEligible
  };
}

/**
 * Calculate continuity bonus - carers who have served this client before
 */
private async calculateContinuityBonus(carerId: string, visit: any): Promise<number> {
  try {
    // Check if carer has completed visits for this client before
    const previousVisits = await this.prisma.visit.count({
      where: {
        assignedCarerId: carerId,
        requestorEmail: visit.requestorEmail,
        status: 'COMPLETED'
      }
    });
    
    if (previousVisits > 0) {
      return Math.min(previousVisits * 5, 20); // Max 20 points for continuity
    }
  } catch (error) {
    logger.warn('Failed to calculate continuity bonus', { error, carerId, visitId: visit.id });
  }
  
  return 0;
}

/**
 * Get carer's weekly hours
 */
private async getCarerWeeklyHours(carerId: string, referenceDate: Date): Promise<number> {
  try {
    const weekStart = this.getWeekStart(referenceDate);
    const weekEnd = new Date(weekStart.getTime() + 7 * 24 * 60 * 60 * 1000);
    
    const assignments = await this.prisma.assignment.findMany({
      where: {
        carerId,
        scheduledTime: { gte: weekStart, lt: weekEnd },
        status: { in: ['ACCEPTED', 'COMPLETED'] }
      },
      include: { visit: true }
    });
    
    return assignments.reduce((total, a) => {
      return total + ((a.visit.estimatedDuration || 60) / 60);
    }, 0);
  } catch (error) {
    logger.warn('Failed to get carer weekly hours', { error, carerId });
    return 0;
  }
}

/**
 * Get start of week for a given date
 */
private getWeekStart(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
  return new Date(d.setDate(diff));
}

/**
 * Calculate workload penalty based on weekly hours
 */
private calculateWorkloadPenalty(weeklyHours: number): number {
  if (weeklyHours >= 45) return 20; // Near WTD limit
  if (weeklyHours >= 40) return 10; // High workload
  if (weeklyHours >= 35) return 5;  // Moderate workload
  return 0; // Low workload - no penalty
}
}