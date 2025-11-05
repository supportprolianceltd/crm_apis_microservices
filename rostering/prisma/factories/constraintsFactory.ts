// prisma/factories/constraintsFactory.ts
import { PrismaClient } from '@prisma/client';

const TENANT_ID = '4';
const TEST_USER_ID = '1';

export async function createConstraints(prisma: PrismaClient) {
  console.log('Seeding constraints...');

  await prisma.rosteringConstraints.upsert({
    where: { tenantId_name: { tenantId: TENANT_ID, name: 'Default Rules' } },
    update: {},
    create: {
      tenantId: TENANT_ID,
      name: 'Default Rules',
      wtdMaxHoursPerWeek: 48,
      restPeriodHours: 11,
      bufferMinutes: 5,
      travelMaxMinutes: 20,
      continuityTargetPercent: 85,
      maxDailyHours: 10,
      isActive: true,
      createdBy: TEST_USER_ID
    }
  });

  await prisma.rosteringConstraints.upsert({
    where: { tenantId_name: { tenantId: TENANT_ID, name: 'Weekend Emergency' } },
    update: {},
    create: {
      tenantId: TENANT_ID,
      name: 'Weekend Emergency',
      wtdMaxHoursPerWeek: 40,
      restPeriodHours: 12,
      bufferMinutes: 10,
      travelMaxMinutes: 30,
      continuityTargetPercent: 70,
      maxDailyHours: 8,
      isActive: false,
      createdBy: TEST_USER_ID
    }
  });

  console.log('Constraints seeded');
}