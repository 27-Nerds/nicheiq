import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Admin layout server load', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const createMockEvent = (user: { id: string; email?: string; role?: string } | null) => ({
    locals: {
      auth: async () => (user ? { user } : null),
    },
    url: new URL('http://localhost:3000/admin'),
  });

  it('redirects to /login when no session', async () => {
    const { load } = await import('../+layout.server');

    try {
      await load(createMockEvent(null) as any);
      expect.fail('Should have thrown redirect');
    } catch (error: any) {
      expect(error.status).toBe(302);
      expect(error.location).toBe('/login');
    }
  });

  it('redirects to /dashboard when user role is USER', async () => {
    const { load } = await import('../+layout.server');

    try {
      await load(createMockEvent({ id: 'user-123', email: 'u@test.com', role: 'USER' }) as any);
      expect.fail('Should have thrown redirect');
    } catch (error: any) {
      expect(error.status).toBe(302);
      expect(error.location).toBe('/dashboard');
    }
  });

  it('redirects to /dashboard when user has no role', async () => {
    const { load } = await import('../+layout.server');

    try {
      await load(createMockEvent({ id: 'user-123', email: 'u@test.com' }) as any);
      expect.fail('Should have thrown redirect');
    } catch (error: any) {
      expect(error.status).toBe(302);
      expect(error.location).toBe('/dashboard');
    }
  });

  it('returns session when user role is ADMIN', async () => {
    const { load } = await import('../+layout.server');

    const result = await load(
      createMockEvent({ id: 'admin-123', email: 'admin@test.com', role: 'ADMIN' }) as any
    );

    expect(result.session.user.id).toBe('admin-123');
    expect(result.session.user.role).toBe('ADMIN');
  });
});
