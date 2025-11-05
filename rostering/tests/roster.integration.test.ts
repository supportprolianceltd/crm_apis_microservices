// tests/roster.integration.test.ts
import { PrismaClient, RequestStatus } from '@prisma/client';
import { RosterGenerationService } from '../src/services/roster-generation.service';
import { ConstraintsService } from '../src/services/constraints.service';
import { TravelService } from '../src/services/travel.service';
import { ClusteringService } from '../src/services/clustering.service';

describe('Roster Generation Integration Tests', () => {
  let prisma: PrismaClient;
  let rosterService: RosterGenerationService;
  let constraintsService: ConstraintsService;
  let travelService: TravelService;
  let clusteringService: ClusteringService;
  let tenantId: string;

  beforeAll(async () => {
    console.log('🔌 Connecting to database for roster tests...');
    
    prisma = new PrismaClient();
    
    try {
      await prisma.$connect();
      console.log('✅ Database connected successfully');
    } catch (error) {
      console.error('❌ Database connection failed:', error);
      throw error;
    }
    
    // Initialize services
    constraintsService = new ConstraintsService(prisma);
    travelService = new TravelService(prisma);
    clusteringService = new ClusteringService(prisma, constraintsService, travelService);
    rosterService = new RosterGenerationService(
      prisma,
      constraintsService,
      travelService,
      clusteringService
    );
    
    tenantId = `test-roster-${Date.now()}`;
  });

  afterAll(async () => {
    if (prisma) {
      try {
        // Cleanup test data
        await prisma.externalRequest.deleteMany({ where: { tenantId } });
        await prisma.carer.deleteMany({ where: { tenantId } });
        await prisma.rosteringConstraints.deleteMany({ where: { tenantId } });
        
        await prisma.$disconnect();
        console.log('✅ Database disconnected');
      } catch (error) {
        console.error('❌ Cleanup failed:', error);
      }
    }
  });

  beforeEach(async () => {
    // Create fresh test data
    await createRosterTestData(prisma, tenantId);
  });

  afterEach(async () => {
    // Cleanup after each test
    try {
      await prisma.externalRequest.deleteMany({ where: { tenantId } });
      await prisma.carer.deleteMany({ where: { tenantId } });
    } catch (error) {
      console.error('❌ Cleanup failed:', error);
    }
  });

  describe('Generate Roster Scenarios', () => {
    it('should generate 3 scenarios with different strategies', async () => {
      console.log('🧪 Testing scenario generation...');
      
      const scenarios = await rosterService.generateRoster(tenantId, {
        dateRange: {
          start: new Date('2024-01-15T00:00:00Z'),
          end: new Date('2024-01-20T23:59:59Z')
        },
        generateScenarios: true
      });

      expect(scenarios).toBeDefined();
      expect(Array.isArray(scenarios)).toBe(true);
      expect(scenarios.length).toBe(3);
      
      // Check strategies
      const strategies = scenarios.map(s => s.strategy);
      expect(strategies).toContain('continuity');
      expect(strategies).toContain('travel');
      expect(strategies).toContain('balanced');
      
      console.log(`✅ Generated ${scenarios.length} scenarios`);
      
      // Validate scenario structure
      scenarios.forEach(scenario => {
        expect(scenario).toHaveProperty('id');
        expect(scenario).toHaveProperty('label');
        expect(scenario).toHaveProperty('strategy');
        expect(scenario).toHaveProperty('assignments');
        expect(scenario).toHaveProperty('metrics');
        expect(scenario).toHaveProperty('score');
        
        // Validate metrics
        expect(scenario.metrics).toHaveProperty('totalTravel');
        expect(scenario.metrics).toHaveProperty('continuityScore');
        expect(scenario.metrics).toHaveProperty('violations');
        expect(scenario.metrics).toHaveProperty('overtimeMinutes');
        
        // Score should be 0-100
        expect(scenario.score).toBeGreaterThanOrEqual(0);
        expect(scenario.score).toBeLessThanOrEqual(100);
      });
    });

    it('should generate single scenario when generateScenarios is false', async () => {
      console.log('🧪 Testing single scenario generation...');
      
      const scenarios = await rosterService.generateRoster(tenantId, {
        dateRange: {
          start: new Date('2024-01-15T00:00:00Z'),
          end: new Date('2024-01-20T23:59:59Z')
        },
        generateScenarios: false,
        strategy: 'balanced'
      });

      expect(scenarios).toBeDefined();
      expect(scenarios.length).toBe(1);
      expect(scenarios[0].strategy).toBe('balanced');
      
      console.log('✅ Single scenario generated correctly');
    });

    it('should handle no available visits gracefully', async () => {
      console.log('🧪 Testing empty visits handling...');
      
      // Delete all requests
      await prisma.externalRequest.deleteMany({ where: { tenantId } });
      
      const scenarios = await rosterService.generateRoster(tenantId, {
        dateRange: {
          start: new Date('2024-01-15T00:00:00Z'),
          end: new Date('2024-01-20T23:59:59Z')
        }
      });

      expect(scenarios).toEqual([]);
      console.log('✅ Empty visits handled correctly');
    });

    it('should throw error when no carers available', async () => {
      console.log('🧪 Testing no carers error...');
      
      // Delete all carers
      await prisma.carer.deleteMany({ where: { tenantId } });
      
      await expect(
        rosterService.generateRoster(tenantId, {
          dateRange: {
            start: new Date('2024-01-15T00:00:00Z'),
            end: new Date('2024-01-20T23:59:59Z')
          }
        })
      ).rejects.toThrow('No available carers found');
      
      console.log('✅ No carers error handled correctly');
    });
  });

  describe('Assignment Validation', () => {
    it('should create valid assignments with compliance checks', async () => {
      console.log('🧪 Testing assignment validation...');
      
      const scenarios = await rosterService.generateRoster(tenantId, {
        dateRange: {
          start: new Date('2024-01-15T00:00:00Z'),
          end: new Date('2024-01-20T23:59:59Z')
        },
        generateScenarios: false
      });

      if (scenarios.length > 0 && scenarios[0].assignments.length > 0) {
        const assignment = scenarios[0].assignments[0];
        
        // Validate assignment structure
        expect(assignment).toHaveProperty('id');
        expect(assignment).toHaveProperty('visitId');
        expect(assignment).toHaveProperty('carerId');
        expect(assignment).toHaveProperty('carerName');
        expect(assignment).toHaveProperty('scheduledTime');
        expect(assignment).toHaveProperty('estimatedEndTime');
        expect(assignment).toHaveProperty('complianceChecks');
        expect(assignment).toHaveProperty('visitDetails');
        
        // Validate compliance checks
        expect(assignment.complianceChecks).toHaveProperty('wtdCompliant');
        expect(assignment.complianceChecks).toHaveProperty('restPeriodOK');
        expect(assignment.complianceChecks).toHaveProperty('travelTimeOK');
        expect(assignment.complianceChecks).toHaveProperty('skillsMatch');
        expect(assignment.complianceChecks).toHaveProperty('warnings');
        
        console.log('✅ Assignment validation passed');
      }
    });

    it('should respect WTD constraints', async () => {
      console.log('🧪 Testing WTD constraint enforcement...');
      
      // Set very low WTD limit
      await prisma.rosteringConstraints.updateMany({
        where: { tenantId },
        data: { wtdMaxHoursPerWeek: 2 } // Only 2 hours per week
      });

      const scenarios = await rosterService.generateRoster(tenantId, {
        dateRange: {
          start: new Date('2024-01-15T00:00:00Z'),
          end: new Date('2024-01-20T23:59:59Z')
        },
        generateScenarios: false
      });

      if (scenarios.length > 0) {
        // Calculate total hours assigned to each carer
        const carerHours = new Map<string, number>();
        
        scenarios[0].assignments.forEach(assignment => {
          const current = carerHours.get(assignment.carerId) || 0;
          const hours = assignment.visitDetails.duration / 60;
          carerHours.set(assignment.carerId, current + hours);
        });

        // No carer should exceed 2 hours
        carerHours.forEach((hours, carerId) => {
          expect(hours).toBeLessThanOrEqual(2);
        });
        
        console.log('✅ WTD constraints respected');
      }
    });
  });

  describe('Scenario Metrics', () => {
    it('should calculate accurate travel metrics', async () => {
      console.log('🧪 Testing travel metrics calculation...');
      
      const scenarios = await rosterService.generateRoster(tenantId, {
        dateRange: {
          start: new Date('2024-01-15T00:00:00Z'),
          end: new Date('2024-01-20T23:59:59Z')
        }
      });

      scenarios.forEach(scenario => {
        expect(scenario.metrics.totalTravel).toBeGreaterThanOrEqual(0);
        expect(typeof scenario.metrics.totalTravel).toBe('number');
      });
      
      console.log('✅ Travel metrics calculated correctly');
    });

    it('should calculate continuity scores', async () => {
      console.log('🧪 Testing continuity score calculation...');
      
      const scenarios = await rosterService.generateRoster(tenantId, {
        dateRange: {
          start: new Date('2024-01-15T00:00:00Z'),
          end: new Date('2024-01-20T23:59:59Z')
        }
      });

      scenarios.forEach(scenario => {
        expect(scenario.metrics.continuityScore).toBeGreaterThanOrEqual(0);
        expect(scenario.metrics.continuityScore).toBeLessThanOrEqual(100);
      });
      
      console.log('✅ Continuity scores calculated correctly');
    });
  });
});

// Helper function to create test data
async function createRosterTestData(prisma: PrismaClient, tenantId: string) {
  try {
    console.log('🧩 Creating roster test data...');

    // Create constraints
    await prisma.rosteringConstraints.upsert({
      where: { 
        tenantId_name: {
          tenantId,
          name: 'Test Roster Constraints'
        }
      },
      update: {},
      create: {
        tenantId,
        name: 'Test Roster Constraints',
        wtdMaxHoursPerWeek: 48,
        restPeriodHours: 11,
        bufferMinutes: 5,
        travelMaxMinutes: 30,
        continuityTargetPercent: 85,
        maxDailyHours: 10,
        isActive: true,
        createdBy: 'test'
      }
    });

    // Create carers
    await prisma.carer.createMany({
      data: [
        {
          tenantId,
          firstName: 'Alice',
          lastName: 'Johnson',
          email: `alice-${Date.now()}@test.com`,
          phone: '+1234567890',
          address: '123 Care Street',
          postcode: 'SW1A 1AA',
          country: 'UK',
          skills: ['Personal care', 'Medication'],
          maxTravelDistance: 15000,
          latitude: 51.5074,
          longitude: -0.1278,
          isActive: true
        },
        {
          tenantId,
          firstName: 'Bob',
          lastName: 'Smith',
          email: `bob-${Date.now()}@test.com`,
          phone: '+1234567891',
          address: '124 Care Street',
          postcode: 'SW1A 2AB',
          country: 'UK',
          skills: ['Personal care', 'Dementia care'],
          maxTravelDistance: 20000,
          latitude: 51.5112,
          longitude: -0.1198,
          isActive: true
        },
        {
          tenantId,
          firstName: 'Carol',
          lastName: 'Williams',
          email: `carol-${Date.now()}@test.com`,
          phone: '+1234567892',
          address: '125 Care Street',
          postcode: 'SW1A 3CD',
          country: 'UK',
          skills: ['Medication', 'Mobility support'],
          maxTravelDistance: 10000,
          latitude: 51.5000,
          longitude: -0.1300,
          isActive: true
        }
      ]
    });

    // Create multiple visits
    const visits = [];
    for (let i = 0; i < 5; i++) {
      visits.push({
        tenantId,
        subject: `Test Visit ${i + 1}`,
        content: `Test content for visit ${i + 1}`,
        requestorEmail: `client${i + 1}@test.com`,
        requestorName: `Client ${i + 1}`,
        address: `${100 + i} Client Street`,
        postcode: 'SW1A 1AA',
        latitude: 51.5074 + (i * 0.01),
        longitude: -0.1278 + (i * 0.01),
        requirements: i % 2 === 0 ? 'Personal care' : 'Medication',
        scheduledStartTime: new Date(`2024-01-15T${9 + i}:00:00Z`),
        scheduledEndTime: new Date(`2024-01-15T${10 + i}:00:00Z`),
        estimatedDuration: 60,
        status: RequestStatus.APPROVED,
        sendToRostering: true
      });
    }

    await prisma.externalRequest.createMany({ data: visits });

    console.log('✅ Roster test data created successfully');
  } catch (error) {
    console.error('❌ Failed to create roster test data:', error);
    throw error;
  }
}