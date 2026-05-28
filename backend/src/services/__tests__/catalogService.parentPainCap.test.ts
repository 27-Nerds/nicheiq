import { describe, expect, it } from 'vitest';

import {
  computeLockedPainCount,
  paginatedPainFetchPolicyForLanding,
} from '../catalogService.js';

describe('paginatedPainFetchPolicyForLanding()', () => {
  it('caps parent landings at 12 with severity-first order (no isFeatured tiebreaker)', () => {
    const policy = paginatedPainFetchPolicyForLanding({ isParentPage: true });

    expect(policy.take).toBe(12);
    expect(policy.orderBy[0]).toEqual({ severityScore: 'desc' });
    // PARENT_PAIN_ORDER intentionally drops the featured-first sort key —
    // featured items at low severity must not crowd out higher-severity
    // non-featured rows on a top-N aggregated view.
    expect(policy.orderBy.some((o) => 'isFeatured' in o)).toBe(false);
  });

  it('leaves leaf / non-parent landings uncapped and featured-first', () => {
    const policy = paginatedPainFetchPolicyForLanding({ isParentPage: false });

    expect(policy.take).toBeUndefined();
    expect(policy.orderBy[0]).toEqual({ isFeatured: 'desc' });
  });
});

describe('computeLockedPainCount()', () => {
  it('returns 0 for entitled users even when the visible set is below the total', () => {
    expect(
      computeLockedPainCount({
        entitled: true,
        totalPainPoints: 123,
        visiblePainPoints: 12,
      }),
    ).toBe(0);
    expect(
      computeLockedPainCount({
        entitled: true,
        totalPainPoints: 5,
        visiblePainPoints: 5,
      }),
    ).toBe(0);
  });

  it('returns the featured-only deficit for non-entitled users', () => {
    expect(
      computeLockedPainCount({
        entitled: false,
        totalPainPoints: 50,
        visiblePainPoints: 1,
      }),
    ).toBe(49);
  });

  it('clamps to 0 when visible exceeds total (defensive — should not happen in practice)', () => {
    expect(
      computeLockedPainCount({
        entitled: false,
        totalPainPoints: 1,
        visiblePainPoints: 5,
      }),
    ).toBe(0);
  });
});
