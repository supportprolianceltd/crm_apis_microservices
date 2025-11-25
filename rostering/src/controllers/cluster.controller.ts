import { Request, Response } from 'express';
import { PrismaClient, RequestStatus } from '@prisma/client';
import { ClusteringService } from '../services/clustering.service';
import { CarerService } from '../services/carer.service';
import { ConstraintsService } from '../services/constraints.service';
import { TravelService } from '../services/travel.service';



export class ClusterController {
  private clusteringService: ClusteringService;
  private constraintsService: ConstraintsService;
  private travelService: TravelService;

  constructor(private prisma: PrismaClient) {
    this.constraintsService = new ConstraintsService(prisma);
    this.travelService = new TravelService(prisma);
    this.clusteringService = new ClusteringService(
      prisma, 
      this.constraintsService, 
      this.travelService
    );
  }

  /**
   * Create a new cluster for the tenant
   */
  public async createCluster(req: Request, res: Response) {
    try {
      const user = req.user;
      if (!user) {
        return res.status(401).json({ error: 'User not authenticated' });
      }

      const tenantId = user.tenantId;
      const { name, description, postcode, latitude, longitude, location } = req.body;

      if (!name) {
        return res.status(400).json({ error: 'name is required' });
      }

    //   if (postcode && !this.isValidPostcode(postcode)) {
    //   return res.status(400).json({ error: 'Invalid postcode format' });
    // }

    let normalizedPostcode: string | null = null

     // Check for duplicate postcode within the same tenant
    if (postcode !== undefined && postcode !== null) {
       if (typeof postcode !== 'string') {
        return res.status(400).json({ error: 'postcode must be a string' });
      }
      // Normalize postcode for comparison (remove spaces, convert to uppercase)
      normalizedPostcode = postcode.trim().replace(/\s+/g, '').toUpperCase();

      const existingCluster = await (this.prisma as any).cluster.findFirst({
        where: {
          tenantId: tenantId.toString(),
          postcode: {
            equals: normalizedPostcode,
            mode: 'insensitive' // Case-insensitive comparison
          }
        }
      });

      if (existingCluster) {
        return res.status(409).json({
          error: 'A cluster with this postcode already exists',
          details: `Cluster "${existingCluster.name}" already uses postcode ${postcode}`
        });
      }
    }

      // Create cluster without PostGIS regionCenter first
      const created = await (this.prisma as any).cluster.create({
        data: {
          tenantId: tenantId.toString(),
          name,
          description: description || null,
          postcode: normalizedPostcode,
          latitude: typeof latitude === 'number' ? latitude : null,
          longitude: typeof longitude === 'number' ? longitude : null,
          location: location,
          radiusMeters: 5000,
          activeRequestCount: 0,
          totalRequestCount: 0,
          activeCarerCount: 0,
          totalCarerCount: 0,
          lastActivityAt: new Date()
        }
      });

      // If lat/lng provided, update PostGIS regionCenter via raw SQL
      if (latitude !== undefined && longitude !== undefined && latitude !== null && longitude !== null) {
        try {
          await this.prisma.$executeRaw`
            UPDATE clusters
            SET "regionCenter" = ST_SetSRID(ST_MakePoint(${longitude}, ${latitude}), 4326)::geography
            WHERE id = ${created.id}
          `;
        } catch (err) {
          console.error('Failed to set regionCenter for cluster', err);
        }
      }

      const cluster = await (this.prisma as any).cluster.findUnique({ where: { id: created.id } });

      return res.status(201).json(cluster);
    } catch (error: any) {
      console.error('createCluster error', error);
      return res.status(500).json({ error: 'Failed to create cluster', details: error?.message });
    }
  }

