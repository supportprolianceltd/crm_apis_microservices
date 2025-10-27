import { Request, Response } from 'express';
import { PrismaClient, RequestStatus } from '@prisma/client';
import { ClusteringService } from '../services/clustering.service';

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

      const { name, description, latitude, longitude, radiusMeters } = req.body;

      if (!name) {
        return res.status(400).json({ error: 'name is required' });
      }

      // Create cluster without PostGIS regionCenter first
      const created = await (this.prisma as any).cluster.create({
        data: {
          tenantId: tenantId.toString(),
          name,
          description: description || null,
          latitude: typeof latitude === 'number' ? latitude : null,
          longitude: typeof longitude === 'number' ? longitude : null,
          radiusMeters: typeof radiusMeters === 'number' ? radiusMeters : 5000,
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
          },
          carers: {
            where: { isActive: true },
            take: 10,
            select: {
              id: true,
              firstName: true,
              lastName: true,
              email: true,
              phone: true,
              skills: true,
              maxTravelDistance: true,
              latitude: true,
              longitude: true
            }
          }
        }
      });

      if (!cluster) {
        return res.status(404).json({ error: 'Cluster not found' });
      }

      return res.json(cluster);
    } catch (error: any) {
      console.error('getClusterDetails error', error);
      return res.status(500).json({ error: 'Failed to fetch cluster details', details: error?.message });
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

      const carers = await this.clusteringService.getCarersInCluster(clusterId, includeNearby);

      return res.json({
        clusterId,
        clusterName: cluster.name,
        includeNearby,
        carers: carers.map(carer => ({
          id: carer.id,
          firstName: carer.firstName,
          lastName: carer.lastName,
          email: carer.email,
          phone: carer.phone,
          skills: carer.skills,
          maxTravelDistance: carer.maxTravelDistance,
          latitude: carer.latitude,
          longitude: carer.longitude,
          isInCluster: carer.clusterId === clusterId
        }))
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

      // Verify carer belongs to tenant
      const carer = await (this.prisma as any).carer.findFirst({
        where: { id: carerId, tenantId: tenantId.toString() }
      });

      if (!carer) {
        return res.status(404).json({ error: 'Carer not found' });
      }

      const cluster = await this.clusteringService.assignCarerToCluster(carerId, latitude, longitude);

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
}