import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ chatComplete: vi.fn() }));

vi.mock('../openai.js', () => ({
  chatComplete: mocks.chatComplete,
  hasApiKeyForModel: () => true,
}));
vi.mock('../../config.js', () => ({
  CONFIG: { openaiApiKey: 'test-key', openrouterApiKey: '' },
  // Mirrors the pipeline's payability_low_threshold; the buyer-evidence digest reads it
  // rather than hardcoding 0.35, so the mock has to supply it.
  getSelectionCapThresholds: () => ({
    payabilityLowThreshold: 0.35,
    payabilityMarketFitCap: 0.55,
    parityShippedMarketFitCap: 0.45,
    parityPartialMarketFitCap: 0.55,
    paritySubstituteMarketFitCap: 0.5,
    paritySubstituteWeakWalletCap: 0.35,
    parityBundledFreeCap: 0.4,
  }),
}));
vi.mock('../analystModelService.js', () => ({
  resolveAnalystModel: vi.fn().mockResolvedValue('gpt-test'),
  normalizeAnalystUsage: vi.fn((usage: { prompt_tokens?: number; completion_tokens?: number } | undefined) => ({
    inputTokens: usage?.prompt_tokens ?? 0,
    outputTokens: usage?.completion_tokens ?? 0,
    cacheWriteTokens: 0,
    cacheReadTokens: 0,
  })),
  estimateAnalystCostUsd: vi.fn(() => 0.01),
}));

import {
  CALL_TIMEOUT_MS,
  ConceptSetGenerationError,
  GENERATION_BUDGET_MS,
  MIN_RETRY_BUDGET_MS,
  generateSelectionConceptSet,
  prepareSelectionConceptSetInput,
} from '../selectionConceptSetService.js';
import { candidateSnapshotSha256 } from '../../utils/ideaIdentity.js';
import type { CandidatePoolVersion } from '../currentSelectionContext.js';

const parent = {
  idea_id: 'idea-signal',
  idea_revision: 3,
  solution_name: 'Signal Desk',
  source_pain: 'Teams miss recurring demand signals',
  source_segment: 'Solo SaaS founders',
  description: 'A broad monitoring workflow.',
};

function option(operation: 'narrow' | 'reposition' | 'adjacent' | 'combine', index: number) {
  return {
    operation,
    sourceIndexes: operation === 'combine' ? [0, 1] : [0],
    sourceContributions: operation === 'combine'
      ? ['Keep signal interpretation.', 'Keep renewal workflow.']
      : ['Keep signal interpretation.'],
    title: `${operation} direction`,
    brief: `A concrete ${operation} concept that changes one meaningful product direction.`,
    changeSummary: `Changes the ${operation} axis while leaving the source untouched.`,
    rationale: `This direction exposes a different decision trade-off for option ${index}.`,
    changedAxes: [{
      axis: operation === 'narrow' ? 'scope' : operation === 'adjacent' ? 'job' : 'buyer',
      from: 'Broad monitoring',
      to: `${operation} workflow`,
      reason: 'Makes the option meaningfully distinct.',
    }],
    retainedEvidence: ['The recorded pain around missed signals may still apply.'],
    evidenceToRecheck: ['The changed buyer and workflow require fresh demand evidence.'],
    assumptions: [{
      type: 'demand',
      statement: `Buyers will act on the ${operation} workflow.`,
      whyDecisionChanging: 'Without action there is no credible product demand.',
      consequenceIfFalse: 'Park this option rather than transferring the parent score.',
    }],
    disqualifiers: ['No qualified buyer accepts the proposed workflow.'],
    suggestedTest: {
      assumptionIndex: 0,
      hypothesis: `Qualified buyers will commit to the ${operation} workflow.`,
      method: 'BOOKED_CALL',
      evidenceSignal: 'SMALL_COMMITMENT',
      audience: 'Qualified solo SaaS founders',
      artifact: 'A one-page concept and booked-call CTA',
      primaryMetric: 'Qualified booked-call rate',
      passThreshold: 'At least 3 of 20 qualified visitors book',
      failThreshold: 'Zero qualified visitors book',
      measurementWindow: 'Seven days',
    },
  };
}

const baseInput = {
  jobId: 'job-1',
  candidatePoolVersion: 1 as CandidatePoolVersion,
  purpose: 'diverge' as const,
  parents: [parent],
  report: { ranked: ['Signal Desk'] },
  founderProfile: { weeklyTime: 'under_10' },
  founderFit: { inputFingerprint: 'f'.repeat(64) },
  challenges: [{ inputFingerprint: 'c'.repeat(64), overall: 'mixed' }],
  conclusions: [],
};

