import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockCategoryFindUnique = vi.fn();
const mockCategoryFindFirst = vi.fn();
const mockCategoryCreate = vi.fn();
const mockCategoryUpdate = vi.fn();
const mockCategoryDelete = vi.fn();
const mockIdeaCount = vi.fn();
const mockPainPointCount = vi.fn();
const mockRedisDel = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    catalogCategory: {
      findUnique: (...args: any[]) => mockCategoryFindUnique(...args),
      findFirst: (...args: any[]) => mockCategoryFindFirst(...args),
      create: (...args: any[]) => mockCategoryCreate(...args),
      update: (...args: any[]) => mockCategoryUpdate(...args),
      delete: (...args: any[]) => mockCategoryDelete(...args),
    },
    catalogIdea: {
      count: (...args: any[]) => mockIdeaCount(...args),
    },
    catalogPainPoint: {
      count: (...args: any[]) => mockPainPointCount(...args),
    },
  },
}));

vi.mock('../redis.js', () => ({
  getRedis: () => ({
    del: (...args: string[]) => mockRedisDel(...args),
  }),
}));

import { createCategory, deleteCategory, updateCategory } from '../catalogService.js';

function deletedKeys(): string[] {
  return mockRedisDel.mock.calls.flat();
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('catalogService cache invalidation', () => {
  it('invalidates old and new landing locations when a category moves parent', async () => {
    mockCategoryFindUnique
      .mockResolvedValueOnce({ id: 'parent-2', parentId: null })
      .mockResolvedValueOnce({
        slug: 'old-child',
        legacySlug: 'old-parent-old-child',
        parentId: 'parent-1',
        parent: { slug: 'old-parent' },
      })
      .mockResolvedValueOnce({
        slug: 'new-child',
        legacySlug: 'old-parent-old-child',
        parentId: 'parent-2',
        parent: { slug: 'new-parent' },
      });
    mockCategoryUpdate.mockResolvedValue({
      slug: 'new-child',
      legacySlug: 'old-parent-old-child',
    });

    await updateCategory('cat-1', { parentId: 'parent-2' });

    expect(deletedKeys()).toEqual(
      expect.arrayContaining([
        'catalog:tree:v1',
        'catalog:landing:v1:old-parent:old-child',
        'catalog:landing:v1:old-parent',
        'catalog:landing:v1:new-parent:new-child',
        'catalog:landing:v1:new-parent',
        'redirect:legacy:v1:category:old-child',
        'redirect:legacy:v1:category:old-parent-old-child',
        'redirect:legacy:v1:category:new-child',
      ]),
    );
  });

  it('invalidates parent landing and tree when creating a child category', async () => {
    mockCategoryFindUnique
      .mockResolvedValueOnce({ id: 'parent-1', parentId: null })
      .mockResolvedValueOnce({ slug: 'parent', parentId: null, parent: null });
    mockCategoryFindFirst.mockResolvedValue(null);
    mockCategoryCreate.mockResolvedValue({
      id: 'child-1',
      slug: 'child',
      parentId: 'parent-1',
    });

    await createCategory({ name: 'Child', parentId: 'parent-1' });

    expect(deletedKeys()).toEqual(
      expect.arrayContaining([
        'catalog:tree:v1',
        'catalog:landing:v1:parent',
      ]),
    );
  });

  it('invalidates old child landing, parent landing, and tree when deleting a child category', async () => {
    mockIdeaCount.mockResolvedValue(0);
    mockPainPointCount.mockResolvedValue(0);
    mockCategoryFindUnique.mockResolvedValue({
      slug: 'child',
      parentId: 'parent-1',
      parent: { slug: 'parent' },
    });
    mockCategoryDelete.mockResolvedValue({ id: 'child-1' });

    await deleteCategory('child-1');

    expect(deletedKeys()).toEqual(
      expect.arrayContaining([
        'catalog:tree:v1',
        'catalog:landing:v1:parent:child',
        'catalog:landing:v1:parent',
      ]),
    );
  });
});
