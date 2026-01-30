import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('GET /api/admin/dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const createMockLocals = (user: { id: string; email?: string; role?: string } | null) => ({
    auth: async () => (user ? { user } : null),
  });

  describe('authentication', () => {
    it('returns 401 when not authenticated', async () => {
      const { GET } = await import('../+server');

      try {
        await GET({
          locals: createMockLocals(null),
        } as any);
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error.status).toBe(401);
      }
    });

    it('returns 401 when session has no user', async () => {
      const { GET } = await import('../+server');

      try {
        await GET({
          locals: { auth: async () => ({}) },
        } as any);
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error.status).toBe(401);
      }
    });

    it('returns 403 when user role is not ADMIN', async () => {
      const { GET } = await import('../+server');

      try {
        await GET({
          locals: createMockLocals({ id: 'user-123', email: 'u@test.com', role: 'USER' }),
        } as any);
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error.status).toBe(403);
      }
    });
  });

  describe('successful request', () => {
    it('proxies response from backend', async () => {
      const statsData = {
        totalUsers: 100,
        totalJobs: 50,
        activeJobs: 5,
        completedJobs: 40,
        failedJobs: 5,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => statsData,
      });

      const { GET } = await import('../+server');
      const response = await GET({
        locals: createMockLocals({ id: 'admin-123', email: 'admin@test.com', role: 'ADMIN' }),
      } as any);

      const data = await response.json();
      expect(data.totalUsers).toBe(100);
      expect(response.status).toBe(200);
    });

    it('includes correct headers in backend request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({}),
      });

      const { GET } = await import('../+server');
      await GET({
        locals: createMockLocals({ id: 'admin-123', email: 'admin@test.com', role: 'ADMIN' }),
      } as any);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/dashboard'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-User-ID': 'admin-123',
            'X-User-Role': 'ADMIN',
          }),
        })
      );
    });
  });

  describe('error handling', () => {
    it('forwards error status from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Internal error' }),
      });

      const { GET } = await import('../+server');
      const response = await GET({
        locals: createMockLocals({ id: 'admin-123', email: 'admin@test.com', role: 'ADMIN' }),
      } as any);

      expect(response.status).toBe(500);
    });
  });
});