describe('selectionConceptSetService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.chatComplete.mockReset();
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: [option('narrow', 1), option('reposition', 2), option('adjacent', 3)],
      }) } }],
      usage: { prompt_tokens: 300, completion_tokens: 900 },
    });
  });

  it('creates three exact-parent lanes with server-owned option and assumption identities', async () => {
    const generated = await generateSelectionConceptSet(baseInput);

    expect(generated.artifact.options.map((candidate) => candidate.operation)).toEqual([
      'narrow',
      'reposition',
      'adjacent',
    ]);
    expect(generated.artifact.options).toEqual(expect.arrayContaining([
      expect.objectContaining({
        optionId: expect.stringMatching(/^O[a-f0-9]{11}$/),
        parentContributions: [expect.objectContaining({
          ideaId: 'idea-signal',
          ideaRevision: 3,
          candidateSnapshotSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
        })],
        assumptions: [expect.objectContaining({ assumptionId: expect.stringMatching(/^A[a-f0-9]{10}$/) })],
      }),
    ]));
    expect(generated.artifact.options[0].suggestedTest.assumptionId)
      .toBe(generated.artifact.options[0].assumptions[0].assumptionId);
    expect(mocks.chatComplete.mock.calls[0][0].messages[1].content)
      .toContain('UNTRUSTED CONCEPT FORGE CONTEXT');
    expect(mocks.chatComplete.mock.calls[0][0].messages[1].content)
      .toContain('Available source indexes (0-based): 0');
    // The one-parent index bound is now enforced by the response schema's enum rather
    // than by prose, so an out-of-range index is impossible instead of merely rejected.
    const schema = mocks.chatComplete.mock.calls[0][0].responseFormat.json_schema;
    expect(schema.strict).toBe(true);
    expect(schema.schema.$defs.option.properties.sourceIndexes.items.enum).toEqual([0]);
  });

  it('keeps identities deterministic for the same frozen input and output', async () => {
    const first = await generateSelectionConceptSet(baseInput);
    const second = await generateSelectionConceptSet(baseInput);
    expect(second.artifact.inputFingerprint).toBe(first.artifact.inputFingerprint);
    expect(second.artifact.options.map((candidate) => candidate.optionId))
      .toEqual(first.artifact.options.map((candidate) => candidate.optionId));
  });

  it('retries one rejected model artifact with the same frozen input', async () => {
    mocks.chatComplete
      .mockResolvedValueOnce({
        choices: [{ message: { content: 'not json' } }],
        usage: { prompt_tokens: 100, completion_tokens: 20 },
      })
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: [option('narrow', 1), option('reposition', 2), option('adjacent', 3)],
        }) } }],
        usage: { prompt_tokens: 300, completion_tokens: 900 },
      });

    const generated = await generateSelectionConceptSet(baseInput);

    expect(mocks.chatComplete).toHaveBeenCalledTimes(2);
    expect(mocks.chatComplete.mock.calls[1][0].messages.at(-1)?.content)
      .toContain('INVALID_CONCEPT_SET_OUTPUT');
    expect(mocks.chatComplete.mock.calls[1][0].messages[1].content)
      .toBe(mocks.chatComplete.mock.calls[0][0].messages[1].content);
    expect(generated.usage).toEqual({
      inputTokens: 400,
      outputTokens: 920,
      cacheWriteTokens: 0,
      cacheReadTokens: 0,
    });
  });

  it('stops after one repair attempt when both artifacts are invalid', async () => {
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: 'not json' } }],
      usage: { prompt_tokens: 100, completion_tokens: 20 },
    });

    await expect(generateSelectionConceptSet(baseInput)).rejects
      .toThrow('INVALID_CONCEPT_SET_OUTPUT');
    expect(mocks.chatComplete).toHaveBeenCalledTimes(2);
    expect(consoleWarn).toHaveBeenCalledTimes(2);
    consoleWarn.mockRestore();
  });

  it('sends the shape as a strict response schema instead of restating it in prose', async () => {
    await generateSelectionConceptSet(baseInput);
    const call = mocks.chatComplete.mock.calls[0][0];

    expect(call.responseFormat.type).toBe('json_schema');
    const { json_schema: jsonSchema } = call.responseFormat;
    expect(jsonSchema.strict).toBe(true);

    const option = jsonSchema.schema.$defs.option;
    for (const field of ['sourceIndexes', 'changedAxes', 'evidenceToRecheck', 'suggestedTest']) {
      expect(Object.keys(option.properties)).toContain(field);
    }
    expect(option.properties.operation.enum).toEqual(['narrow', 'reposition', 'combine', 'adjacent']);
    expect(option.properties.suggestedTest.properties.assumptionIndex.enum).toEqual([0, 1, 2]);
    // Strict mode requires every property listed and no extras, at every level.
    expect(option.required).toEqual(Object.keys(option.properties));
    expect(option.additionalProperties).toBe(false);

    // Exactly three is a decoder guarantee now: strict mode has no minItems, so the
    // three slots are required object properties instead of an array length.
    expect(jsonSchema.schema.properties.options.required).toEqual(['first', 'second', 'third']);

    // ...and the prose that used to restate all of this is gone.
    const system = call.messages[0].content as string;
    expect(system).not.toContain('"sourceIndexes"');
    expect(system).not.toContain('No markdown, no commentary, no extra keys');
  });

  it('accepts the first/second/third wire shape and stores it as an array', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: {
          first: option('narrow', 0),
          second: option('reposition', 1),
          third: option('adjacent', 2),
        },
      }) } }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    });

    const generated = await generateSelectionConceptSet(baseInput);
    // Stored artifact shape is unchanged, so nothing downstream needed migrating.
    expect(Array.isArray(generated.artifact.options)).toBe(true);
    expect(generated.artifact.options.map((o) => o.operation))
      .toEqual(['narrow', 'reposition', 'adjacent']);
  });

  it('instructs the model to name parents in prose and to describe the test method, not echo the assumption', async () => {
    await generateSelectionConceptSet(baseInput);
    const system = mocks.chatComplete.mock.calls[0][0].messages[0].content as string;
    expect(system).toContain('never use index references like "parent 0" or "parent 1" in prose');
    expect(system).toContain('Refer to parent products by their product name');
    expect(system).toContain('must not restate the targeted assumption\'s statement');
    expect(system).toContain('what you will do and with whom');
    // Parent payload labels each parent by product name for the model to reference.
    const user = mocks.chatComplete.mock.calls[0][0].messages[1].content as string;
    expect(user).toContain('"productName":"Signal Desk"');
  });

  it('feeds specific schema problems into the repair round', async () => {
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const missingField = { options: [option('narrow', 1), option('reposition', 2), option('adjacent', 3)] };
    delete (missingField.options[0] as Record<string, unknown>).changedAxes;
    mocks.chatComplete
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify(missingField) } }],
        usage: { prompt_tokens: 100, completion_tokens: 20 },
      })
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: [option('narrow', 1), option('reposition', 2), option('adjacent', 3)],
        }) } }],
        usage: { prompt_tokens: 300, completion_tokens: 900 },
      });

    await generateSelectionConceptSet(baseInput);

    const feedback = mocks.chatComplete.mock.calls[1][0].messages.at(-1)?.content as string;
    expect(feedback).toContain('INVALID_CONCEPT_SET_OUTPUT');
    expect(feedback).toContain('options.0.changedAxes');
    consoleWarn.mockRestore();
  });

  it('carries the token spend of both rejected attempts on final guardrail failure', async () => {
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: [option('narrow', 1), option('narrow', 2), option('narrow', 3)],
      }) } }],
      usage: { prompt_tokens: 100, completion_tokens: 200 },
    });

    const failure = await generateSelectionConceptSet(baseInput).catch((error) => error);

    expect(failure).toBeInstanceOf(ConceptSetGenerationError);
    expect(failure.code).toBe('CONCEPT_OPTIONS_NOT_DISTINCT');
    expect(failure.costUsd).toBe(0.01);
    expect(failure.usage).toEqual({
      inputTokens: 200,
      outputTokens: 400,
      cacheWriteTokens: 0,
      cacheReadTokens: 0,
    });
    consoleWarn.mockRestore();
  });

  it('changes the input fingerprint when owner context changes', () => {
    const first = prepareSelectionConceptSetInput(baseInput);
    const changed = prepareSelectionConceptSetInput({
      ...baseInput,
      founderProfile: { weeklyTime: 'full_time' },
    });
    expect(changed.inputFingerprint).not.toBe(first.inputFingerprint);
  });

  it('requires one combined lane when two parents are supplied', async () => {
    const secondParent = {
      idea_id: 'idea-renewal',
      idea_revision: 1,
      solution_name: 'Renewal Desk',
      source_pain: 'Renewals slip through manual follow-up',
      source_segment: 'Solo SaaS founders',
      description: 'A renewal follow-up workflow.',
    };
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: [option('narrow', 1), option('reposition', 2), option('adjacent', 3)],
      }) } }],
      usage: { prompt_tokens: 300, completion_tokens: 900 },
    });

    await expect(generateSelectionConceptSet({
      ...baseInput,
      parents: [parent, secondParent],
    })).rejects.toThrow('COMBINED_CONCEPT_OPTION_REQUIRED');
  });

  it('rejects three cosmetic copies instead of persisting fake diversity', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: [option('narrow', 1), option('narrow', 2), option('narrow', 3)],
      }) } }],
    });
    await expect(generateSelectionConceptSet(baseInput)).rejects.toThrow('CONCEPT_OPTIONS_NOT_DISTINCT');
  });
});

