/**
 * Dummy Data Seeder for Roster Generation Testing
 * Run with: npx tsx prisma/dummy-seed.ts
 */

import { PrismaClient } from '@prisma/client';
import { faker } from '@faker-js/faker';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Starting dummy data seeding...');

  const tenantId = 'tenant-123';

  // Clean existing data
  await cleanExistingData(tenantId);

  // Seed carers
  await seedCarers(tenantId);

  // Seed visits
  await seedVisits(tenantId);

  // Seed travel matrix
  await seedTravelMatrix();

  // Seed historical matches
  await seedHistoricalMatches(tenantId);

  // Seed constraints
  await seedConstraints(tenantId);

  console.log('✅ Dummy data seeding completed!');
  console.log('\n📊 Seeded Data Summary:');
  console.log('- 25 Active Carers');
  console.log('- 150 Approved Visits (next 7 days)');
  console.log('- Complete Travel Matrix');
  console.log('- Historical Match Data');
  console.log('- Rostering Constraints');
  console.log('\n🚀 Ready for roster generation testing!');
}

async function cleanExistingData(tenantId: string) {
  console.log('🧹 Cleaning existing test data...');

  await prisma.assignment.deleteMany({ where: { tenantId } });
  await prisma.roster.deleteMany({ where: { tenantId } });
  await prisma.requestCarerMatch.deleteMany({ where: { tenantId } });
  await prisma.externalRequest.deleteMany({ where: { tenantId } });
  await prisma.carer.deleteMany({ where: { tenantId } });
  await prisma.travelMatrix.deleteMany();
  await prisma.rosteringConstraints.deleteMany({ where: { tenantId } });
}

async function seedCarers(tenantId: string) {
  console.log('👥 Seeding carers...');

  const carers = [];
  const skills = ['personal-care', 'medication', 'mobility', 'dementia', 'complex-care', 'hoist'];
  const londonPostcodes = [
    'SW1A 1AA', 'E1 6AN', 'N1 9AL', 'SE1 2AB', 'W1B 1AB',
    'NW1 0AB', 'EC1A 1BB', 'WC1B 3AB', 'SE1 7AB', 'N1 6AB'
  ];

  for (let i = 0; i < 25; i++) {
    const postcode = londonPostcodes[i % londonPostcodes.length];
    const [lat, lng] = getCoordinatesForPostcode(postcode);

    carers.push({
      id: `carer-${String(i + 1).padStart(3, '0')}`,
      tenantId,
      email: `carer${i + 1}@test.com`,
      firstName: faker.person.firstName(),
      lastName: faker.person.lastName(),
      phone: faker.phone.number('+447#######'),
      address: faker.location.streetAddress(),
      postcode,
      latitude: lat + (Math.random() - 0.5) * 0.01, // Add some variation
      longitude: lng + (Math.random() - 0.5) * 0.01,
      isActive: true,
      maxTravelDistance: 10000,
      availabilityHours: {
        monday: ['08:00', '18:00'],
        tuesday: ['08:00', '18:00'],
        wednesday: ['08:00', '18:00'],
        thursday: ['08:00', '18:00'],
        friday: ['08:00', '18:00']
      },
      skills: faker.helpers.arrayElements(skills, faker.number.int({ min: 2, max: 4 })),
      languages: ['english'],
      hourlyRate: faker.number.float({ min: 20, max: 35, precision: 0.01 })
    });
  }

  await prisma.carer.createMany({ data: carers });
  console.log(`✅ Created ${carers.length} carers`);
}

