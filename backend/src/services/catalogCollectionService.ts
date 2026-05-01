/**
 * Phase 5.4 — Featured catalog collections.
 *
 * Curated groupings of CatalogIdea / CatalogPainPoint, manually managed via
 * the admin UI. Read-side consumed by the public `/ideas` index page.
 *
 * Data model: each CatalogCollectionItem references EXACTLY ONE of `ideaId`
 * or `painPointId`. The XOR is enforced both at the DB level (CHECK
 * constraint added in migration 20260430143529_catalog_rebuild_extensions)
 * and at the service level (`validateXor` below) for clearer error messages.
 *
 * Cache: collection list is cached in Redis 5 min (catalog:collections:v1).
 * Mutations call `invalidateCollectionsCache`.
 */

import { Prisma } from '@prisma/client';
import { prisma } from './db.js';
import { getRedis } from './redis.js';

const COLLECTIONS_CACHE_KEY = 'catalog:collections:v1';
const COLLECTIONS_CACHE_TTL = 300;

export interface CatalogCollectionSummary {
  slug: string;
  name: string;
  description: string | null;
  tagline: string | null;
  colorAccent: string | null;
  sortOrder: number;
  itemCount: number;
}

export interface CatalogCollectionItemPreview {
  position: number;
  kind: 'idea' | 'pain-point';
  idea?: Record<string, unknown>;
  painPoint?: Record<string, unknown>;
}

export interface CatalogCollectionDetail extends CatalogCollectionSummary {
  items: CatalogCollectionItemPreview[];
}

/** Validate exactly-one-of (`ideaId` XOR `painPointId`). Throws on violation. */
function validateXor(args: { ideaId?: string | null; painPointId?: string | null }): void {
  const hasIdea = !!args.ideaId;
  const hasPain = !!args.painPointId;
  if (hasIdea === hasPain) {
    throw new Error(
      'CatalogCollectionItem requires exactly one of ideaId or painPointId',
    );
  }
}

/**
 * Public read — list active collections with item counts only (no items
 * hydrated). Cheap; cached.
 */
export async function listCollectionSummaries(): Promise<CatalogCollectionSummary[]> {
  const redis = getRedis();
  try {
    const cached = await redis.get(COLLECTIONS_CACHE_KEY);
    if (cached) return JSON.parse(cached) as CatalogCollectionSummary[];
  } catch (err) {
    console.error('Collections cache read failed:', err);
  }

  const rows = await prisma.catalogCollection.findMany({
    where: { isActive: true },
    orderBy: [{ sortOrder: 'asc' }, { name: 'asc' }],
    include: { _count: { select: { items: true } } },
  });

  const summaries: CatalogCollectionSummary[] = rows.map((c) => ({
    slug: c.slug,
    name: c.name,
    description: c.description,
    tagline: c.tagline,
    colorAccent: c.colorAccent,
    sortOrder: c.sortOrder,
    itemCount: c._count.items,
  }));

  try {
    await redis.setex(COLLECTIONS_CACHE_KEY, COLLECTIONS_CACHE_TTL, JSON.stringify(summaries));
  } catch (err) {
    console.error('Collections cache write failed:', err);
  }
  return summaries;
}

/**
 * Public read — single collection detail with items hydrated as previews.
 * Each item carries either `idea` or `painPoint`, never both.
 */
export async function getCollectionDetail(slug: string): Promise<CatalogCollectionDetail | null> {
  const collection = await prisma.catalogCollection.findUnique({
    where: { slug },
    include: {
      items: {
        orderBy: { position: 'asc' },
        include: {
          idea: {
            include: {
              category: {
                select: {
                  id: true, name: true, slug: true,
                  parent: { select: { name: true, slug: true } },
                },
              },
            },
          },
          painPoint: {
            include: {
              category: {
                select: {
                  id: true, name: true, slug: true,
                  parent: { select: { name: true, slug: true } },
                },
              },
            },
          },
        },
      },
    },
  });

  if (!collection || !collection.isActive) return null;

  const items: CatalogCollectionItemPreview[] = collection.items.map((it) => {
    if (it.idea) {
      const { sourceJobId: _s, publishedById: _p, ...rest } = it.idea;
      return { position: it.position, kind: 'idea', idea: rest };
    }
    if (it.painPoint) {
      const { sourceJobId: _s, publishedById: _p, ...rest } = it.painPoint;
      return { position: it.position, kind: 'pain-point', painPoint: rest };
    }
    // Defensive: DB CHECK ensures one is non-null. This branch should be
    // unreachable; if it fires, log and skip the row.
    console.error(`CatalogCollectionItem ${it.id} has neither idea nor painPoint`);
    return { position: it.position, kind: 'idea' };
  });

  return {
    slug: collection.slug,
    name: collection.name,
    description: collection.description,
    tagline: collection.tagline,
    colorAccent: collection.colorAccent,
    sortOrder: collection.sortOrder,
    itemCount: items.length,
    items,
  };
}

// ============================================
// Admin CRUD — invoked by /api/admin/catalog/collections endpoints.
// All mutations invalidate the public cache.
// ============================================

export interface CreateCollectionArgs {
  slug: string;
  name: string;
  description?: string | null;
  tagline?: string | null;
  colorAccent?: string | null;
  sortOrder?: number;
  isActive?: boolean;
}

