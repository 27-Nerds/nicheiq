import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Type for the load function result
interface LoadResult {
  packages: Array<{ id: string; name?: string; credits?: number; priceInCents?: number }>;
  billing: {
    balance: number;
    totalPurchased: number;
    totalUsed: number;
    recentTransactions: unknown[];
  };
  success: boolean;
  canceled: boolean;
}

// ============================================
// T10: Billing page server load tests
// ============================================

describe('+page.server.ts load function', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockParent = vi.fn();
  const createMockUrl = (params: Record<string, string> = {}) => {
    const url = new URL('http://localhost:3000/billing');
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.set(key, value);
    });
    return url;
  };

  describe('packages fetching', () => {
    it('fetches packages from backend', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            packages: [
              { id: 'pkg-1', name: 'Starter', credits: 5, priceInCents: 999 },
            ],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            balance: 10,
            totalPurchased: 15,
            totalUsed: 5,
            recentTransactions: [],
          }),
        });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any) as LoadResult;

      expect(result.packages).toHaveLength(1);
      expect(result.packages[0].name).toBe('Starter');
    });

    it('returns empty packages array on fetch error', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            balance: 0,
            totalPurchased: 0,
            totalUsed: 0,
            recentTransactions: [],
          }),
        });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any) as LoadResult;

      expect(result.packages).toEqual([]);
    });

    it('returns empty packages when response not ok', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockResolvedValueOnce({ ok: false, status: 500 })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            balance: 0,
            totalPurchased: 0,
            totalUsed: 0,
            recentTransactions: [],
          }),
        });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any) as LoadResult;

      expect(result.packages).toEqual([]);
    });
  });

  describe('success/canceled query params', () => {
    it('detects success=true query param', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ packages: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            balance: 15,
            totalPurchased: 20,
            totalUsed: 5,
            recentTransactions: [],
          }),
        });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl({ success: 'true' }),
      } as any) as LoadResult;

      expect(result.success).toBe(true);
      expect(result.canceled).toBe(false);
    });

    it('detects canceled=true query param', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ packages: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            balance: 10,
            totalPurchased: 10,
            totalUsed: 0,
            recentTransactions: [],
          }),
        });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl({ canceled: 'true' }),
      } as any) as LoadResult;

      expect(result.success).toBe(false);
      expect(result.canceled).toBe(true);
    });

    it('defaults to false when no query params', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ packages: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            balance: 10,
            totalPurchased: 10,
            totalUsed: 0,
            recentTransactions: [],
          }),
        });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any) as LoadResult;

      expect(result.success).toBe(false);
      expect(result.canceled).toBe(false);
    });
  });

  describe('unauthenticated user', () => {
    it('returns default billing data when no session', async () => {
      mockParent.mockResolvedValue({ session: null });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ packages: [{ id: 'pkg-1' }] }),
      });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any) as LoadResult;

      expect(result.billing.balance).toBe(0);
      expect(result.billing.totalPurchased).toBe(0);
      expect(result.billing.totalUsed).toBe(0);
      expect(result.billing.recentTransactions).toEqual([]);
      // Still fetches packages even without session
      expect(result.packages).toHaveLength(1);
    });

    it('returns default billing when userId is missing', async () => {
      mockParent.mockResolvedValue({ session: { user: {} } });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ packages: [] }),
      });

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any) as LoadResult;

      expect(result.billing.balance).toBe(0);
    });
  });

  describe('billing data fetching', () => {
    it('includes auth headers when fetching billing', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ packages: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            balance: 10,
            totalPurchased: 10,
            totalUsed: 0,
            recentTransactions: [],
          }),
        });

      const { load } = await import('../+page.server');
      await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any);

      // Second call is billing endpoint
      const billingCall = mockFetch.mock.calls[1];
      expect(billingCall[0]).toContain('/api/billing');
      expect(billingCall[1].headers['X-User-ID']).toBe('user-123');
    });

    it('returns default billing on fetch error', async () => {
      mockParent.mockResolvedValue({ session: { user: { id: 'user-123' } } });

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ packages: [] }),
        })
        .mockRejectedValueOnce(new Error('Network error'));

      const { load } = await import('../+page.server');
      const result = await load({
        parent: mockParent,
        url: createMockUrl(),
      } as any) as LoadResult;

      expect(result.billing.balance).toBe(0);
    });
  });
});
