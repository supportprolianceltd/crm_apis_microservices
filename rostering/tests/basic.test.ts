// tests/basic.test.ts
describe('Basic Test Suite', () => {
  it('should pass a basic test', () => {
    expect(1 + 1).toBe(2);
  });

  it('should import services', () => {
    expect(() => {
      const { PrismaClient } = require('@prisma/client');
      const { ClusteringService } = require('../src/services/clustering.service');
      const { ConstraintsService } = require('../src/services/constraints.service');
      const { TravelService } = require('../src/services/travel.service');
    }).not.toThrow();
  });
});