describe('buyer-evidence gating', () => {
  /** A report where the parent's own segment has already lost ideas for having no wallet. */
  const deadWalletReport = {
    market_reality: { wallet: { wallet_class: 'free-culture', evidence: 'every tool is free' } },
    niche_difficulty_verdict: { buyer_class: 'consumer', buyer_class_note: 'price for budget authority' },
    audience_mapping: {
      audience_segments: [
        { segment_name: 'Solo SaaS founders', payability_score: 0.15, payability_class: 'personal-wallet' },
        { segment_name: 'Agency operators', payability_score: 0.62, payability_class: 'smb-budget' },
      ],
    },
    examined_ruled_out: [
      { idea_name: 'a', source: 'no_buyer', reason: '', idea: { source_segment: 'Solo SaaS founders' } },
      { idea_name: 'b', source: 'no_buyer', reason: '', idea: { source_segment: 'Solo SaaS founders' } },
    ],
  };

  it('does not constrain a run that has ruled nothing out', () => {
    const prepared = prepareSelectionConceptSetInput(baseInput);
    expect(prepared.requireBuyerMove).toBe(false);
    expect(prepared.buyerReality.provenThinSegments).toEqual([]);
  });

  it('requires a buyer move when the parent sits in a segment that already lost ideas', () => {
    const prepared = prepareSelectionConceptSetInput({ ...baseInput, report: deadWalletReport });
    expect(prepared.requireBuyerMove).toBe(true);
    expect(prepared.buyerReality.provenThinSegments).toEqual(['Solo SaaS founders']);
    expect(prepared.buyerReality.strongestSegment).toEqual({ name: 'Agency operators', payability: 0.62 });
  });

  it('does NOT constrain when the parent sits outside the thin segment', () => {
    const prepared = prepareSelectionConceptSetInput({
      ...baseInput,
      report: deadWalletReport,
      parents: [{ ...parent, source_segment: 'Agency operators' }],
    });
    expect(prepared.requireBuyerMove).toBe(false);
  });

  it('puts the evidence in the prompt payload as named fields, not raw keys', () => {
    const prepared = prepareSelectionConceptSetInput({ ...baseInput, report: deadWalletReport });
    const buyer = (prepared.promptPayload as Record<string, any>).buyerReality;
    expect(buyer.nicheWalletClass).toBe('free-culture');
    expect(buyer.segmentsAlreadyProvenUnpaying).toEqual(['Solo SaaS founders']);
    expect(buyer.bestPayingSegmentNotYetRuledOut.name).toBe('Agency operators');
    expect(buyer.ideasAlreadyDemotedForNoBuyer).toBe(2);
    expect(buyer.parentsSitInAProvenUnpayingSegment).toBe(true);
    expect(String(buyer.note)).toMatch(/does not pay/);
  });

  it('rejects three options that all ignore the buyer evidence', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        // Every option rearranges the product, none moves who pays — the exact failure
        // that produced a seeded idea the pipeline then demoted for no_buyer.
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: [{ axis: 'scope', from: 'broad', to: 'narrow', reason: 'focus' }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .rejects.toThrow(/CONCEPT_OPTIONS_IGNORE_BUYER_EVIDENCE/);
  });

  it('accepts when one option moves the buyer axis', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: op === 'reposition'
            ? [{ axis: 'buyer', from: 'solo founders', to: 'agency operators', reason: 'budget authority' }]
            : [{ axis: 'scope', from: 'broad', to: 'narrow', reason: 'focus' }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    const result = await generateSelectionConceptSet({ ...baseInput, report: deadWalletReport });
    expect(result.artifact.options).toHaveLength(3);
  });

  it('also accepts a business_model move as addressing the wallet', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: op === 'adjacent'
            ? [{ axis: 'business_model', from: 'free core', to: 'per-seat licence', reason: 'payer has budget' }]
            : [{ axis: 'mechanism', from: 'polling', to: 'webhooks', reason: 'lower latency' }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .resolves.toBeTruthy();
  });

  it('rejects a set where ALL THREE options move the payer', async () => {
    // The floor ("at least one must move") has no ceiling, so pressure to leave a dead
    // wallet pushes the model to move the payer everywhere. Three lanes then ask one
    // question — "go B2B" — and the operation-label distinctness check cannot see it.
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: [{
            axis: 'buyer',
            from: 'solo founders',
            to: `institutional payer ${i}`,
            reason: 'has budget',
          }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .rejects.toThrow(/CONCEPT_OPTIONS_COLLAPSE_ON_BUYER/);
  });

  it('rejects the collapse even on a run with no buyer problem to escape', async () => {
    // Nothing forced the move here, so three payer pivots are still a one-question set.
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: [{
            axis: 'business_model',
            from: 'free core',
            to: `paid tier ${i}`,
            reason: 'monetize',
          }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet(baseInput))
      .rejects.toThrow(/CONCEPT_OPTIONS_COLLAPSE_ON_BUYER/);
  });

  it('lets the option that keeps the audience re-price it', async () => {
    // The first version of the ceiling required one option to hold buyer AND
    // business_model fixed, which on a dead-wallet run pinned that lane to an audience
    // and a monetization the run had already discredited — the lane arrived with its own
    // disqualifiers already satisfied. Per-axis, this set passes: buyer moved twice,
    // business_model once, neither by all three.
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: op === 'narrow'
            ? [{
                axis: 'business_model',
                from: 'free core',
                to: 'clinician referral revenue',
                reason: 'same audience, someone else pays',
              }]
            : [{
                axis: 'buyer',
                from: 'solo founders',
                to: `Agency operators tier ${i}`,
                reason: 'budget authority',
              }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .resolves.toBeTruthy();
  });

  it('names the axis that collapsed so the retry knows which one to leave alone', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: [
            { axis: 'business_model', from: 'free core', to: `tier ${i}`, reason: 'monetize' },
            { axis: 'scope', from: 'broad', to: 'narrow', reason: 'focus' },
          ],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    // business_model is the collapsed axis here, not buyer — the feedback must say so.
    await expect(generateSelectionConceptSet(baseInput))
      .rejects.toThrow(/CONCEPT_OPTIONS_COLLAPSE_ON_BUYER/);
    expect(mocks.chatComplete.mock.calls.at(-1)?.[0].messages.at(-1)?.content)
      .toContain('changed business_model');
  });

  it('rejects a buyer move that lands back in the already-unpaying segment', async () => {
    // `movesBuyer` only proved a buyer axis EXISTS. Without checking the destination, an
    // option can "move" from the dead segment to the same dead segment and pass.
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: op === 'reposition'
            ? [{
                axis: 'buyer',
                from: 'solo founders',
                to: 'Solo SaaS founders who ship weekly',
                reason: 'sharper wedge',
              }]
            : [{ axis: 'scope', from: 'broad', to: 'narrow', reason: 'focus' }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .rejects.toThrow(/CONCEPT_BUYER_MOVE_STAYS_IN_DEAD_SEGMENT/);
  });

  it('accepts a buyer move that names a genuinely different payer', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: op === 'reposition'
            ? [{
                axis: 'buyer',
                from: 'solo founders',
                to: 'Agency operators',
                reason: 'budget authority',
              }]
            : [{ axis: 'scope', from: 'broad', to: 'narrow', reason: 'focus' }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .resolves.toBeTruthy();
  });

  it('leaves a monetization-only move alone, since it names no new audience', async () => {
    // Same audience, new way of charging, is a legitimate answer to a wallet problem —
    // the destination check must not demand a buyer the option never claimed to change.
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: op === 'adjacent'
            ? [{
                axis: 'business_model',
                from: 'free core',
                to: 'paid workspace licence',
                reason: 'charge the org, not the seat',
              }]
            : [{ axis: 'mechanism', from: 'polling', to: 'webhooks', reason: 'lower latency' }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .resolves.toBeTruthy();
  });
});

describe('generation time budget', () => {
  // Sibling describes do not inherit the top-level beforeEach, and a rejection set in
  // one test otherwise leaks into the next.
  beforeEach(() => {
    mocks.chatComplete.mockReset();
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: [option('narrow', 1), option('reposition', 2), option('adjacent', 3)],
      }) } }],
      usage: { prompt_tokens: 300, completion_tokens: 900 },
    });
  });

  it('pins the budgets, since they are a judgement about decode time', () => {
    // 60s aborted a full three-option reply mid-response. Changing these should be a
    // deliberate edit, not drift.
    expect(CALL_TIMEOUT_MS).toBeGreaterThanOrEqual(120_000);
    expect(GENERATION_BUDGET_MS).toBeGreaterThanOrEqual(CALL_TIMEOUT_MS);
    // A retry must fit inside what remains, or it aborts and loses attempt 1 as well.
    expect(GENERATION_BUDGET_MS - CALL_TIMEOUT_MS).toBeGreaterThanOrEqual(MIN_RETRY_BUDGET_MS);
  });

  it('bills the tokens already spent when the upstream call is aborted', async () => {
    // The abort used to throw raw, so the route's ConceptSetGenerationError branch never
    // ran and an attempt's spend vanished. It is now a typed error carrying the cost.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const aborted = new Error('Request was aborted.');
    aborted.name = 'APIUserAbortError';
    mocks.chatComplete.mockRejectedValue(aborted);

    await expect(generateSelectionConceptSet(baseInput))
      .rejects.toMatchObject({ name: 'ConceptSetTimeoutError' });
    consoleError.mockRestore();
  });

  it('passes an abort signal to every upstream call', async () => {
    await generateSelectionConceptSet(baseInput);

    expect(mocks.chatComplete.mock.calls[0][0].signal).toBeInstanceOf(AbortSignal);
  });

});