  /**
   * Get overview of all clusters for a tenant
   */
  public async getClusterOverview(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const analytics = await this.clusteringService.getClusterAnalytics(tenantId.toString());
      return res.json(analytics);
    } catch (error: any) {
      console.error('getClusterOverview error', error);
      return res.status(500).json({ error: 'Failed to fetch cluster overview', details: error?.message });
    }
  }

  /**
   * Get detailed information about a specific cluster
   */
  public async getClusterDetails(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId } = req.params;
      if (!clusterId) {
        return res.status(400).json({ error: 'clusterId required in path' });
      }

      const cluster = await (this.prisma as any).cluster.findFirst({
        where: { id: clusterId, tenantId: tenantId.toString() },
        include: {
          requests: {
            where: { status: { in: ['PENDING', 'PROCESSING', 'MATCHED'] } },
            orderBy: { createdAt: 'desc' },
            take: 10
          }
          // REMOVED: carers inclusion
        }
      });

      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      // Load linked schedules and extract distinct clientIds
      const scheduleLinks = await (this.prisma as any).clusterAgreedCareSchedule.findMany({
        where: { clusterId: clusterId, tenantId: tenantId.toString() },
        select: {
          agreedCareSchedule: { select: { careRequirements: { select: { carePlan: { select: { clientId: true } } } } } }
        }
      });

      const linkedClientIds = Array.from(new Set(
        scheduleLinks
          .map((s: any) => s?.agreedCareSchedule?.careRequirements?.carePlan?.clientId)
          .filter((id: any) => !!id)
      ));

      // Get carer assignments from clustering service
      const assignments = await this.clusteringService.getCarerAssignmentsInCluster(clusterId);
      
      // Get carer details from auth service
      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
      const carerService = new CarerService();
      
      const carersWithDetails = await Promise.all(
        assignments.map(async (assignment: any) => {
          const carer = await carerService.getCarerById(token, assignment.carerId);
          return {
            assignmentId: assignment.id,
            carerId: assignment.carerId,
            assignedAt: assignment.assignedAt,
            carerDetails: carer ? {
              id: carer.id,
              firstName: carer.first_name,
              lastName: carer.last_name,
              email: carer.email,
              phone: carer.profile?.personal_phone || carer.profile?.work_phone || null,
              skills: carer.profile?.professional_qualifications || [],
              // Add other fields you need from auth service
            } : null
          };
        })
      );

      return res.json({
        ...cluster,
        carerAssignments: carersWithDetails,
        linkedClientIds
      });
    } catch (error: any) {
      console.error('getClusterDetails error', error);
      return res.status(500).json({ error: 'Failed to fetch cluster details', details: error?.message });
    }
  }

  /**
   * Remove carer from cluster
   */
  public async removeCarerFromCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { carerId } = req.params;

      await this.clusteringService.removeCarerFromCluster(tenantId.toString(), carerId);

      return res.json({
        carerId,
        message: 'Carer removed from cluster successfully'
      });
    } catch (error: any) {
      console.error('removeCarerFromCluster error', error);
      return res.status(500).json({ error: 'Failed to remove carer from cluster', details: error?.message });
    }
  }

  /**
   * Move carer to different cluster
   */
  public async moveCarerToCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { carerId } = req.params;
      const { newClusterId } = req.body;

      if (!newClusterId) {
        return res.status(400).json({ error: 'newClusterId required in body' });
      }

      const result = await this.clusteringService.moveCarerToCluster(
        tenantId.toString(), 
        carerId, 
        newClusterId
      );

      return res.json(result);
    } catch (error: any) {
      console.error('moveCarerToCluster error', error);
      return res.status(500).json({ error: 'Failed to move carer to cluster', details: error?.message });
    }
  }

  /**
   * Get carer's current cluster assignment
   */
  public async getCarerClusterAssignment(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { carerId } = req.params;

      const assignment = await this.clusteringService.getCarerClusterAssignment(
        tenantId.toString(), 
        carerId
      );

      if (!assignment) {
        return res.status(404).json({ error: 'Carer cluster assignment not found' });
      }

      return res.json(assignment);
    } catch (error: any) {
      console.error('getCarerClusterAssignment error', error);
      return res.status(500).json({ error: 'Failed to fetch carer cluster assignment', details: error?.message });
    }
  }

  /**
   * Get carers available in a specific cluster
   */
  public async getClusterCarers(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId } = req.params;
      const includeNearby = req.query.includeNearby === 'true';

      if (!clusterId) {
        return res.status(400).json({ error: 'clusterId required in path' });
      }

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({
        where: { id: clusterId, tenantId: tenantId.toString() }
      });

      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      // Use new method that returns assignments
      const assignments = await this.clusteringService.getCarerAssignmentsInClusterWithNearby(
        clusterId, 
        includeNearby
      );

      // Get carer details from auth service
      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
      const carerService = new CarerService();
      
      const carersWithDetails = await Promise.all(
        assignments.map(async (assignment: any) => {
          const carer = await carerService.getCarerById(token, assignment.carerId);
          return {
            assignmentId: assignment.id,
            carerId: assignment.carerId,
            assignedAt: assignment.assignedAt,
            isInCluster: assignment.clusterId === clusterId,
            carerDetails: carer ? {
              id: carer.id,
              firstName: carer.first_name,
              lastName: carer.last_name,
              email: carer.email,
              phone: carer.profile?.personal_phone || carer.profile?.work_phone || null,
              skills: carer.profile?.professional_qualifications || [],
              // Add other fields from auth service
            } : null
          };
        })
      );

      return res.json({
        clusterId,
        clusterName: cluster.name,
        includeNearby,
        carerAssignments: carersWithDetails
      });
    } catch (error: any) {
      console.error('getClusterCarers error', error);
      return res.status(500).json({ error: 'Failed to fetch cluster carers', details: error?.message });
    }
  }

  /**
   * Update cluster statistics manually (usually done automatically)
   */
  public async updateClusterStats(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId } = req.params;
      if (!clusterId) {
        return res.status(400).json({ error: 'clusterId required in path' });
      }

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({
        where: { id: clusterId, tenantId: tenantId.toString() }
      });

      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      await this.clusteringService.updateClusterStats(clusterId);

      // Return updated cluster
      const updatedCluster = await (this.prisma as any).cluster.findUnique({
        where: { id: clusterId }
      });

      return res.json(updatedCluster);
    } catch (error: any) {
      console.error('updateClusterStats error', error);
      return res.status(500).json({ error: 'Failed to update cluster stats', details: error?.message });
    }
  }

  /**
    * Assign a carer to a cluster based on location
    */
   public async assignCarerToCluster(req: Request, res: Response) {
     console.log('=== ASSIGN CARER TO CLUSTER START ===');
     try {
       const tenantId = req.user?.tenantId;
       console.log('Tenant ID from auth:', tenantId);

       if (!tenantId) {
         console.log('ERROR: tenantId missing from auth context');
         return res.status(403).json({ error: 'tenantId missing from auth context' });
       }

       const { carerId } = req.params;
       const { latitude, longitude } = req.body;
       console.log('Request params:', { carerId, latitude, longitude });

       if (!carerId) {
         console.log('ERROR: carerId required in path');
         return res.status(400).json({ error: 'carerId required in path' });
       }

       if (!latitude || !longitude) {
         console.log('ERROR: latitude and longitude required in body');
         return res.status(400).json({ error: 'latitude and longitude required in body' });
       }

       // Use auth-backed CarerService to validate carer exists
       const authHeader = req.headers.authorization as string | undefined;
       const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
       console.log('Auth token present:', !!token);

       const carerService = new CarerService();
       console.log('Calling carerService.getCarerById...');
       const carer = await carerService.getCarerById(token, carerId);
       console.log('Carer lookup result:', carer ? `Found carer ${carer.first_name} ${carer.last_name}` : 'Carer not found');

       if (!carer) {
         console.log('ERROR: Carer not found in auth service');
         return res.status(404).json({ error: 'Carer not found in auth service' });
       }

       // No tenant check needed - endpoint already filters by tenant
       console.log('Calling clusteringService.assignCarerToCluster...');
       const cluster = await this.clusteringService.assignCarerToCluster(tenantId.toString(), carerId, latitude, longitude);
       console.log('Cluster assignment result:', cluster ? `Assigned to cluster ${cluster.name}` : 'No cluster returned');

       console.log('=== ASSIGN CARER TO CLUSTER SUCCESS ===');
       return res.json({
         carerId,
         clusterId: cluster?.id,
         clusterName: cluster?.name,
         message: 'Carer assigned to cluster successfully'
       });
     } catch (error: any) {
       console.error('=== ASSIGN CARER TO CLUSTER ERROR ===');
       console.error('Error details:', error);
       console.error('Error message:', error?.message);
       console.error('Error stack:', error?.stack);
       return res.status(500).json({ error: 'Failed to assign carer to cluster', details: error?.message });
     }
   }

  /**
   * Assign carer to specific cluster (manual assignment)
   */
  public async assignCarerToSpecificCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId, carerId } = req.params;
      const { latitude, longitude } = req.body;

      if (!clusterId || !carerId) {
        return res.status(400).json({ error: 'clusterId and carerId required in path' });
      }

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({
        where: { id: clusterId, tenantId: tenantId.toString() }
      });

      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      // Verify carer exists
      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
      const carerService = new CarerService();
      const carer = await carerService.getCarerById(token, carerId);

      if (!carer) {
        return res.status(404).json({ error: 'Carer not found in auth service' });
      }

      // Use the moveCarerToCluster method
      const result = await this.clusteringService.moveCarerToCluster(
        tenantId.toString(), 
        carerId, 
        clusterId
      );

      return res.json(result);
    } catch (error: any) {
      console.error('assignCarerToSpecificCluster error', error);
      return res.status(500).json({ error: 'Failed to assign carer to specific cluster', details: error?.message });
    }
  }

  /**
   * Manually assign a request to a cluster
   * POST /clusters/:clusterId/assign-request/:requestId
   */
  public async assignRequestToCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId, requestId } = req.params as { clusterId?: string; requestId?: string };
      if (!clusterId || !requestId) {
        return res.status(400).json({ error: 'clusterId and requestId are required in path' });
      }

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

        // Verify request belongs to tenant
        const existingRequest = await (this.prisma as any).externalRequest.findFirst({ where: { id: requestId, tenantId: tenantId.toString() } });
        if (!existingRequest) {
          return res.status(404).json({ error: 'Request not found' });
        }

        // Only allow assigning requests that are APPROVED
        if (existingRequest.status !== RequestStatus.APPROVED) {
          return res.status(400).json({ error: 'Only requests with status APPROVED can be assigned to a cluster' });
        }

      // Update the request with the clusterId
      const updatedRequest = await (this.prisma as any).externalRequest.update({
        where: { id: requestId },
        data: { clusterId }
      });

      // Update cluster statistics asynchronously
      this.clusteringService.updateClusterStats(clusterId).catch((err) => console.error('updateClusterStats after assignRequest failed', err));

      return res.json({
        success: true,
        data: updatedRequest,
        message: 'Request assigned to cluster successfully'
      });
    } catch (error: any) {
      console.error('assignRequestToCluster error', error);
      return res.status(500).json({ error: 'Failed to assign request to cluster', details: error?.message });
    }
  }

  /**
   * Assign an existing visit to a cluster
   * POST /clusters/:clusterId/assign-visit/:visitId
   */
  public async assignVisitToCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId, visitId } = req.params as { clusterId?: string; visitId?: string };
      if (!clusterId || !visitId) {
        return res.status(400).json({ error: 'clusterId and visitId are required in path' });
      }

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({
        where: { id: clusterId, tenantId: tenantId.toString() }
      });
      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      // Verify visit belongs to tenant and exists
      const existingVisit = await (this.prisma as any).visit.findFirst({
        where: { id: visitId, tenantId: tenantId.toString() }
      });
      if (!existingVisit) {
        return res.status(404).json({ error: 'Visit not found' });
      }

      // Check if visit is already assigned to this cluster
      if (existingVisit.clusterId === clusterId) {
        return res.status(409).json({
          error: 'Visit is already assigned to this cluster',
          visitId: existingVisit.id,
          currentClusterId: existingVisit.clusterId
        });
      }

      // Get the old cluster ID for statistics update
      const oldClusterId = existingVisit.clusterId;

      // Update the visit with the new cluster assignment
      const updatedVisit = await (this.prisma as any).visit.update({
        where: { id: visitId },
        data: {
          clusterId: clusterId,
          updatedAt: new Date()
        }
      });

      // Update cluster statistics for both old and new clusters
      if (oldClusterId) {
        this.clusteringService.updateClusterStats(oldClusterId).catch((err) =>
          console.error(`updateClusterStats failed for old cluster ${oldClusterId}`, err)
        );
      }
      this.clusteringService.updateClusterStats(clusterId).catch((err) =>
        console.error(`updateClusterStats failed for new cluster ${clusterId}`, err)
      );

      return res.json({
        success: true,
        data: {
          visit: updatedVisit,
          cluster: {
            id: cluster.id,
            name: cluster.name,
            previousClusterId: oldClusterId
          }
        },
        message: `Visit reassigned to cluster '${cluster.name}' successfully`
      });
    } catch (error: any) {
      console.error('assignVisitToCluster error', error);
      return res.status(500).json({
        error: 'Failed to assign visit to cluster',
        details: error?.message
      });
    }
  }

  /**
   * Assign an AgreedCareSchedule to a Cluster (idempotent)
   * POST /clusters/:clusterId/assign-agreed-care-schedule/:scheduleId
   */
  public async assignAgreedCareScheduleToCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const { clusterId, scheduleId } = req.params as { clusterId?: string; scheduleId?: string };
      if (!clusterId || !scheduleId) return res.status(400).json({ error: 'clusterId and scheduleId are required in path' });

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!cluster) return res.status(404).json({ error: 'Cluster not found' });

      // Verify schedule belongs to tenant
      const schedule = await (this.prisma as any).agreedCareSchedule.findFirst({ where: { id: scheduleId, tenantId: tenantId.toString() } });
      if (!schedule) return res.status(404).json({ error: 'AgreedCareSchedule not found' });

      // Idempotent create: skip if already linked
      const existingLink = await (this.prisma as any).clusterAgreedCareSchedule.findFirst({
        where: {
          tenantId: tenantId.toString(),
          clusterId: clusterId,
          agreedCareScheduleId: scheduleId
        }
      });

      if (existingLink) {
        return res.json({ success: true, message: 'Schedule already assigned to cluster', data: existingLink });
      }

      const created = await (this.prisma as any).clusterAgreedCareSchedule.create({
        data: {
          tenantId: tenantId.toString(),
          clusterId: clusterId,
          agreedCareScheduleId: scheduleId
        }
      });

      this.clusteringService.updateClusterStats(clusterId).catch((err) => console.error('updateClusterStats after assign schedule failed', err));

      return res.status(201).json({ success: true, message: 'Schedule assigned to cluster', data: created });
    } catch (error: any) {
      console.error('assignAgreedCareScheduleToCluster error', error);
      return res.status(500).json({ error: 'Failed to assign schedule to cluster', details: error?.message });
    }
  }

  /**
   * List AgreedCareSchedules linked to a Cluster
   * GET /clusters/:clusterId/agreedschedules
   */
  public async getClusterAgreedSchedules(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const { clusterId } = req.params as { clusterId?: string };
      if (!clusterId) return res.status(400).json({ error: 'clusterId required in path' });

      const cluster = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!cluster) return res.status(404).json({ error: 'Cluster not found' });

      const links = await (this.prisma as any).clusterAgreedCareSchedule.findMany({
        where: { tenantId: tenantId.toString(), clusterId },
        include: {
          agreedCareSchedule: {
            include: {
              careRequirements: {
                include: { carePlan: true }
              }
            }
          }
        }
      });

      const schedules = links.map((l: any) => ({
        id: l.agreedCareSchedule?.id,
        day: l.agreedCareSchedule?.day,
        enabled: l.agreedCareSchedule?.enabled,
        careRequirementsId: l.agreedCareSchedule?.careRequirementsId,
        carePlanId: l.agreedCareSchedule?.careRequirements?.carePlan?.id || null,
        carePlanClientId: l.agreedCareSchedule?.careRequirements?.carePlan?.clientId || null,
        linkedAt: l.createdAt
      }));

      return res.json({ clusterId, clusterName: cluster.name, schedules });
    } catch (error: any) {
      console.error('getClusterAgreedSchedules error', error);
      return res.status(500).json({ error: 'Failed to fetch cluster agreed schedules', details: error?.message });
    }
  }

  /**
   * Assign a client to a cluster (persist link)
   * POST /clusters/:clusterId/assign-client/:clientId
   */
  public async assignClientToCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const { clusterId, clientId } = req.params as { clusterId?: string; clientId?: string };
      if (!clusterId || !clientId) return res.status(400).json({ error: 'clusterId and clientId are required in path' });

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!cluster) return res.status(404).json({ error: 'Cluster not found' });

      // Validate client exists in auth service
      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
      const { ClientService } = await import('../services/client.service');
      const clientService = new ClientService();
      const client = await clientService.getClientById(token, clientId);
      if (!client) return res.status(404).json({ error: 'Client not found in auth service' });

      // Idempotent create: skip if already linked
      const existingLink = await (this.prisma as any).clusterClient.findFirst({
        where: { tenantId: tenantId.toString(), clusterId: clusterId, clientId }
      });

      if (existingLink) {
        return res.json({ success: true, message: 'Client already assigned to cluster', data: existingLink });
      }

      const created = await (this.prisma as any).clusterClient.create({ data: { tenantId: tenantId.toString(), clusterId, clientId } });

      // Update cluster statistics asynchronously
      this.clusteringService.updateClusterStats(clusterId).catch((err) => console.error('updateClusterStats after assign client failed', err));

      return res.status(201).json({ success: true, message: 'Client assigned to cluster', data: created });
    } catch (error: any) {
      console.error('assignClientToCluster error', error);
      return res.status(500).json({ error: 'Failed to assign client to cluster', details: error?.message });
    }
  }

  /**
   * List clients assigned to a cluster and enrich via auth service
   * GET /clusters/:clusterId/clients
   */
  public async listClusterClients(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const { clusterId } = req.params as { clusterId?: string };
      if (!clusterId) return res.status(400).json({ error: 'clusterId required in path' });

      const cluster = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!cluster) return res.status(404).json({ error: 'Cluster not found' });

      const links = await (this.prisma as any).clusterClient.findMany({ where: { tenantId: tenantId.toString(), clusterId }, select: { clientId: true } });
      const clientIds = links.map((l: any) => l.clientId).filter(Boolean);

      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;

      let clients: any[] = [];
      if (clientIds.length > 0) {
        const { ClientService } = await import('../services/client.service');
        const clientService = new ClientService();
        try {
          clients = await clientService.getClientsByIds(token, clientIds) as any[];
        } catch (err) {
          console.error('Failed to fetch clients from auth service', err);
          clients = clientIds.map((id: string) => ({ id }));
        }
      }

      return res.json({ clusterId, clusterName: cluster.name, clients });
    } catch (error: any) {
      console.error('listClusterClients error', error);
      return res.status(500).json({ error: 'Failed to list cluster clients', details: error?.message });
    }
  }

  /**
   * Batch assign multiple clients to a cluster
   * POST /clusters/:clusterId/assign-clients
   * Body: { clientIds: string[] }
   */
  public async assignClientsToCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const { clusterId } = req.params as { clusterId?: string };
      if (!clusterId) return res.status(400).json({ error: 'clusterId required in path' });

      const { clientIds } = req.body as { clientIds?: string[] };
      if (!Array.isArray(clientIds) || clientIds.length === 0) return res.status(400).json({ error: 'clientIds array required in body' });

      // Verify cluster belongs to tenant
      const cluster = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!cluster) return res.status(404).json({ error: 'Cluster not found' });

      // Validate clients exist via auth service (strict: only create for validated IDs)
      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
      const { ClientService } = await import('../services/client.service');
      const clientService = new ClientService();

      let returnedIds: string[] = [];
      try {
        const clients = await clientService.getClientsByIds(token, clientIds) as any[];
        if (!Array.isArray(clients)) {
          console.error('Auth service returned non-array response for getClientsByIds');
          return res.status(502).json({ error: 'Auth service returned unexpected response' });
        }
        returnedIds = clients.map(c => String(c.id)).filter(Boolean);
      } catch (err) {
        console.error('Failed to validate clients with auth service', err);
        return res.status(502).json({ error: 'Failed to validate clients with auth service' });
      }

      const invalidIds = clientIds.filter(id => !returnedIds.includes(id));
      const validClientIds = returnedIds;

      if (validClientIds.length === 0) {
        // Nothing to create
        return res.status(400).json({ clusterId, requested: clientIds.length, validated: 0, created: 0, alreadyLinked: 0, invalidIds, message: 'No valid client IDs found' });
      }

      // Find existing links to avoid duplicates (only check among validated ids)
      const existing = await (this.prisma as any).clusterClient.findMany({
        where: { tenantId: tenantId.toString(), clusterId, clientId: { in: validClientIds } },
        select: { clientId: true }
      });
      const existingIds = new Set(existing.map((e: any) => e.clientId));

      const toCreate = validClientIds.filter(id => !existingIds.has(id)).map(id => ({ tenantId: tenantId.toString(), clusterId, clientId: id }));

      const createdIds: string[] = [];
      const alreadyLinkedIds: string[] = validClientIds.filter(id => existingIds.has(id));

      if (toCreate.length > 0) {
        try {
          const result = await (this.prisma as any).clusterClient.createMany({ data: toCreate, skipDuplicates: true });
          // createMany doesn't return ids; assume those not in existingIds were created
          createdIds.push(...toCreate.map(t => t.clientId));
        } catch (e) {
          // Fallback: create individually and collect created ids
          for (const row of toCreate) {
            try {
              const c = await (this.prisma as any).clusterClient.create({ data: row });
              createdIds.push(c.clientId);
            } catch (innerErr) {
              console.error('clusterClient.create error (ignored)', innerErr);
            }
          }
        }
      }

      // Update cluster statistics asynchronously
      this.clusteringService.updateClusterStats(clusterId).catch((err) => console.error('updateClusterStats after assign clients failed', err));

      return res.json({
        clusterId,
        requested: clientIds.length,
        validated: validClientIds.length,
        created: createdIds.length,
        createdIds,
        alreadyLinked: alreadyLinkedIds.length,
        alreadyLinkedIds,
        invalidIds,
        message: `Batch assign completed: created ${createdIds.length}, already linked ${alreadyLinkedIds.length}`
      });
    } catch (error: any) {
      console.error('assignClientsToCluster error', error);
      return res.status(500).json({ error: 'Failed to assign clients to cluster', details: error?.message });
    }
  }

  /**
   * Batch assign multiple existing visits to clusters
   * POST /clusters/batch-assign-visits
   */
  public async batchAssignVisitsToClusters(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { assignments } = req.body;
      if (!Array.isArray(assignments) || assignments.length === 0) {
        return res.status(400).json({ error: 'assignments array is required' });
      }

      const results = [];
      const errors = [];
      const affectedClusters = new Set<string>();

      for (const assignment of assignments) {
        try {
          const { clusterId, visitId } = assignment;

          if (!clusterId || !visitId) {
            errors.push({
              assignment,
              error: 'clusterId and visitId are required'
            });
            continue;
          }

          // Verify cluster belongs to tenant
          const cluster = await (this.prisma as any).cluster.findFirst({
            where: { id: clusterId, tenantId: tenantId.toString() }
          });
          if (!cluster) {
            errors.push({
              assignment,
              error: 'Cluster not found'
            });
            continue;
          }

          // Verify visit belongs to tenant and exists
          const existingVisit = await (this.prisma as any).visit.findFirst({
            where: { id: visitId, tenantId: tenantId.toString() }
          });
          if (!existingVisit) {
            errors.push({
              assignment,
              error: 'Visit not found'
            });
            continue;
          }

          // Check if visit is already assigned to this cluster
          if (existingVisit.clusterId === clusterId) {
            errors.push({
              assignment,
              error: 'Visit is already assigned to this cluster',
              currentClusterId: existingVisit.clusterId
            });
            continue;
          }

          // Track old cluster for statistics update
          const oldClusterId = existingVisit.clusterId;
          if (oldClusterId) affectedClusters.add(oldClusterId);
          affectedClusters.add(clusterId);

          // Update the visit with the new cluster assignment
          const updatedVisit = await (this.prisma as any).visit.update({
            where: { id: visitId },
            data: {
              clusterId: clusterId,
              updatedAt: new Date()
            }
          });

          results.push({
            assignment,
            visit: updatedVisit,
            cluster: {
              id: cluster.id,
              name: cluster.name,
              previousClusterId: oldClusterId
            },
            success: true
          });

        } catch (error: any) {
          errors.push({
            assignment,
            error: error.message
          });
        }
      }

      // Update cluster statistics for all affected clusters
      for (const clusterId of affectedClusters) {
        this.clusteringService.updateClusterStats(clusterId).catch((err) =>
          console.error(`updateClusterStats failed for cluster ${clusterId}`, err)
        );
      }

      return res.json({
        success: true,
        data: {
          successful: results,
          failed: errors,
          summary: {
            total: assignments.length,
            successful: results.length,
            failed: errors.length,
            affectedClusters: Array.from(affectedClusters)
          }
        },
        message: `Batch reassignment completed: ${results.length} successful, ${errors.length} failed`
      });
    } catch (error: any) {
      console.error('batchAssignVisitsToClusters error', error);
      return res.status(500).json({
        error: 'Failed to batch assign visits to clusters',
        details: error?.message
      });
    }
  }

  // private isValidPostcode(postcode: string): boolean {
  //   // Basic UK postcode validation - adjust for your region if needed
  //   const ukPostcodeRegex = /^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$/i;
  //   return ukPostcodeRegex.test(postcode.trim());
  // }

  /**
   * Update a cluster's metadata (name, description, postcode, radius, location)
   */
  public async updateCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId } = req.params as { clusterId?: string };
      if (!clusterId) {
        return res.status(400).json({ error: 'clusterId required in path' });
      }

      const { name, description, postcode, latitude, longitude, radiusMeters } = req.body;

      // Verify cluster belongs to tenant
      const existing = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!existing) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      const updateData: any = {};
      if (name !== undefined) updateData.name = name;
      if (description !== undefined) updateData.description = description || null;

      if (postcode !== undefined && postcode !== null) {
        if (typeof postcode !== 'string') {
          return res.status(400).json({ error: 'postcode must be a string' });
        }
        updateData.postcode = postcode.trim().replace(/\s+/g, '').toUpperCase();
      }

      if (radiusMeters !== undefined) {
        const parsed = Number(radiusMeters);
        if (Number.isNaN(parsed)) {
          return res.status(400).json({ error: 'radiusMeters must be a number' });
        }
        updateData.radiusMeters = parsed;
      }

      if (latitude !== undefined) updateData.latitude = typeof latitude === 'number' ? latitude : (latitude === null ? null : Number(latitude));
      if (longitude !== undefined) updateData.longitude = typeof longitude === 'number' ? longitude : (longitude === null ? null : Number(longitude));

      const updated = await (this.prisma as any).cluster.update({ where: { id: clusterId }, data: updateData });

      // If lat/lng provided, update PostGIS regionCenter via raw SQL
      if ((latitude !== undefined && latitude !== null) && (longitude !== undefined && longitude !== null)) {
        try {
          await this.prisma.$executeRaw`
            UPDATE clusters
            SET "regionCenter" = ST_SetSRID(ST_MakePoint(${Number(longitude)}, ${Number(latitude)}), 4326)::geography
            WHERE id = ${clusterId}
          `;
        } catch (err) {
          console.error('Failed to update regionCenter for cluster', err);
        }
      }

      const cluster = await (this.prisma as any).cluster.findUnique({ where: { id: clusterId } });
      return res.json(cluster);
    } catch (error: any) {
      console.error('updateCluster error', error);
      return res.status(500).json({ error: 'Failed to update cluster', details: error?.message });
    }
  }

  /**
   * Delete a cluster. Prevent deletion if cluster has active requests.
   */
  public async deleteCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { clusterId } = req.params as { clusterId?: string };
      if (!clusterId) {
        return res.status(400).json({ error: 'clusterId required in path' });
      }

      const cluster = await (this.prisma as any).cluster.findFirst({ where: { id: clusterId, tenantId: tenantId.toString() } });
      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      // Prevent deletion if there are active or processing requests
      const activeRequests = await (this.prisma as any).externalRequest.count({ where: { clusterId, status: { in: [RequestStatus.PENDING, RequestStatus.PROCESSING, RequestStatus.MATCHED] } } });
      if (activeRequests > 0) {
        return res.status(400).json({ error: 'Cannot delete cluster with active requests', activeRequests });
      }

      await (this.prisma as any).cluster.delete({ where: { id: clusterId } });

      return res.json({ success: true, message: 'Cluster deleted' });
    } catch (error: any) {
      console.error('deleteCluster error', error);
      return res.status(500).json({ error: 'Failed to delete cluster', details: error?.message });
    }
  }



























