import { PrismaClient } from '@prisma/client';
import { config } from 'dotenv';

// Load environment variables
config();

const prisma = new PrismaClient();

async function main() {
  // Create a test tenant
  const tenant = await prisma.tenant.upsert({
    where: { schema: 'test_tenant' },
    update: {},
    create: {
      name: 'Test Tenant',
      schema: 'test_tenant',
    },
  });

  console.log('Created tenant:', tenant);

  // Create test users
  const users = [
    {
      email: 'alice@example.com',
      username: 'alice',
      firstName: 'Alice',
      lastName: 'Smith',
      role: 'USER',
      tenantId: tenant.id,
    },
    {
      email: 'bob@example.com',
      username: 'bob',
      firstName: 'Bob',
      lastName: 'Johnson',
      role: 'USER',
      tenantId: tenant.id,
    },
    {
      email: 'charlie@example.com',
      username: 'charlie',
      firstName: 'Charlie',
      lastName: 'Brown',
      role: 'ADMIN',
      tenantId: tenant.id,
    },
  ];

  const createdUsers = [];
  for (const userData of users) {
    const user = await prisma.user.upsert({
      where: { email: userData.email },
      update: {},
      create: userData,
    });
    createdUsers.push(user);
    console.log(`Created user: ${user.email}`);
  }

  // Create a chat between the users
  const chat = await prisma.chat.create({
    data: {
      name: 'General Chat',
      users: {
        create: createdUsers.map(user => ({
          user: { connect: { id: user.id } },
        })),
      },
    },
    include: {
      users: {
        include: {
          user: true,
        },
      },
    },
  });

  console.log('Created chat:', chat);
  console.log('Seeding completed successfully!');
}

main()
  .catch((e) => {
    console.error('Error seeding database:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
