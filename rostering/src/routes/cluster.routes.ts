import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { ClusterController } from '../controllers/cluster.controller';

const router = Router();

export function createClusterRoutes(prisma: PrismaClient) {
  const clusterController = new ClusterController(prisma);

  // Get cluster overview for tenant
  router.get('/', clusterController.getClusterOverview.bind(clusterController));

  // Get detailed information about a specific cluster
  router.get('/:clusterId', clusterController.getClusterDetails.bind(clusterController));

  // Get carers in a specific cluster
  router.get('/:clusterId/carers', clusterController.getClusterCarers.bind(clusterController));

  // Update cluster statistics
  router.post('/:clusterId/refresh-stats', clusterController.updateClusterStats.bind(clusterController));

  // Assign carer to cluster
  router.post('/assign-carer/:carerId', clusterController.assignCarerToCluster.bind(clusterController));

  return router;
}