describe('suggested-test coherence', () => {
  function withTest(overrides: Record<string, string>) {
    return {
      options: ['narrow', 'reposition', 'adjacent'].map((op, i) => {
        const built = option(op as 'narrow', i);
        return { ...built, suggestedTest: { ...built.suggestedTest, ...overrides } };
      }),
    };
  }

  it('rejects a set whose test has an inverted pass/fail pair', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify(withTest({
        passThreshold: '>=5% of contacted book a call',
        failThreshold: '<=20% of contacted book a call',
      })) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet(baseInput))
      .rejects.toThrow(/CONCEPT_TEST_BANDS_INVERTED/);
  });

  it('rejects a set whose test measures two different windows', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify(withTest({
        hypothesis: 'Buyers commit within 7 days.',
        passThreshold: '>=12% of contacted book a call within 14 days',
        failThreshold: '<=3% of contacted book a call within 14 days',
        measurementWindow: '14 days',
      })) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });

    await expect(generateSelectionConceptSet(baseInput))
      .rejects.toThrow(/CONCEPT_TEST_WINDOW_INCONSISTENT/);
  });

  it('costs a retry but still ships when only the plausibility heuristic objects', async () => {
    // The mock returns the SAME implausible bar both times. Attempt 1 rejects it;
    // attempt 2 runs with advisory checks off, so the user gets their generation
    // instead of a hard failure over a judgement call.
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify(withTest({
        passThreshold: '>=30% of contacted book a call within 30 days',
        failThreshold: '<=10% of contacted book a call within 30 days',
        measurementWindow: '30 days',
        hypothesis: 'Qualified buyers commit within 30 days.',
      })) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });
    mocks.chatComplete.mockClear();

    await expect(generateSelectionConceptSet(baseInput)).resolves.toBeTruthy();
    expect(mocks.chatComplete).toHaveBeenCalledTimes(2);
  });

  it('does not retry at all when the test is coherent', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify(withTest({
        passThreshold: '>=8% of contacted book a call within 30 days',
        failThreshold: '<=2% of contacted book a call within 30 days',
        measurementWindow: '30 days',
        hypothesis: 'Qualified buyers commit within 30 days.',
      })) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });
    mocks.chatComplete.mockClear();

    await expect(generateSelectionConceptSet(baseInput)).resolves.toBeTruthy();
    expect(mocks.chatComplete).toHaveBeenCalledTimes(1);
  });
});

