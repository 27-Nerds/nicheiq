import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Every guardrail must state its rule in the INITIAL system prompt, not only in the
 * corrective feedback sent after a rejection.
 *
 * Two production failures came from exactly this gap. `CONCEPT_OPTIONS_COLLAPSE_ON_BUYER`
 * and the suggested-test window rule were both enforced by the server and described in
 * `GuardrailRetryFeedback`, but absent from the prompt — so the model could not satisfy
 * them until it had already failed, and with only two attempts the user saw a hard error
 * instead of options.
 *
 * The load-bearing assertion is the FIRST one: every code must appear in the table below.
 * Adding a guardrail without deciding how the model learns about it fails this suite.
 */

const mocks = vi.hoisted(() => ({ chatComplete: vi.fn() }));
vi.mock('../openai.js', () => ({ chatComplete: mocks.chatComplete }));
vi.mock('../../config.js', () => ({
  CONFIG: { openaiApiKey: 'test-key', openrouterApiKey: '' },
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
  resolveAnalystModel: vi.fn().mockResolvedValue('gpt-5-mini'),
  normalizeAnalystUsage: vi.fn(() => ({
    inputTokens: 0, outputTokens: 0, cacheWriteTokens: 0, cacheReadTokens: 0,
  })),
  analystCostUsd: vi.fn(() => 0),
}));

const { CONCEPT_SET_GUARDRAIL_CODES, generateSelectionConceptSet } =
  await import('../selectionConceptSetService.js');
type Code = (typeof CONCEPT_SET_GUARDRAIL_CODES)[number];

/**
 * For each guardrail: patterns that must ALL appear in the initial system prompt.
 *
 * `exempt` marks a rule the model cannot usefully be taught in prose — with the reason.
 * Exempting is a deliberate choice, not a way to silence the test.
 */
const PROMPT_COVERAGE: Record<Code, { patterns: RegExp[]; exempt?: string }> = {
  INVALID_CONCEPT_SET_OUTPUT: {
    patterns: [],
    exempt: 'Schema-shape failure. RESPONSE_SCHEMA_TEXT is the statement of this rule.',
  },
  UNSUPPORTED_CONCEPT_SET_CLAIM: {
    patterns: [/validated/i, /proven/i, /confirmed/i, /guaranteed/i],
  },
  CONCEPT_OPTIONS_NOT_DISTINCT: {
    patterns: [/genuinely different|not three phrasings/i],
  },
  INVALID_CONCEPT_OPTION_LANES: {
    patterns: [/narrow/i, /reposition/i, /adjacent/i],
  },
  COMBINED_CONCEPT_OPTION_REQUIRED: {
    patterns: [/combine/i],
  },
  INVALID_CONCEPT_SOURCE: {
    patterns: [/only numbers from this list|0-based parent indexes|never use index/i],
  },
  DUPLICATE_CONCEPT_SOURCE: {
    // Naming the field is not the rule; the rule is that an index cannot repeat.
    patterns: [/never repeat within one option|must not repeat/i],
  },
  INVALID_CONCEPT_SOURCE_COUNT: {
    patterns: [/exactly one entry per sourceIndexes entry/i],
  },
  INVALID_CONCEPT_TEST_ASSUMPTION: {
    patterns: [/assumptionIndex/],
  },
  CONCEPT_OPTIONS_IGNORE_BUYER_EVIDENCE: {
    patterns: [/buyer/i, /business_model/],
  },
  CONCEPT_OPTIONS_COLLAPSE_ON_BUYER: {
    // The regression this suite exists for: the ceiling, not just the floor.
    patterns: [/leave "?buyer"? unchanged|not put a payer change in every option/i],
  },
  CONCEPT_BUYER_MOVE_STAYS_IN_DEAD_SEGMENT: {
    // The heuristic compares significant words, so a re-label reads as no move at all.
    patterns: [/outside that audience/i, /not the same one relabelled|significant words/i],
  },
  CONCEPT_TEST_WINDOW_INCONSISTENT: {
    // NOT merely /window/ — the schema names the FIELD `measurementWindow`, which says
    // nothing about the rule. The rule is that one test uses ONE window throughout.
    patterns: [/one test, one time window|measurementWindow ONLY|same (measurement )?window/i],
  },
  CONCEPT_TEST_BANDS_INVERTED: {
    // Naming both fields is not the rule; the rule is their ORDER.
    patterns: [/pass[^.]{0,60}above[^.]{0,60}fail|stronger result/i],
  },
  CONCEPT_TEST_THRESHOLD_IMPLAUSIBLE: {
    patterns: [/absolute count|cold outreach|conversion rate/i],
  },
};

