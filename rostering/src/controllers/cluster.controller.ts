import { Request, Response } from 'express';
import { PrismaClient, RequestStatus } from '@prisma/client';
import { ClusteringService } from '../services/clustering.service';
import { CarerService } from '../services/carer.service';

export class ClusterController {
  private clusteringService: ClusteringService;

  constructor(private prisma: PrismaClient) {
    this.clusteringService = new ClusteringService(prisma);
  }

  /**
   * Create a new cluster for the tenant
   */
  public async createCluster(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

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

      // Get carer assignments from clustering service
      const assignments = await this.clusteringService.getCarerAssignmentsInCluster(clusterId);
      
      // Get carer details from auth service
      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
      const carerService = new CarerService();
      
      const carersWithDetails = await Promise.all(
        assignments.map(async (assignment) => {
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
        carerAssignments: carersWithDetails
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
        assignments.map(async (assignment) => {
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
    try {
      const tenantId = req.user?.tenantId;
      if (!tenantId) {
        return res.status(403).json({ error: 'tenantId missing from auth context' });
      }

      const { carerId } = req.params;
      const { latitude, longitude } = req.body;

      if (!carerId) {
        return res.status(400).json({ error: 'carerId required in path' });
      }

      if (!latitude || !longitude) {
        return res.status(400).json({ error: 'latitude and longitude required in body' });
      }

      // Use auth-backed CarerService to validate carer identity and tenant
      const authHeader = req.headers.authorization as string | undefined;
      const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : authHeader;
      const carerService = new CarerService();
      const carer = await carerService.getCarerById(token, carerId);

      if (!carer) {
        return res.status(404).json({ error: 'Carer not found in auth service' });
      }

      if (carer.tenantId !== tenantId.toString()) {
        return res.status(403).json({ error: 'Carer does not belong to tenant' });
      }

      const cluster = await this.clusteringService.assignCarerToCluster(tenantId.toString(), carerId, latitude, longitude);

      return res.json({
        carerId,
        clusterId: cluster?.id,
        clusterName: cluster?.name,
        message: 'Carer assigned to cluster successfully'
      });
    } catch (error: any) {
      console.error('assignCarerToCluster error', error);
      return res.status(500).json({ error: 'Failed to assign carer to cluster', details: error?.message });
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
}