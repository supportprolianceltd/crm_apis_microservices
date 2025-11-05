import { Request, Response } from 'express';
import { z } from 'zod';
import { PrismaClient, RequestStatus, MatchStatus, Prisma } from '@prisma/client';
import { GeocodingService } from '../services/geocoding.service';
import { MatchingService } from '../services/matching.service';
import { ClusteringService } from '../services/clustering.service';
import { ConstraintsService } from '../services/constraints.service';
import { TravelService } from '../services/travel.service';
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

  constructor(
    prisma: PrismaClient, 
    geocodingService: GeocodingService, 
    matchingService: MatchingService
  ) {
    this.prisma = prisma;
    this.geocodingService = geocodingService;
    this.matchingService = matchingService;
    const constraintsService = new ConstraintsService(prisma);
    const travelService = new TravelService(prisma);
    this.clusteringService = new ClusteringService(prisma, constraintsService, travelService);
  }

  /**
   * Create a new request
   */
  createRequest = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      
      // Validate request body
      const validatedData = createRequestSchema.parse(req.body);

      // Geocode the address
      const geocoded = await this.geocodingService.geocodeAddress(
        validatedData.address, 
        validatedData.postcode
      );

      let clusterId: string | undefined;
      let cluster: any = null;

  // Find or create cluster if we have coordinates
  // Controlled by AUTO_ASSIGN_REQUESTS env var. Automatic assignment only runs when AUTO_ASSIGN_REQUESTS === 'true'.
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

      // Create the request
      const createData: any = {
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
        status: RequestStatus.PENDING,
        // Use the schema field name `sendToRostering` (not `endToRostering`)
        sendToRostering: false
      };

      // If we have a cluster, connect the relation instead of setting clusterId directly
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

      logServiceError('Request', 'createRequest', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to create request',
        message: 'Internal server error'
      });
    }
  };

  /**
   * Get requests for current tenant by status (path param)
   * Example: GET /requests/status/PENDING
   */
  getRequestsByStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const statusParam = (req.params.status || '').toUpperCase();

      // Validate status against generated Prisma enum values
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
          // include basic match fields (carer is external — do not try to include relation)
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
        // require here to avoid circular imports at module load time
        // eslint-disable-next-line @typescript-eslint/no-var-requires
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

      // Enrich matches with carer details from external service
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
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
        }
      }

      // Update the request
      const updatedRequest = await this.prisma.externalRequest.update({
        where: { id: requestId },
        data: updateData
      });

      // Update PostGIS location field if coordinates changed
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
   * List all requests for a tenant (simplified version of searchRequests)
   */
  listRequests = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
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
                carerId: true
              },
              orderBy: {
                matchScore: 'desc'
              },
              take: 5 // Show top 5 matches
            }
          }
        })
      ]);

        // Enrich results with external carer information
        try {
          // eslint-disable-next-line @typescript-eslint/no-var-requires
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
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
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

  /**
   * Approve a request (mark as PROCESSING).
   * Assumption: Approving moves a PENDING request into PROCESSING and sets processedAt.
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

      // Optional metadata from body (who approved) and optional sendToRostering flag
      const { approvedBy, sendToRostering } = req.body as { approvedBy?: string; sendToRostering?: boolean | string };

      const updateData: any = {
        status: RequestStatus.APPROVED,
        processedAt: new Date(),
        approvedAt: new Date(),
        updatedAt: new Date()
      };

      if (approvedBy) {
        updateData.approvedBy = approvedBy;
      }

      // Allow the caller to explicitly set sendToRostering to true/false when approving.
      // Accept boolean or string representations ("true"/"false"). Only set the field when provided.
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

      // Kick off matching again in background to ensure processing continues
      this.matchingService.autoMatchRequest(requestId).catch(error =>
        logServiceError('Request', 'autoMatchAfterApprove', error, { requestId })
      );

      logger.info(`Approved request ${requestId}`, { tenantId, requestId });

      res.json({ success: true, data: updated, message: 'Request approved and set to processing' });

    } catch (error) {
       console.error('Approve request error:', error);
      logServiceError('Request', 'approveRequest', error, { requestId: req.params.id });
      res.status(500).json({ success: false, error: 'Failed to approve request' });
    }
  };

  /**
   * Decline a request (mark as DECLINED). Optionally accepts a reason in body.reason.
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

      // Use a transaction to update request and cancel any outstanding matches
      const updated = await this.prisma.$transaction(async (tx: Prisma.TransactionClient) => {
        // Cancel request matches
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

