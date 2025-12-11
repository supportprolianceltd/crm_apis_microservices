const { PrismaClient } = require('@prisma/client');

async function checkClusterClients() {
  const prisma = new PrismaClient();

  try {
    console.log('=== CHECKING CLUSTER CLIENT ASSIGNMENTS ===');

    const clusterId = 'cmizxfm7w0004pv01cwzghaqz';

    // Check if cluster exists
    const cluster = await prisma.cluster.findUnique({
      where: { id: clusterId }
    });

    console.log('Cluster found:', !!cluster);
    if (cluster) {
      console.log('Cluster details:', {
        id: cluster.id,
        name: cluster.name,
        tenantId: cluster.tenantId
      });
    }

    // Check client assignments for this cluster
    const assignments = await prisma.clusterClient.findMany({
      where: { clusterId: clusterId }
    });

    console.log(`\nClient assignments for cluster ${clusterId}:`);
    console.log('Number of assignments:', assignments.length);

    if (assignments.length > 0) {
      console.log('Assignments:');
      assignments.forEach((assignment, index) => {
        console.log(`${index + 1}. Client ID: ${assignment.clientId}, Tenant: ${assignment.tenantId}`);
      });

      const clientIds = assignments.map(a => a.clientId);
      console.log('All client IDs:', clientIds);
    } else {
      console.log('No client assignments found for this cluster');
    }

    // Also check if there are any clusterClient records at all
    const totalAssignments = await prisma.clusterClient.count();
    console.log(`\nTotal clusterClient records in database: ${totalAssignments}`);

    // Check recent assignments
    const recentAssignments = await prisma.clusterClient.findMany({
      orderBy: { createdAt: 'desc' },
      take: 5
    });

    console.log('\nRecent clusterClient assignments:');
    recentAssignments.forEach((assignment, index) => {
      console.log(`${index + 1}. Cluster: ${assignment.clusterId}, Client: ${assignment.clientId}, Created: ${assignment.createdAt}`);
    });

  } catch (error) {
    console.error('Error checking cluster clients:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkClusterClients();