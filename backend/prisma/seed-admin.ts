import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  const email = process.argv[2];

  if (!email) {
    console.error('Usage: npx tsx prisma/seed-admin.ts <email>');
    process.exit(1);
  }

  const user = await prisma.user.update({
    where: { email },
    data: { role: 'ADMIN' },
    select: { id: true, email: true, name: true, role: true },
  });

  console.log(`Promoted user to ADMIN:`, user);
}

main()
  .catch((error) => {
    console.error('Failed to promote user:', error.message);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
