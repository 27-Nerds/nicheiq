import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// ============================================
// T11: Checkout API proxy tests
// ============================================

describe('POST /api/billing/checkout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const createMockRequest = (body: any) => ({
    json: async () => body,
  });

  const createMockLocals = (user: { id: string; email?: string } | null) => ({
    auth: async () => (user ? { user } : null),
  });

  describe('authentication', () => {
    it('returns 401 when not authenticated', async () => {
      const { POST } = await import('../+server');

      try {
        await POST({
          request: createMockRequest({ packageId: 'pkg-123' }),
          locals: createMockLocals(null),
        } as any);
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error.status).toBe(401);
      }
    });

    it('returns 401 when session has no user', async () => {
      const { POST } = await import('../+server');

      const localsWithEmptySession = {
        auth: async () => ({}),
      };

      try {
        await POST({
          request: createMockRequest({ packageId: 'pkg-123' }),
          locals: localsWithEmptySession,
        } as any);
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error.status).toBe(401);
      }
    });
  });

  describe('successful checkout', () => {
    it('forwards request to backend and returns checkout URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ url: 'https://checkout.stripe.com/xxx' }),
      });

      const { POST } = await import('../+server');
      const response = await POST({
        request: createMockRequest({ packageId: 'pkg-123' }),
        locals: createMockLocals({ id: 'user-123', email: 'user@example.com' }),
      } as any);

      const data = await response.json();
      expect(data.url).toBe('https://checkout.stripe.com/xxx');
      expect(response.status).toBe(200);
    });

    it('includes correct headers in backend request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ url: 'https://checkout.stripe.com/xxx' }),
      });

      const { POST } = await import('../+server');
      await POST({
        request: createMockRequest({ packageId: 'pkg-123' }),
        locals: createMockLocals({ id: 'user-123', email: 'user@example.com' }),
      } as any);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/billing/checkout'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-User-ID': 'user-123',
            'X-User-Email': 'user@example.com',
          }),
        })
      );
    });

    it('forwards packageId in request body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ url: 'https://checkout.stripe.com/xxx' }),
      });

      const { POST } = await import('../+server');
      await POST({
        request: createMockRequest({ packageId: 'pkg-starter' }),
        locals: createMockLocals({ id: 'user-123', email: 'user@example.com' }),
      } as any);

      const [, options] = mockFetch.mock.calls[0];
      const body = JSON.parse(options.body);
      expect(body.packageId).toBe('pkg-starter');
    });

    it('handles missing email gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ url: 'https://checkout.stripe.com/xxx' }),
      });

      const { POST } = await import('../+server');
      await POST({
        request: createMockRequest({ packageId: 'pkg-123' }),
        locals: createMockLocals({ id: 'user-123' }), // no email
      } as any);

      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers['X-User-Email']).toBe('');
    });
  });

  describe('error handling', () => {
    it('forwards 400 error from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Package ID is required', code: 'MISSING_PACKAGE_ID' }),
      });

      const { POST } = await import('../+server');
      const response = await POST({
        request: createMockRequest({}),
        locals: createMockLocals({ id: 'user-123', email: 'user@example.com' }),
      } as any);

      const data = await response.json();
      expect(response.status).toBe(400);
      expect(data.code).toBe('MISSING_PACKAGE_ID');
    });

    it('forwards 404 error from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'Package not found', code: 'PACKAGE_NOT_FOUND' }),
      });

      const { POST } = await import('../+server');
      const response = await POST({
        request: createMockRequest({ packageId: 'nonexistent' }),
        locals: createMockLocals({ id: 'user-123', email: 'user@example.com' }),
      } as any);

      const data = await response.json();
      expect(response.status).toBe(404);
      expect(data.code).toBe('PACKAGE_NOT_FOUND');
    });

    it('forwards 500 error from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Failed to create checkout session', code: 'CHECKOUT_FAILED' }),
      });

      const { POST } = await import('../+server');
      const response = await POST({
        request: createMockRequest({ packageId: 'pkg-123' }),
        locals: createMockLocals({ id: 'user-123', email: 'user@example.com' }),
      } as any);

      expect(response.status).toBe(500);
    });
  });
});
