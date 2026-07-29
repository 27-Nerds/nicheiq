import { describe, expect, it } from 'vitest';
import {
  SALES_CONVERSION_CEILING_PCT,
  checkSuggestedTest,
  parseThreshold,
  timeWindowsInDays,
} from '../selectionTestThresholds.js';

const base = {
  hypothesis: 'Buyers will click through to the safety toolkit.',
  method: 'CTA_SMOKE_TEST',
  passThreshold: '>=18% click-through',
  failThreshold: '<=6% click-through',
  measurementWindow: '14 days',
};

describe('timeWindowsInDays', () => {
  it.each([
    ['within 7 days', [7]],
    ['a 30-day outbound window', [30]],
    ['within 6 weeks', [42]],
    ['8 weeks', [56]],
    ['3 months', [90]],
    ['no window here', []],
  ])('reads %s', (text, expected) => {
    expect(timeWindowsInDays(text)).toEqual(expected);
  });
});

describe('parseThreshold', () => {
  it.each([
    ['>=18% click-through', { direction: 'at-least', value: 18, unit: 'percent' }],
    ['<=6% click-through', { direction: 'at-most', value: 6, unit: 'percent' }],
    ['At least 12 paid pilot signups', { direction: 'at-least', value: 12, unit: 'count' }],
    ['<4 paid pilot signups', { direction: 'at-most', value: 4, unit: 'count' }],
    ['fewer than 2 requests', { direction: 'at-most', value: 2, unit: 'count' }],
  ])('parses %s', (text, expected) => {
    expect(parseThreshold(text)).toEqual(expected);
  });

  it('returns null when the line states no quantity', () => {
    expect(parseThreshold('buyers seem interested')).toBeNull();
  });
});

describe('checkSuggestedTest', () => {
  it('accepts a coherent test', () => {
    expect(checkSuggestedTest(base)).toBeNull();
  });

  it('rejects one test that measures two different windows', () => {
    // Real output: the hypothesis said 7 days while both bands said 14.
    const problem = checkSuggestedTest({
      ...base,
      hypothesis: 'At least 18% will click through within 7 days.',
      passThreshold: '>=18% click-through within 14 days',
      failThreshold: '<=6% click-through within 14 days',
      measurementWindow: '14 days',
    });

    expect(problem?.code).toBe('CONCEPT_TEST_WINDOW_INCONSISTENT');
    expect(problem?.detail).toMatch(/7d/);
  });

  it('accepts a test whose single window is repeated across its fields', () => {
    expect(checkSuggestedTest({
      ...base,
      hypothesis: 'Buyers click through within 2 weeks.',
      passThreshold: '>=18% within 14 days',
      failThreshold: '<=6% within 14 days',
      measurementWindow: '14 days',
    })).toBeNull();
  });

  it('rejects an inverted pass/fail pair', () => {
    const problem = checkSuggestedTest({
      ...base,
      passThreshold: '>=6% click-through',
      failThreshold: '<=18% click-through',
    });

    expect(problem?.code).toBe('CONCEPT_TEST_BANDS_INVERTED');
  });

  it('rejects an equal pass/fail pair, which leaves no readable result', () => {
    expect(checkSuggestedTest({
      ...base,
      passThreshold: '>=10% click-through',
      failThreshold: '<=10% click-through',
    })?.code).toBe('CONCEPT_TEST_BANDS_INVERTED');
  });

  it('keeps the deliberate inconclusive gap between the bands', () => {
    expect(checkSuggestedTest({
      ...base,
      passThreshold: '>=18% click-through',
      failThreshold: '<=6% click-through',
    })).toBeNull();
  });

  it('does not compare a percentage against a raw count', () => {
    // Different units are not on the same scale; guessing would produce false rejections.
    expect(checkSuggestedTest({
      ...base,
      passThreshold: '>=8% of contacted',
      failThreshold: 'fewer than 20 responses',
    })).toBeNull();
  });

  it('flags a booked-call bar cold outreach cannot reach', () => {
    // Real output: ">=30% request a paid pilot/book a call within 6 weeks".
    const problem = checkSuggestedTest({
      ...base,
      method: 'BOOKED_CALL',
      passThreshold: '>=30% request a paid pilot within 6 weeks',
      failThreshold: '<=10% request a paid pilot within 6 weeks',
      measurementWindow: '6 weeks',
      hypothesis: 'Clinics will pay for a subscription.',
    });

    expect(problem?.code).toBe('CONCEPT_TEST_THRESHOLD_IMPLAUSIBLE');
    expect(problem?.detail).toMatch(/30%/);
  });

  it('leaves the same bar alone on the final attempt', () => {
    // Advisory: a heuristic must cost a retry, never block a paid generation outright.
    expect(checkSuggestedTest({
      ...base,
      method: 'BOOKED_CALL',
      passThreshold: '>=30% request a paid pilot within 6 weeks',
      failThreshold: '<=10% request a paid pilot within 6 weeks',
      measurementWindow: '6 weeks',
      hypothesis: 'Clinics will pay for a subscription.',
    }, false)).toBeNull();
  });

  it('leaves an absolute commitment count alone whatever its size', () => {
    // "12 booked pilots" is a scope call, not a conversion-rate error.
    expect(checkSuggestedTest({
      ...base,
      method: 'BOOKED_CALL',
      passThreshold: 'At least 12 paid pilot signups within 30 days',
      failThreshold: 'fewer than 4 paid pilot signups within 30 days',
      measurementWindow: '30 days',
      hypothesis: 'Coaches will pay for a pilot.',
    })).toBeNull();
  });

  it('leaves a high bar alone for a method that is not a commitment ask', () => {
    // 30% click-through on an in-page module is ambitious but not impossible.
    expect(checkSuggestedTest({
      ...base,
      method: 'CTA_SMOKE_TEST',
      passThreshold: '>=30% click-through',
    })).toBeNull();
  });

  it('pins the ceiling that decides which bars are implausible', () => {
    // A judgement, not a fact — changing it should be a deliberate, visible edit.
    expect(SALES_CONVERSION_CEILING_PCT).toBe(25);
  });
});

