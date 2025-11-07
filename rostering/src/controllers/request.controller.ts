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
  availabilityRequirements: z.any().optional()
});

const updateRequestSchema = createRequestSchema.partial().omit({}).extend({
  status: z.enum(['PENDING', 'PROCESSING', 'MATCHED', 'APPROVED', 'COMPLETED', 'DECLINED', 'FAILED']).optional()
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
        updatedAt: new Date(),
        // NEW: Track updater information
        updatedBy: user?.id,
        updatedByEmail: user?.email,
        updatedByFirstName: user?.firstName || user?.first_name,
        updatedByLastName: user?.lastName || user?.last_name
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
   * Check request feasibility - which carers can handle this request
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

      // Get all carers from auth service using CarerService
      const authToken = req.headers?.authorization?.split?.(' ')?.[1];
      if (!authToken) {
        res.status(401).json({ success: false, error: 'Authorization token required' });
        return;
      }

      let allCarers: any[] = [];
      try {
        logger.info('Fetching carers from auth service');

        // Get carers directly from auth service using CarerService
        allCarers = await this.carerService.getCarers(authToken, tenantId);

        logger.info(`Fetched ${allCarers.length} carers from auth service`);
      } catch (error) {
        logger.error('Failed to fetch carers from auth service', {
          error: error instanceof Error ? error.message : String(error),
          tenantId,
          hasAuthToken: !!authToken
        });
        res.status(500).json({
          success: false,
          error: 'Failed to fetch carer data from auth service',
          details: error instanceof Error ? error.message : 'Unknown error'
        });
        return;
      }

      const requiredSkills = (existingRequest as any).requiredSkills || [];
      const requirements = existingRequest.requirements || '';

      // Ensure we have valid dates (already checked above but TypeScript needs reassurance)
      const requestStartTime = existingRequest.scheduledStartTime!;
      const requestEndTime = existingRequest.scheduledEndTime ||
        new Date(requestStartTime.getTime() + (existingRequest.estimatedDuration || 60) * 60 * 1000);

      // Check each carer for skills match and availability
      const feasibilityResults = await Promise.all(
        allCarers.map(async (carer) => {
          // 1. Check skills match using carer skills from profile
          const carerSkills = carer.profile?.skill_details || [];
          const skillsMatch = this.checkSkillsMatch(carerSkills, requiredSkills, requirements);

          // 2. Check availability based on profile availability
          const availabilityCheck = this.checkCarerAvailability(
            carer,
            requestStartTime,
            requestEndTime
          );

          // 3. Optional: Advanced scheduling check using existing assignments
          // Note: Schedule conflicts check is not available when using external carer API
          let scheduleConflicts: any[] = [];
          if (includeScheduleCheck === 'true') {
            // Since we're using external carer API, we don't have assignment data
            // This would need to be implemented by calling another API endpoint
            scheduleConflicts = [];
          }

          return {
            carerId: carer.id,
            carerName: `${carer.first_name || 'Unknown'} ${carer.last_name || 'Carer'}`,
            email: carer.email,
            skills: carer.profile?.skill_details || [], // Skills from carer profile
            skillsMatch: {
              hasRequiredSkills: skillsMatch.hasSomeRequired,
              missingSkills: skillsMatch.missingSkills,
              matchingSkills: skillsMatch.matchingSkills,
              requirementsMatch: skillsMatch.requirementsMatch
            },
            availability: {
              isAvailable: availabilityCheck.isAvailable,
              conflicts: availabilityCheck.conflicts,
              availableHours: carer.profile?.availability || {}
            },
            scheduleCheck: includeScheduleCheck === 'true' ? {
              hasConflicts: scheduleConflicts.length > 0,
              conflicts: scheduleConflicts,
              conflictCount: scheduleConflicts.length
            } : null,
            overallEligible: skillsMatch.hasSomeRequired && availabilityCheck.isAvailable && (includeScheduleCheck !== 'true' || scheduleConflicts.length === 0)
          };
        })
      );

      // Sort by eligibility (eligible first, then by skill match quality)
      feasibilityResults.sort((a, b) => {
        if (a.overallEligible !== b.overallEligible) {
          return b.overallEligible ? 1 : -1;
        }
        // If both eligible or both ineligible, sort by matching skills count
        return b.skillsMatch.matchingSkills.length - a.skillsMatch.matchingSkills.length;
      });

      const eligibleCarers = feasibilityResults.filter(r => r.overallEligible);
      const ineligibleCarers = feasibilityResults.filter(r => !r.overallEligible);

      res.json({
        success: true,
        data: {
          requestId,
          requestDetails: {
            subject: existingRequest.subject,
            scheduledStartTime: existingRequest.scheduledStartTime,
            scheduledEndTime: existingRequest.scheduledEndTime,
            estimatedDuration: existingRequest.estimatedDuration,
            requiredSkills,
            requirements
          },
          summary: {
            totalCarers: allCarers.length,
            eligibleCarers: eligibleCarers.length,
            ineligibleCarers: ineligibleCarers.length,
            checkedSchedule: includeScheduleCheck === 'true'
          },
          eligibleCarers,
          ineligibleCarers
        },
        message: `Found ${eligibleCarers.length} eligible carers out of ${allCarers.length} total carers`
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
   * Check carer availability based on profile availability data
   */
  private checkCarerAvailability(carer: any, requestStart: Date, requestEnd: Date) {
    const availability = carer.profile?.availability || {};

    // Get the day of the week for the request
    const daysOfWeek = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const requestDay = daysOfWeek[requestStart.getDay()].toLowerCase();

    // Check if carer has availability for this day
    const dayAvailability = availability[requestDay];
    if (!dayAvailability) {
      return {
        isAvailable: false,
        conflicts: [`No availability configured for ${requestDay}`]
      };
    }

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

      return {
        isAvailable,
        conflicts
      };
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

      return {
        isAvailable,
        conflicts
      };
    }

    // If neither object nor string format
    return {
      isAvailable: false,
      conflicts: [`Unsupported availability format for ${requestDay}`]
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
}