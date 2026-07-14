import { describe, it, expect } from 'vitest';
import { assessPoolHealth } from '../poolHealth.js';

describe('assessPoolHealth', () => {
  it('is weak when wallet is free-culture and no idea clears the market-fit bar', () => {
    const result = assessPoolHealth({ wallet_class: 'free-culture', max_visible_mf: 0.45 });
    expect(result.weak).toBe(true);
    expect(result.advisoryLine).toContain("don't recommend spending Deep Research credits here");
  });

  it('is healthy when wallet is paying, even with a low market fit', () => {
    const result = assessPoolHealth({ wallet_class: 'paying', max_visible_mf: 0.3 });
    expect(result.weak).toBe(false);
    expect(result.advisoryLine).toBeNull();
  });

  it('is healthy when a candidate clears the market-fit bar, even with a free-culture wallet', () => {
    const result = assessPoolHealth({ wallet_class: 'free-culture', max_visible_mf: 0.75 });
    expect(result.weak).toBe(false);
    expect(result.advisoryLine).toBeNull();
  });

  it('is healthy when the market fit is exactly at the ceiling (not strictly below)', () => {
    const result = assessPoolHealth({ wallet_class: 'free-culture', max_visible_mf: 0.6 });
    expect(result.weak).toBe(false);
  });

  it('treats a missing/null wallet_class or max_visible_mf as healthy (fail-soft)', () => {
    expect(assessPoolHealth({}).weak).toBe(false);
    expect(assessPoolHealth({ wallet_class: 'free-culture' }).weak).toBe(false);
    expect(assessPoolHealth({ max_visible_mf: 0.1 }).weak).toBe(false);
  });

  it('is case-insensitive on wallet_class', () => {
    const result = assessPoolHealth({ wallet_class: 'FREE-CULTURE', max_visible_mf: 0.2 });
    expect(result.weak).toBe(true);
  });

  it('strengthens the advisory wording when difficulty is high, without being required to fire', () => {
    const high = assessPoolHealth({ wallet_class: 'free-culture', max_visible_mf: 0.2, difficulty_level: 'high' });
    const base = assessPoolHealth({ wallet_class: 'free-culture', max_visible_mf: 0.2 });
    expect(high.weak).toBe(true);
    expect(high.advisoryLine).not.toEqual(base.advisoryLine);
    expect(high.advisoryLine).toContain(base.advisoryLine as string);
  });

  it('does not require high difficulty to fire the weak verdict', () => {
    const result = assessPoolHealth({ wallet_class: 'free-culture', max_visible_mf: 0.2, difficulty_level: 'low' });
    expect(result.weak).toBe(true);
  });
});