describe('offer durations are not measurement windows', () => {
  // REGRESSION: "explore directions" hard-failed with CONCEPT_TEST_WINDOW_INCONSISTENT
  // because a duration being SOLD ("a 3-month pilot") was counted as a competing window
  // against the one the test is read over ("in 30 days"). Both are correct together.
  const sold = [
    ['At least 12 paid 3-month pilots in 30 days', [30]],
    ['>=5 users start a 14-day trial in the first 30 days', [30]],
    ['At least 8 of 40 request a 3-month pilot', []],
    ['Fewer than 2 clinics sign a 12-month contract', []],
  ] as const;

  it.each(sold)('reads only the measurement window from %j', (text, expected) => {
    expect(timeWindowsInDays(text, 'measurement')).toEqual([...expected]);
  });

  it('still counts every duration in the measurementWindow field itself', () => {
    expect(timeWindowsInDays('30 days')).toEqual([30]);
    expect(timeWindowsInDays('a 30-day window')).toEqual([30]);
  });

  it('accepts a test that sells a 3-month pilot inside a 30-day window', () => {
    expect(checkSuggestedTest({
      hypothesis: 'Contacted clinics will request a paid pilot.',
      method: 'BOOKED_CALL',
      passThreshold: 'At least 4 of 40 clinics request a 3-month pilot',
      failThreshold: 'Fewer than 1 of 40 clinics requests a pilot',
      measurementWindow: '30 days',
    })).toBeNull();
  });

  it('still catches a genuinely inconsistent window', () => {
    const problem = checkSuggestedTest({
      hypothesis: 'Buyers respond within 14 days.',
      method: 'BOOKED_CALL',
      passThreshold: 'At least 3 of 40 book',
      failThreshold: 'Zero of 40 book',
      measurementWindow: '7 days',
    });
    expect(problem?.code).toBe('CONCEPT_TEST_WINDOW_INCONSISTENT');
  });

  it('keeps a genuinely inconsistent window hard-failing on every attempt', () => {
    // Mechanical, not a judgement call: two windows make the result unreadable however
    // many attempts remain. Only the funnel-plausibility check is advisory.
    const inconsistent = {
      hypothesis: 'Buyers respond within 14 days.',
      method: 'BOOKED_CALL',
      passThreshold: 'At least 3 of 40 book',
      failThreshold: 'Zero of 40 book',
      measurementWindow: '7 days',
    };
    expect(checkSuggestedTest(inconsistent, true)?.code).toBe('CONCEPT_TEST_WINDOW_INCONSISTENT');
    expect(checkSuggestedTest(inconsistent, false)?.code).toBe('CONCEPT_TEST_WINDOW_INCONSISTENT');
  });

  it('keeps inverted bands hard-failing on every attempt — that is broken arithmetic', () => {
    const inverted = {
      hypothesis: 'Buyers convert.',
      method: 'BOOKED_CALL',
      passThreshold: 'At least 2 of 40 book',
      failThreshold: 'Fewer than 5 of 40 book',
      measurementWindow: '30 days',
    };
    expect(checkSuggestedTest(inverted, false)?.code).toBe('CONCEPT_TEST_BANDS_INVERTED');
  });
});

describe('written-out zero in a fail bar', () => {
  // REGRESSION: "Zero of 40 book" parsed as 40 (the sample size), so a correctly ordered
  // pair — pass 3, fail 0 — read as inverted and hard-failed on every attempt. "Zero" is
  // the most natural way to write a fail bar, so this rejected good generations.
  it.each([
    ['Zero of 40 book', 0],
    ['None of the 40 clinics book', 0],
    ['Zero signups', 0],
    ['0 of 40 book', 0],
  ])('reads %j as %i', (text, value) => {
    expect(parseThreshold(text)?.value).toBe(value);
  });

  it('does not mistake "no more than N" for zero', () => {
    expect(parseThreshold('No more than 5 churn')).toMatchObject({ direction: 'at-most', value: 5 });
    expect(parseThreshold('No fewer than 8 book')).toMatchObject({ value: 8 });
  });

  it('keeps reading the numerator, not the denominator, when both are digits', () => {
    expect(parseThreshold('At least 3 of 40 book')).toMatchObject({ direction: 'at-least', value: 3 });
  });

  it('accepts pass-above-zero-fail, which is the commonest honest pair', () => {
    expect(checkSuggestedTest({
      hypothesis: 'Contacted clinics book a call.',
      method: 'BOOKED_CALL',
      passThreshold: 'At least 3 of 40 clinics book',
      failThreshold: 'Zero of 40 clinics book',
      measurementWindow: '30 days',
    }, false)).toBeNull();
  });
});
