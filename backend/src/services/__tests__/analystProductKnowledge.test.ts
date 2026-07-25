import { describe, expect, it } from 'vitest';
import {
  ANALYST_PRODUCT_KNOWLEDGE,
  buildAnalystProductKnowledge,
} from '../analystProductKnowledge.js';

describe('ANALYST_PRODUCT_KNOWLEDGE', () => {
  it('describes the workflow, research foundations, and comparison boundary', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Discovery frames the niche');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Dozens of narrow specialist roles');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Self-Consistency');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Chain-of-Verification');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('SemDeDup');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Never say NicheIQ is objectively better overall');
  });

  it('is the fully granted composition', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toBe(buildAnalystProductKnowledge(true));
  });

  it('documents the selection workspace without conflating it with the post-report Decision Lab', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('THE SELECTION WORKSPACE');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Choosing one to three candidates is the ONLY required step');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Plan a test is a contextual follow-up');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('One confirmed run covers the exact selected shortlist');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('THE POST-RESEARCH DECISION LAB');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Do not use this name for the pre-purchase selection workspace');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('never alter Discovery scores');
    expect(ANALYST_PRODUCT_KNOWLEDGE).not.toContain('which one to two');
    expect(ANALYST_PRODUCT_KNOWLEDGE).not.toContain('Concept Forge');
  });

  it('keeps the Decision Lab copy free of em and en dashes', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).not.toMatch(/[–—]/);
  });

  it('preserves stage-scoped mutation boundaries', () => {
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('only propose changes supported by the current checkpoint');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('captured research findings and report artifacts are read-only');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Decision Lab may write a separate owner-judgment and handoff layer');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('never edits the findings, scores, or report verdict');
    expect(ANALYST_PRODUCT_KNOWLEDGE).toContain('Never imply that chat can bypass those boundaries');
  });
});

describe('buildAnalystProductKnowledge(false)', () => {
  const trimmed = buildAnalystProductKnowledge(false);

  it('keeps the required path and the durable product context', () => {
    expect(trimmed).toContain('Discovery frames the niche');
    expect(trimmed).toContain('THE SELECTION WORKSPACE');
    expect(trimmed).toContain('Choose ideas, Compare trade-offs, then Review and start');
    expect(trimmed).toContain('Choosing one to three candidates is the ONLY required step');
    expect(trimmed).toContain('One confirmed run covers the exact selected shortlist');
    expect(trimmed).toContain('Dozens of narrow specialist roles');
    expect(trimmed).toContain('Self-Consistency');
    expect(trimmed).toContain('captured research findings and report artifacts are read-only');
    expect(trimmed).toContain('Never imply that chat can bypass those boundaries');
  });

  it('names none of the gated tools, so the analyst cannot recommend one', () => {
    for (const phrase of [
      'THE OPTIONAL SELECTION CHECKS',
      'THE POST-RESEARCH DECISION LAB',
      'Decision Lab',
      'Build limits',
      'Check the evidence',
      'Things to prove',
      'Plan a test',
      'Branch a new direction',
      'Fit analysis',
    ]) {
      expect(trimmed).not.toContain(phrase);
    }
  });

  it('still avoids em and en dashes', () => {
    expect(trimmed).not.toMatch(/[\u2013\u2014]/);
  });
});