const parent = {
  idea_id: 'idea-signal',
  idea_revision: 3,
  solution_name: 'Signal Desk',
  source_pain: 'Teams miss recurring demand signals',
  source_segment: 'Solo SaaS founders',
  description: 'A broad monitoring workflow.',
};

/** A report where the parents' audience is already proven unpaying, so the buyer rules
 *  are present in the prompt — otherwise they are correctly omitted. */
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

/** Some rules only apply to one parent count — `combine` cannot occur with a single
 *  parent — so coverage is checked against the union of both configurations. */
async function captureAllSystemPrompts(): Promise<string> {
  const single = await captureSystemPrompt();
  mocks.chatComplete.mockReset();
  mocks.chatComplete.mockResolvedValue({
    choices: [{ message: { content: 'x' } }],
    usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
  });
  await generateSelectionConceptSet({
    jobId: 'job-1',
    purpose: 'diverge',
    parents: [parent, { ...parent, idea_id: 'idea-two', solution_name: 'Second Desk' }],
    report: deadWalletReport,
    founderProfile: null,
    founderFit: null,
    challenges: [],
    conclusions: [],
  } as never).catch(() => undefined);
  const call = mocks.chatComplete.mock.calls[0]?.[0];
  const pair = String(call?.messages?.find((m: { role: string }) => m.role === 'system')?.content ?? '');
  return `${single}\n${pair}`;
}

async function captureSystemPrompt(): Promise<string> {
  mocks.chatComplete.mockResolvedValue({
    choices: [{ message: { content: 'not json — we only need the request' } }],
    usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
  });
  await generateSelectionConceptSet({
    jobId: 'job-1',
    purpose: 'diverge',
    parents: [parent],
    report: deadWalletReport,
    founderProfile: null,
    founderFit: null,
    challenges: [],
    conclusions: [],
  } as never).catch(() => undefined);

  const call = mocks.chatComplete.mock.calls[0]?.[0];
  const system = call?.messages?.find((m: { role: string }) => m.role === 'system');
  return String(system?.content ?? '');
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chatComplete.mockReset();
});