// Add this method to your existing ClusterController

/**
 * Generate AI-powered clusters for a date range
 */
public async generateClusters(req: Request, res: Response) {
  try {
    const tenantId = req.user?.tenantId;
    if (!tenantId) {
      return res.status(403).json({ error: 'tenantId missing from auth context' });
    }

    const {
      startDate,
      endDate,
      maxTravelTime = 30,
      timeWindowTolerance = 15,
      minClusterSize = 2,
      maxClusterSize = 8,
      epsilon = 0.1,
      minPoints = 2
    } = req.body;

    if (!startDate || !endDate) {
      return res.status(400).json({ error: 'startDate and endDate are required' });
    }

    // Initialize services
    const constraintsService = new ConstraintsService(this.prisma);
    const travelService = new TravelService(this.prisma);
    const clusteringService = new ClusteringService(
      this.prisma, 
      constraintsService, 
      travelService
    );

    const params = {
      dateRange: {
        start: new Date(startDate),
        end: new Date(endDate)
      },
      maxTravelTime,
      timeWindowTolerance,
      minClusterSize,
      maxClusterSize,
      epsilon,
      minPoints
    };

    const clusters = await clusteringService.generateClusters(tenantId.toString(), params);

    // Create actual cluster records in database
    const createdClusters = await this.createClusterRecords(tenantId.toString(), clusters);

    return res.json({
      success: true,
      data: {
        clusters: createdClusters,
        summary: {
          totalClusters: clusters.length,
          totalVisits: clusters.reduce((sum, cluster) => sum + cluster.visits.length, 0),
          averageClusterSize: clusters.length > 0 
            ? clusters.reduce((sum, cluster) => sum + cluster.visits.length, 0) / clusters.length 
            : 0
        }
      }
    });

  } catch (error: any) {
    console.error('generateClusters error', error);
    return res.status(500).json({ 
      error: 'Failed to generate clusters', 
      details: error.message 
    });
  }
}

