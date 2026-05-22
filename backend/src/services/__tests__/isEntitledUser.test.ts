import { describe, it, expect, vi, beforeEach } from 'vitest';

/**
 * Unit test for the DB-backed entitlement helper. The route tests MOCK
 * `isEntitledUser`, so they only prove the routes don't read `req.user.role`;
 * this proves the helper itself resolves role + fullCatalogAccess correctly.
 */

const mockUserFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: { user: { findUnique: (...a: any[]) => mockUserFindUnique(...a) } },
}));
vi.mock('../redis.js', () => ({ getRedis: () => ({ del: vi.fn() }) }));

import { isEntitledUser } from '../catalogService.js';

beforeEach(() => vi.clearAllMocks());

describe('isEntitledUser', () => {
  it('ADMIN role → true (even without fullCatalogAccess)', async () => {
    mockUserFindUnique.mockResolvedValue({ role: 'ADMIN', fullCatalogAccess: false });
    expect(await isEntitledUser('u1')).toBe(true);
  });

  it('fullCatalogAccess grant → true (even as a plain USER)', async () => {
    mockUserFindUnique.mockResolvedValue({ role: 'USER', fullCatalogAccess: true });
    expect(await isEntitledUser('u1')).toBe(true);
  });

  it('plain user → false', async () => {
    mockUserFindUnique.mockResolvedValue({ role: 'USER', fullCatalogAccess: false });
    expect(await isEntitledUser('u1')).toBe(false);
  });

  it('missing user row → false', async () => {
    mockUserFindUnique.mockResolvedValue(null);
    expect(await isEntitledUser('u1')).toBe(false);
  });

  it('undefined id → false without a DB call', async () => {
    expect(await isEntitledUser(undefined)).toBe(false);
    expect(mockUserFindUnique).not.toHaveBeenCalled();
  });
});
