import { Request, Response } from 'express';
import { PrismaClient, RequestStatus } from '@prisma/client';
import { ClusteringService } from '../services/clustering.service';
import { ConstraintsService } from '../services/constraints.service';
import { TravelService } from '../services/travel.service';

interface Carer {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  skills: string[];
  maxTravelDistance: number;
  latitude: number | null;
  longitude: number | null;
  clusterId?: string;
}

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

      const tenantId = user.tenantId.toString();
      const { name, description, postcode, latitude, longitude } = req.body;

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
        carers: carers.map((carer: Carer) => ({
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
}