export async function createCollection(args: CreateCollectionArgs) {
  const created = await prisma.catalogCollection.create({
    data: {
      slug: args.slug,
      name: args.name,
      description: args.description ?? null,
      tagline: args.tagline ?? null,
      colorAccent: args.colorAccent ?? null,
      sortOrder: args.sortOrder ?? 0,
      isActive: args.isActive ?? true,
    },
  });
  await invalidateCollectionsCache();
  return created;
}

export async function updateCollection(
  id: string,
  args: Partial<CreateCollectionArgs>,
) {
  const updated = await prisma.catalogCollection.update({
    where: { id },
    data: {
      ...(args.slug !== undefined && { slug: args.slug }),
      ...(args.name !== undefined && { name: args.name }),
      ...(args.description !== undefined && { description: args.description }),
      ...(args.tagline !== undefined && { tagline: args.tagline }),
      ...(args.colorAccent !== undefined && { colorAccent: args.colorAccent }),
      ...(args.sortOrder !== undefined && { sortOrder: args.sortOrder }),
      ...(args.isActive !== undefined && { isActive: args.isActive }),
    },
  });
  await invalidateCollectionsCache();
  return updated;
}

export async function deleteCollection(id: string) {
  await prisma.catalogCollection.delete({ where: { id } });
  await invalidateCollectionsCache();
}

export interface AddItemArgs {
  collectionId: string;
  ideaId?: string | null;
  painPointId?: string | null;
  /** When omitted, the item is appended to the end. */
  position?: number;
}

export async function addItemToCollection(args: AddItemArgs) {
  validateXor(args);
  const position = args.position ?? (await nextPosition(args.collectionId));
  try {
    const created = await prisma.catalogCollectionItem.create({
      data: {
        collectionId: args.collectionId,
        ideaId: args.ideaId ?? null,
        painPointId: args.painPointId ?? null,
        position,
      },
    });
    await invalidateCollectionsCache();
    return created;
  } catch (err) {
    if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === 'P2002') {
      throw new Error(
        `Collection slot conflict: this item or position already exists in the collection`,
      );
    }
    throw err;
  }
}

export async function removeItemFromCollection(itemId: string) {
  await prisma.catalogCollectionItem.delete({ where: { id: itemId } });
  await invalidateCollectionsCache();
}

/**
 * Reorder items in a collection by passing the desired item-id sequence.
 * Each item's `position` is updated to match its index in `orderedIds`.
 * Wraps in a transaction so partial reorders never leak to the cache.
 */
export async function reorderItems(collectionId: string, orderedIds: string[]) {
  // Validate: all IDs must belong to the collection.
  const existing = await prisma.catalogCollectionItem.findMany({
    where: { collectionId, id: { in: orderedIds } },
    select: { id: true },
  });
  if (existing.length !== orderedIds.length) {
    throw new Error('reorderItems: some IDs do not belong to the collection');
  }

  // Two-pass update to avoid the unique (collectionId, position) constraint
  // tripping during the move: first park items at large negative positions,
  // then assign final positions in order.
  await prisma.$transaction(async (tx) => {
    for (let i = 0; i < orderedIds.length; i++) {
      await tx.catalogCollectionItem.update({
        where: { id: orderedIds[i] },
        data: { position: -(i + 1) - 1_000_000 },
      });
    }
    for (let i = 0; i < orderedIds.length; i++) {
      await tx.catalogCollectionItem.update({
        where: { id: orderedIds[i] },
        data: { position: i },
      });
    }
  });
  await invalidateCollectionsCache();
}

async function nextPosition(collectionId: string): Promise<number> {
  const last = await prisma.catalogCollectionItem.findFirst({
    where: { collectionId },
    orderBy: { position: 'desc' },
    select: { position: true },
  });
  return (last?.position ?? -1) + 1;
}

export async function invalidateCollectionsCache(): Promise<void> {
  try {
    await getRedis().del(COLLECTIONS_CACHE_KEY);
  } catch (err) {
    console.error('Collections cache invalidate failed:', err);
  }
}

// Admin list helper — returns ALL collections (active + inactive) with
// counts. Used by the admin curation UI.
export async function listCollectionsAdmin() {
  return prisma.catalogCollection.findMany({
    orderBy: [{ isActive: 'desc' }, { sortOrder: 'asc' }, { name: 'asc' }],
    include: { _count: { select: { items: true } } },
  });
}

/**
 * Admin detail — like getCollectionDetail but works for inactive collections
 * AND looks up by id (admin UI uses cuid, not slug). Returns the full row
 * plus hydrated items with idea/painPoint titles for the picker UI.
 */
export async function getCollectionAdmin(id: string) {
  const collection = await prisma.catalogCollection.findUnique({
    where: { id },
    include: {
      items: {
        orderBy: { position: 'asc' },
        include: {
          idea: {
            select: {
              id: true,
              slug: true,
              solutionName: true,
              headline: true,
              shortDescription: true,
              category: { select: { id: true, name: true, slug: true } },
            },
          },
          painPoint: {
            select: {
              id: true,
              slug: true,
              title: true,
              category: { select: { id: true, name: true, slug: true } },
            },
          },
        },
      },
    },
  });
  if (!collection) return null;
  return collection;
}