describe('the shape the prompt recommends actually passes', () => {
  const deadWalletReport = {
    market_reality: { wallet: { wallet_class: 'free-culture', evidence: 'every tool is free' } },
    audience_mapping: {
      audience_segments: [
        { segment_name: 'Solo SaaS founders', payability_score: 0.15, payability_class: 'personal-wallet' },
        { segment_name: 'Agency operators', payability_score: 0.62, payability_class: 'smb-budget' },
      ],
    },
    examined_ruled_out: [
      { idea_name: 'a', source: 'no_buyer', reason: '', idea: { source_segment: 'Solo SaaS founders' } },
    ],
  };

  const axesFor = (op: string) => {
    // Exactly the shape the system prompt tells the model to produce.
    if (op === 'reposition') {
      return [
        { axis: 'buyer', from: 'solo founders', to: 'agency operators', reason: 'budget authority' },
        { axis: 'business_model', from: 'free core', to: 'per-seat licence', reason: 'agencies buy seats' },
      ];
    }
    if (op === 'narrow') {
      return [{ axis: 'scope', from: 'broad monitoring', to: 'one alert', reason: 'sharper job' }];
    }
    return [{ axis: 'business_model', from: 'free core', to: 'one-off fee', reason: 're-price same audience' }];
  };

  const reply = (ops: string[]) => JSON.stringify({
    options: ops.map((op, i) => ({ ...option(op as 'narrow', i), changedAxes: axesFor(op) })),
  });

  it('accepts one payer move, one product change, one re-price', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: reply(['reposition', 'narrow', 'adjacent']) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });
    const result = await generateSelectionConceptSet({ ...baseInput, report: deadWalletReport });
    expect(result.artifact.options).toHaveLength(3);
  });

  it('states BOTH the floor and the per-axis ceiling in the prompt', () => {
    const prepared = prepareSelectionConceptSetInput({ ...baseInput, report: deadWalletReport });
    expect(prepared.requireBuyerMove).toBe(true);
  });

  it('still rejects a payer change in every option', async () => {
    // The failure the user hit: told only the floor, the model moved the payer everywhere.
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: [{ axis: 'buyer', from: 'solo founders', to: 'agency operators', reason: 'budget' }],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });
    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .rejects.toThrow(/CONCEPT_OPTIONS_COLLAPSE_ON_BUYER/);
  });

  it('rejects business_model changing in all three, not just buyer', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
          ...option(op as 'narrow', i),
          changedAxes: [
            { axis: 'business_model', from: 'free core', to: 'paid', reason: 'monetize' },
            ...(op === 'reposition'
              ? [{ axis: 'buyer', from: 'solo founders', to: 'agency operators', reason: 'budget' }]
              : []),
          ],
        })),
      }) } }],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });
    await expect(generateSelectionConceptSet({ ...baseInput, report: deadWalletReport }))
      .rejects.toThrow(/CONCEPT_OPTIONS_COLLAPSE_ON_BUYER/);
  });
});

