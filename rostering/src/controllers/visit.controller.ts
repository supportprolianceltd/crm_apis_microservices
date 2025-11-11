import { Request, Response } from 'express';
import { z } from 'zod';
import { PrismaClient, VisitStatus, Prisma } from '@prisma/client';
import { logger, logServiceError } from '../utils/logger';
import { generateUniqueVisitId } from '../utils/idGenerator';

// Validation schemas
const createVisitSchema = z.object({
  externalRequestId: z.string().min(1, 'External request ID is required').optional(),
  subject: z.string().min(1, 'Subject is required'),
  content: z.string().min(1, 'Content is required'),
  requestorEmail: z.string().email('Valid email is required'),
  requestorName: z.string().optional(),
  requestorPhone: z.string().optional(),
  address: z.string().min(1, 'Address is required'),
  postcode: z.string().optional(),
  latitude: z.number().optional(),
  longitude: z.number().optional(),
  urgency: z.enum(['LOW', 'MEDIUM', 'HIGH', 'URGENT']).optional(),
  requirements: z.string().optional(),
  requiredSkills: z.array(z.string()).optional(),
  estimatedDuration: z.number().int().positive().optional(),
  scheduledStartTime: z.string().datetime(),
  scheduledEndTime: z.string().datetime().optional(),
  recurrencePattern: z.string().nullable().optional(),
  notes: z.string().optional(),
  clusterId: z.string().optional()
});

const updateVisitSchema = createVisitSchema.partial().omit({ externalRequestId: true }).extend({
  status: z.enum(['SCHEDULED', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'NO_SHOW']).optional(),
  isActive: z.boolean().optional(),
  assignmentStatus: z.enum(['PENDING', 'OFFERED', 'ACCEPTED', 'DECLINED']).optional(),
  assignedAt: z.string().datetime().optional(),
  travelFromPrevious: z.number().int().optional(),
  complianceChecks: z.any().optional()
});

const searchVisitsSchema = z.object({
  status: z.enum(['SCHEDULED', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'NO_SHOW']).optional(),
  urgency: z.enum(['LOW', 'MEDIUM', 'HIGH', 'URGENT']).optional(),
  postcode: z.string().optional(),
  dateFrom: z.string().datetime().optional(),
  dateTo: z.string().datetime().optional(),
  requestorEmail: z.string().email().optional(),
  clusterId: z.string().optional(),
  page: z.number().int().positive().optional(),
  limit: z.number().int().positive().max(100).optional()
});

export class VisitController {
  private prisma: PrismaClient;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  /**
   * Create a new visit
   */
  createVisit = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();

      // Validate request body
      const validatedData = createVisitSchema.parse(req.body);

      // Verify external request exists and belongs to tenant (only if provided)
      let externalRequest = null;
      if (validatedData.externalRequestId) {
        externalRequest = await this.prisma.externalRequest.findFirst({
          where: {
            id: validatedData.externalRequestId,
            tenantId
          }
        });

        if (!externalRequest) {
          res.status(404).json({
            success: false,
            error: 'External request not found'
          });
          return;
        }
      }

      // Generate unique visit ID using the visit generator
      const visitId = await generateUniqueVisitId(async (id: string) => {
        const existing = await this.prisma.visit.findUnique({
          where: { id },
          select: { id: true }
        });
        return !!existing;
      });

      // Create the visit
      const visitData: any = {
        id: visitId, // Use generated readable ID
        tenantId,
        subject: validatedData.subject,
        content: validatedData.content,
        requestorEmail: validatedData.requestorEmail,
        requestorName: validatedData.requestorName,
        requestorPhone: validatedData.requestorPhone,
        address: validatedData.address,
        postcode: validatedData.postcode || '',
        latitude: validatedData.latitude,
        longitude: validatedData.longitude,
        urgency: validatedData.urgency || 'MEDIUM',
        requirements: validatedData.requirements,
        requiredSkills: validatedData.requiredSkills || [],
        estimatedDuration: validatedData.estimatedDuration,
        scheduledStartTime: new Date(validatedData.scheduledStartTime),
        scheduledEndTime: validatedData.scheduledEndTime ? new Date(validatedData.scheduledEndTime) : undefined,
        recurrencePattern: validatedData.recurrencePattern,
        notes: validatedData.notes,
        status: VisitStatus.SCHEDULED,
        createdBy: user?.id,
        createdByEmail: user?.email
      };

      // Only add externalRequestId if provided
      if (validatedData.externalRequestId) {
        visitData.externalRequestId = validatedData.externalRequestId;
      }