describe('Concept Forge prompt/guardrail conformance', () => {
  it('has a coverage decision recorded for every guardrail code', () => {
    // Fails the moment someone adds a guardrail without deciding how the model learns it.
    for (const code of CONCEPT_SET_GUARDRAIL_CODES) {
      expect(PROMPT_COVERAGE[code], `no prompt-coverage entry for ${code}`).toBeDefined();
    }
    expect(Object.keys(PROMPT_COVERAGE).sort()).toEqual([...CONCEPT_SET_GUARDRAIL_CODES].sort());
  });

  it('states every non-exempt guardrail rule in the initial system prompt', async () => {
    const prompt = await captureAllSystemPrompts();
    expect(prompt.length).toBeGreaterThan(200);

    const missing: string[] = [];
    for (const code of CONCEPT_SET_GUARDRAIL_CODES) {
      const coverage = PROMPT_COVERAGE[code];
      if (coverage.exempt) continue;
      for (const pattern of coverage.patterns) {
        if (!pattern.test(prompt)) missing.push(`${code}: prompt does not match ${pattern}`);
      }
    }
    expect(missing, `guardrails the model can only learn by failing:\n${missing.join('\n')}`)
      .toEqual([]);
  });

  it('documents a reason for every exemption', () => {
    for (const [code, coverage] of Object.entries(PROMPT_COVERAGE)) {
      if (!coverage.exempt) continue;
      expect(coverage.exempt.length, `${code} exemption needs a reason`).toBeGreaterThan(20);
      expect(coverage.patterns, `${code} is exempt, so it should assert nothing`).toEqual([]);
    }
  });

  it('states the buyer CEILING, not only the floor', async () => {
    // The exact regression: the floor was stated, the ceiling only appeared after a
    // rejection, so the model moved the payer in all three options and burned both
    // attempts.
    const prompt = await captureSystemPrompt();
    expect(prompt).toMatch(/FLOOR/);
    expect(prompt).toMatch(/CEILING/);
    expect(prompt).toMatch(/leave "buyer" unchanged/);
    expect(prompt).toMatch(/leave "business_model" unchanged/);
  });

  it('omits the buyer rules entirely when the run has ruled nothing out', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: 'x' } }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    });
    await generateSelectionConceptSet({
      jobId: 'job-1',
      purpose: 'diverge',
      parents: [parent],
      report: { audience_mapping: { audience_segments: [] }, examined_ruled_out: [] },
      founderProfile: null,
      founderFit: null,
      challenges: [],
      conclusions: [],
    } as never).catch(() => undefined);

    const call = mocks.chatComplete.mock.calls[0]?.[0];
    const prompt = String(call?.messages?.find((m: { role: string }) => m.role === 'system')?.content ?? '');
    // A fresh run must not be told to chase a buyer problem it has not demonstrated.
    expect(prompt).not.toMatch(/FLOOR/);
    expect(prompt).not.toMatch(/already-unpaying/);
  });

  it('states the output length budget, which no surface previously mentioned', async () => {
    // Summing the zod maxima gives ~20k output tokens against a 6k budget, so a model
    // writing to the documented ceilings gets truncated and surfaces as a schema error.
    const prompt = await captureSystemPrompt();
    expect(prompt).toMatch(/ceilings, not targets|truncated/i);
  });

  it('tells the model the purpose of the run, outside the fenced payload', async () => {
    // purpose and targetTradeoff previously reached the model ONLY inside the block the
    // prompt tells it to treat as untrusted data, so all three modes behaved alike.
    const prompt = await captureSystemPrompt();
    expect(prompt).toMatch(/^PURPOSE — /m);
  });

describe('call parameters for a reasoning model', () => {
  it('raises reasoning effort above the implicit minimal, without exceeding the budget', async () => {
    await captureSystemPrompt();
    const call = mocks.chatComplete.mock.calls[0]?.[0];
    // 'minimal' is what this ran at before and is wrong for multi-step planning; 'high'
    // was measured and blew the call timeout on gpt-5-mini. 'medium' is OpenAI's own
    // default and the most this call can afford.
    expect(call.reasoningEffort).toBe('medium');
  });

  it('sends no temperature — reasoning models accept only the default', async () => {
    await captureSystemPrompt();
    const call = mocks.chatComplete.mock.calls[0]?.[0];
    expect(call.temperature).toBeUndefined();
  });

  it('budgets tokens for reasoning as well as output', async () => {
    await captureSystemPrompt();
    const call = mocks.chatComplete.mock.calls[0]?.[0];
    // max_completion_tokens covers reasoning tokens too; 6k at high effort would be
    // spent thinking before any JSON was written.
    expect(call.maxTokens).toBeGreaterThanOrEqual(16_000);
    expect(call.verbosity).toBe('low');
  });

  it('tells the model to fix its axes before writing the options', async () => {
    const prompt = await captureSystemPrompt();
    expect(prompt).toMatch(/Before writing any option/);
    expect(prompt).toMatch(/make the third bolder/);
  });
});
});
