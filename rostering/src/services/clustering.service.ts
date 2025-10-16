import { PrismaClient } from '@prisma/client';

export class ClusteringService {
  constructor(private prisma: PrismaClient) {}

  /**
   * Find the nearest cluster for a location or create a new one if none exists within threshold
   */
  async findOrCreateClusterForLocation(
    tenantId: string,
    latitude: number,
    longitude: number,
    maxDistanceMeters: number = 5000
  ) {
    try {
      // Find nearest existing cluster using PostGIS
      const nearestClusters = await this.prisma.$queryRaw<Array<{
        id: string;
        name: string;
        distance: number;
      }>>`
        SELECT 
          id, 
          name,
          ST_Distance(
            "regionCenter"::geography, 
            ST_SetSRID(ST_MakePoint(${longitude}, ${latitude}), 4326)::geography
          ) AS distance
        FROM clusters 
        WHERE "tenantId" = ${tenantId}
        ORDER BY "regionCenter" <-> ST_SetSRID(ST_MakePoint(${longitude}, ${latitude}), 4326)
        LIMIT 1
      `;

      // If nearest cluster is within threshold, use it
      if (nearestClusters.length > 0 && nearestClusters[0].distance <= maxDistanceMeters) {
        return await this.prisma.cluster.findUnique({
          where: { id: nearestClusters[0].id }
        });
      }

      // Otherwise, create new cluster
      return await this.createNewCluster(tenantId, latitude, longitude);
    } catch (error) {
      console.error('Error finding/creating cluster:', error);
      // Fallback: create new cluster
      return await this.createNewCluster(tenantId, latitude, longitude);
    }
  }

  /**
   * Create a new cluster at the specified location
   */
  private async createNewCluster(tenantId: string, latitude: number, longitude: number) {
    const clusterName = await this.generateClusterName(latitude, longitude);
    
    // Create cluster without PostGIS field first
    const cluster = await (this.prisma as any).cluster.create({
      data: {
        tenantId,
        name: clusterName,
        latitude,
        longitude,
        radiusMeters: 5000,
        activeRequestCount: 0,
        totalRequestCount: 0,
        activeCarerCount: 0,
        totalCarerCount: 0,
        lastActivityAt: new Date()
      }
    });

    // Update PostGIS regionCenter field using raw SQL
    try {
      await this.prisma.$executeRaw`
        UPDATE clusters 
        SET "regionCenter" = ST_SetSRID(ST_MakePoint(${longitude}, ${latitude}), 4326)::geography
        WHERE id = ${cluster.id}
      `;
    } catch (error) {
      console.error('Failed to update cluster regionCenter:', error);
    }

    return cluster;
  }

  /**
   * Generate a readable cluster name based on coordinates
   */
  private async generateClusterName(latitude: number, longitude: number): Promise<string> {
    // Generate cluster name based on coordinates
    const latPrefix = latitude >= 0 ? 'N' : 'S';
    const lngPrefix = longitude >= 0 ? 'E' : 'W';
    const timestamp = Date.now().toString().slice(-4);
    
    return `Cluster ${latPrefix}${Math.abs(latitude).toFixed(2)} ${lngPrefix}${Math.abs(longitude).toFixed(2)}-${timestamp}`;
  }

