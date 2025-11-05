// tests/clustering.test.ts
import { PrismaClient } from '@prisma/client';
import { ClusteringService } from '../src/services/clustering.service'; // ✅ FIXED PATH
import { ConstraintsService } from '../src/services/constraints.service'; // ✅ FIXED PATH
import { TravelService } from '../src/services/travel.service'; // ✅ FIXED PATH

// Fix the tenantId variable issue
async function testClusteringEndpoints() {
  const prisma = new PrismaClient();
  const constraintsService = new ConstraintsService(prisma);
  const travelService = new TravelService(prisma);
  const clusteringService = new ClusteringService(prisma, constraintsService, travelService);

  console.log('🧪 Testing Clustering Endpoints...\n');

  const tenantId = `test-tenant-${Date.now()}`; // ✅ DEFINE tenantId here

  // Test 1: Basic clustering
  console.log('1. Testing basic clustering...');
  try {
    const basicClusters = await clusteringService.generateClusters(tenantId, {
      dateRange: {
        start: new Date('2024-01-15'),
        end: new Date('2024-01-20')
      },
      minClusterSize: 2,
      maxClusterSize: 6
    });
    console.log(`✅ Basic clustering: ${basicClusters.length} clusters generated`);
  } catch (error: any) {
    console.log('❌ Basic clustering failed:', error.message);
  }

  // ... rest of your test code

  // Cleanup at the end
  await cleanupTestData(prisma, tenantId); // ✅ Now tenantId is defined
  await prisma.$disconnect();
}