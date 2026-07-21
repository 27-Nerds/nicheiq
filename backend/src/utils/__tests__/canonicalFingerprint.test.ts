import { describe, expect, it } from 'vitest';
import { canonicalizeJson, canonicalJsonSha256 } from '../canonicalFingerprint.js';

describe('canonical selection fingerprints', () => {
  it('orders nested object keys without changing array order', () => {
    const left = { z: 1, a: { y: 2, x: [3, null] } };
    const right = { a: { x: [3, null], y: 2 }, z: 1 };

    expect(canonicalizeJson(left)).toEqual(right);
    expect(canonicalJsonSha256(left)).toBe(
      'bbf3287411a9524e660c289f319e31e7f23327e3cf36a4d834e41e018b8ae082',
    );
    expect(canonicalJsonSha256(right)).toBe(canonicalJsonSha256(left));
  });

  it('freezes the existing JSON semantics for undefined values', () => {
    expect(canonicalJsonSha256({ a: undefined, b: 1 })).toBe(
      'eb8ed3ccb5023093b56f490a46501e88d09736687e609fdbc1c71b3df8b9ccd3',
    );
    expect(canonicalJsonSha256([undefined, 1])).toBe(
      'a6336ae0a33a235e9cca062e513b1dd5583b938f2dbaba32d71383377eb2b523',
    );
  });
});