/**
 * Create actual cluster records in database from generated clusters
 */
private async createClusterRecords(tenantId: string, clusters: any[]) {
  const createdClusters = [];

  for (const cluster of clusters) {
    // Create cluster record
    const clusterRecord = await (this.prisma as any).cluster.create({
      data: {
        tenantId,
        name: cluster.name,
        latitude: cluster.centroid.latitude,
        longitude: cluster.centroid.longitude,
        radiusMeters: 5000,
        activeRequestCount: cluster.visits.length,
        totalRequestCount: cluster.visits.length,
        activeCarerCount: cluster.metrics.suggestedCarers.length,
        totalCarerCount: cluster.metrics.suggestedCarers.length,
        lastActivityAt: new Date()
      }
    });

    // Update PostGIS regionCenter
    try {
      await this.prisma.$executeRaw`
        UPDATE clusters 
        SET "regionCenter" = ST_SetSRID(ST_MakePoint(${cluster.centroid.longitude}, ${cluster.centroid.latitude}), 4326)::geography
        WHERE id = ${clusterRecord.id}
      `;
    } catch (error) {
      console.error('Failed to update cluster regionCenter:', error);
    }

    // Assign visits to cluster
    for (const visit of cluster.visits) {
      await (this.prisma as any).externalRequest.update({
        where: { id: visit.id },
        data: { clusterId: clusterRecord.id }
      });
    }

    createdClusters.push({
      ...clusterRecord,
      metrics: cluster.metrics,
      visits: cluster.visits
    });
  }

  return createdClusters;
}


