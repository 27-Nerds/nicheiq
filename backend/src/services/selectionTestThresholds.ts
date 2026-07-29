/**
 * Consistency checks for a Concept Forge option's `suggestedTest`.
 *
 * `passThreshold`, `failThreshold`, `hypothesis` and `measurementWindow` are all free
 * text (`z.string().min(3).max(500)`), validated against nothing. Two live runs produced:
 *
 *   - a hypothesis measured "within 7 days" whose pass/fail bands both said "within
 *     14 days" — one test, two windows;
 *   - "at least 12 paid 3-month pilots in 30 days" and ">=30% of contacted clinics
 *     request a paid pilot" as *cheapest useful tests*. Cold outbound to a PAID
 *     commitment runs low single digits, so those bars fail a good idea by construction.
 *
 * The first two checks below are mechanical. The third is a judgement call about funnel
 * reality, so it is deliberately advisory — see `SALES_CONVERSION_CEILING_PCT`.
 */

const DAYS_PER_UNIT: Record<string, number> = {
  day: 1, days: 1,
  week: 7, weeks: 7,
  fortnight: 14, fortnights: 14,
  month: 30, months: 30,
  quarter: 91, quarters: 91,
};

/**
 * Durations introduced by a temporal preposition — "in 30 days", "within a 14-day
 * window", "over the first quarter". These are the ones that say WHEN the test is read.
 *
 * Up to three filler words are allowed between the preposition and the number so
 * "in the first 30 days" and "over a 30-day window" both match.
 */
const MEASUREMENT_LEAD = /\b(?:in|within|over|during|across|after|by|for)\b(?:\s+\w+){0,3}\s*$/i;

/**
 * Every time window named in a text, normalized to days. "a 30-day window" → [30].
 *
 * @param mode `'all'` counts every duration. `'measurement'` counts only durations
 *   introduced by a temporal preposition, which is how English separates the window a
 *   result is read over ("...in 30 days") from a duration that is part of the OFFER
 *   ("a 3-month pilot", "a 14-day trial"). Both can appear in one honest threshold —
 *   "12 paid 3-month pilots in 30 days" names one product and one window, not two
 *   windows — so counting them together made a correct test look self-contradictory.
 */
export function timeWindowsInDays(text: string, mode: 'all' | 'measurement' = 'all'): number[] {
  const windows: number[] = [];
  const pattern = /(\d+(?:\.\d+)?)\s*[-‐-―]?\s*(day|days|week|weeks|fortnight|fortnights|month|months|quarter|quarters)\b/gi;
  for (const match of text.matchAll(pattern)) {
    const value = Number(match[1]);
    const perUnit = DAYS_PER_UNIT[match[2].toLowerCase()];
    if (!Number.isFinite(value) || !perUnit) continue;
    if (mode === 'measurement' && !MEASUREMENT_LEAD.test(text.slice(0, match.index ?? 0))) continue;
    windows.push(value * perUnit);
  }
  return windows;
}

export interface ThresholdValue {
  /** Comparator direction as written: 'at-least' for >=/at least, 'at-most' for <=/under. */
  direction: 'at-least' | 'at-most' | null;
  value: number;
  unit: 'percent' | 'count';
}

const AT_LEAST = /(?:>=|≥|at\s+least|minimum\s+of|no\s+fewer\s+than)/i;
const AT_MOST = /(?:<=|≤|<|at\s+most|fewer\s+than|less\s+than|under|no\s+more\s+than)/i;

