const { PrismaClient } = require('@prisma/client');

async function checkClusterClients() {
  const prisma = new PrismaClient();

  try {
    // Set the schema for multi-tenant setup
    await prisma.$executeRaw`SET search_path TO proliance`;

    // Check specific cluster
    const clusterId = 'cmizxfm7w0004pv01cwzghaqz';
    const tenantId = '4'; // From your JWT token

    console.log(`Checking client assignments for cluster ${clusterId} in tenant ${tenantId} (schema: proliance)`);

    // First check if cluster exists
    const cluster = await prisma.cluster.findUnique({
      where: {
        id: clusterId,
        tenantId: tenantId
      }
    });

    if (!cluster) {
      console.log(`❌ Cluster ${clusterId} not found in tenant ${tenantId}`);
      return;
    }

    console.log(`✅ Cluster found: ${cluster.name} (${cluster.postcode})`);

    // Query all client assignments for this cluster
    const assignments = await prisma.clusterClient.findMany({
      where: {
        tenantId: tenantId,
        clusterId: clusterId
      }
    });

    console.log(`\nFound ${assignments.length} client assignments for cluster ${clusterId}:`);

    if (assignments.length === 0) {
      console.log('❌ No clients assigned to this cluster.');
    } else {
      assignments.forEach((assignment, index) => {
        console.log(`${index + 1}. Client ID: ${assignment.clientId}`);
        console.log(`   Assigned At: ${assignment.createdAt}`);
        console.log('');
      });

      console.log(`✅ Cluster ${clusterId} has ${assignments.length} client(s) assigned.`);
      console.log('Client IDs:', assignments.map(a => a.clientId));
    }

    // Also check total clusterClient records
    const totalRecords = await prisma.clusterClient.count({
      where: { tenantId: tenantId }
    });
    console.log(`\nTotal clusterClient records in tenant ${tenantId}: ${totalRecords}`);

  } catch (error) {
    console.error('Error checking cluster clients:', error);
  } finally {
    await prisma.$disconnect();
  }
}

// Run the check
checkClusterClients();