/**
 * Generate OPTIMIZED AI-powered clusters
 */
public async generateOptimizedClusters(req: Request, res: Response) {
  try {
    const tenantId = req.user?.tenantId;
    if (!tenantId) {
      return res.status(403).json({ error: 'tenantId missing from auth context' });
    }

    const {
      startDate,
      endDate,
      maxTravelTime = 30,
      timeWindowTolerance = 15,
      minClusterSize = 2,
      maxClusterSize = 8,
      epsilon = 0.1,
      minPoints = 2,
      enableOptimization = true
    } = req.body;

    if (!startDate || !endDate) {
      return res.status(400).json({ error: 'startDate and endDate are required' });
    }

    // Initialize services
    const constraintsService = new ConstraintsService(this.prisma);
    const travelService = new TravelService(this.prisma);
    const clusteringService = new ClusteringService(
      this.prisma,
      constraintsService,
      travelService
    );

    const params = {
      dateRange: {
        start: new Date(startDate),
        end: new Date(endDate)
      },
      maxTravelTime,
      timeWindowTolerance,
      minClusterSize,
      maxClusterSize,
      epsilon,
      minPoints,
      enableOptimization
    };

    let result;
    if (enableOptimization) {
      // Use the optimized method
      result = await clusteringService.generateOptimizedClusters(tenantId.toString(), params);
    } else {
      // Use regular method and create compatible result structure
      const clusters = await clusteringService.generateClusters(tenantId.toString(), params);
      const metrics = clusteringService.calculateOverallQualityMetrics(clusters);

      result = {
        clusters,
        metrics: {
          before: metrics,
          after: metrics,
          improvements: {
            geographicCompactness: 0,
            timeWindowCohesion: 0,
            carerFitScore: 0,
            workloadBalance: 0
          }
        },
        actions: {
          clustersSplit: 0,
          clustersMerged: 0,
          outliersRemoved: 0,
          visitsReassigned: 0
        }
      };
    }

    return res.json({
      success: true,
      data: result,
      message: enableOptimization ?
        `Generated ${result.clusters.length} optimized clusters` :
        `Generated ${result.clusters.length} raw clusters`
    });

  } catch (error: any) {
    console.error('generateOptimizedClusters error', error);
    return res.status(500).json({
      error: 'Failed to generate clusters',
      details: error.message
    });
  }
}

