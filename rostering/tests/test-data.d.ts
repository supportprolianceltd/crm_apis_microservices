import { PrismaClient } from '@prisma/client';
export declare function createTestData(prisma: PrismaClient, tenantId: string): Promise<void>;
export declare function cleanupTestData(prisma: PrismaClient, tenantId?: string): Promise<void>;
//# sourceMappingURL=test-data.d.ts.map