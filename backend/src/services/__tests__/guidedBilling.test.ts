/**
 * Guided segment billing.
 *
 * Guided runs pay for discovery a segment at a time, as the user authorizes each one:
 *
 *   guided_s1     job creation      stage 1     -> G1
 *   guided_s2_4   Continue at G1    stages 2-4  -> G2
 *   guided_s5     Continue at G2    stage 5     -> selection
 *
 * These tests pin the two things that are expensive and quiet to get wrong: a price the admin
 * panel appears to change but doesn't, and a full guided run that costs a different total than a
 * standard one.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockSettingsFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    appSettings: { findUnique: (a: any) => mockSettingsFindUnique(a) },
    job: {}, jobDispatch: {}, jobProgress: {}, userCredits: {}, creditTransaction: {},
    $transaction: (cb: any) => cb({}),
  },
}));

/** No admin overrides — every price falls back to its derived default. */
function noOverrides() {
  mockSettingsFindUnique.mockResolvedValue(null);
}

beforeEach(() => {
  vi.clearAllMocks();
  noOverrides();
});

describe('the default split follows the work, not the calendar', () => {
  it('splits a 5-credit discovery as 1 / 3 / 1 — a full guided run costs the same as a standard one', async () => {
    const { getGuidedSegmentCosts } = await import('../creditService.js');
    const costs = await getGuidedSegmentCosts();

    // Segment B runs THREE stages; A and C run one each. Equal thirds would have charged the same
    // for all three, and with 5 credits the rounding would have landed on 1/1/3 — least money for
    // the most work.
    expect(costs).toEqual({ guided_s1: 1, guided_s2_4: 3, guided_s5: 1, total: 5 });
  });

  it('the three segments always sum to exactly the discovery price (rounding remainder included)', async () => {
    const { getGuidedSegmentCosts } = await import('../creditService.js');

    for (const discovery of [0, 1, 2, 3, 4, 5, 7, 9, 11, 13, 20, 99]) {
      mockSettingsFindUnique.mockImplementation(async ({ where }: any) =>
        where.key === 'token_cost_discovery' ? { value: String(discovery) } : null,
      );
      const costs = await getGuidedSegmentCosts();
      expect(costs.total).toBe(discovery);
      expect(costs.guided_s1 + costs.guided_s2_4 + costs.guided_s5).toBe(discovery);
    }
  });

  it('re-pricing discovery re-prices the segments with it', async () => {
    const { getGuidedSegmentCosts } = await import('../creditService.js');
    mockSettingsFindUnique.mockImplementation(async ({ where }: any) =>
      where.key === 'token_cost_discovery' ? { value: '10' } : null,
    );

    // Derived, not a static default — so the guided and standard prices can never drift apart
    // behind the admin's back.
    expect(await getGuidedSegmentCosts()).toEqual({
      guided_s1: 2, guided_s2_4: 6, guided_s5: 2, total: 10,
    });
  });
});

describe('admin overrides actually load', () => {
  it('reads token_cost_guided_s2_4 — the settings key the stage name generates', async () => {
    // The trap this test exists for: getStageCost builds its key mechanically as
    // `token_cost_${stage}`. An earlier draft named the stages `discovery_s*` while naming the
    // settings `token_cost_guided_*`, so the lookup would have asked for a key nobody writes —
    // the admin panel would have appeared to work while changing nothing at all.
    const { getStageCost } = await import('../creditService.js');
    mockSettingsFindUnique.mockImplementation(async ({ where }: any) =>
      where.key === 'token_cost_guided_s2_4' ? { value: '7' } : null,
    );

    expect(await getStageCost('guided_s2_4')).toBe(7);
    expect(mockSettingsFindUnique).toHaveBeenCalledWith(
      expect.objectContaining({ where: { key: 'token_cost_guided_s2_4' } }),
    );
  });

  it('refuses a price that is not an exact integer, rather than silently reading part of it', async () => {
    // parseInt would read "1.5" and "1abc" as 1 — a price change nobody typed.
    const { getStageCost } = await import('../creditService.js');

    for (const junk of ['1.5', '1abc', 'free', '', '-2']) {
      mockSettingsFindUnique.mockImplementation(async ({ where }: any) =>
        where.key === 'token_cost_guided_s1' ? { value: junk } : null,
      );
      // Falls back to the derived default (1 of a 5-credit discovery) instead of inventing a price.
      expect(await getStageCost('guided_s1')).toBe(1);
    }
  });
});

describe('which segment a checkpoint buys', () => {
  it('G1 Continue buys stages 2-4; G2 Continue buys stage 5', async () => {
    const { segmentForGateContinue } = await import('../creditService.js');
    expect(segmentForGateContinue(1)).toBe('guided_s2_4');
    expect(segmentForGateContinue(4)).toBe('guided_s5');
  });
});
