import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { ClusterController } from '../controllers/cluster.controller';

const router = Router();

export function createClusterRoutes(prisma: PrismaClient) {
  const clusterController = new ClusterController(prisma);

  // Get cluster overview for tenant
  router.get('/', clusterController.getClusterOverview.bind(clusterController));
  // Create a new cluster
  router.post('/', clusterController.createCluster.bind(clusterController));

  // Get detailed information about a specific cluster
  router.get('/:clusterId', clusterController.getClusterDetails.bind(clusterController));

  // Get carers in a specific cluster
  router.get('/:clusterId/carers', clusterController.getClusterCarers.bind(clusterController));

  // Update cluster statistics
  router.post('/:clusterId/refresh-stats', clusterController.updateClusterStats.bind(clusterController));

  // Update cluster metadata
  router.put('/:clusterId', clusterController.updateCluster.bind(clusterController));

  // Delete cluster
  router.delete('/:clusterId', clusterController.deleteCluster.bind(clusterController));

  // Assign carer to cluster
  router.post('/assign-carer/:carerId', clusterController.assignCarerToCluster.bind(clusterController));

  // Assign request to cluster
  router.post('/:clusterId/assign-request/:requestId', clusterController.assignRequestToCluster.bind(clusterController));


    // NEW: AI Clustering endpoint
  router.post('/generate', clusterController.generateClusters.bind(clusterController));
    // NEW: Optimized AI Clustering endpoint
  router.post('/generate/optimized', clusterController.generateOptimizedClusters.bind(clusterController));

  return router;
}