      // Only add clusterId if provided
      if (validatedData.clusterId) {
        visitData.clusterId = validatedData.clusterId;
      }

      const visit = await this.prisma.visit.create({
        data: visitData
      });

      logger.info(`Created visit: ${visit.id}`, {
        tenantId,
        externalRequestId: validatedData.externalRequestId,
        visitId: visit.id,
        createdBy: user?.email
      });

      res.status(201).json({
        success: true,
        data: visit,
        message: 'Visit created successfully'
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
      console.error('Visit creation error:', error);
      logServiceError('Visit', 'createVisit', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to create visit',
        message: error instanceof Error ? error.message : 'Internal server error'
      });
    }
  };

  /**
   * Get visit by ID
   */
  getVisit = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const visitId = req.params.id;

      const visit = await this.prisma.visit.findFirst({
        where: {
          id: visitId,
          tenantId
        },
        include: {
          externalRequest: {
            select: {
              id: true,
              subject: true,
              status: true,
              approvedAt: true
            }
          },
          assignments: {
            select: {
              id: true,
              carerId: true,
              scheduledTime: true,
              status: true
            },
            orderBy: { scheduledTime: 'asc' }
          },
          cluster: {
            select: {
              id: true,
              name: true
            }
          }
        }
      });

      if (!visit) {
        res.status(404).json({
          success: false,
          error: 'Visit not found'
        });
        return;
      }

      res.json({
        success: true,
        data: visit
      });

    } catch (error) {
      logServiceError('Visit', 'getVisit', error, { visitId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve visit'
      });
    }
  };

  /**
   * Update visit
   */
  updateVisit = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const visitId = req.params.id;

      const validatedData = updateVisitSchema.parse(req.body);

      const existingVisit = await this.prisma.visit.findFirst({
        where: {
          id: visitId,
          tenantId
        }
      });

      if (!existingVisit) {
        res.status(404).json({
          success: false,
          error: 'Visit not found'
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

      const updatedVisit = await this.prisma.visit.update({
        where: { id: visitId },
        data: updateData
      });

      logger.info(`Updated visit: ${visitId}`, { tenantId, visitId });

      res.json({
        success: true,
        data: updatedVisit,
        message: 'Visit updated successfully'
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

      logServiceError('Visit', 'updateVisit', error, { visitId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to update visit'
      });
    }
  };

  /**
   * List visits for a tenant
   */
  listVisits = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const page = parseInt(req.query.page as string) || 1;
      const limit = Math.min(parseInt(req.query.limit as string) || 20, 100);
      const skip = (page - 1) * limit;

      const [total, visits] = await Promise.all([
        this.prisma.visit.count({ where: { tenantId, isActive: true } }),
        this.prisma.visit.findMany({
          where: { tenantId, isActive: true },
          skip,
          take: limit,
          orderBy: {
            scheduledStartTime: 'desc'
          },
          include: {
            externalRequest: {
              select: {
                id: true,
                subject: true,
                status: true
              }
            },
            cluster: {
              select: {
                id: true,
                name: true
              }
            }
          }
        })
      ]);

      const totalPages = Math.ceil(total / limit);

      const response = {
        data: visits,
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
      logServiceError('VisitController', 'listVisits', error, {
        tenantId: req.user?.tenantId
      });
      res.status(500).json({
        success: false,
        error: 'Failed to list visits',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  };

  /**
   * Search visits with pagination
   */
  searchVisits = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();

      const validatedQuery = searchVisitsSchema.parse(req.query);

      const page = validatedQuery.page || 1;
      const limit = validatedQuery.limit || 20;
      const skip = (page - 1) * limit;

      const whereClause: any = {
        tenantId,
        isActive: true,
        ...(validatedQuery.status && { status: validatedQuery.status }),
        ...(validatedQuery.urgency && { urgency: validatedQuery.urgency }),
        ...(validatedQuery.postcode && { postcode: { contains: validatedQuery.postcode, mode: 'insensitive' } }),
        ...(validatedQuery.requestorEmail && { requestorEmail: { contains: validatedQuery.requestorEmail, mode: 'insensitive' } }),
        ...(validatedQuery.clusterId && { clusterId: validatedQuery.clusterId })
      };

      if (validatedQuery.dateFrom || validatedQuery.dateTo) {
        whereClause.scheduledStartTime = {};
        if (validatedQuery.dateFrom) {
          whereClause.scheduledStartTime.gte = new Date(validatedQuery.dateFrom);
        }
        if (validatedQuery.dateTo) {
          whereClause.scheduledStartTime.lte = new Date(validatedQuery.dateTo);
        }
      }

      const [total, visits] = await Promise.all([
        this.prisma.visit.count({ where: whereClause }),
        this.prisma.visit.findMany({
          where: whereClause,
          skip,
          take: limit,
          orderBy: {
            scheduledStartTime: 'desc'
          },
          include: {
            externalRequest: {
              select: {
                id: true,
                subject: true,
                status: true
              }
            },
            cluster: {
              select: {
                id: true,
                name: true
              }
            }
          }
        })
      ]);

      const totalPages = Math.ceil(total / limit);

      const response = {
        data: visits,
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

      logServiceError('Visit', 'searchVisits', error, { tenantId: req.user?.tenantId });
      res.status(500).json({
        success: false,
        error: 'Failed to search visits'
      });
    }
  };

  /**
   * Delete visit
   */
  deleteVisit = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = (req as any).user;
      const tenantId = user?.tenantId?.toString();
      const visitId = req.params.id;

      const existingVisit = await this.prisma.visit.findFirst({
        where: {
          id: visitId,
          tenantId
        }
      });

      if (!existingVisit) {
        res.status(404).json({
          success: false,
          error: 'Visit not found'
        });
        return;
      }

      // Check if visit has assignments
      const assignmentCount = await this.prisma.assignment.count({
        where: { visitId }
      });

      if (assignmentCount > 0) {
        res.status(400).json({
          success: false,
          error: 'Cannot delete visit with existing assignments'
        });
        return;
      }

      await this.prisma.visit.delete({
        where: { id: visitId }
      });

      logger.info(`Deleted visit: ${visitId}`, { tenantId, visitId });

      res.json({
        success: true,
        message: 'Visit deleted successfully'
      });

    } catch (error) {
      logServiceError('Visit', 'deleteVisit', error, { visitId: req.params.id });
      res.status(500).json({
        success: false,
        error: 'Failed to delete visit'
      });
    }
  };

  /**
    * Get visits by status
    */
   getVisitsByStatus = async (req: Request, res: Response): Promise<void> => {
     try {
       const user = (req as any).user;
       const tenantId = user?.tenantId?.toString();
       const statusParam = (req.params.status || '').toUpperCase();

       const validStatuses = Object.values(VisitStatus) as string[];
       if (!validStatuses.includes(statusParam)) {
         res.status(400).json({ success: false, error: 'Invalid status', valid: validStatuses });
         return;
       }

       const visits = await this.prisma.visit.findMany({
         where: {
           tenantId,
           status: statusParam as VisitStatus
         },
         orderBy: { scheduledStartTime: 'desc' },
         include: {
           externalRequest: {
             select: {
               id: true,
               subject: true,
               status: true
             }
           },
           cluster: {
             select: {
               id: true,
               name: true
             }
           }
         }
       });

       res.json({ success: true, data: visits });
     } catch (error) {
       logServiceError('Visit', 'getVisitsByStatus', error, { status: req.params.status, tenantId: req.user?.tenantId });
       res.status(500).json({ success: false, error: 'Failed to get visits by status' });
     }
   };

   /**
    * Get visits by client ID (requestorEmail)
    */
   getVisitsByClient = async (req: Request, res: Response): Promise<void> => {
     try {
       const user = (req as any).user;
       const tenantId = user?.tenantId?.toString();
       const clientId = req.params.clientId;

       if (!clientId) {
         res.status(400).json({
           success: false,
           error: 'Client ID is required'
         });
         return;
       }

       const visits = await this.prisma.visit.findMany({
         where: {
           tenantId,
           requestorEmail: clientId,
           isActive: true
         },
         orderBy: { scheduledStartTime: 'desc' },
         include: {
           externalRequest: {
             select: {
               id: true,
               subject: true,
               status: true,
               approvedAt: true
             }
           },
           cluster: {
             select: {
               id: true,
               name: true
             }
           },
           assignments: {
             select: {
               id: true,
               carerId: true,
               scheduledTime: true,
               status: true
             },
             orderBy: { scheduledTime: 'asc' }
           }
         }
       });

       res.json({
         success: true,
         data: visits,
         clientId,
         total: visits.length
       });

     } catch (error) {
       logServiceError('Visit', 'getVisitsByClient', error, { clientId: req.params.clientId });
       res.status(500).json({
         success: false,
         error: 'Failed to get visits by client'
       });
     }
   };
 }