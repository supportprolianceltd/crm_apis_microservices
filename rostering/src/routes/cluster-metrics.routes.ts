import { Router } from 'express';
import { ClusterMetricsController } from '../controllers/cluster-metrics.controller';
import { PrismaClient } from '@prisma/client';

/**
 * @swagger
 * tags:
 *   name: Cluster Metrics
 *   description: Cluster performance metrics and analytics
 */

export function createClusterMetricsRoutes(prisma: PrismaClient): Router {
  const router = Router();
  const controller = new ClusterMetricsController(prisma);

  /**
   * @swagger
   * /api/rostering/cluster-metrics/calculate:
   *   post:
   *     summary: Calculate metrics for a cluster
   *     tags: [Cluster Metrics]
   *     requestBody:
   *       required: true
   *       content:
   *         application/json:
   *           schema:
   *             type: object
   *             required:
   *               - clusterId
   *             properties:
   *               clusterId:
   *                 type: string
   *                 description: ID of the cluster to calculate metrics for
   *     responses:
   *       200:
   *         description: Cluster metrics calculated successfully
   *       400:
   *         description: Missing required parameters
   *       500:
   *         description: Internal server error
   */
  router.post('/calculate', controller.calculateClusterMetrics);

  /**
   * @swagger
   * /api/rostering/cluster-metrics/{clusterId}:
   *   get:
   *     summary: Get latest metrics for a cluster
   *     tags: [Cluster Metrics]
   *     parameters:
   *       - in: path
   *         name: clusterId
   *         required: true
   *         schema:
   *           type: string
   *         description: Cluster ID
   *       - in: query
   *         name: hoursBack
   *         schema:
   *           type: integer
   *           default: 24
   *         description: Maximum age of metrics in hours
   *     responses:
   *       200:
   *         description: Cluster metrics retrieved successfully
   *       404:
   *         description: No recent metrics found
   *       500:
   *         description: Internal server error
   */
  router.get('/:clusterId', controller.getClusterMetrics);

  /**
   * @swagger
   * /api/rostering/cluster-metrics/batch:
   *   post:
   *     summary: Get metrics for multiple clusters
   *     tags: [Cluster Metrics]
   *     requestBody:
   *       required: true
   *       content:
   *         application/json:
   *           schema:
   *             type: object
   *             required:
   *               - clusterIds
   *             properties:
   *               clusterIds:
   *                 type: array
   *                 items:
   *                   type: string
   *               hoursBack:
   *                 type: integer
   *                 default: 24
   *     responses:
   *       200:
   *         description: Batch metrics retrieved successfully
   *       400:
   *         description: Invalid request parameters
   *       500:
   *         description: Internal server error
   */
  router.post('/batch', controller.getBatchClusterMetrics);

  /**
   * @swagger
   * /api/rostering/cluster-metrics/{clusterId}/history:
   *   get:
   *     summary: Get metrics history for a cluster
   *     tags: [Cluster Metrics]
   *     parameters:
   *       - in: path
   *         name: clusterId
   *         required: true
   *         schema:
   *           type: string
   *         description: Cluster ID
   *       - in: query
   *         name: days
   *         schema:
   *           type: integer
   *           default: 7
   *         description: Number of days of history to retrieve
   *       - in: query
   *         name: limit
   *         schema:
   *           type: integer
   *           default: 50
   *         description: Maximum number of records to return
   *     responses:
   *       200:
   *         description: Metrics history retrieved successfully
   *       500:
   *         description: Internal server error
   */
  router.get('/:clusterId/history', controller.getClusterMetricsHistory);

  /**
   * @swagger
   * /api/rostering/cluster-metrics/recalculate-all:
   *   post:
   *     summary: Recalculate metrics for all clusters
   *     tags: [Cluster Metrics]
   *     responses:
   *       200:
   *         description: Recalculation completed
   *       500:
   *         description: Internal server error
   */
  router.post('/recalculate-all', controller.recalculateAllClusters);

  /**
   * @swagger
   * /api/rostering/cluster-metrics/comparison:
   *   post:
   *     summary: Compare multiple clusters
   *     tags: [Cluster Metrics]
   *     requestBody:
   *       required: true
   *       content:
   *         application/json:
   *           schema:
   *             type: object
   *             required:
   *               - clusterIds
   *             properties:
   *               clusterIds:
   *                 type: array
   *                 items:
   *                   type: string
   *     responses:
   *       200:
   *         description: Comparison generated successfully
   *       400:
   *         description: Invalid request parameters
   *       500:
   *         description: Internal server error
   */
  router.post('/comparison', controller.getClusterComparison);

  return router;
}