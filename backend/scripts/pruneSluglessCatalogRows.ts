/**
 * Identify (and optionally delete) active CatalogIdea / CatalogPainPoint rows
 * with NULL slug. These rows can never be linked to publicly (`/idea/:slug`
 * and `/pain-point/:slug` require a slug), but they DO inflate
 * `payload.totalIdeas` / `payload.totalPainPoints` on the category landing
 * payload — which the loader subtracts the visible (slugged) set from to
 * derive `lockedIdeaCount` / `lockedPainCount`. Result: entitled users
 * (ADMIN / fullCatalogAccess / active sub) see a non-zero locked skeleton on
 * `/ideas/[niche]` even though they have full access.
 *
 * The count-mismatch in `buildCategoryLandingPayload` is the user-facing bug
 * and is patched separately. This script is the data-cleanup side: the
 * slugless rows shouldn't exist for active items in the first place.
 *
 * Cascades (per `prisma/schema.prisma`):
 *   CatalogIdea       → SavedIdea, CatalogCollectionItem  (onDelete: Cascade)
 *   CatalogPainPoint  → SavedPainPoint, CatalogCollectionItem (onDelete: Cascade)
 * These dependents are reported before any delete so the operator sees the
 * blast radius.
 *
 * Usage:
 *   npx tsx scripts/pruneSluglessCatalogRows.ts                 # dry run
 *   npx tsx scripts/pruneSluglessCatalogRows.ts --category ai-machine-learning
 *   npx tsx scripts/pruneSluglessCatalogRows.ts --delete        # interactive confirm
 *   npx tsx scripts/pruneSluglessCatalogRows.ts --delete --yes  # no prompt (CI)
 */

import { PrismaClient } from '@prisma/client';
import * as readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';

const prisma = new PrismaClient();

type Args = {
  delete: boolean;
  yes: boolean;
  category: string | null;
};

function parseArgs(argv: string[]): Args {
  const args: Args = { delete: false, yes: false, category: null };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--delete') args.delete = true;
    else if (a === '--yes' || a === '-y') args.yes = true;
    else if (a === '--category') {
      const v = argv[++i];
      if (!v) throw new Error('--category requires a slug argument');
      args.category = v;
    } else {
      throw new Error(`Unknown argument: ${a}`);
    }
  }
  return args;
}

async function resolveCategoryIds(categorySlug: string): Promise<string[]> {
  const root = await prisma.catalogCategory.findFirst({
    where: { slug: categorySlug, parentId: null },
    select: { id: true },
  });
  if (!root) {
    throw new Error(`No top-level category with slug "${categorySlug}"`);
  }
  const children = await prisma.catalogCategory.findMany({
    where: { parentId: root.id },
    select: { id: true },
  });
  return [root.id, ...children.map((c) => c.id)];
}

async function summarize(categoryIdFilter: string[] | null) {
  const where = {
    isActive: true,
    slug: null,
    ...(categoryIdFilter ? { categoryId: { in: categoryIdFilter } } : {}),
  };

  const [ideaCount, painCount] = await Promise.all([
    prisma.catalogIdea.count({ where }),
    prisma.catalogPainPoint.count({ where }),
  ]);

  // Top 10 categories by slugless-row count. groupBy is per-table — merge
  // afterward so the operator sees one ranked list.
  const [ideaByCat, painByCat] = await Promise.all([
    prisma.catalogIdea.groupBy({
      by: ['categoryId'],
      where,
      _count: { _all: true },
    }),
    prisma.catalogPainPoint.groupBy({
      by: ['categoryId'],
      where,
      _count: { _all: true },
    }),
  ]);

  const perCat = new Map<string, { ideas: number; pains: number }>();
  for (const row of ideaByCat) {
    const e = perCat.get(row.categoryId) ?? { ideas: 0, pains: 0 };
    e.ideas = row._count._all;
    perCat.set(row.categoryId, e);
  }
  for (const row of painByCat) {
    const e = perCat.get(row.categoryId) ?? { ideas: 0, pains: 0 };
    e.pains = row._count._all;
    perCat.set(row.categoryId, e);
  }

  const catRows = await prisma.catalogCategory.findMany({
    where: { id: { in: Array.from(perCat.keys()) } },
    select: { id: true, name: true, slug: true, parent: { select: { slug: true } } },
  });
  const catById = new Map(catRows.map((c) => [c.id, c]));

  const ranked = Array.from(perCat.entries())
    .map(([id, c]) => ({ id, ...c, total: c.ideas + c.pains, cat: catById.get(id) }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10);

  return { ideaCount, painCount, ranked };
}

async function sampleRows(categoryIdFilter: string[] | null) {
  const where = {
    isActive: true,
    slug: null,
    ...(categoryIdFilter ? { categoryId: { in: categoryIdFilter } } : {}),
  };
  const [ideas, pains] = await Promise.all([
    prisma.catalogIdea.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: 10,
      select: {
        id: true,
        solutionName: true,
        sourceJobId: true,
        categoryId: true,
        createdAt: true,
      },
    }),
    prisma.catalogPainPoint.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: 10,
      select: {
        id: true,
        title: true,
        sourceJobId: true,
        categoryId: true,
        createdAt: true,
      },
    }),
  ]);
  return { ideas, pains };
}

