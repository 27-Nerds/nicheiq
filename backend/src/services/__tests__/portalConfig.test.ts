import { describe, it, expect, vi, beforeEach } from 'vitest';

// Verifies createBillingPortalSession's portal-configuration handling: lazy create + cache the
// cancel-at-period-end config, reuse the cached id, self-heal a stale id, and fall back to the
// account default when config creation fails.

const userFindUnique = vi.fn();
const apptFindUnique = vi.fn();
const apptUpsert = vi.fn();
const apptDeleteMany = vi.fn();
const cfgCreate = vi.fn();
const sessCreate = vi.fn();

vi.mock('../stripeClient.js', () => ({
  getStripe: () => ({
    billingPortal: {
      configurations: { create: (...a: any[]) => cfgCreate(...a) },
      sessions: { create: (...a: any[]) => sessCreate(...a) },
    },
  }),
}));
vi.mock('../db.js', () => ({
  prisma: {
    user: { findUnique: (...a: any[]) => userFindUnique(...a) },
    appSettings: {
      findUnique: (...a: any[]) => apptFindUnique(...a),
      upsert: (...a: any[]) => apptUpsert(...a),
      deleteMany: (...a: any[]) => apptDeleteMany(...a),
    },
  },
}));
vi.mock('../creditService.js', () => ({ resetMonthlyAllowance: vi.fn() }));
vi.mock('../../config.js', () => ({ CONFIG: { baseUrl: 'http://localhost:3000', stripe: {} } }));

import { createBillingPortalSession } from '../subscriptionService.js';

beforeEach(() => {
  vi.clearAllMocks();
  userFindUnique.mockResolvedValue({ stripeCustomerId: 'cus_1' });
  apptUpsert.mockResolvedValue({});
  apptDeleteMany.mockResolvedValue({ count: 1 });
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

describe('createBillingPortalSession — portal configuration', () => {
  it('creates + caches a config on first open and passes it to the session', async () => {
    apptFindUnique.mockResolvedValue(null);
    cfgCreate.mockResolvedValue({ id: 'bpc_new' });
    sessCreate.mockResolvedValue({ url: 'https://portal/new' });

    const res = await createBillingPortalSession('u1');

    expect(cfgCreate).toHaveBeenCalledTimes(1);
    // cancel-at-period-end, no proration
    expect(cfgCreate.mock.calls[0][0].features.subscription_cancel).toEqual(
      expect.objectContaining({ enabled: true, mode: 'at_period_end', proration_behavior: 'none' }),
    );
    expect(apptUpsert).toHaveBeenCalled();
    expect(sessCreate).toHaveBeenCalledWith(expect.objectContaining({ configuration: 'bpc_new' }));
    expect(res.url).toBe('https://portal/new');
  });

  it('reuses the cached config id (no second create)', async () => {
    apptFindUnique.mockResolvedValue({ value: 'bpc_cached' });
    sessCreate.mockResolvedValue({ url: 'https://portal/cached' });

    await createBillingPortalSession('u1');

    expect(cfgCreate).not.toHaveBeenCalled();
    expect(sessCreate).toHaveBeenCalledWith(expect.objectContaining({ configuration: 'bpc_cached' }));
  });

  it('self-heals a stale cached id: clears it and retries without configuration', async () => {
    apptFindUnique.mockResolvedValue({ value: 'bpc_stale' });
    sessCreate
      .mockRejectedValueOnce(new Error('No such configuration: bpc_stale'))
      .mockResolvedValueOnce({ url: 'https://portal/default' });

    const res = await createBillingPortalSession('u1');

    expect(apptDeleteMany).toHaveBeenCalled();
    expect(sessCreate).toHaveBeenCalledTimes(2);
    expect(sessCreate.mock.calls[1][0]).not.toHaveProperty('configuration');
    expect(res.url).toBe('https://portal/default');
  });

  it('falls back to the account default when config creation fails', async () => {
    apptFindUnique.mockResolvedValue(null);
    cfgCreate.mockRejectedValue(new Error('a public business profile is required'));
    sessCreate.mockResolvedValue({ url: 'https://portal/fallback' });

    const res = await createBillingPortalSession('u1');

    expect(sessCreate).toHaveBeenCalledTimes(1);
    expect(sessCreate.mock.calls[0][0]).not.toHaveProperty('configuration');
    expect(res.url).toBe('https://portal/fallback');
  });
});
