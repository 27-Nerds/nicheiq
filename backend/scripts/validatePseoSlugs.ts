import { PrismaClient } from '@prisma/client';
import { programmaticIdeaPages } from '../../frontend/src/lib/data/programmaticIdeaPages.ts';

const prisma = new PrismaClient();

function fail(message: string): never {
  console.error(`[pseo] ${message}`);
  process.exit(1);
}

async function main() {
  const launchGateOn = (process.env.SEO_LAUNCH_GATE ?? 'true') !== 'false';
  const pseoSlugs = programmaticIdeaPages.map((p) => p.slug);
  const duplicatePseoSlugs = pseoSlugs.filter((slug, index) => pseoSlugs.indexOf(slug) !== index);
  if (duplicatePseoSlugs.length > 0) {
    fail(`Duplicate programmatic page slugs: ${[...new Set(duplicatePseoSlugs)].join(', ')}`);
  }

  const topCategories = await prisma.catalogCategory.findMany({
    where: { parentId: null },
    select: { slug: true },
  });
  const categorySlugs = new Set(topCategories.map((c) => c.slug));
  const collisions = pseoSlugs.filter((slug) => categorySlugs.has(slug));
  if (collisions.length > 0) {
    fail(`Programmatic page slug collision with top-level categories: ${collisions.join(', ')}`);
  }

  if (!launchGateOn) {
    const allFeaturedSlugs = new Set(programmaticIdeaPages.flatMap((p) => p.featuredIdeaSlugs));
    for (const page of programmaticIdeaPages) {
      if (page.featuredIdeaSlugs.length < 4) {
        fail(`${page.slug} must have at least 4 featuredIdeaSlugs before SEO_LAUNCH_GATE=false`);
      }
    }

    const activeIdeas = await prisma.catalogIdea.findMany({
      where: {
        isActive: true,
        slug: { in: [...allFeaturedSlugs] },
      },
      select: { slug: true },
    });
    const activeIdeaSlugs = new Set(activeIdeas.map((i) => i.slug).filter(Boolean));
    const missing = [...allFeaturedSlugs].filter((slug) => !activeIdeaSlugs.has(slug));
    if (missing.length > 0) {
      fail(`Featured idea slugs missing or inactive: ${missing.join(', ')}`);
    }
  }

  console.log(
    `[pseo] ok: ${programmaticIdeaPages.length} pages, launchGate=${launchGateOn ? 'on' : 'off'}`,
  );
}

main()
  .catch((error) => {
    console.error('[pseo] validation failed:', error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
