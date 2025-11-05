// prisma/seed.ts
import { PrismaClient } from '@prisma/client';
import { createConstraints } from './factories/constraintsFactory';
import { createCarer } from './factories/carerFactory';
import { seedVisits } from './factories/visitFactory';

const prisma = new PrismaClient();
const TENANT_ID = '4';

async function main() {
  console.log('Starting factory-based seed...\n');

  // Cleanup
  await cleanup();

  // Seed in order
  await createConstraints(prisma);

  // Seed specific carers (your 8 known ones)
  const carers = await seedKnownCarers();

  // Or generate random ones
  // const randomCarers = await Promise.all(Array.from({ length: 20 }, () => createCarer(prisma)));

  const visits = await seedVisits(prisma);
  // await seedHistoricalMatches(carers, visits);
  // await seedTravelMatrixCache(prisma);

  console.log('\nSeed completed!');
  console.log(`Carers: ${carers.length} | Visits: ${visits.length}`);
}

async function cleanup() {
  console.log('Cleaning old data...');
  const deleteOps = [
    prisma.requestCarerMatch.deleteMany({ where: { tenantId: TENANT_ID } }),
    prisma.assignment.deleteMany({ where: { tenantId: TENANT_ID } }),
    prisma.externalRequest.deleteMany({ where: { tenantId: TENANT_ID } }),
    prisma.carer.deleteMany({ where: { tenantId: TENANT_ID } }),
    prisma.rosteringConstraints.deleteMany({ where: { tenantId: TENANT_ID } }),
    prisma.travelMatrixCache.deleteMany()
  ];
  await Promise.all(deleteOps);
  console.log('Cleanup done\n');
}

async function seedKnownCarers() {
  console.log('Seeding known carers...');
  const known = [
    { firstName: 'Robert', lastName: 'Johnson', postcode: 'NW4' as const, experience: 8 },
    { firstName: 'Christine', lastName: 'Williams', postcode: 'NW4' as const, experience: 12 },
    { firstName: 'Hasan', lastName: 'Ahmed', postcode: 'HA2' as const, experience: 5 },
    { firstName: 'Olivia', lastName: 'Martinez', postcode: 'W5' as const, experience: 6 },
    { firstName: 'Janet', lastName: 'Thompson', postcode: 'NW10' as const, experience: 15 },
    { firstName: 'Daniel', lastName: 'Brown', postcode: 'HA2' as const, experience: 4 },
    { firstName: 'Sarah', lastName: 'Davis', postcode: 'N12' as const, experience: 10 },
    { firstName: 'Michael', lastName: 'Wilson', postcode: 'HA5' as const, experience: 9 },
  ];

  const carers = [];
  for (const c of known) {
    const carer = await createCarer(prisma, c);
    carers.push(carer);
  }
  console.log(`Created ${carers.length} known carers`);
  return carers;
}


main()
  .catch(e => {
    console.error('Seed failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });