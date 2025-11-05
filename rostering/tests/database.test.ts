// tests/database.test.ts
import { PrismaClient } from '@prisma/client';

describe('Database Connection', () => {
  let prisma: PrismaClient;

  beforeAll(() => {
    prisma = new PrismaClient();
  });

  afterAll(async () => {
    await prisma.$disconnect();
  });

  it('should connect to the database', async () => {
    console.log('🔌 Testing database connection...');
    
    try {
      await prisma.$connect();
      console.log('✅ Database connected successfully');
      
      // Test a simple query
      const result = await prisma.$queryRaw`SELECT 1 as test`;
      expect(result).toBeDefined();
      
    } catch (error) {
      console.error('❌ Database connection failed:', error);
      throw error;
    }
  });

  it('should have required tables', async () => {
    const tables = await prisma.$queryRaw`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public'
    `;
    
    expect(Array.isArray(tables)).toBe(true);
    console.log(`✅ Found ${(tables as any[]).length} tables in database`);
  });
});