async function countCascadeDependents(
  ideaIds: string[],
  painIds: string[],
): Promise<{ savedIdea: number; savedPain: number; collectionItem: number }> {
  if (ideaIds.length === 0 && painIds.length === 0) {
    return { savedIdea: 0, savedPain: 0, collectionItem: 0 };
  }
  const [savedIdea, savedPain, collectionItemIdea, collectionItemPain] =
    await Promise.all([
      ideaIds.length
        ? prisma.savedIdea.count({ where: { ideaId: { in: ideaIds } } })
        : Promise.resolve(0),
      painIds.length
        ? prisma.savedPainPoint.count({ where: { painPointId: { in: painIds } } })
        : Promise.resolve(0),
      ideaIds.length
        ? prisma.catalogCollectionItem.count({ where: { ideaId: { in: ideaIds } } })
        : Promise.resolve(0),
      painIds.length
        ? prisma.catalogCollectionItem.count({
            where: { painPointId: { in: painIds } },
          })
        : Promise.resolve(0),
    ]);
  return {
    savedIdea,
    savedPain,
    collectionItem: collectionItemIdea + collectionItemPain,
  };
}

async function confirm(prompt: string): Promise<boolean> {
  const rl = readline.createInterface({ input, output });
  try {
    const answer = await rl.question(prompt);
    return answer.trim() === 'YES';
  } finally {
    rl.close();
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const categoryIds = args.category ? await resolveCategoryIds(args.category) : null;

  const scope = args.category ? `category "${args.category}" (subtree)` : 'entire catalog';
  console.log(`Scope: ${scope}`);
  console.log(`Mode:  ${args.delete ? 'DELETE' : 'DRY RUN (use --delete to remove)'}`);
  console.log('');

  const { ideaCount, painCount, ranked } = await summarize(categoryIds);

  console.log('Slugless active rows:');
  console.log(`  CatalogIdea:      ${ideaCount}`);
  console.log(`  CatalogPainPoint: ${painCount}`);
  console.log('');

  if (ideaCount === 0 && painCount === 0) {
    console.log('Nothing to do.');
    return;
  }

  if (ranked.length > 0) {
    console.log('Top categories by slugless-row count:');
    for (const r of ranked) {
      const path = r.cat
        ? r.cat.parent
          ? `${r.cat.parent.slug}/${r.cat.slug}`
          : r.cat.slug
        : '(unknown)';
      console.log(
        `  ${String(r.total).padStart(4)}  ${path.padEnd(48)}  ideas=${r.ideas} pains=${r.pains}`,
      );
    }
    console.log('');
  }

  const { ideas, pains } = await sampleRows(categoryIds);
  if (ideas.length > 0) {
    console.log(`Sample slugless ideas (newest ${ideas.length}):`);
    for (const i of ideas) {
      console.log(
        `  ${i.id}  ${i.createdAt.toISOString().slice(0, 10)}  job=${i.sourceJobId}  "${i.solutionName.slice(0, 60)}"`,
      );
    }
    console.log('');
  }
  if (pains.length > 0) {
    console.log(`Sample slugless pains (newest ${pains.length}):`);
    for (const p of pains) {
      console.log(
        `  ${p.id}  ${p.createdAt.toISOString().slice(0, 10)}  job=${p.sourceJobId}  "${p.title.slice(0, 60)}"`,
      );
    }
    console.log('');
  }

  if (!args.delete) {
    console.log('Dry run only — re-run with --delete to remove these rows.');
    return;
  }

  // Resolve full ID lists for the delete + cascade count.
  const where = {
    isActive: true,
    slug: null,
    ...(categoryIds ? { categoryId: { in: categoryIds } } : {}),
  };
  const [allIdeas, allPains] = await Promise.all([
    prisma.catalogIdea.findMany({ where, select: { id: true } }),
    prisma.catalogPainPoint.findMany({ where, select: { id: true } }),
  ]);
  const ideaIds = allIdeas.map((r) => r.id);
  const painIds = allPains.map((r) => r.id);

  const cascade = await countCascadeDependents(ideaIds, painIds);
  console.log('Cascade impact (auto-deleted via FK):');
  console.log(`  SavedIdea:             ${cascade.savedIdea}`);
  console.log(`  SavedPainPoint:        ${cascade.savedPain}`);
  console.log(`  CatalogCollectionItem: ${cascade.collectionItem}`);
  console.log('');

  if (!args.yes) {
    const ok = await confirm(
      `About to DELETE ${ideaIds.length} ideas + ${painIds.length} pains. Type YES to proceed: `,
    );
    if (!ok) {
      console.log('Aborted.');
      return;
    }
  }

  // One transaction so a failure mid-delete doesn't leave a half-cleaned state.
  const result = await prisma.$transaction([
    prisma.catalogIdea.deleteMany({ where: { id: { in: ideaIds } } }),
    prisma.catalogPainPoint.deleteMany({ where: { id: { in: painIds } } }),
  ]);

  console.log('Deleted:');
  console.log(`  CatalogIdea:      ${result[0].count}`);
  console.log(`  CatalogPainPoint: ${result[1].count}`);
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
