import { describe, expect, it } from 'vitest';
import { ANALYST_PRODUCT_KNOWLEDGE } from '../analystProductKnowledge.js';

describe('ANALYST_PRODUCT_KNOWLEDGE', () => {
  it('describes the workflow, research foundations, and comparison boundary', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Discovery frames the niche');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Dozens of narrow specialist roles');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Self-Consistency');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Chain-of-Verification');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('SemDeDup');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Never say NicheIQ is objectively better overall');
  });

  it('preserves stage-scoped mutation boundaries', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('only propose changes supported by the current checkpoint');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('completed reports are read-only');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('never imply that chat can bypass those boundaries');
  });
});
