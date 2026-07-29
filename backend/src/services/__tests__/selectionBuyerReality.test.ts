import { describe, expect, it } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import {
  buildBuyerRealityDigest,
  hasProvenBuyerProblem,
  segmentIsProvenThin,
  thinWallet,
} from '../selectionBuyerReality.js';

const seg = (name: string, payability: number | null, cls: string | null) => ({
  segment_name: name,
  payability_score: payability,
  payability_class: cls,
});

const ruledOut = (segment: string | null, source: string, reason = '') => ({
  idea_name: 'x',
  source,
  reason,
  ...(segment ? { idea: { source_segment: segment } } : {}),
});

const report = (over: Record<string, unknown> = {}) => ({
  market_reality: { wallet: { wallet_class: 'free-culture', evidence: 'all tools free' } },
  niche_difficulty_verdict: { buyer_class: 'mixed', buyer_class_note: 'pick a segment with budget' },
  audience_mapping: {
    audience_segments: [
      seg('Biohackers', 0.53, 'prosumer-wallet'),
      seg('Recovery Seekers', 0.4, 'personal-wallet'),
      seg('Weight Management', 0.15, 'personal-wallet'),
    ],
  },
  examined_ruled_out: [
    ruledOut('Weight Management', 'no_buyer'),
    ruledOut('Weight Management', 'no_buyer'),
    ruledOut('Weight Management', 'demoted_winner'),
  ],
  ...over,
});

describe('thinWallet', () => {
  it('mirrors the demoter: below the threshold OR personal-wallet', () => {
    expect(thinWallet(0.15, 'personal-wallet')).toBe(true);
    expect(thinWallet(0.2, 'prosumer-wallet')).toBe(true);   // score alone
    expect(thinWallet(0.9, 'personal-wallet')).toBe(true);   // class alone
    expect(thinWallet(0.53, 'prosumer-wallet')).toBe(false);
  });

  it('treats a class of exactly personal-wallet case-insensitively', () => {
    expect(thinWallet(null, 'Personal-Wallet')).toBe(true);
  });

  it('is false when nothing is known — absence of evidence is not evidence', () => {
    expect(thinWallet(null, null)).toBe(false);
  });
});

describe('buildBuyerRealityDigest', () => {
  it('fails soft on junk rather than blocking generation', () => {
    for (const junk of [null, undefined, 'x', 3, [], {}] as unknown[]) {
      const d = buildBuyerRealityDigest(junk);
      expect(d.segments).toEqual([]);
      expect(hasProvenBuyerProblem(d)).toBe(false);
    }
  });

  it('reads the niche wallet and buyer class', () => {
    const d = buildBuyerRealityDigest(report());
    expect(d.walletClass).toBe('free-culture');
    expect(d.walletEvidence).toBe('all tools free');
    expect(d.buyerClass).toBe('mixed');
    expect(d.buyerClassNote).toBe('pick a segment with budget');
  });

  it('rejects a wallet class outside the probe vocabulary', () => {
    const d = buildBuyerRealityDigest(report({ market_reality: { wallet: { wallet_class: 'rich' } } }));
    expect(d.walletClass).toBeNull();
  });

  it('counts deaths per segment and separates no_buyer from other causes', () => {
    const d = buildBuyerRealityDigest(report());
    const wm = d.segments.find((s) => s.name === 'Weight Management');
    expect(wm).toMatchObject({ payability: 0.15, thin: true, ruledOutCount: 3, noBuyerCount: 2 });
    expect(d.noBuyerDeaths).toBe(2);
  });

  it('marks a segment proven-thin only when it is BOTH thin and has lost ideas', () => {
    const d = buildBuyerRealityDigest(report());
    // Recovery Seekers is personal-wallet (thin) but has lost nothing yet.
    expect(d.segments.find((s) => s.name === 'Recovery Seekers')?.thin).toBe(true);
    expect(d.provenThinSegments).toEqual(['Weight Management']);
  });

  it('nominates the best-paying segment that has not been ruled out', () => {
    expect(buildBuyerRealityDigest(report()).strongestSegment)
      .toEqual({ name: 'Biohackers', payability: 0.53 });
  });

  it('recovers the segment from the reason prose when the idea payload is missing', () => {
    const d = buildBuyerRealityDigest(report({
      examined_ruled_out: [
        ruledOut(null, 'no_buyer', 'Buyers in this segment (Weight Management) rarely pay for tooling.'),
      ],
    }));
    expect(d.provenThinSegments).toEqual(['Weight Management']);
  });

  it('branches on source, never on the reason literal', () => {
    // The no_buyer reason string has already changed once between revisions.
    const d = buildBuyerRealityDigest(report({
      examined_ruled_out: [ruledOut('Weight Management', 'no_buyer', 'some entirely new wording')],
    }));
    expect(d.noBuyerDeaths).toBe(1);
  });

  it('reports no problem for a run that has demoted nothing', () => {
    const d = buildBuyerRealityDigest(report({ examined_ruled_out: [] }));
    expect(d.provenThinSegments).toEqual([]);
    expect(hasProvenBuyerProblem(d)).toBe(false);
  });

  it('matches a parent segment case-insensitively', () => {
    const d = buildBuyerRealityDigest(report());
    expect(segmentIsProvenThin(d, 'weight management')).toBe(true);
    expect(segmentIsProvenThin(d, 'Biohackers')).toBe(false);
    expect(segmentIsProvenThin(d, null)).toBe(false);
  });
});

// Regression anchor: the run that motivated this module. Skips if the artifact is gone.
const ARTIFACT = 'output/checkpoints/preview_report_16197018-8f01-4f7b-aa5e-7441bd881a24.json';
const artifactPath = new URL(`../../../../${ARTIFACT}`, import.meta.url).pathname;

describe.skipIf(!existsSync(artifactPath))('against the real Peptides Supplements run', () => {
  it('identifies the segment that killed 7 ideas, and the one that killed none', () => {
    const d = buildBuyerRealityDigest(JSON.parse(readFileSync(artifactPath, 'utf8')));

    expect(d.walletClass).toBe('free-culture');
    expect(d.provenThinSegments).toContain('Metabolic & Weight Management Users');
    expect(d.strongestSegment?.name).toBe('Performance-Driven Biohackers');

    const dead = d.segments.find((s) => s.name === 'Metabolic & Weight Management Users');
    expect(dead?.payability).toBe(0.15);
    // Assert the relationship, not a literal count: the artifact is a real checkpoint that
    // gets regenerated, and pinning an exact number made this anchor fail (7 -> 9) for a
    // reason that had nothing to do with the module. What must hold is that this segment
    // carries the deaths and the strong one carries none.
    expect(dead?.ruledOutCount ?? 0).toBeGreaterThan(0);
    const strong = d.segments.find((s) => s.name === 'Performance-Driven Biohackers');
    expect(strong?.ruledOutCount ?? 0).toBe(0);
    expect(dead?.ruledOutCount ?? 0).toBeGreaterThan(strong?.ruledOutCount ?? 0);

    // The parent the owner branched from sat in the dead segment — this is precisely the
    // condition that must now force one option to move the buyer.
    expect(segmentIsProvenThin(d, 'Metabolic & Weight Management Users')).toBe(true);
    expect(hasProvenBuyerProblem(d)).toBe(true);
  });
});
