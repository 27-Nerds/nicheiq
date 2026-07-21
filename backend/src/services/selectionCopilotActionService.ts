import { SelectionChallengeArtifactSchema, type SelectionChallengeLens } from '../types/selectionChallenge.js';
import {
  PrepareSelectionActionArgsSchema,
  SelectionCopilotActionSchema,
  type PrepareSelectionActionArgs,
  type SelectionCopilotAction,
} from '../types/selectionCopilotAction.js';
import { ideaName } from '../utils/ideaIdentity.js';

type RawIdea = Record<string, unknown>;

interface AssumptionRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  lens: string;
  statement: string;
  impact: string;
  ownerState: string;
  version: number;
}

interface ExperimentRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  status: string;
  assumption: string;
  method: string;
  primaryMetric: string;
  passThreshold: string;
  failThreshold: string;
}

interface OwnerEvidenceRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  lens: string;
  kind: string;
  position: string;
  title: string;
  content: string;
  retractedAt: Date | string | null;
}

export interface CurrentChallengeRow {
  id: string;
  artifact: unknown;
}

export function matchCurrentSelectionChallengeRows(
  rows: CurrentChallengeRow[],
  currentArtifacts: unknown[],
): CurrentChallengeRow[] {
  const currentKeys = new Set(currentArtifacts.flatMap((value) => {
    const parsed = SelectionChallengeArtifactSchema.safeParse(value);
    return parsed.success
      ? [`${parsed.data.ideaId}\0${parsed.data.ideaRevision}\0${parsed.data.lens}\0${parsed.data.inputFingerprint}`]
      : [];
  }));
  const matched: CurrentChallengeRow[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const parsed = SelectionChallengeArtifactSchema.safeParse(row.artifact);
    if (!parsed.success) continue;
    const key = `${parsed.data.ideaId}\0${parsed.data.ideaRevision}\0${parsed.data.lens}\0${parsed.data.inputFingerprint}`;
    if (!currentKeys.has(key) || seen.has(key)) continue;
    seen.add(key);
    matched.push(row);
  }
  return matched;
}

interface CatalogIdea {
  ref: string;
  ideaId: string;
  ideaRevision: number;
  solutionName: string;
}

interface CatalogAssumption extends AssumptionRow {
  ref: string;
  lens: SelectionChallengeLens;
}

interface CatalogExperiment extends ExperimentRow {
  ref: string;
}

interface CatalogEvidence extends Omit<OwnerEvidenceRow, 'lens'> {
  ref: string;
  lens: SelectionChallengeLens;
}

interface CatalogQuestion {
  ref: string;
  challengeId: string;
  questionId: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  consensus: string;
}

export interface SelectionCopilotCatalog {
  ideas: CatalogIdea[];
  assumptions: CatalogAssumption[];
  experiments: CatalogExperiment[];
  evidence: CatalogEvidence[];
  questions: CatalogQuestion[];
  selectionDraftVersion: number;
}

interface BuildCatalogInput {
  ideas: RawIdea[];
  assumptions: AssumptionRow[];
  experiments: ExperimentRow[];
  ownerEvidence: OwnerEvidenceRow[];
  currentChallenges: CurrentChallengeRow[];
  selectionDraftVersion: number;
}

const APP_LENS: Record<string, SelectionChallengeLens | undefined> = {
  demand: 'demand',
  competition: 'competition',
  distribution: 'distribution',
  dependencies: 'dependencies',
  DEMAND: 'demand',
  COMPETITION: 'competition',
  DISTRIBUTION: 'distribution',
  DEPENDENCIES: 'dependencies',
};

