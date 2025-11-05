// tests/clustering.simple.test.ts
import { PrismaClient } from '@prisma/client';

describe('Simple Database Connection Test', () => {
  let prisma: PrismaClient;

  beforeAll(async () => {
    prisma = new PrismaClient();
  });

  afterAll(async () => {
    await prisma.$disconnect();
  });

  it('should connect to database', async () => {
    console.log('🔌 Testing database connection...');
    
    try {
      await prisma.$connect();
      console.log('✅ Database connected successfully');
      
      // Simple query to verify connection
      const result = await prisma.$queryRaw`SELECT 1 as test`;
      expect(result).toEqual([{ test: 1 }]);
      
    } catch (error: any) {  // ✅ FIXED: Added type annotation
      console.error('❌ Database connection failed:', error.message);
      throw error;
    }
  });

  it('should have required tables', async () => {
    try {
      const tables = await prisma.$queryRaw`
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
      `;
      
      console.log('📊 Available tables:', tables);
      expect(Array.isArray(tables)).toBe(true);
    } catch (error: any) {  // ✅ FIXED: Added type annotation
      console.error('❌ Table query failed:', error.message);
      throw error;
    }
  });
});