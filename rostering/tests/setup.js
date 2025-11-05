"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@prisma/client");
jest.setTimeout(30000);
beforeAll(async () => {
    console.log('🧪 Starting clustering tests...');
});
afterAll(async () => {
    console.log('✅ Clustering tests completed');
});
afterAll(async () => {
    const prisma = new client_1.PrismaClient();
    await prisma.$disconnect();
});
//# sourceMappingURL=setup.js.map