  /**
   * Update cluster statistics (call this after adding/removing requests or carers)
   */
  async updateClusterStats(clusterId: string) {
    try {
      const stats = await this.prisma.$queryRaw<Array<{
        active_requests: number;
        total_requests: number;
        active_carers: number;
        total_carers: number;
      }>>`
        SELECT 
          COUNT(CASE WHEN er.status IN ('PENDING', 'PROCESSING', 'MATCHED') THEN 1 END) as active_requests,
          COUNT(er.id) as total_requests,
          COUNT(CASE WHEN c."isActive" = true THEN 1 END) as active_carers,
          COUNT(c.id) as total_carers
        FROM clusters cl
        LEFT JOIN external_requests er ON er."clusterId" = cl.id
        LEFT JOIN carers c ON c."clusterId" = cl.id
        WHERE cl.id = ${clusterId}
        GROUP BY cl.id
      `;

      if (stats.length > 0) {
        await this.prisma.cluster.update({
          where: { id: clusterId },
          data: {
            activeRequestCount: Number(stats[0].active_requests) || 0,
            totalRequestCount: Number(stats[0].total_requests) || 0,
            activeCarerCount: Number(stats[0].active_carers) || 0,
            totalCarerCount: Number(stats[0].total_carers) || 0,
            lastActivityAt: new Date()
          }
        });
      }
    } catch (error) {
      console.error('Error updating cluster stats:', error);
    }
  }

  /**
   * Get available carers in a cluster, with option to include nearby carers
   */
  async getCarersInCluster(clusterId: string, includeNearby: boolean = false) {
    let carers = await this.prisma.carer.findMany({
      where: {
        clusterId,
        isActive: true
      }
    });

    // If not enough carers in cluster, find nearby ones
    if (includeNearby && carers.length < 3) {
      const cluster = await (this.prisma as any).cluster.findUnique({
        where: { id: clusterId }
      });

      if (cluster && cluster.latitude && cluster.longitude) {
        try {
          const nearbyCarers = await this.prisma.$queryRaw<any[]>`
            SELECT c.* 
            FROM carers c
            WHERE c."tenantId" = ${cluster.tenantId}
              AND c."isActive" = true
              AND (c."clusterId" != ${clusterId} OR c."clusterId" IS NULL)
              AND c.location IS NOT NULL
              AND ST_DWithin(
                c.location::geography,
                ST_SetSRID(ST_MakePoint(${cluster.longitude}, ${cluster.latitude}), 4326)::geography,
                c."maxTravelDistance"
              )
            ORDER BY ST_Distance(
              c.location::geography,
              ST_SetSRID(ST_MakePoint(${cluster.longitude}, ${cluster.latitude}), 4326)::geography
            )
            LIMIT 10
          `;

          carers = [...carers, ...nearbyCarers];
        } catch (error) {
          console.error('Error finding nearby carers:', error);
        }
      }
    }

    return carers;
  }

  /**
   * Assign a carer to a cluster based on their location
   */
  async assignCarerToCluster(carerId: string, latitude: number, longitude: number) {
    try {
      const carer = await this.prisma.carer.findUnique({
        where: { id: carerId }
      });

      if (!carer) {
        throw new Error('Carer not found');
      }

      const cluster = await this.findOrCreateClusterForLocation(
        carer.tenantId.toString(),
        latitude,
        longitude
      );

      if (cluster) {
        await (this.prisma as any).carer.update({
          where: { id: carerId },
          data: { clusterId: cluster.id }
        });

        // Update cluster stats
        await this.updateClusterStats(cluster.id);
      }

      return cluster;
    } catch (error) {
      console.error('Error assigning carer to cluster:', error);
      throw error;
    }
  }

  /**
   * Get cluster overview for analytics
   */
  async getClusterAnalytics(tenantId: string) {
    const clusters = await (this.prisma as any).cluster.findMany({
      where: { tenantId: tenantId.toString() },
      orderBy: [
        { activeRequestCount: 'desc' },
        { activeCarerCount: 'desc' }
      ]
    });

    // Find clusters that need attention (high demand, low supply)
    const needAttention = clusters.filter(
      (c: any) => c.activeRequestCount > 5 && c.activeCarerCount < 3
    );

    return {
      clusters,
      summary: {
        totalClusters: clusters.length,
        needAttention: needAttention.length,
        totalActiveRequests: clusters.reduce((sum: number, c: any) => sum + c.activeRequestCount, 0),
        totalActiveCarers: clusters.reduce((sum: number, c: any) => sum + c.activeCarerCount, 0),
        clustersNeedingAttention: needAttention
      }
    };
  }
}