/** The leading quantity of a threshold line. Returns null when it states no number. */
export function parseThreshold(text: string): ThresholdValue | null {
  const match = text.match(/(\d+(?:\.\d+)?)\s*(%|percent)?/i);
  // "Zero of 40 book" — the only digits are the SAMPLE SIZE, so reading the first number
  // returns 40 and makes a perfectly ordered pair look inverted (pass 3 <= fail 40).
  // "zero" and "none" are the most natural way to write a fail bar, so this fired often.
  // Matched only as standalone words: "no more than 5" must stay AT_MOST 5, not 0.
  const zeroWord = /\b(?:zero|none)\b/i.exec(text);
  if (zeroWord && (!match || (match.index ?? 0) > zeroWord.index)) {
    return { direction: null, value: 0, unit: /%|percent/i.test(text) ? 'percent' : 'count' };
  }
  if (!match) return null;
  const value = Number(match[1]);
  if (!Number.isFinite(value)) return null;
  const before = text.slice(0, match.index ?? 0);
  // `>` alone must not be read as `<`; test AT_MOST first only on its own tokens.
  const direction = AT_MOST.test(before)
    ? 'at-most'
    : AT_LEAST.test(before) || /(?:>|>)/.test(before)
      ? 'at-least'
      : null;
  return { direction, value, unit: match[2] ? 'percent' : 'count' };
}

/**
 * Pass thresholds above this, for a method whose signal is a paid or booked commitment,
 * are treated as mis-calibrated. Cold outbound to a booked call is typically 1-5%; to a
 * PAID pilot lower still. Even a warm, referred list rarely clears 15% to a paid
 * commitment, so 25 only trips on bars that would fail a good idea by construction.
 *
 * Advisory, not a fact about your funnel: `checkSuggestedTest` only enforces it on a
 * non-final attempt, so it costs one retry and never blocks a generation. Lower it to
 * ~15 to also catch the ">=20% sign an NDA and request a paid pilot" shape.
 */
export const SALES_CONVERSION_CEILING_PCT = 25;

const COMMITMENT_METHODS = new Set(['BOOKED_CALL', 'PREORDER', 'CONCIERGE']);

export interface SuggestedTestLike {
  hypothesis: string;
  method: string;
  passThreshold: string;
  failThreshold: string;
  measurementWindow: string;
}

export type TestThresholdCode =
  | 'CONCEPT_TEST_WINDOW_INCONSISTENT'
  | 'CONCEPT_TEST_BANDS_INVERTED'
  | 'CONCEPT_TEST_THRESHOLD_IMPLAUSIBLE';

export interface TestThresholdProblem {
  code: TestThresholdCode;
  detail: string;
}

/**
 * @param advisory when false, the judgement-based plausibility check is skipped. Pass
 *   false on the final attempt so a stubborn model still ships rather than hard-failing
 *   the user's paid generation over a heuristic.
 */
export function checkSuggestedTest(
  test: SuggestedTestLike,
  advisory = true,
): TestThresholdProblem | null {
  // 1. One test, one window. `measurementWindow` is the field for it, so every duration
  //    there counts; elsewhere only prepositional durations do, or a "3-month pilot"
  //    sold within a 30-day test reads as two conflicting windows.
  const windows = new Set([
    ...timeWindowsInDays(test.measurementWindow),
    ...timeWindowsInDays(test.passThreshold, 'measurement'),
    ...timeWindowsInDays(test.failThreshold, 'measurement'),
    ...timeWindowsInDays(test.hypothesis, 'measurement'),
  ]);
  if (windows.size > 1) {
    return {
      code: 'CONCEPT_TEST_WINDOW_INCONSISTENT',
      detail: `windows disagree: ${[...windows].sort((a, b) => a - b).join('d, ')}d`,
    };
  }

  const pass = parseThreshold(test.passThreshold);
  const fail = parseThreshold(test.failThreshold);

  // 2. Pass must actually sit above fail. The gap between them is the deliberate
  //    inconclusive zone; an inverted or equal pair makes the test unreadable.
  if (pass && fail && pass.unit === fail.unit && pass.value <= fail.value) {
    return {
      code: 'CONCEPT_TEST_BANDS_INVERTED',
      detail: `pass ${pass.value} is not above fail ${fail.value}`,
    };
  }

  // 3. Judgement, not arithmetic — advisory only.
  if (
    advisory
    && pass?.unit === 'percent'
    && pass.direction !== 'at-most'
    && COMMITMENT_METHODS.has(test.method)
    && pass.value >= SALES_CONVERSION_CEILING_PCT
  ) {
    return {
      code: 'CONCEPT_TEST_THRESHOLD_IMPLAUSIBLE',
      detail: `${test.method} pass bar at ${pass.value}% of contacted`,
    };
  }

  return null;
}
