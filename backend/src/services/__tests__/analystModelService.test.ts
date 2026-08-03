import { beforeEach, describe, expect, it, vi } from 'vitest';

const { findSetting } = vi.hoisted(() => ({ findSetting: vi.fn() }));

vi.mock('../db.js', () => ({
  prisma: { appSettings: { findUnique: findSetting } },
}));

vi.mock('../../config.js', () => ({
  CONFIG: { chatModel: 'gpt-5-mini' },
}));

import {
  ANALYST_MODEL_OPTIONS,
  estimateAnalystCostUsd,
  normalizeAnalystUsage,
  resolveAnalystModel,
} from '../analystModelService.js';

describe('analyst model configuration', () => {
  beforeEach(() => vi.clearAllMocks());

  it('exposes gpt-5.6-luna with the configured cache-aware rates', () => {
    expect(ANALYST_MODEL_OPTIONS.find((option) => option.id === 'gpt-5.6-luna')).toEqual({
      id: 'gpt-5.6-luna',
      pricing: { input: 0.2, output: 1.2, cacheWrite: 0.25, cacheRead: 0.02 },
    });
  });

  it('uses the deployment default when no admin override exists', async () => {
    findSetting.mockResolvedValue(null);
    await expect(resolveAnalystModel()).resolves.toBe('gpt-5-mini');
  });

  it('uses a supported override and rejects an unsupported persisted value', async () => {
    findSetting.mockResolvedValueOnce({ value: 'gpt-5.6-luna' });
    await expect(resolveAnalystModel()).resolves.toBe('gpt-5.6-luna');

    findSetting.mockResolvedValueOnce({ value: 'unknown-model' });
    await expect(resolveAnalystModel()).resolves.toBe('gpt-5-mini');
  });

  it('separates cache tokens and prices all four luna usage classes', () => {
    const usage = normalizeAnalystUsage({
      prompt_tokens: 1_000_000,
      completion_tokens: 1_000_000,
      prompt_tokens_details: { cached_tokens: 200_000, cache_write_tokens: 100_000 },
    });
    expect(usage).toEqual({
      inputTokens: 700_000,
      outputTokens: 1_000_000,
      cacheWriteTokens: 100_000,
      cacheReadTokens: 200_000,
    });
    expect(estimateAnalystCostUsd('gpt-5.6-luna', usage)).toBeCloseTo(1.369, 8);
    expect(estimateAnalystCostUsd('openrouter/openai/gpt-5.6-luna', usage)).toBeCloseTo(1.369, 8);
  });
});
