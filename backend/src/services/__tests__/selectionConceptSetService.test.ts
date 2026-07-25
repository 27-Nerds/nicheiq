import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ chatComplete: vi.fn() }));

vi.mock('../openai.js', () => ({ chatComplete: mocks.chatComplete }));
vi.mock('../../config.js', () => ({ CONFIG: { openaiApiKey: 'test-key', openrouterApiKey: '' } }));
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
  ConceptSetGenerationError,
  generateSelectionConceptSet,
  prepareSelectionConceptSetInput,
} from '../selectionConceptSetService.js';

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
    expect(mocks.chatComplete.mock.calls[0][0].messages[0].content)
      .toContain('Only one parent exists');
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

  it('describes the response schema in the system prompt so the model uses exact field names', async () => {
    await generateSelectionConceptSet(baseInput);
    const system = mocks.chatComplete.mock.calls[0][0].messages[0].content as string;
    for (const field of ['"sourceIndexes"', '"changedAxes"', '"evidenceToRecheck"', '"suggestedTest"', '"assumptionIndex"']) {
      expect(system).toContain(field);
    }
    expect(system).toContain('"narrow" | "reposition" | "combine" | "adjacent"');
  });

  it('instructs the model to name parents in prose and to describe the test method, not echo the assumption', async () => {
    await generateSelectionConceptSet(baseInput);
    const system = mocks.chatComplete.mock.calls[0][0].messages[0].content as string;
    expect(system).toContain('never use index references like "parent 0" or "parent 1" in prose');
    expect(system).toContain('Refer to parent products by their product name');
    expect(system).toContain('must not restate the targeted assumption\'s statement');
    expect(system).toContain('what you will do, with whom, and within what window');
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
