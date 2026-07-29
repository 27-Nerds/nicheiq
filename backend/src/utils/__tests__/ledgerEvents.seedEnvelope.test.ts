/**
 * buildSeedEnvelope / buildSeedReceiptContent (plans/eager-meandering-feather.md Phase 5/6) —
 * the durable seed_submitted/seed_settled receipt shape the frontend's chatLedger store reads
 * (frontend/src/lib/api.ts LedgerEventEnvelope, read-only against this contract).
 */
import { describe, it, expect } from 'vitest';
import { buildSeedEnvelope, buildSeedReceiptContent } from '../ledgerEvents.js';

describe('buildSeedEnvelope', () => {
  it('builds a seed_submitted envelope carrying the required sourceMessageId, empty patch/rows, no outcome', () => {
    const envelope = buildSeedEnvelope('seed_submitted', 'msg-abc');

    expect(envelope).toEqual({
      kind: 'ledger_event',
      version: 1,
      event: 'seed_submitted',
      patch: {},
      rows: [],
      sourceMessageId: 'msg-abc',
    });
  });

  it('builds a seed_settled envelope carrying the outcome and compact evaluated result', () => {
    const envelope = buildSeedEnvelope('seed_settled', 'msg-abc', 'accepted', {
      solution_name: 'PatchZero',
      short_description: 'Finds missed esports reporting leads.',
      market_fit_score: 0.45,
      idea_id: 'idea-child',
      idea_revision: 1,
      synthesis_operation: 'narrow',
      synthesized_from: [{
        idea_id: 'idea-parent',
        idea_revision: 3,
        solution_name: 'Signal Desk',
        contribution: 'Keep the recurring signal workflow.',
      }],
      synthesis_source_message_id: 'msg-abc',
      summary: 'Large field that should not be copied into chat history.',
    });

    expect(envelope).toEqual({
      kind: 'ledger_event',
      version: 1,
      event: 'seed_settled',
      patch: {},
      rows: [],
      sourceMessageId: 'msg-abc',
      idea: {
        solution_name: 'PatchZero',
        short_description: 'Finds missed esports reporting leads.',
        market_fit_score: 0.45,
        idea_id: 'idea-child',
        idea_revision: 1,
        synthesis_operation: 'narrow',
        synthesized_from: [{
          idea_id: 'idea-parent',
          idea_revision: 3,
          solution_name: 'Signal Desk',
          contribution: 'Keep the recurring signal workflow.',
        }],
        synthesis_source_message_id: 'msg-abc',
      },
      outcome: 'accepted',
    });
  });

  it('preserves both exact source revisions for a combined variant', () => {
    const envelope = buildSeedEnvelope('seed_settled', 'msg-combine', 'accepted', {
      solution_name: 'Agency Signal Desk',
      idea_id: 'idea-combined-child',
      idea_revision: 1,
      synthesis_operation: 'combine',
      synthesized_from: [
        {
          idea_id: 'idea-alerts',
          idea_revision: 2,
          solution_name: 'Change Monitor',
          contribution: 'Keep the alerting mechanism.',
        },
        {
          idea_id: 'idea-briefing',
          idea_revision: 4,
          solution_name: 'Briefing Desk',
          contribution: 'Keep the client-ready summary.',
        },
      ],
      synthesis_source_message_id: 'msg-combine',
    });

    expect(envelope.idea).toMatchObject({
      synthesis_operation: 'combine',
      synthesized_from: [
        { idea_id: 'idea-alerts', idea_revision: 2 },
        { idea_id: 'idea-briefing', idea_revision: 4 },
      ],
      synthesis_source_message_id: 'msg-combine',
    });
  });

  it('keeps evaluation identity, proposed title, and demotion reason in the compact result', () => {
    const envelope = buildSeedEnvelope(
      'seed_settled',
      'msg-exact',
      'demoted',
      {
        solution_name: 'Exact evaluated result',
        evaluation_id: '11111111-1111-1111-1111-111111111111',
        proposed_title: 'Exact selected direction',
        evaluation_reason: 'Demand did not clear the market-fit threshold.',
      },
      '11111111-1111-1111-1111-111111111111',
    );

    expect(envelope).toMatchObject({
      evaluationId: '11111111-1111-1111-1111-111111111111',
      sourceMessageId: 'msg-exact',
      outcome: 'demoted',
      idea: {
        evaluation_id: '11111111-1111-1111-1111-111111111111',
        proposed_title: 'Exact selected direction',
        reason: 'Demand did not clear the market-fit threshold.',
      },
    });
  });

  it.each(['accepted', 'demoted', 'failed'] as const)('threads outcome=%s through unchanged', (outcome) => {
    expect(buildSeedEnvelope('seed_settled', 'msg-abc', outcome).outcome).toBe(outcome);
  });
});

describe('buildSeedReceiptContent', () => {
  it('is chrome-only content — never empty, distinct per outcome', () => {
    expect(buildSeedReceiptContent('seed_submitted')).toMatch(/evaluat/i);
    expect(buildSeedReceiptContent('seed_settled', 'accepted')).toMatch(/ranked candidates/i);
    expect(buildSeedReceiptContent('seed_settled', 'demoted')).toMatch(/market-fit/i);
    expect(buildSeedReceiptContent('seed_settled', 'failed')).toMatch(/refund/i);
  });
});
