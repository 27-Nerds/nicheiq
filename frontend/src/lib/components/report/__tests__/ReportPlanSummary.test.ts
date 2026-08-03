import { describe, it, expect } from 'vitest';
import { formatBuyingTrigger, formatPersonaIntro } from '../ReportPlanSummary.svelte';

describe('formatBuyingTrigger', () => {
  it('drops the lead-in when the backend copy already opens with a trigger clause', () => {
    const raw =
      'Triggered when a versus-deal settlement dispute arises over house-nut deductions.';

    expect(formatBuyingTrigger(raw)).toBe(raw);
    expect(formatBuyingTrigger(raw)).not.toContain('Their buying trigger is Triggered');
  });

  it('handles other trigger-clause openers', () => {
    expect(formatBuyingTrigger('When the quarterly audit fails.')).toBe(
      'When the quarterly audit fails.'
    );
    expect(formatBuyingTrigger('after a payout conflict')).toBe(
      'After a payout conflict.'
    );
  });

  it('adds the lead-in for a bare noun-phrase trigger', () => {
    expect(formatBuyingTrigger('Budget approval for new tooling')).toBe(
      'Their buying trigger is budget approval for new tooling.'
    );
  });

  it('leaves acronyms and camel-cased names capitalised in the lead-in form', () => {
    expect(formatBuyingTrigger('SOC2 audit deadline')).toBe(
      'Their buying trigger is SOC2 audit deadline.'
    );
    expect(formatBuyingTrigger('QuickBooks migration')).toBe(
      'Their buying trigger is QuickBooks migration.'
    );
  });

  it('returns an empty string for missing or blank values', () => {
    expect(formatBuyingTrigger(undefined)).toBe('');
    expect(formatBuyingTrigger(null)).toBe('');
    expect(formatBuyingTrigger('   ')).toBe('');
  });
});

describe('formatPersonaIntro', () => {
  it('introduces the persona with its ICP descriptor', () => {
    expect(
      formatPersonaIntro(
        'Multi-Room Operator Maya',
        '35-55 year old independent venue owners and general managers'
      )
    ).toBe(
      'Start with Multi-Room Operator Maya — 35-55 year old independent venue owners and general managers.'
    );
  });

  it('keeps existing terminal punctuation', () => {
    expect(formatPersonaIntro('Maya', 'Independent venue owners.')).toBe(
      'Start with Maya — independent venue owners.'
    );
  });

  it('falls back to the bare name when no descriptor exists', () => {
    expect(formatPersonaIntro('Maya', null)).toBe('Start with Maya.');
    expect(formatPersonaIntro('Maya')).toBe('Start with Maya.');
  });

  it('returns an empty string without a persona name', () => {
    expect(formatPersonaIntro('', 'Independent venue owners')).toBe('');
  });
});
