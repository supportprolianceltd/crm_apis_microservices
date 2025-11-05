import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { ClusterMetricsService } from '../services/cluster-metrics.service';
import { logger } from '../utils/logger';

interface AuthenticatedRequest extends Request {
  user: {
    id: string;
    email: string;
    tenantId: string;
  };
}

export class ClusterMetricsController {
  private clusterMetricsService: ClusterMetricsService;

  constructor(private prisma: PrismaClient) {
    this.clusterMetricsService = new ClusterMetricsService(prisma);
  }

  /**
   * Calculate metrics for a specific cluster
   * POST /api/rostering/cluster-metrics/calculate
   */
  calculateClusterMetrics = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { clusterId } = req.body;

      if (!clusterId) {
        res.status(400).json({
          success: false,
          error: 'clusterId is required'
        });
        return;
      }

      logger.info('Calculating cluster metrics', { tenantId, clusterId });

      const metrics = await this.clusterMetricsService.calculateClusterMetrics(clusterId);

      res.json({
        success: true,
        data: metrics,
        message: 'Cluster metrics calculated successfully'
      });

    } catch (error: any) {
      logger.error('Failed to calculate cluster metrics:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to calculate cluster metrics',
        message: error.message
      });
    }
  };

  /**
   * Get latest metrics for a cluster
   * GET /api/rostering/cluster-metrics/:clusterId
   */
  getClusterMetrics = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { clusterId } = req.params;
      const { hoursBack = '24' } = req.query;

      if (!clusterId) {
        res.status(400).json({
          success: false,
          error: 'clusterId is required'
        });
        return;
      }

      logger.info('Getting cluster metrics', { tenantId, clusterId, hoursBack });

      const metrics = await this.clusterMetricsService.getClusterMetrics(
        clusterId, 
        parseInt(hoursBack as string)
      );

      if (!metrics) {
        res.status(404).json({
          success: false,
          error: 'No recent metrics found for this cluster',
          message: 'Metrics may need to be calculated first'
        });
        return;
      }

      res.json({
        success: true,
        data: metrics
      });

    } catch (error: any) {
      logger.error('Failed to get cluster metrics:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get cluster metrics',
        message: error.message
      });
    }
  };

  /**
   * Get metrics for multiple clusters
   * POST /api/rostering/cluster-metrics/batch
   */
  getBatchClusterMetrics = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { clusterIds, hoursBack = 24 } = req.body;

      if (!Array.isArray(clusterIds) || clusterIds.length === 0) {
        res.status(400).json({
          success: false,
          error: 'clusterIds array is required'
        });
        return;
      }

      logger.info('Getting batch cluster metrics', { 
        tenantId, 
        clusterCount: clusterIds.length,
        hoursBack 
      });

      const metricsPromises = clusterIds.map(clusterId =>
        this.clusterMetricsService.getClusterMetrics(clusterId, hoursBack)
      );

      const metricsResults = await Promise.all(metricsPromises);
      
      const metrics = metricsResults.filter(metric => metric !== null);
      const missing = clusterIds.length - metrics.length;

      res.json({
        success: true,
        data: {
          metrics,
          summary: {
            totalRequested: clusterIds.length,
            found: metrics.length,
            missing,
            missingClusters: clusterIds.filter((_, index) => metricsResults[index] === null)
          }
        }
      });

    } catch (error: any) {
      logger.error('Failed to get batch cluster metrics:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get batch cluster metrics',
        message: error.message
      });
    }
  };

  /**
   * Get cluster metrics history
   * GET /api/rostering/cluster-metrics/:clusterId/history
   */
  getClusterMetricsHistory = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { clusterId } = req.params;
      const { days = '7', limit = '50' } = req.query;

      if (!clusterId) {
        res.status(400).json({
          success: false,
          error: 'clusterId is required'
        });
        return;
      }

      const daysAgo = new Date();
      daysAgo.setDate(daysAgo.getDate() - parseInt(days as string));

      const metricsHistory = await this.prisma.clusterMetrics.findMany({
        where: {
          clusterId,
          calculatedAt: {
            gte: daysAgo
          }
        },
        orderBy: {
          calculatedAt: 'desc'
        },
        take: parseInt(limit as string)
      });

      logger.info('Retrieved cluster metrics history', {
        tenantId,
        clusterId,
        records: metricsHistory.length
      });

      res.json({
        success: true,
        data: {
          clusterId,
          history: metricsHistory,
          summary: {
            totalRecords: metricsHistory.length,
            dateRange: {
              from: daysAgo,
              to: new Date()
            }
          }
        }
      });

    } catch (error: any) {
      logger.error('Failed to get cluster metrics history:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get cluster metrics history',
        message: error.message
      });
    }
  };

  /**
   * Force recalculate all clusters for tenant
   * POST /api/rostering/cluster-metrics/recalculate-all
   */
  recalculateAllClusters = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();

      logger.info('Recalculating metrics for all clusters', { tenantId });

      // Get all active clusters for tenant
      const clusters = await this.prisma.cluster.findMany({
        where: { tenantId },
        select: { id: true, name: true }
      });

      const results = {
        total: clusters.length,
        successful: 0,
        failed: 0,
        details: [] as Array<{ clusterId: string; clusterName: string; status: string; error?: string }>
      };

      // Calculate metrics for each cluster
      for (const cluster of clusters) {
        try {
          await this.clusterMetricsService.calculateClusterMetrics(cluster.id);
          results.successful++;
          results.details.push({
            clusterId: cluster.id,
            clusterName: cluster.name,
            status: 'success'
          });
        } catch (error: any) {
          results.failed++;
          results.details.push({
            clusterId: cluster.id,
            clusterName: cluster.name,
            status: 'failed',
            error: error.message
          });
          logger.error(`Failed to calculate metrics for cluster ${cluster.id}:`, error);
        }
      }

      logger.info('Cluster metrics recalculation completed', results);

      res.json({
        success: true,
        data: results,
        message: `Recalculation completed: ${results.successful} successful, ${results.failed} failed`
      });

    } catch (error: any) {
      logger.error('Failed to recalculate all cluster metrics:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to recalculate all cluster metrics',
        message: error.message
      });
    }
  };

  /**
   * Get cluster comparison report
   * POST /api/rostering/cluster-metrics/comparison
   */
  getClusterComparison = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { clusterIds } = req.body;

      if (!Array.isArray(clusterIds) || clusterIds.length === 0) {
        res.status(400).json({
          success: false,
          error: 'clusterIds array is required'
        });
        return;
      }

      logger.info('Generating cluster comparison report', { 
        tenantId, 
        clusterCount: clusterIds.length 
      });

      // Get latest metrics for all specified clusters
      const metricsPromises = clusterIds.map(clusterId =>
        this.clusterMetricsService.getClusterMetrics(clusterId, 24)
      );

      const metricsResults = await Promise.all(metricsPromises);
      const validMetrics = metricsResults.filter(metric => metric !== null);

      if (validMetrics.length === 0) {
        res.status(404).json({
          success: false,
          error: 'No metrics found for the specified clusters',
          message: 'Please calculate metrics first'
        });
        return;
      }

      // Generate comparison data
      const comparison = {
        clusters: validMetrics,
        summary: {
          totalClusters: validMetrics.length,
          averageVisits: this.calculateAverage(validMetrics, 'totalVisits'),
          averageHours: this.calculateAverage(validMetrics, 'totalHours'),
          averageSkillCoverage: this.calculateAverage(validMetrics, 'skillCoverage'),
          averageContinuityRisk: this.calculateAverage(validMetrics, 'continuityRisk'),
          bestPerforming: this.findBestPerforming(validMetrics),
          needsAttention: this.findNeedsAttention(validMetrics)
        }
      };

      res.json({
        success: true,
        data: comparison
      });

    } catch (error: any) {
      logger.error('Failed to generate cluster comparison:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to generate cluster comparison',
        message: error.message
      });
    }
  };

  // Helper methods for comparison
  private calculateAverage(metrics: any[], field: string): number {
    const values = metrics.map(m => m[field]).filter(val => val !== undefined);
    if (values.length === 0) return 0;
    return values.reduce((sum, val) => sum + val, 0) / values.length;
  }

  private findBestPerforming(metrics: any[]): any {
    return metrics.reduce((best, current) => {
      const bestScore = (best.skillCoverage || 0) - (best.continuityRisk || 0);
      const currentScore = (current.skillCoverage || 0) - (current.continuityRisk || 0);
      return currentScore > bestScore ? current : best;
    }, metrics[0]);
  }

  private findNeedsAttention(metrics: any[]): any[] {
    return metrics.filter(metric => 
      (metric.skillCoverage || 0) < 0.7 || 
      (metric.continuityRisk || 0) > 0.3
    );
  }
}