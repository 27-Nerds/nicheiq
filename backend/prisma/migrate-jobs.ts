import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // Get first user
  const firstUser = await prisma.user.findFirst({
    orderBy: { createdAt: 'asc' }
  });

  if (!firstUser) {
    console.log('No users found. Please register first.');
    return;
  }

  console.log(`Found first user: ${firstUser.email} (${firstUser.id})`);

  // Update all jobs to belong to first user
  const result = await prisma.job.updateMany({
    data: { userId: firstUser.id }
  });

  console.log(`Migrated ${result.count} jobs to user: ${firstUser.email}`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
