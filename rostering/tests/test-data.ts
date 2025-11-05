// tests/test-data.ts
import { PrismaClient, RequestStatus } from '@prisma/client';

export async async function createTestData(prisma: PrismaClient, tenantId: string) {
  // Create default constraints
  await prisma.rosteringConstraints.upsert({
    where: { 
      tenantId_name: { // ✅ FIXED: Use correct unique constraint
        tenantId,
        name: 'Test Constraints'
      }
    },
    update: {},
    create: {
      tenantId,
      name: 'Test Constraints',
      wtdMaxHoursPerWeek: 48,
      restPeriodHours: 11,
      bufferMinutes: 5,
      travelMaxMinutes: 30,
      continuityTargetPercent: 85,
      isActive: true,
      createdBy: 'test'
    }
  });

  // Create test carers with required fields
  await prisma.carer.createMany({
    data: [
      {
        tenantId,
        firstName: 'Test',
        lastName: 'Carer1',
        email: 'carer1@test.com',
        phone: '+1234567890',
        address: '123 Test Street', // ✅ ADDED
        postcode: 'SW1A 1AA', // ✅ ADDED
        country: 'UK', // ✅ ADDED
        skills: ['nursing', 'elderly_care'],
        maxTravelDistance: 10000,
        latitude: 51.5074,
        longitude: -0.1278,
        isActive: true
      },
      {
        tenantId,
        firstName: 'Test',
        lastName: 'Carer2',
        email: 'carer2@test.com',
        phone: '+1234567891',
        address: '124 Test Street', // ✅ ADDED
        postcode: 'SW1A 2AB', // ✅ ADDED
        country: 'UK', // ✅ ADDED
        skills: ['dementia_care', 'mobility_support'],
        maxTravelDistance: 15000,
        latitude: 51.5112,
        longitude: -0.1198,
        isActive: true
      }
    ]
  });

  // Create test requests with required fields
  await prisma.externalRequest.createMany({
    data: [
      {
        tenantId,
        subject: 'Test Request 1', // ✅ ADDED
        content: 'Test content for request 1', // ✅ ADDED
        requestorEmail: 'client1@test.com', // ✅ ADDED
        address: '125 Test Street', // ✅ ADDED
        postcode: 'SW1A 1AA',
        latitude: 51.5014,
        longitude: -0.1419,
        requirements: 'nursing, elderly_care',
        scheduledStartTime: new Date('2024-01-15T09:00:00Z'),
        scheduledEndTime: new Date('2024-01-15T10:00:00Z'),
        estimatedDuration: 60,
        status: RequestStatus.APPROVED,
        sendToRostering: true // ✅ ADDED
      },
      {
        tenantId,
        subject: 'Test Request 2', // ✅ ADDED
        content: 'Test content for request 2', // ✅ ADDED
        requestorEmail: 'client2@test.com', // ✅ ADDED
        address: '126 Test Street', // ✅ ADDED
        postcode: 'SW1A 2AB',
        latitude: 51.5020,
        longitude: -0.1400,
        requirements: 'dementia_care',
        scheduledStartTime: new Date('2024-01-15T10:30:00Z'),
        scheduledEndTime: new Date('2024-01-15T11:30:00Z'),
        estimatedDuration: 60,
        status: RequestStatus.APPROVED,
        sendToRostering: true // ✅ ADDED
      },
      {
        tenantId,
        subject: 'Test Request 3', // ✅ ADDED
        content: 'Test content for request 3', // ✅ ADDED
        requestorEmail: 'client3@test.com', // ✅ ADDED
        address: '127 Test Street', // ✅ ADDED
        postcode: 'SW1A 1BA',
        latitude: 51.5005,
        longitude: -0.1425,
        requirements: 'mobility_support',
        scheduledStartTime: new Date('2024-01-15T14:00:00Z'),
        scheduledEndTime: new Date('2024-01-15T15:00:00Z'),
        estimatedDuration: 60,
        status: RequestStatus.APPROVED,
        sendToRostering: true // ✅ ADDED
      }
    ]
  });
}
export async function cleanupTestData(prisma: PrismaClient, tenantId: string = 'test-tenant') {
  console.log('🧹 Cleaning up test data...');
  
  await prisma.externalRequest.deleteMany({
    where: { tenantId }
  });
  
  await prisma.carer.deleteMany({
    where: { tenantId }
  });

  await prisma.rosteringConstraints.deleteMany({
    where: { tenantId }
  });

  console.log('✅ Test data cleaned up');
}