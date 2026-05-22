import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

/**
 * Access-control guard for the saves feature. A user may only SAVE/PATCH an item
 * they can access (featured items, or anything if entitled); the saved-list
 * redacts non-featured rows to locked placeholders for non-entitled users.
 *
 * Entitlement is stubbed via the DB-backed `isEntitledUser` (NOT the X-User-Role
 * header — the saves proxies don't forward it), proving the DB-backed path.
 */

const SECRET = 'test-internal-secret';
const UUID_A = '11111111-1111-1111-1111-111111111111';
const UUID_FEATURED = '22222222-2222-2222-2222-222222222222';

const mockIsEntitledUser = vi.fn();
const mockResolveFeaturedIdeaId = vi.fn();
const mockResolveFeaturedPainId = vi.fn();

vi.mock('../../services/catalogService.js', () => ({
  isEntitledUser: (...a: any[]) => mockIsEntitledUser(...a),
  resolveFeaturedIdeaId: (...a: any[]) => mockResolveFeaturedIdeaId(...a),
  resolveFeaturedPainId: (...a: any[]) => mockResolveFeaturedPainId(...a),
}));

const mockIdeaFindUnique = vi.fn();
const mockPainFindUnique = vi.fn();
const mockSavedIdeaUpsert = vi.fn();
const mockSavedIdeaFindUnique = vi.fn();
const mockSavedIdeaUpdate = vi.fn();
const mockSavedIdeaFindMany = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    catalogIdea: { findUnique: (...a: any[]) => mockIdeaFindUnique(...a) },
    catalogPainPoint: { findUnique: (...a: any[]) => mockPainFindUnique(...a) },
    savedIdea: {
      upsert: (...a: any[]) => mockSavedIdeaUpsert(...a),
      findUnique: (...a: any[]) => mockSavedIdeaFindUnique(...a),
      update: (...a: any[]) => mockSavedIdeaUpdate(...a),
      findMany: (...a: any[]) => mockSavedIdeaFindMany(...a),
      deleteMany: vi.fn(),
    },
    savedPainPoint: {
      upsert: vi.fn(),
      findUnique: vi.fn(),
      update: vi.fn(),
      findMany: vi.fn(),
      deleteMany: vi.fn(),
    },
  },
}));

let app: Express;
let prevSecret: string | undefined;

beforeAll(() => {
  prevSecret = process.env.INTERNAL_SERVICE_SECRET;
  process.env.INTERNAL_SERVICE_SECRET = SECRET;
});
afterAll(() => {
  if (prevSecret === undefined) delete process.env.INTERNAL_SERVICE_SECRET;
  else process.env.INTERNAL_SERVICE_SECRET = prevSecret;
});

beforeEach(async () => {
  vi.clearAllMocks();
  mockSavedIdeaUpsert.mockResolvedValue({ id: 'saved-1', ideaId: UUID_A });
  const { savesRouter } = await import('../saves.js');
  app = express();
  app.use(express.json());
  app.use('/api/saves', savesRouter);
});

// Authenticated request helper: service secret + X-User-ID, NO X-User-Role.
function as(userId: string) {
  return { 'X-Internal-Service': SECRET, 'X-User-ID': userId } as Record<string, string>;
}

describe('POST /api/saves/ideas — access control', () => {
  it('non-entitled user saving a NON-featured idea → 403', async () => {
    mockIsEntitledUser.mockResolvedValue(false);
    mockIdeaFindUnique.mockResolvedValue({ id: UUID_A, categoryId: 'cat-1', isActive: true, slug: 'an-idea' });
    mockResolveFeaturedIdeaId.mockResolvedValue(UUID_FEATURED); // a different idea is featured

    const res = await request(app).post('/api/saves/ideas').set(as('user-1')).send({ ideaId: UUID_A });
    expect(res.status).toBe(403);
    expect(mockSavedIdeaUpsert).not.toHaveBeenCalled();
  });

  it('non-entitled user saving the FEATURED idea → 200', async () => {
    mockIsEntitledUser.mockResolvedValue(false);
    mockIdeaFindUnique.mockResolvedValue({ id: UUID_A, categoryId: 'cat-1', isActive: true, slug: 'an-idea' });
    mockResolveFeaturedIdeaId.mockResolvedValue(UUID_A); // this idea IS featured

    const res = await request(app).post('/api/saves/ideas').set(as('user-1')).send({ ideaId: UUID_A });
    expect(res.status).toBe(200);
    expect(mockSavedIdeaUpsert).toHaveBeenCalledOnce();
  });

  it('entitled user (ADMIN/fullCatalogAccess, NO X-User-Role) saving a non-featured idea → 200', async () => {
    mockIsEntitledUser.mockResolvedValue(true); // DB says entitled
    mockIdeaFindUnique.mockResolvedValue({ id: UUID_A, categoryId: 'cat-1', isActive: true, slug: 'an-idea' });
    mockResolveFeaturedIdeaId.mockResolvedValue(UUID_FEATURED);

    const res = await request(app).post('/api/saves/ideas').set(as('admin-1')).send({ ideaId: UUID_A });
    expect(res.status).toBe(200);
    // resolveFeaturedIdeaId is short-circuited when entitled.
    expect(mockResolveFeaturedIdeaId).not.toHaveBeenCalled();
  });

  it('inactive / slug-less idea → 404 (notfound), not 403', async () => {
    mockIsEntitledUser.mockResolvedValue(false);
    mockIdeaFindUnique.mockResolvedValue({ id: UUID_A, categoryId: 'cat-1', isActive: false, slug: null });

    const res = await request(app).post('/api/saves/ideas').set(as('user-1')).send({ ideaId: UUID_A });
    expect(res.status).toBe(404);
  });
});

