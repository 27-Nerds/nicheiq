import { describe, expect, it } from 'vitest';
import {
  bigramSimilarity,
  canonicalizeAddressedTitles,
  normalizeTitle,
} from '../titleMatching.js';

describe('normalizeTitle', () => {
  it('lowercases', () => {
    expect(normalizeTitle('Subscription Pricing')).toBe('subscription pricing');
  });
  it('strips punctuation without inserting a separator (matches existing workers.ts behavior)', () => {
    // Hyphens collapse adjacent letters — preserved verbatim from the lifted
    // implementation. Fuzzy match (bigram) still recovers these via corrected[].
    expect(normalizeTitle('Subscription-pricing')).toBe('subscriptionpricing');
    expect(normalizeTitle('Pricing!')).toBe('pricing');
  });
  it('collapses whitespace and trims', () => {
    expect(normalizeTitle('  Subscription   pricing  ')).toBe('subscription pricing');
  });
});

describe('bigramSimilarity', () => {
  it('returns 1 for identical strings', () => {
    expect(bigramSimilarity('subscription pricing', 'subscription pricing')).toBe(1);
  });
  it('returns 0 for entirely disjoint strings', () => {
    expect(bigramSimilarity('xyz', 'abc')).toBe(0);
  });
  it('produces a high score for near-matches', () => {
    const score = bigramSimilarity('subscription pricing', 'subscription pricing models');
    expect(score).toBeGreaterThan(0.7);
  });
});

describe('canonicalizeAddressedTitles', () => {
  const pains = [
    { title: 'Subscription pricing' },
    { title: 'Onboarding friction' },
    { title: 'Data export limitations' },
  ];

  it('passes through exact matches with no corrections', () => {
    const r = canonicalizeAddressedTitles(['Subscription pricing'], pains);
    expect(r.canonical).toEqual(['Subscription pricing']);
    expect(r.dropped).toEqual([]);
    expect(r.corrected).toEqual([]);
  });

  it('matches case drift via normalization without recording a correction', () => {
    const r = canonicalizeAddressedTitles(['subscription pricing'], pains);
    expect(r.canonical).toEqual(['Subscription pricing']);
    expect(r.corrected).toEqual([]);
  });

  it('matches punctuation drift via fuzzy bigram (recorded as a correction)', () => {
    // 'Subscription-pricing!' normalizes to 'subscriptionpricing' (no space, by
    // existing normalizeTitle behavior). Direct match fails; bigram similarity
    // against 'subscription pricing' is well above 0.7, so the fuzzy path
    // resolves it and records the correction for audit.
    const r = canonicalizeAddressedTitles(['Subscription-pricing!'], pains);
    expect(r.canonical).toEqual(['Subscription pricing']);
    expect(r.dropped).toEqual([]);
    expect(r.corrected).toHaveLength(1);
    expect(r.corrected[0].canonical).toBe('Subscription pricing');
  });

  it('matches whitespace drift via normalization', () => {
    const r = canonicalizeAddressedTitles(['  Subscription   pricing  '], pains);
    expect(r.canonical).toEqual(['Subscription pricing']);
    expect(r.corrected).toEqual([]);
  });

  it('records a fuzzy correction when normalized form differs but bigram >= threshold', () => {
    const r = canonicalizeAddressedTitles(['Subscription pricing models'], pains);
    expect(r.canonical).toEqual(['Subscription pricing']);
    expect(r.dropped).toEqual([]);
    expect(r.corrected).toHaveLength(1);
    expect(r.corrected[0]).toMatchObject({
      original: 'Subscription pricing models',
      canonical: 'Subscription pricing',
    });
    expect(r.corrected[0].score).toBeGreaterThanOrEqual(0.7);
  });

  it('drops titles whose best bigram similarity is below threshold', () => {
    const r = canonicalizeAddressedTitles(['Quantum entanglement'], pains);
    expect(r.canonical).toEqual([]);
    expect(r.dropped).toEqual(['Quantum entanglement']);
    expect(r.corrected).toEqual([]);
  });

  it('selects the highest-scoring canonical when multiple candidates pass threshold', () => {
    const fuzzyPains = [
      { title: 'Pricing transparency' },
      { title: 'Pricing model complexity' },
    ];
    const r = canonicalizeAddressedTitles(['pricing model complexity issues'], fuzzyPains);
    expect(r.canonical).toEqual(['Pricing model complexity']);
    expect(r.corrected).toHaveLength(1);
  });

  it('dedupes resolved canonicals keep-first', () => {
    const r = canonicalizeAddressedTitles(
      ['Subscription pricing', 'subscription pricing', 'SUBSCRIPTION-PRICING'],
      pains,
    );
    expect(r.canonical).toEqual(['Subscription pricing']);
  });

  it('preserves input order across distinct canonicals', () => {
    const r = canonicalizeAddressedTitles(
      ['Onboarding friction', 'Subscription pricing'],
      pains,
    );
    expect(r.canonical).toEqual(['Onboarding friction', 'Subscription pricing']);
  });

  it('returns empty results for empty llmTitles', () => {
    const r = canonicalizeAddressedTitles([], pains);
    expect(r).toEqual({ canonical: [], dropped: [], corrected: [] });
  });

  it('drops every title when canonicalPains is empty', () => {
    const r = canonicalizeAddressedTitles(['Subscription pricing', 'Other'], []);
    expect(r.canonical).toEqual([]);
    expect(r.dropped).toEqual(['Subscription pricing', 'Other']);
    expect(r.corrected).toEqual([]);
  });

  it('ignores malformed canonical entries gracefully', () => {
    const malformed = [
      { title: 'Real pain' },
      { title: 123 as unknown },
      { title: null as unknown },
      {},
      null as unknown as { title?: unknown },
    ];
    const r = canonicalizeAddressedTitles(['Real pain'], malformed);
    expect(r.canonical).toEqual(['Real pain']);
    expect(r.dropped).toEqual([]);
  });

  it('skips non-string and empty llmTitles entries', () => {
    const r = canonicalizeAddressedTitles(
      ['Subscription pricing', '', 42 as unknown as string, null as unknown as string],
      pains,
    );
    expect(r.canonical).toEqual(['Subscription pricing']);
    expect(r.dropped).toEqual([]);
  });
});
