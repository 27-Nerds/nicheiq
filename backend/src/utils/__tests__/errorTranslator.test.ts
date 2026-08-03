import { describe, expect, it } from 'vitest';

import { translateError } from '../errorTranslator.js';


describe('translateError provider billing', () => {
  it('gives an actionable service-account message for exhausted provider credits', () => {
    const translated = translateError(
      'PROVIDER_BILLING_ERROR',
      'OpenRouter HTTP 402: insufficient provider credits',
    );

    expect(translated).toEqual(expect.objectContaining({
      code: 'PROVIDER_BILLING_ERROR',
      severity: 'error',
      userMessage: 'Research provider account unavailable',
    }));
    expect(translated.actionableGuidance).toContain('progress is saved');
    expect(translated.actionableGuidance).toContain('contact support');
  });
});