describe('PATCH /api/saves/ideas/:ideaId — access control (Option B)', () => {
  it('a saved-but-now-locked idea by a non-entitled user → 403', async () => {
    mockSavedIdeaFindUnique.mockResolvedValue({ id: 'saved-1' }); // ownership ok
    mockIsEntitledUser.mockResolvedValue(false);
    mockIdeaFindUnique.mockResolvedValue({ id: UUID_A, categoryId: 'cat-1', isActive: true, slug: 'an-idea' });
    mockResolveFeaturedIdeaId.mockResolvedValue(UUID_FEATURED);

    const res = await request(app)
      .patch(`/api/saves/ideas/${UUID_A}`)
      .set(as('user-1'))
      .send({ notes: 'hi' });
    expect(res.status).toBe(403);
    expect(mockSavedIdeaUpdate).not.toHaveBeenCalled();
  });

  it('an unsaved idea → 404 (ownership checked before access)', async () => {
    mockSavedIdeaFindUnique.mockResolvedValue(null); // no saved row

    const res = await request(app)
      .patch(`/api/saves/ideas/${UUID_A}`)
      .set(as('user-1'))
      .send({ notes: 'hi' });
    expect(res.status).toBe(404);
  });
});

describe('GET /api/saves/ideas — locked redaction', () => {
  const rows = [
    {
      id: 'saved-feat', ideaId: UUID_FEATURED, notes: 'my featured note', createdAt: '2026-01-02T00:00:00Z',
      idea: { id: UUID_FEATURED, solutionName: 'FeaturedIdeaTitle', description: 'featured desc', marketFitScore: 90, category: { id: 'cat-1' } },
    },
    {
      id: 'saved-lock', ideaId: UUID_A, notes: 'secret private note', createdAt: '2026-01-01T00:00:00Z',
      idea: { id: UUID_A, solutionName: 'LockedSecretIdea', description: 'leaky description', marketFitScore: 77, category: { id: 'cat-1' } },
    },
  ];

  it('non-entitled: featured row full, non-featured row redacted to locked', async () => {
    mockIsEntitledUser.mockResolvedValue(false);
    mockResolveFeaturedIdeaId.mockResolvedValue(UUID_FEATURED); // featured for cat-1
    mockSavedIdeaFindMany.mockResolvedValue(rows);

    const res = await request(app).get('/api/saves/ideas').set(as('user-1'));
    expect(res.status).toBe(200);

    const body = JSON.stringify(res.body);
    // Featured item content present.
    expect(body).toContain('FeaturedIdeaTitle');
    // Locked item content + note must NOT leak.
    expect(body).not.toContain('LockedSecretIdea');
    expect(body).not.toContain('leaky description');
    expect(body).not.toContain('secret private note');

    const locked = res.body.items.find((r: any) => r.id === 'saved-lock');
    expect(locked.locked).toBe(true);
    expect(locked.idea).toBeNull();
    expect(locked.notes).toBeNull();
  });

  it('entitled: both rows returned full', async () => {
    mockIsEntitledUser.mockResolvedValue(true);
    mockSavedIdeaFindMany.mockResolvedValue(rows);

    const res = await request(app).get('/api/saves/ideas').set(as('admin-1'));
    expect(res.status).toBe(200);
    const body = JSON.stringify(res.body);
    expect(body).toContain('FeaturedIdeaTitle');
    expect(body).toContain('LockedSecretIdea');
    expect(mockResolveFeaturedIdeaId).not.toHaveBeenCalled();
  });
});

describe('POST /api/saves — auth gate', () => {
  it('401 without X-User-ID (service secret only)', async () => {
    const res = await request(app)
      .post('/api/saves/ideas')
      .set('X-Internal-Service', SECRET)
      .send({ ideaId: UUID_A });
    expect(res.status).toBe(401);
  });
});
