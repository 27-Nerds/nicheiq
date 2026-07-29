import { describe, expect, it } from 'vitest';
import {
  buildRegenerationEnvelope,
  buildRegenerationReceiptContent,
} from '../ledgerEvents.js';

describe('additional-batch ledger envelopes', () => {
  it('keys submitted and settled receipts to the same dispatch operation', () => {
    const submitted = buildRegenerationEnvelope({
      event: 'regeneration_submitted',
      operationId: 'dispatch-1',
      ordinal: 2,
      focus: 'novelty',
    });
    const settled = buildRegenerationEnvelope({
      event: 'regeneration_settled',
      operationId: 'dispatch-1',
      ordinal: 2,
      outcome: 'completed',
      generatedCount: 4,
      addedIdeaIds: ['idea-a', 'idea-b'],
      addedIdeas: [
        { ideaId: 'idea-a', ideaRevision: 2 },
        { ideaId: 'idea-b', ideaRevision: 1 },
      ],
      refPrecision: 'exact',
      ruledOutCount: 2,
      refunded: false,
    });

    expect(submitted).toMatchObject({
      event: 'regeneration_submitted',
      operationId: 'dispatch-1',
      batch: { ordinal: 2, focus: 'novelty' },
    });
    expect(settled).toMatchObject({
      event: 'regeneration_settled',
      operationId: 'dispatch-1',
      batch: {
        outcome: 'completed',
        generatedCount: 4,
        addedCount: 2,
        addedIdeaIds: ['idea-a', 'idea-b'],
        addedIdeas: [
          { ideaId: 'idea-a', ideaRevision: 2 },
          { ideaId: 'idea-b', ideaRevision: 1 },
        ],
        refPrecision: 'exact',
        ruledOutCount: 2,
        refunded: false,
      },
    });
  });

  it('describes a successful zero-addition batch without implying failure', () => {
    expect(
      buildRegenerationReceiptContent(
        'regeneration_settled',
        'no_candidates_added',
        0,
      ),
    ).toMatch(/no new candidates/i);
  });
});
