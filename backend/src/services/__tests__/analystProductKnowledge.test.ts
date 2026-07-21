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

  it('documents the Decision Lab, its tools, and their costs', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('THE DECISION LAB');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Shortlisting one to three candidates is the ONLY required step');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Stress-test evidence');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Shape:');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('never alter research scores');
    // "Concept Forge" was retired from user-facing copy; it must not resurface here.
    expect(ANALYST_PRODUCT_KNOWLEDGE).not.toContain('Concept Forge');
  });

  it('keeps the Decision Lab copy free of em and en dashes', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).not.toMatch(/[–—]/);
  });

  it('preserves stage-scoped mutation boundaries', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('only propose changes supported by the current checkpoint');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('completed reports are read-only');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('never imply that chat can bypass those boundaries');
  });
});
