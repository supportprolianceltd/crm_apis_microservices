// src/tests/setup.ts
import { PrismaClient } from '@prisma/client';

// Global test timeout
jest.setTimeout(30000);

// Global test setup
beforeAll(async () => {
  // Optional: Add global test setup here
  console.log('🧪 Starting clustering tests...');
});

afterAll(async () => {
  // Optional: Add global cleanup here
  console.log('✅ Clustering tests completed');
});

// Global test teardown
afterAll(async () => {
  const prisma = new PrismaClient();
  await prisma.$disconnect();
});