async function seedVisits(tenantId: string) {
  console.log('📅 Seeding visits...');

  const visits = [];
  const requirements = [
    'personal-care',
    'personal-care, medication',
    'complex-care, hoist, mobility',
    'personal-care, dementia',
    'medication, mobility',
    'personal-care, medication, mobility'
  ];

  const postcodes = [
    'SW1A 1AA', 'E1 6AN', 'N1 9AL', 'SE1 2AB', 'W1B 1AB',
    'NW1 0AB', 'EC1A 1BB', 'WC1B 3AB', 'SE1 7AB', 'N1 6AB',
    'E2 7AB', 'N7 8AB', 'SW1V 1AB', 'SE11 5AB', 'W2 3AB'
  ];

  for (let i = 0; i < 150; i++) {
    const daysFromNow = Math.floor(i / 20) + 1; // Distribute over 7 days
    const hour = 8 + Math.floor((i % 20) / 2); // 8 AM to 6 PM
    const startTime = new Date();
    startTime.setDate(startTime.getDate() + daysFromNow);
    startTime.setHours(hour, 0, 0, 0);

    const duration = faker.helpers.arrayElement([30, 60, 90, 120]);
    const endTime = new Date(startTime.getTime() + duration * 60000);

    const postcode = postcodes[i % postcodes.length];
    const [lat, lng] = getCoordinatesForPostcode(postcode);

    visits.push({
      id: `visit-${String(i + 1).padStart(3, '0')}`,
      tenantId,
      subject: `Test Visit ${i + 1}`,
      content: faker.lorem.sentences(2),
      requestorEmail: `client${i + 1}@test.com`,
      requestorName: faker.person.fullName(),
      requestorPhone: faker.phone.number('+447#######'),
      address: faker.location.streetAddress(),
      postcode,
      latitude: lat + (Math.random() - 0.5) * 0.005,
      longitude: lng + (Math.random() - 0.5) * 0.005,
      urgency: faker.helpers.arrayElement(['LOW', 'MEDIUM', 'HIGH']),
      status: 'APPROVED',
      requirements: faker.helpers.arrayElement(requirements),
      estimatedDuration: duration,
      scheduledStartTime: startTime,
      scheduledEndTime: endTime,
      notes: faker.lorem.sentence(),
      approvedBy: 'coordinator@test.com',
      approvedAt: new Date(),
      sendToRostering: true,
      processedAt: new Date()
    });
  }

  await prisma.externalRequest.createMany({ data: visits });
  console.log(`✅ Created ${visits.length} visits`);
}

async function seedTravelMatrix() {
  console.log('🗺️ Seeding travel matrix...');

  const postcodes = [
    'SW1A 1AA', 'E1 6AN', 'N1 9AL', 'SE1 2AB', 'W1B 1AB',
    'NW1 0AB', 'EC1A 1BB', 'WC1B 3AB', 'SE1 7AB', 'N1 6AB',
    'E2 7AB', 'N7 8AB', 'SW1V 1AB', 'SE11 5AB', 'W2 3AB'
  ];

  const matrix = [];
  for (const from of postcodes) {
    for (const to of postcodes) {
      if (from !== to) {
        const [lat1, lng1] = getCoordinatesForPostcode(from);
        const [lat2, lng2] = getCoordinatesForPostcode(to);
        const distance = calculateHaversineDistance(lat1, lng1, lat2, lng2);
        const duration = Math.max(5, Math.min(60, Math.ceil(distance / 500) + 5)); // 500m per minute + 5min base

        matrix.push({
          fromPostcode: from,
          toPostcode: to,
          durationMinutes: duration,
          distanceMeters: Math.round(distance),
          lastUpdated: new Date(),
          expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours
        });
      }
    }
  }

  await prisma.travelMatrix.createMany({ data: matrix });
  console.log(`✅ Created ${matrix.length} travel matrix entries`);
}

