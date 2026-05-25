import { beforeEach, describe, expect, it, vi } from 'vitest';

// The free-preview gate keys ONLY on `isFreePreview` (no score fallback) and returns null when
// nothing is flagged. (The one-per-category demote-first ordering in updateCatalogIdea is enforced
// at the DB level by the partial unique index, and exercised end-to-end — not re-asserted here.)

const mockIdeaFindFirst = vi.fn();
const mockPainFindFirst = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    catalogIdea: { findFirst: (...a: any[]) => mockIdeaFindFirst(...a) },
    catalogPainPoint: { findFirst: (...a: any[]) => mockPainFindFirst(...a) },
  },
}));
vi.mock('../redis.js', () => ({ getRedis: () => ({ del: vi.fn() }) }));

import { resolveFreePreviewIdeaId, resolveFreePreviewPainId } from '../catalogService.js';

beforeEach(() => vi.clearAllMocks());

describe('resolveFreePreviewIdeaId / PainId', () => {
  it('returns the flagged idea id and queries with isFreePreview:true', async () => {
    mockIdeaFindFirst.mockResolvedValue({ id: 'idea-1' });
    expect(await resolveFreePreviewIdeaId('cat-1')).toBe('idea-1');
    expect(mockIdeaFindFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ categoryId: 'cat-1', isActive: true, isFreePreview: true }),
      }),
    );
  });

  it('returns null when no idea is flagged (no score fallback → fully gated)', async () => {
    mockIdeaFindFirst.mockResolvedValue(null);
    expect(await resolveFreePreviewIdeaId('cat-1')).toBeNull();
  });

  it('returns the flagged pain id, null when none', async () => {
    mockPainFindFirst.mockResolvedValueOnce({ id: 'pain-1' }).mockResolvedValueOnce(null);
    expect(await resolveFreePreviewPainId('cat-1')).toBe('pain-1');
    expect(await resolveFreePreviewPainId('cat-1')).toBeNull();
    expect(mockPainFindFirst).toHaveBeenCalledWith(
      expect.objectContaining({ where: expect.objectContaining({ isFreePreview: true }) }),
    );
  });
});