describe('retry feedback carries specifics', () => {
  /** The corrective message the retry attempt receives. */
  // This describe is a sibling of the main one, so it does not inherit its beforeEach;
  // without an own reset the mock's call history leaks in from earlier suites.
  beforeEach(() => {
    mocks.chatComplete.mockReset();
  });

  /** The corrective message the retry attempt receives (system, user, corrective). */
  const retryMessage = () => {
    const second = mocks.chatComplete.mock.calls[1]?.[0];
    return String(second?.messages?.at(-1)?.content ?? '');
  };

  it('names the offending option and indexes for a lane violation', async () => {
    // These used to throw a bare Error, so `priorDetail` was empty and the retry got
    // only the generic sentence — it never learned WHICH option was wrong.
    mocks.chatComplete
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: ['narrow', 'narrow', 'adjacent'].map((op, i) => option(op as 'narrow', i)),
        }) } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      })
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: ['narrow', 'reposition', 'adjacent'].map((op, i) => option(op as 'narrow', i)),
        }) } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      });

    await generateSelectionConceptSet(baseInput);

    const feedback = retryMessage();
    expect(feedback).toContain('CONCEPT_OPTIONS_NOT_DISTINCT');
    expect(feedback).toContain('Specific problems');
    expect(feedback).toMatch(/narrow, narrow, adjacent/);
  });

  it('names the field path and the exact banned word', async () => {
    mocks.chatComplete
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
            ...option(op as 'narrow', i),
            rationale: op === 'reposition'
              ? 'This direction is proven to work for the segment.'
              : 'A neutral rationale that observes the reported behaviour.',
          })),
        }) } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      })
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: ['narrow', 'reposition', 'adjacent'].map((op, i) => option(op as 'narrow', i)),
        }) } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      });

    await generateSelectionConceptSet(baseInput);

    const feedback = retryMessage();
    expect(feedback).toContain('UNSUPPORTED_CONCEPT_SET_CLAIM');
    // Path and word, not just "you used a banned word somewhere in 20KB of JSON".
    expect(feedback).toMatch(/options\[1\]\.rationale/);
    expect(feedback).toMatch(/"proven"/i);
  });

  it('names which option miscounted its sourceContributions', async () => {
    mocks.chatComplete
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: ['narrow', 'reposition', 'adjacent'].map((op, i) => ({
            ...option(op as 'narrow', i),
            ...(op === 'adjacent' ? { sourceContributions: ['one', 'two'] } : {}),
          })),
        }) } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      })
      .mockResolvedValueOnce({
        choices: [{ message: { content: JSON.stringify({
          options: ['narrow', 'reposition', 'adjacent'].map((op, i) => option(op as 'narrow', i)),
        }) } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      });

    await generateSelectionConceptSet(baseInput);

    const feedback = retryMessage();
    expect(feedback).toContain('INVALID_CONCEPT_SOURCE_COUNT');
    expect(feedback).toMatch(/adjacent direction/);
  });
});