async function seedHistoricalMatches(tenantId: string) {
  console.log('📊 Seeding historical matches...');

  // Get all visits and carers
  const visits = await prisma.externalRequest.findMany({
    where: { tenantId, status: 'APPROVED' },
    select: { id: true }
  });

  const carers = await prisma.carer.findMany({
    where: { tenantId, isActive: true },
    select: { id: true }
  });

  const matches = [];
  for (const visit of visits.slice(0, 50)) { // Create matches for first 50 visits
    const numMatches = faker.number.int({ min: 1, max: 3 });
    const selectedCarers = faker.helpers.arrayElements(carers, numMatches);

    for (const carer of selectedCarers) {
      matches.push({
        id: `match-${visit.id}-${carer.id}`,
        tenantId,
        requestId: visit.id,
        carerId: carer.id,
        distance: faker.number.float({ min: 0.5, max: 8.0, precision: 0.1 }),
        matchScore: faker.number.float({ min: 0.6, max: 0.95, precision: 0.01 }),
        status: faker.helpers.arrayElement(['ACCEPTED', 'DECLINED', 'PENDING']),
        respondedAt: faker.helpers.maybe(() => faker.date.past({ years: 1 })),
        response: faker.helpers.arrayElement(['ACCEPTED', 'DECLINED', null]),
        responseNotes: faker.helpers.maybe(() => faker.lorem.sentence()),
        notificationSent: faker.datatype.boolean(),
        createdAt: faker.date.past({ years: 1 })
      });
    }
  }

  await prisma.requestCarerMatch.createMany({ data: matches });
  console.log(`✅ Created ${matches.length} historical matches`);
}

async function seedConstraints(tenantId: string) {
  console.log('⚙️ Seeding rostering constraints...');

  try {
    await prisma.rosteringConstraints.create({
      data: {
        tenantId: tenantId,
        name: 'Test Constraints',
        wtdMaxHoursPerWeek: 168, // Much more relaxed for testing
        restPeriodHours: 8, // Reduced rest period
        bufferMinutes: 15, // Increased buffer
        travelMaxMinutes: 60, // Increased travel time
        continuityTargetPercent: 50, // Lower continuity target
        maxDailyHours: 12, // Increased daily hours
        minRestBetweenVisits: 30, // Added minimum rest between visits
        maxTravelTimePerVisit: 120, // Increased max travel per visit
        isActive: true,
        updatedBy: 'system',
        updatedByEmail: 'system@test.com',
        updatedByFirstName: 'System',
        updatedByLastName: 'Admin'
      }
    });

    console.log('✅ Created rostering constraints');
  } catch (error) {
    console.log('⚠️ Rostering constraints already exist, skipping...');
  }
}

// Helper functions
function getCoordinatesForPostcode(postcode: string): [number, number] {
  const coordinates: { [key: string]: [number, number] } = {
    'SW1A 1AA': [51.5074, -0.1278], // Buckingham Palace
    'E1 6AN': [51.5174, -0.0798],   // Brick Lane
    'N1 9AL': [51.5374, -0.1078],   // Islington
    'SE1 2AB': [51.4974, -0.0978],  // Southwark
    'W1B 1AB': [51.5174, -0.1478],  // Oxford Street
    'NW1 0AB': [51.5274, -0.1678],  // Camden
    'EC1A 1BB': [51.5174, -0.1078], // Barbican
    'WC1B 3AB': [51.5174, -0.1278], // Bloomsbury
    'SE1 7AB': [51.4974, -0.1178],  // Waterloo
    'N1 6AB': [51.5374, -0.0878],   // De Beauvoir
    'E2 7AB': [51.5274, -0.0678],   // Bethnal Green
    'N7 8AB': [51.5574, -0.1178],   // Holloway
    'SW1V 1AB': [51.4974, -0.1378], // Pimlico
    'SE11 5AB': [51.4874, -0.1178], // Kennington
    'W2 3AB': [51.5174, -0.1778]    // Paddington
  };

  return coordinates[postcode] || [51.5074, -0.1278];
}

function calculateHaversineDistance(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371e3; // Earth radius in meters
  const φ1 = lat1 * Math.PI / 180;
  const φ2 = lat2 * Math.PI / 180;
  const Δφ = (lat2 - lat1) * Math.PI / 180;
  const Δλ = (lng2 - lng1) * Math.PI / 180;

  const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ/2) * Math.sin(Δλ/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

  return R * c;
}

main()
  .catch((e) => {
    console.error('❌ Seeding failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });