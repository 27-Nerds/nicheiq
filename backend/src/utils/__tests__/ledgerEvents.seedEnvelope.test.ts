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
      },
      outcome: 'accepted',
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
