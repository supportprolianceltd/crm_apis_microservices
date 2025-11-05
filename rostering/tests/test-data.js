"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createTestData = createTestData;
exports.cleanupTestData = cleanupTestData;
const client_1 = require("@prisma/client");
async async function createTestData(prisma, tenantId) {
    await prisma.rosteringConstraints.upsert({
        where: {
            tenantId_name: {
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
    await prisma.carer.createMany({
        data: [
            {
                tenantId,
                firstName: 'Test',
                lastName: 'Carer1',
                email: 'carer1@test.com',
                phone: '+1234567890',
                address: '123 Test Street',
                postcode: 'SW1A 1AA',
                country: 'UK',
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
                address: '124 Test Street',
                postcode: 'SW1A 2AB',
                country: 'UK',
                skills: ['dementia_care', 'mobility_support'],
                maxTravelDistance: 15000,
                latitude: 51.5112,
                longitude: -0.1198,
                isActive: true
            }
        ]
    });
    await prisma.externalRequest.createMany({
        data: [
            {
                tenantId,
                subject: 'Test Request 1',
                content: 'Test content for request 1',
                requestorEmail: 'client1@test.com',
                address: '125 Test Street',
                postcode: 'SW1A 1AA',
                latitude: 51.5014,
                longitude: -0.1419,
                requirements: 'nursing, elderly_care',
                scheduledStartTime: new Date('2024-01-15T09:00:00Z'),
                scheduledEndTime: new Date('2024-01-15T10:00:00Z'),
                estimatedDuration: 60,
                status: client_1.RequestStatus.APPROVED,
                sendToRostering: true
            },
            {
                tenantId,
                subject: 'Test Request 2',
                content: 'Test content for request 2',
                requestorEmail: 'client2@test.com',
                address: '126 Test Street',
                postcode: 'SW1A 2AB',
                latitude: 51.5020,
                longitude: -0.1400,
                requirements: 'dementia_care',
                scheduledStartTime: new Date('2024-01-15T10:30:00Z'),
                scheduledEndTime: new Date('2024-01-15T11:30:00Z'),
                estimatedDuration: 60,
                status: client_1.RequestStatus.APPROVED,
                sendToRostering: true
            },
            {
                tenantId,
                subject: 'Test Request 3',
                content: 'Test content for request 3',
                requestorEmail: 'client3@test.com',
                address: '127 Test Street',
                postcode: 'SW1A 1BA',
                latitude: 51.5005,
                longitude: -0.1425,
                requirements: 'mobility_support',
                scheduledStartTime: new Date('2024-01-15T14:00:00Z'),
                scheduledEndTime: new Date('2024-01-15T15:00:00Z'),
                estimatedDuration: 60,
                status: client_1.RequestStatus.APPROVED,
                sendToRostering: true
            }
        ]
    });
}
async function cleanupTestData(prisma, tenantId = 'test-tenant') {
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
//# sourceMappingURL=test-data.js.map