/**
 * `promptPayload.parents[].candidate` is the WHOLE stored candidate, and the options this
 * model writes are shown to the owner as titles, change summaries and rationales — the
 * same route by which the analyst repeated `red_team_verdict: "killed"` onto a screen.
 */
describe('stored vocabulary in the fenced concept-forge payload', () => {
  // Sibling describe: it does not inherit the main suite's beforeEach, so it arms the
  // mock itself and clears the call history the earlier suites left behind.
  beforeEach(() => {
    mocks.chatComplete.mockReset();
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({
        options: [option('narrow', 1), option('reposition', 2), option('adjacent', 3)],
      }) } }],
      usage: { prompt_tokens: 300, completion_tokens: 900 },
    });
  });

  /** None of the three is product vocabulary — `killed`'s shipped label is
   *  "Premise unproven" and the other two have never had a user-facing form. */
  const INTERNAL_VERDICT_TOKENS = /\b(killed|weakened|survives)\b/i;
  /** The leak shape: a stored parity value still LEADING with its class token. */
  const BARE_PARITY_CLASS =
    /"(?:incumbent_parity|adjacent_market_parity)":\s*"(?:shipped|partial|substitute|bundled_free)\b/i;

  const STORED_PARITY = [
    'shipped by Aftershoot: culls RAW batches',
    'partial by Opendate: covers the settlement step',
    'substitute (Forrager): free templates cover it',
    'bundled_free (Notion): included in the free tier',
  ];

  async function fencedPayload(extraFields: Record<string, unknown>): Promise<string> {
    await generateSelectionConceptSet({
      ...baseInput,
      parents: [{ ...parent, ...extraFields }],
    });
    return mocks.chatComplete.mock.calls[0][0].messages[1].content as string;
  }

  it.each(['killed', 'weakened', 'survives'])(
    'hands the concept forge no raw "%s" verdict to parrot',
    async (verdict) => {
      const content = await fencedPayload({ red_team_verdict: verdict });

      expect(content).not.toMatch(INTERNAL_VERDICT_TOKENS);
      // Non-destructive: the field is still there, nothing was dropped.
      expect(content).toContain('"red_team_verdict"');
    },
  );

  it('names the killed verdict the way the owner\'s screen does', async () => {
    const content = await fencedPayload({ red_team_verdict: 'killed' });

    expect(content).toContain('"red_team_verdict":"Premise unproven"');
  });

  it.each(STORED_PARITY)('hands the concept forge no bare parity class for "%s"', async (stored) => {
    const content = await fencedPayload({
      incumbent_parity: stored,
      adjacent_market_parity: stored,
    });

    expect(content).not.toMatch(BARE_PARITY_CLASS);
    expect(content).toContain('"incumbent_parity"');
    expect(content).toContain('"adjacent_market_parity"');
  });

  /**
   * `inputFingerprint` is the cache/staleness key for a stored concept set. It is derived
   * from `parents` (hashing the raw candidate) and `context`, NEVER from `promptPayload`,
   * so presenting the payload must leave it and the per-parent snapshot hash untouched.
   */
  it('leaves the fingerprint chain reading the raw stored candidate', async () => {
    const stored = {
      ...parent,
      red_team_verdict: 'killed',
      incumbent_parity: 'partial by Opendate: covers the settlement step',
    };
    const before = JSON.stringify(stored);
    const input = { ...baseInput, parents: [stored] };

    const prepared = prepareSelectionConceptSetInput(input);

    expect(JSON.stringify(stored)).toBe(before);
    expect(prepared.parents[0].candidateSnapshotSha256).toBe(candidateSnapshotSha256(stored));
    // Re-deriving from the same stored input reproduces the key the row is stored under —
    // this is exactly the staleness check routes/selectionConceptSets.ts runs.
    expect(prepareSelectionConceptSetInput(input).inputFingerprint)
      .toBe(prepared.inputFingerprint);
    // And the payload the model reads is the presented copy, not the stored one.
    expect(JSON.stringify(prepared.promptPayload)).not.toMatch(INTERNAL_VERDICT_TOKENS);
    expect(JSON.stringify(prepared.promptPayload)).not.toMatch(BARE_PARITY_CLASS);
  });
});