/**
 * Get intelligent cluster suggestions for a client
 */
public async getClientClusterSuggestions(req: Request, res: Response) {
  try {
    const tenantId = req.user?.tenantId;
    if (!tenantId) {
      return res.status(403).json({ error: 'tenantId missing from auth context' });
    }

    const { clientId } = req.params;
    const {
      maxSuggestions = 3,
      maxDistanceKm = 50,
      includeInactiveClusters = false
    } = req.query;

    if (!clientId) {
      return res.status(400).json({ error: 'clientId required in path' });
    }

    // Import the service dynamically to avoid circular dependencies
    const { ClientClusterDistanceService } = await import('../services/client-cluster-distance.service');
    const distanceService = new ClientClusterDistanceService(this.prisma);

    const suggestions = await distanceService.getClusterSuggestions(
      clientId,
      tenantId.toString(),
      {
        maxSuggestions: Number(maxSuggestions),
        maxDistanceKm: Number(maxDistanceKm),
        includeInactiveClusters: includeInactiveClusters === 'true'
      }
    );

    return res.json({
      success: true,
      data: suggestions
    });
  } catch (error: any) {
    console.error('getClientClusterSuggestions error', error);
    return res.status(500).json({
      error: 'Failed to get cluster suggestions',
      details: error.message
    });
  }
}

