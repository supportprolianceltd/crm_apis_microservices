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
    maxDistanceMeters: number = 500
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
   * Update cluster statistics using ClusterAssignment table
   */
  async updateClusterStats(clusterId: string) {
    try {
      // Get counts from ClusterAssignment table
      const stats = await this.prisma.$queryRaw<Array<{
        active_carers: number;
        total_carers: number;
        active_requests: number;
        total_requests: number;
      }>>`
        SELECT 
          COUNT(ca.id) as active_carers,
          COUNT(ca.id) as total_carers, -- For now, all assigned carers are considered active
          COUNT(CASE WHEN er.status IN ('PENDING', 'PROCESSING', 'MATCHED') THEN 1 END) as active_requests,
          COUNT(er.id) as total_requests
        FROM clusters cl
        LEFT JOIN cluster_assignments ca ON ca."clusterId" = cl.id
        LEFT JOIN external_requests er ON er."clusterId" = cl.id
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
   * Get carer assignments in a cluster (returns assignment IDs, not carer details)
   */
  async getCarerAssignmentsInCluster(clusterId: string) {
    return await this.prisma.clusterAssignment.findMany({
      where: { clusterId },
      include: { cluster: true }
    });
  }

  /**
   * Get available carer assignments in cluster with optional nearby clusters
   */
    async getCarerAssignmentsInClusterWithNearby(
      clusterId: string, 
      includeNearby: boolean = false,
      maxDistanceMeters: number = 10000
    ) {
      const cluster = await this.prisma.cluster.findUnique({
        where: { id: clusterId }
      });

      if (!cluster || !cluster.latitude || !cluster.longitude) {
        return await this.getCarerAssignmentsInCluster(clusterId);
      }

      let assignments = await this.getCarerAssignmentsInCluster(clusterId);

      // If not enough carers in cluster and nearby requested, find nearby assignments
      if (includeNearby && assignments.length < 3) {
        try {
          const nearbyAssignments = await this.prisma.$queryRaw<any[]>`
            SELECT ca.* 
            FROM cluster_assignments ca
            JOIN clusters c ON c.id = ca."clusterId"
            WHERE ca."clusterId" != ${clusterId}
              AND ca."tenantId" = ${cluster.tenantId}
              AND c.latitude IS NOT NULL 
              AND c.longitude IS NOT NULL
              AND ST_DWithin(
                c."regionCenter"::geography,
                ST_SetSRID(ST_MakePoint(${cluster.longitude}, ${cluster.latitude}), 4326)::geography,
                ${maxDistanceMeters}
              )
            ORDER BY ST_Distance(
              c."regionCenter"::geography,
              ST_SetSRID(ST_MakePoint(${cluster.longitude}, ${cluster.latitude}), 4326)::geography
            )
            LIMIT 10
          `;

          assignments = [...assignments, ...nearbyAssignments];
        } catch (error) {
          console.error('Error finding nearby carer assignments:', error);
        }
      }

      return assignments;
    }


  /**
   * Assign a carer to a cluster based on their location
   */
  async assignCarerToCluster(tenantId: string, carerId: string, latitude: number, longitude: number) {
    try {


      const cluster = await this.findOrCreateClusterForLocation(
        tenantId,
        latitude,
        longitude
      );

      if (cluster) {
        await this.prisma.clusterAssignment.upsert({
        where: {
          carerId_tenantId: {
            carerId: carerId,
            tenantId: tenantId
          }
        },
        update: { 
          clusterId: cluster.id,
          updatedAt: new Date()
        },
        create: {
          carerId: carerId,
          clusterId: cluster.id,
          tenantId: tenantId,
          assignedAt: new Date()
        }
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

  /**
   * Remove carer from cluster (when they become inactive)
   */
  async removeCarerFromCluster(tenantId: string, carerId: string) {
    const assignment = await this.prisma.clusterAssignment.findUnique({
      where: { carerId_tenantId: { carerId, tenantId } }
    });

    if (assignment) {
      await this.prisma.clusterAssignment.delete({
        where: { carerId_tenantId: { carerId, tenantId } }
      });
      await this.updateClusterStats(assignment.clusterId);
    }
  }

  /**
   * Get carer's current cluster assignment
   */
  async getCarerClusterAssignment(tenantId: string, carerId: string) {
    return await this.prisma.clusterAssignment.findUnique({
      where: { carerId_tenantId: { carerId, tenantId } },
      include: { cluster: true }
    });
  }

  /**
   * Move carer from one cluster to another
   */
  async moveCarerToCluster(tenantId: string, carerId: string, newClusterId: string) {
    try {
      // Verify the new cluster exists and belongs to the same tenant
      const newCluster = await this.prisma.cluster.findUnique({
        where: { id: newClusterId }
      });

      if (!newCluster) {
        throw new Error('Target cluster not found');
      }

      if (newCluster.tenantId !== tenantId) {
        throw new Error('Target cluster does not belong to tenant');
      }

      // Get current assignment to track which cluster stats to update
      const currentAssignment = await this.prisma.clusterAssignment.findUnique({
        where: {
          carerId_tenantId: {
            carerId: carerId,
            tenantId: tenantId
          }
        }
      });

      // Move carer to new cluster
      const updatedAssignment = await this.prisma.clusterAssignment.upsert({
        where: {
          carerId_tenantId: {
            carerId: carerId,
            tenantId: tenantId
          }
        },
        update: { 
          clusterId: newClusterId,
          updatedAt: new Date()
        },
        create: {
          carerId: carerId,
          clusterId: newClusterId,
          tenantId: tenantId,
          assignedAt: new Date()
        }
      });

      // Update stats for both old and new clusters
      if (currentAssignment) {
        await this.updateClusterStats(currentAssignment.clusterId); // Old cluster
      }
      await this.updateClusterStats(newClusterId); // New cluster

      return {
        carerId,
        previousClusterId: currentAssignment?.clusterId || null,
        newClusterId,
        message: 'Carer moved to cluster successfully'
      };
    } catch (error) {
      console.error('Error moving carer to cluster:', error);
      throw error;
    }
  }
}