function short(value: unknown, max = 220): string {
  const text = typeof value === 'string' ? value.trim().replace(/\s+/g, ' ') : '';
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

function currentIdeaKeys(ideas: CatalogIdea[]): Set<string> {
  return new Set(ideas.map(idea => `${idea.ideaId}\0${idea.ideaRevision}`));
}

export function buildSelectionCopilotCatalog(input: BuildCatalogInput): SelectionCopilotCatalog {
  const ideas = input.ideas.flatMap((idea, index): CatalogIdea[] => {
    const ideaId = typeof idea.idea_id === 'string' ? idea.idea_id : null;
    const ideaRevision = typeof idea.idea_revision === 'number' && Number.isInteger(idea.idea_revision)
      ? idea.idea_revision
      : null;
    const solutionName = ideaName(idea);
    return ideaId && ideaRevision && ideaRevision > 0 && solutionName
      ? [{ ref: `R${index + 1}`, ideaId, ideaRevision, solutionName }]
      : [];
  });
  const current = currentIdeaKeys(ideas);

  const assumptions = input.assumptions.flatMap((row): CatalogAssumption[] => {
    const lens = APP_LENS[row.lens];
    return lens && current.has(`${row.ideaId}\0${row.ideaRevision}`)
      ? [{ ...row, lens, ref: '' }]
      : [];
  }).slice(0, 30).map((row, index) => ({ ...row, ref: `A${index + 1}` }));

  const experiments = input.experiments
    .filter(row => current.has(`${row.ideaId}\0${row.ideaRevision}`))
    .slice(0, 30)
    .map((row, index) => ({ ...row, ref: `X${index + 1}` }));

  const evidence = input.ownerEvidence.flatMap((row): CatalogEvidence[] => {
    const lens = APP_LENS[row.lens];
    return !row.retractedAt && lens && current.has(`${row.ideaId}\0${row.ideaRevision}`)
      ? [{ ...row, lens, ref: '' }]
      : [];
  }).slice(0, 30).map((row, index) => ({ ...row, ref: `O${index + 1}` }));

  const questions: CatalogQuestion[] = [];
  for (const row of input.currentChallenges) {
    const parsed = SelectionChallengeArtifactSchema.safeParse(row.artifact);
    if (!parsed.success) continue;
    const artifact = parsed.data;
    if (!current.has(`${artifact.ideaId}\0${artifact.ideaRevision}`)) continue;
    for (const question of artifact.questions) {
      if (questions.length >= 36) break;
      questions.push({
        ref: `Q${questions.length + 1}`,
        challengeId: row.id,
        questionId: question.questionId,
        ideaId: artifact.ideaId,
        ideaRevision: artifact.ideaRevision,
        lens: artifact.lens,
        consensus: question.consensus,
      });
    }
  }

  return {
    ideas,
    assumptions,
    experiments,
    evidence,
    questions,
    selectionDraftVersion: Math.max(0, input.selectionDraftVersion),
  };
}

export function buildSelectionCopilotReferenceBlock(catalog: SelectionCopilotCatalog): string {
  const ideaRef = (ideaId: string, ideaRevision: number) =>
    catalog.ideas.find(idea => idea.ideaId === ideaId && idea.ideaRevision === ideaRevision)?.ref ?? 'stale';
  const lines = [
    'Selection copilot references (current owner workspace only; use these references in prepare_selection_action):',
    '- Candidate references are the R-references in the ranked idea dossier.',
  ];
  if (catalog.assumptions.length) {
    lines.push('Current owner assumptions:');
    lines.push(...catalog.assumptions.map(item =>
      `- ${item.ref}: [${ideaRef(item.ideaId, item.ideaRevision)}] ${short(item.statement)} | ${item.lens} | ${item.impact} | ${item.ownerState} | version ${item.version}`,
    ));
  }
  if (catalog.experiments.length) {
    lines.push('Current test briefs:');
    lines.push(...catalog.experiments.map(item =>
      `- ${item.ref}: [${ideaRef(item.ideaId, item.ideaRevision)}] ${item.status} | ${short(item.assumption)} | ${item.method} | metric ${short(item.primaryMetric, 120)} | pass ${short(item.passThreshold, 120)} | fail ${short(item.failThreshold, 120)}`,
    ));
  }
  if (catalog.evidence.length) {
    lines.push('Current owner-provided evidence:');
    lines.push(...catalog.evidence.map(item =>
      `- ${item.ref}: [${ideaRef(item.ideaId, item.ideaRevision)}] ${item.lens} | ${item.kind}/${item.position} | ${short(item.title, 120)} | ${short(item.content)}`,
    ));
  }
  if (catalog.questions.length) {
    lines.push('Current evidence-check questions:');
    lines.push(...catalog.questions.map(item =>
      `- ${item.ref}: [${ideaRef(item.ideaId, item.ideaRevision)}] ${item.lens}/${item.questionId} | ${item.consensus}`,
    ));
  }
  lines.push('For an assumption draft, ground every drafted text field with one or more current R/A/O/Q references for that exact candidate revision and lens. Impact and owner state are owner judgments and cannot be drafted by the analyst.');
  lines.push('The tool only opens a workspace or prepares a draft. It never saves, runs, locks, launches, pays, shortlists, or changes research by itself.');
  return lines.join('\n');
}

function itemFor<T extends { ref: string }>(items: T[], ref: string | undefined): T | undefined {
  return ref ? items.find(item => item.ref === ref) : undefined;
}

function canonicalIdea(item: CatalogIdea) {
  return { ideaId: item.ideaId, ideaRevision: item.ideaRevision, solutionName: item.solutionName };
}

function sameIdea(item: { ideaId: string; ideaRevision: number }, idea: CatalogIdea): boolean {
  return item.ideaId === idea.ideaId && item.ideaRevision === idea.ideaRevision;
}

const ASSUMPTION_DRAFT_FIELDS = [
  'statement',
  'impactIfFalse',
  'falsificationQuestion',
] as const;

type AssumptionDraftField = typeof ASSUMPTION_DRAFT_FIELDS[number];

function resolveAssumptionGrounding(
  grounding: Partial<Record<AssumptionDraftField, string[]>>,
  idea: CatalogIdea,
  lens: SelectionChallengeLens,
  catalog: SelectionCopilotCatalog,
) {
  const resolved: Partial<Record<AssumptionDraftField, Array<{
    ref: string;
    kind: 'candidate' | 'assumption' | 'owner_evidence' | 'challenge_question';
    label: string;
    recordId?: string;
    challengeId?: string;
    questionId?: string;
  }>>> = {};

  for (const field of ASSUMPTION_DRAFT_FIELDS) {
    const refs = grounding[field];
    if (!refs) continue;
    const sources = [];
    const seen = new Set<string>();
    for (const ref of refs) {
      if (seen.has(ref)) continue;
      seen.add(ref);
      if (ref.startsWith('R')) {
        const candidate = itemFor(catalog.ideas, ref);
        if (!candidate || !sameIdea(candidate, idea)) return null;
        sources.push({ ref, kind: 'candidate' as const, label: `Candidate · ${candidate.solutionName}` });
        continue;
      }
      if (ref.startsWith('A')) {
        const assumption = itemFor(catalog.assumptions, ref);
        if (!assumption || !sameIdea(assumption, idea) || assumption.lens !== lens) return null;
        sources.push({
          ref,
          kind: 'assumption' as const,
          label: `Current assumption · ${short(assumption.statement)}`,
          recordId: assumption.id,
        });
        continue;
      }
      if (ref.startsWith('O')) {
        const evidence = itemFor(catalog.evidence, ref);
        if (!evidence || !sameIdea(evidence, idea) || evidence.lens !== lens) return null;
        sources.push({
          ref,
          kind: 'owner_evidence' as const,
          label: `Owner evidence · ${short(evidence.title)}`,
          recordId: evidence.id,
        });
        continue;
      }
      const question = itemFor(catalog.questions, ref);
      if (!question || !sameIdea(question, idea) || question.lens !== lens) return null;
      sources.push({
        ref,
        kind: 'challenge_question' as const,
        label: `${question.lens} evidence check · ${question.questionId} · ${question.consensus}`,
        challengeId: question.challengeId,
        questionId: question.questionId,
      });
    }
    resolved[field] = sources;
  }

  return resolved;
}

function parseAction(args: PrepareSelectionActionArgs | unknown): PrepareSelectionActionArgs | null {
  const parsed = PrepareSelectionActionArgsSchema.safeParse(args);
  return parsed.success ? parsed.data : null;
}

export function resolveSelectionCopilotAction(
  rawArgs: PrepareSelectionActionArgs | unknown,
  catalog: SelectionCopilotCatalog,
): SelectionCopilotAction | null {
  const args = parseAction(rawArgs);
  if (!args) return null;

  if (args.kind === 'shortlist_review') {
    const ideas = args.idea_refs.map(ref => itemFor(catalog.ideas, ref));
    if (ideas.some(item => !item) || new Set(args.idea_refs).size !== args.idea_refs.length) return null;
    return SelectionCopilotActionSchema.parse({
      kind: 'selection_copilot_action',
      action: 'shortlist_review',
      target: 'shortlist',
      ideas: (ideas as CatalogIdea[]).map(canonicalIdea),
      expectedVersion: catalog.selectionDraftVersion,
      rationale: args.rationale,
      caveats: [],
    });
  }

  if (args.kind === 'open') {
    const ideas = args.idea_refs.map(ref => itemFor(catalog.ideas, ref));
    if (ideas.some(item => !item)) return null;
    const assumption = itemFor(catalog.assumptions, args.assumption_ref);
    const experiment = itemFor(catalog.experiments, args.experiment_ref);
    const evidence = itemFor(catalog.evidence, args.evidence_ref);
    const question = itemFor(catalog.questions, args.question_ref);
    if (args.assumption_ref && !assumption) return null;
    if (args.experiment_ref && !experiment) return null;
    if (args.evidence_ref && !evidence) return null;
    if (args.question_ref && !question) return null;
    const allowedRecord =
      (args.target === 'assumptions' && assumption)
      || (args.target === 'experiments' && experiment)
      || (args.target === 'owner_evidence' && evidence)
      || (args.target === 'challenge' && question);
    if ((assumption || experiment || evidence || question) && !allowedRecord) return null;
    const requestedIdeas = ideas as CatalogIdea[];
    const anchored = assumption ?? experiment ?? evidence ?? question;
    if (anchored && requestedIdeas.length && !requestedIdeas.some(idea => sameIdea(anchored, idea))) return null;
    const record = assumption
      ? { id: assumption.id, version: assumption.version }
      : experiment
        ? { id: experiment.id, status: experiment.status }
        : evidence
          ? { id: evidence.id }
          : undefined;
    return SelectionCopilotActionSchema.parse({
      kind: 'selection_copilot_action',
      action: 'open',
      target: args.target,
      ideas: requestedIdeas.map(canonicalIdea),
      lens: args.lens,
      record,
      origin: question ? { challengeId: question.challengeId, questionId: question.questionId } : undefined,
      rationale: args.rationale,
      caveats: [],
    });
  }

  const { draft } = args;
  if (draft.form === 'decision_profile') {
    return SelectionCopilotActionSchema.parse({
      kind: 'selection_copilot_action',
      action: 'prefill',
      target: 'decision_profile',
      values: draft.values,
      rationale: args.rationale,
      caveats: args.caveats,
    });
  }

  if (draft.form === 'concept_forge') {
    const ideas = draft.idea_refs.map(ref => itemFor(catalog.ideas, ref));
    if (ideas.some(item => !item)) return null;
    return SelectionCopilotActionSchema.parse({
      kind: 'selection_copilot_action',
      action: 'prefill',
      target: 'concept_forge',
      ideas: (ideas as CatalogIdea[]).map(canonicalIdea),
      values: draft.values,
      rationale: args.rationale,
      caveats: args.caveats,
    });
  }

  const idea = itemFor(catalog.ideas, draft.idea_ref);
  if (!idea) return null;

  if (draft.form === 'assumption') {
    const assumption = itemFor(catalog.assumptions, draft.assumption_ref);
    const question = itemFor(catalog.questions, draft.question_ref);
    if (draft.assumption_ref && (!assumption || !sameIdea(assumption, idea))) return null;
    if (draft.question_ref && (!question || !sameIdea(question, idea))) return null;
    const lens = assumption?.lens ?? question?.lens ?? draft.lens;
    if (!lens || (draft.lens && draft.lens !== lens) || (question && question.lens !== lens)) return null;
    const grounding = resolveAssumptionGrounding(draft.grounding, idea, lens, catalog);
    if (!grounding) return null;
    return SelectionCopilotActionSchema.parse({
      kind: 'selection_copilot_action',
      action: 'prefill',
      target: 'assumption',
      ideas: [canonicalIdea(idea)],
      lens,
      record: assumption ? { id: assumption.id, version: assumption.version } : undefined,
      origin: question ? { challengeId: question.challengeId, questionId: question.questionId } : undefined,
      values: {
        ideaId: idea.ideaId,
        ideaRevision: idea.ideaRevision,
        lens,
        ...draft.values,
      },
      grounding,
      rationale: args.rationale,
      caveats: args.caveats,
    });
  }

  if (draft.form === 'owner_evidence') {
    return SelectionCopilotActionSchema.parse({
      kind: 'selection_copilot_action',
      action: 'prefill',
      target: 'owner_evidence',
      ideas: [canonicalIdea(idea)],
      lens: draft.lens,
      values: {
        ideaId: idea.ideaId,
        ideaRevision: idea.ideaRevision,
        lens: draft.lens,
        ...draft.values,
      },
      rationale: args.rationale,
      caveats: args.caveats,
    });
  }

  const experiment = itemFor(catalog.experiments, draft.experiment_ref);
  const assumption = itemFor(catalog.assumptions, draft.assumption_ref);
  const question = itemFor(catalog.questions, draft.question_ref);
  if (draft.experiment_ref && (!experiment || !sameIdea(experiment, idea) || experiment.status !== 'DRAFT')) return null;
  if (draft.assumption_ref && (!assumption || !sameIdea(assumption, idea))) return null;
  if (draft.question_ref && (!question || !sameIdea(question, idea))) return null;
  return SelectionCopilotActionSchema.parse({
    kind: 'selection_copilot_action',
    action: 'prefill',
    target: 'experiment',
    ideas: [canonicalIdea(idea)],
    record: experiment ? { id: experiment.id, status: experiment.status } : undefined,
    origin: question ? { challengeId: question.challengeId, questionId: question.questionId } : undefined,
    values: {
      ideaId: idea.ideaId,
      ideaRevision: idea.ideaRevision,
      assumptionId: assumption?.id ?? null,
      originChallengeId: question?.challengeId ?? null,
      originQuestionId: question?.questionId ?? null,
      ...draft.values,
    },
    rationale: args.rationale,
    caveats: args.caveats,
  });
}