/**
 * Get batch cluster suggestions for multiple clients
 */
public async getBatchClientClusterSuggestions(req: Request, res: Response) {
  try {
    const tenantId = req.user?.tenantId;
    if (!tenantId) {
      return res.status(403).json({ error: 'tenantId missing from auth context' });
    }

    const { clientIds } = req.body;
    const {
      maxSuggestions = 3,
      maxDistanceKm = 50,
      includeInactiveClusters = false
    } = req.query;

    if (!Array.isArray(clientIds) || clientIds.length === 0) {
      return res.status(400).json({ error: 'clientIds array required in body' });
    }

    // Import the service dynamically to avoid circular dependencies
    const { ClientClusterDistanceService } = await import('../services/client-cluster-distance.service');
    const distanceService = new ClientClusterDistanceService(this.prisma);

    const suggestions = await distanceService.getBatchClusterSuggestions(
      clientIds,
      tenantId.toString(),
      {
        maxSuggestions: Number(maxSuggestions),
        maxDistanceKm: Number(maxDistanceKm),
        includeInactiveClusters: includeInactiveClusters === 'true'
      }
    );

    return res.json({
      success: true,
      data: suggestions,
      summary: {
        totalClients: clientIds.length,
        processedClients: suggestions.length,
        averageSuggestionsPerClient: suggestions.length > 0
          ? suggestions.reduce((sum, s) => sum + s.suggestions.length, 0) / suggestions.length
          : 0
      }
    });
  } catch (error: any) {
    console.error('getBatchClientClusterSuggestions error', error);
    return res.status(500).json({
      error: 'Failed to get batch cluster suggestions',
      details: error.message
    });
  }
}
}