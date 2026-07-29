import { prepareSelectionChallengeInput } from './selectionChallengeService.js';
import {
  serializeSelectionAssumption,
  type SelectionAssumptionWithEvidence,
} from './selectionAssumptionService.js';
import type { FounderFitArtifact } from '../types/founderFit.js';
import type { SelectionDecisionProfile } from '../types/job.js';
import type { SelectionDecisionState } from '../types/selectionDecisionState.js';
import {
  SelectionChallengeArtifactSchema,
  type SelectionChallengeArtifact,
} from '../types/selectionChallenge.js';
import {
  SelectionExperimentConclusionSnapshotSchema,
  type SelectionExperimentConclusionSnapshot,
} from '../types/selectionExperiment.js';
import {
  SelectionConceptSetArtifactSchema,
  type SelectionConceptSetArtifact,
} from '../types/selectionConceptSet.js';
import type { SelectionDecisionHandoffArtifact } from './selectionDecisionHandoffService.js';
import { ideaDisplayTitle, ideaName } from '../utils/ideaIdentity.js';
import type { SelectionDraftResponse } from '../utils/selectionDraft.js';
import { sanitizeUntrustedContent } from '../utils/promptFence.js';

export interface CollaboratorVoteFeedback {
  solutionId: string | null;
  solutionName: string;
  comment: string | null;
}

export type SelectionAssumptionContext = ReturnType<typeof serializeSelectionAssumption>;

function truncateContextText(value: string, maxLength: number): string {
  if (!value) return '';
  return value.length > maxLength
    ? `${value.slice(0, Math.max(0, maxLength - 1))}…`
    : value;
}

function humanizeContextKey(key: string): string {
  return key.replace(/_/g, ' ');
}

/**
 * Resolve a candidate's ranked R-reference (R1, R2, ...) so blocks that key by
 * database id can print the same reference the tools and idea list use. Returns
 * null when the candidate is not in the current ranked pool (stale revision).
 */
function ideaRefLabel(
  ideas: Record<string, unknown>[],
  ideaId: string,
  ideaRevision: number,
): string | null {
  const index = ideas.findIndex(idea =>
    idea.idea_id === ideaId
    && Number(idea.idea_revision) === ideaRevision
  );
  return index >= 0 ? `R${index + 1}` : null;
}

/**
 * The title the owner sees for a candidate a stored artifact points at. Artifacts keep
 * `solutionName` (the internal codename) for lineage and matching; the dossier must not
 * hand that codename to the analyst, which repeats whatever it is given.
 */
function displayTitleFor(
  ideas: Record<string, unknown>[],
  ideaId: string,
  ideaRevision: number,
  fallback: string,
): string {
  const idea = ideas.find(candidate =>
    candidate.idea_id === ideaId
    && Number(candidate.idea_revision) === ideaRevision
  );
  return (idea ? ideaDisplayTitle(idea) : null) ?? fallback;
}

export function buildSelectionDecisionStateBlock(
  state: SelectionDecisionState | null,
  ideas: Record<string, unknown>[],
  /**
   * Whether the owner has the optional decision tools grant. When false the record
   * counts and the "optional decision work" phrasing are dropped: they enumerate the
   * gated toolset to the model on every turn (as a row of zeroes), which is exactly the
   * vocabulary the analyst must not have.
   */
  decisionTools = false,
): string {
  if (!state) return '';
  const ideaLabels = state.nextAction.ideas.flatMap((reference) => {
    const index = ideas.findIndex(idea =>
      idea.idea_id === reference.ideaId
      && Number(idea.idea_revision) === reference.ideaRevision
    );
    return index >= 0 ? [`R${index + 1} revision ${reference.ideaRevision}`] : [];
  });
  const currentCounts = [
    `${state.challenges.length} evidence checks`,
    `${state.ownerEvidence.length} owner evidence items`,
    `${state.assumptions.length} assumptions`,
    `${state.experiments.length} tests`,
    `${state.conclusions.length} conclusions`,
  ].join(', ');
  const deepResearch = state.deepResearch.eligible
    ? decisionTools
      ? 'available now; optional decision work does not block it'
      : 'available now'
    : `blocked only by ${state.deepResearch.blockers.map(humanizeContextKey).join(', ')}`;
  const actionLabel = state.nextAction.required ? 'Required next step' : 'Recommended optional next step';
  return [
    'Server-derived selection decision state (deterministic and read-only; never model-authored):',
    `- Deep Research: ${deepResearch}.`,
    `- ${actionLabel}: ${humanizeContextKey(state.nextAction.kind)} — ${state.nextAction.reason}`,
    `- Exact target: ${ideaLabels.join(', ') || 'selection workspace'}${state.nextAction.lens ? `; ${state.nextAction.lens} lens` : ''}.`,
    ...(decisionTools
      ? [
        `- Current exact-revision records: ${currentCounts}.`,
        `- Historical/stale artifacts excluded from current state: ${state.staleCounts.total}.`,
      ]
      : []),
  ].join('\n');
}

export function currentSelectionAssumptions(
  assumptions: SelectionAssumptionWithEvidence[],
  ideas: Record<string, unknown>[],
): SelectionAssumptionContext[] {
  const currentIdeaRevisions = new Set(ideas.flatMap((idea) => {
    const ideaId = typeof idea.idea_id === 'string' ? idea.idea_id : null;
    const ideaRevision = typeof idea.idea_revision === 'number' ? idea.idea_revision : null;
    return ideaId && ideaRevision ? [`${ideaId}\0${ideaRevision}`] : [];
  }));
  return assumptions.map(assumption => serializeSelectionAssumption(
    assumption,
    !currentIdeaRevisions.has(`${assumption.ideaId}\0${assumption.ideaRevision}`),
  ));
}

export function buildSelectionAssumptionBlock(
  assumptions: SelectionAssumptionContext[],
): string {
  if (!assumptions.length) return '';
  const blocks = assumptions.map((assumption) => {
    const linkedTests = assumption.experiments.length > 0
      ? assumption.experiments.map(experiment =>
          `${experiment.id}: ${humanizeContextKey(experiment.status).toLowerCase()} / ${experiment.outcome
            ? humanizeContextKey(experiment.outcome).toLowerCase()
            : 'no owner outcome yet'}`,
        ).join('; ')
      : 'none linked';
    const staleMarker = assumption.stale
      ? ' | STALE REVISION — historical only; do not apply to the current idea'
      : '';
    return [
      `- ${truncateContextText(assumption.statement, 260)} [${assumption.ideaId} rev ${assumption.ideaRevision}]${staleMarker}`,
      `  Lens: ${humanizeContextKey(assumption.lens)} | Owner impact: ${humanizeContextKey(assumption.impact).toLowerCase()} | Owner state: ${humanizeContextKey(assumption.ownerState).toLowerCase()}`,
      `  Derived direction: ${humanizeContextKey(assumption.direction).toLowerCase()} | Linked-input evidence class: ${humanizeContextKey(assumption.evidenceClass).toLowerCase()}`,
      `  What breaks if false: ${truncateContextText(assumption.impactIfFalse, 220)}`,
      `  Falsification question: ${truncateContextText(assumption.falsificationQuestion, 220)}`,
      `  Explicitly linked test outcomes: ${linkedTests}`,
    ].join('\n');
  });
  return [
    'Owner assumption ledger (owner-authored decision risks; not evidence, validation, or research-score changes):',
    ...blocks,
  ].join('\n');
}

export function buildFounderDecisionBlock(
  profile: SelectionDecisionProfile | null,
  founderFit: FounderFitArtifact | null,
  ideas: Record<string, unknown>[] = [],
): string {
  if (!profile) return '';

  const profileBlock = [
    'Owner decision context (user supplied; not market evidence):',
    `- Weekly time: ${profile.weeklyTime}`,
    `- Budget: ${profile.budget}`,
    `- Team: ${profile.team}`,
    `- Revenue horizon: ${profile.revenueHorizon}`,
    `- Distribution advantages: ${profile.distributionAdvantages.join(', ') || 'none supplied'}`,
    `- Strengths: ${profile.strengths || 'not supplied'}`,
    `- Hard constraints: ${profile.hardConstraints || 'none supplied'}`,
  ].join('\n');

  if (!founderFit) return profileBlock;

  const fitRoster = founderFit.results
    .map((result) => {
      const ref = ideaRefLabel(ideas, result.ideaId, result.ideaRevision);
      return ref ? `[${ref}] ${result.ideaTitle}` : null;
    })
    .filter((entry): entry is string => entry !== null);
  const fitScope = fitRoster.length
    ? `In-scope candidates for founder fit: ${fitRoster.join(', ')}. Only these R-references are valid here; if the owner names a candidate not listed, ask which of these they mean rather than guessing an R-reference.`
    : '';

  const fitBlock = founderFit.results.map((result) => {
    const experiment = result.suggestedExperiment;
    const ref = ideaRefLabel(ideas, result.ideaId, result.ideaRevision);
    const label = ref
      ? `[${ref}] ${result.ideaTitle} (revision ${result.ideaRevision})`
      : `${result.ideaTitle} [${result.ideaId} rev ${result.ideaRevision}]`;
    return [
      `- ${label}: ${result.verdict}`,
      `  Assessment: ${result.summary}`,
      `  Strongest founder advantage: ${result.strongestAdvantage}`,
      `  Blocking conflict: ${result.blockingConflict ?? 'none identified'}`,
      `  Decision-changing unknown: ${result.decisionChangingUnknown}`,
      `  Sensitivity: ${result.sensitivity}`,
      `  Draft test (not saved): ${experiment.assumption}; method ${experiment.method}; metric ${experiment.primaryMetric}; pass ${experiment.passThreshold}; fail ${experiment.failThreshold}; window ${experiment.measurementWindow}.`,
    ].join('\n');
  }).join('\n');

  const fitHeader = [
    'Current founder-fit specialist analysis (advisory; does not alter research ranking or shortlist):',
    fitScope,
  ].filter(Boolean).join('\n');
  return `${profileBlock}\n\n${fitHeader}\n${fitBlock}`;
}

export function currentSelectionChallenges(
  rows: unknown[],
  ideas: Record<string, unknown>[],
  previewReport: unknown,
  discoveryData: unknown,
): SelectionChallengeArtifact[] {
  const current: SelectionChallengeArtifact[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const artifactValue = row && typeof row === 'object' && 'artifact' in row
      ? (row as { artifact: unknown }).artifact
      : row;
    const parsed = SelectionChallengeArtifactSchema.safeParse(artifactValue);
    if (!parsed.success) continue;
    const artifact = parsed.data;
    const idea = ideas.find(candidate =>
      candidate.idea_id === artifact.ideaId
      && Number(candidate.idea_revision) === artifact.ideaRevision
    );
    if (!idea) continue;
    const prepared = prepareSelectionChallengeInput({
      lens: artifact.lens,
      idea,
      previewReport,
      discoveryData,
    });
    const key = `${artifact.ideaId}:${artifact.lens}`;
    if (prepared.inputFingerprint !== artifact.inputFingerprint || seen.has(key)) continue;
    seen.add(key);
    current.push(artifact);
  }
  return current.slice(0, 12);
}

export function selectionChallengesFromDecisionState(
  rows: unknown[],
  state: SelectionDecisionState,
): SelectionChallengeArtifact[] {
  const artifactById = new Map<string, SelectionChallengeArtifact>();
  for (const row of rows) {
    if (!row || typeof row !== 'object' || !('id' in row) || !('artifact' in row)) continue;
    const id = (row as { id?: unknown }).id;
    if (typeof id !== 'string') continue;
    const parsed = SelectionChallengeArtifactSchema.safeParse((row as { artifact: unknown }).artifact);
    if (parsed.success) artifactById.set(id, parsed.data);
  }
  return state.challenges
    .map(challenge => artifactById.get(challenge.id))
    .filter((artifact): artifact is SelectionChallengeArtifact => Boolean(artifact));
}

export function buildSelectionChallengeBlock(
  challenges: SelectionChallengeArtifact[],
  ideas: Record<string, unknown>[] = [],
): string {
  if (!challenges.length) return '';
  const overallLabels: Record<SelectionChallengeArtifact['overall'], string> = {
    withstands: 'evidence holds',
    weakened: 'case weakened',
    contradicted: 'contradiction found',
    disputed: 'the two assessments disagree',
    insufficient_evidence: 'evidence is insufficient',
  };
  const blocks = challenges.map((challenge) => {
    const questionLines = challenge.questions.map((question) => {
      const sourceKeys = new Set([...question.skeptic.evidenceKeys, ...question.auditor.evidenceKeys]);
      const sources = challenge.evidenceSnapshot
        .filter(source => sourceKeys.has(source.key))
        .map(source => source.title)
        .slice(0, 3);
      return [
        `  - ${humanizeContextKey(question.questionId)}: ${question.consensus}`,
        `falsification: ${truncateContextText(question.skeptic.summary, 140)}`,
        `audit: ${truncateContextText(question.auditor.summary, 140)}`,
        `sources: ${sources.join('; ') || 'none captured'}`,
      ].join(' | ');
    });
    const ref = ideaRefLabel(ideas, challenge.ideaId, challenge.ideaRevision);
    const label = ref
      ? `[${ref}] ${challenge.ideaTitle} (revision ${challenge.ideaRevision})`
      : `${challenge.ideaTitle} [${challenge.ideaId} rev ${challenge.ideaRevision}]`;
    return [
      `- ${label}: ${humanizeContextKey(challenge.lens)}: ${overallLabels[challenge.overall]}`,
      ...questionLines,
    ].join('\n');
  });
  const roster = challenges
    .map((challenge) => {
      const ref = ideaRefLabel(ideas, challenge.ideaId, challenge.ideaRevision);
      return ref ? `[${ref}] ${challenge.ideaTitle}` : null;
    })
    .filter((entry, index, all): entry is string => entry !== null && all.indexOf(entry) === index);
  const scope = roster.length
    ? `In-scope candidates for these checks: ${roster.join(', ')}. Only these R-references are valid here; if the owner names a candidate not listed, ask which of these they mean rather than guessing an R-reference.`
    : '';
  return [
    'Current independent evidence stress tests (read-only audits of captured research; not new market research, scores, or shortlist changes):',
    scope,
    ...blocks,
  ].filter(Boolean).join('\n');
}

export function currentExperimentConclusions(
  rows: unknown[],
  ideas: Record<string, unknown>[],
): SelectionExperimentConclusionSnapshot[] {
  const current: SelectionExperimentConclusionSnapshot[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const conclusion = row && typeof row === 'object' && 'conclusion' in row
      ? (row as { conclusion?: unknown }).conclusion
      : row;
    const snapshotValue = conclusion && typeof conclusion === 'object' && 'snapshot' in conclusion
      ? (conclusion as { snapshot?: unknown }).snapshot
      : conclusion;
    const parsed = SelectionExperimentConclusionSnapshotSchema.safeParse(snapshotValue);
    if (!parsed.success) continue;
    const snapshot = parsed.data;
    const idea = ideas.find(candidate =>
      candidate.idea_id === snapshot.experiment.ideaId
      && Number(candidate.idea_revision) === snapshot.experiment.ideaRevision
    );
    if (!idea || seen.has(snapshot.experiment.experimentId)) continue;
    seen.add(snapshot.experiment.experimentId);
    current.push(snapshot);
  }
  return current.slice(0, 12);
}

export function experimentConclusionsFromDecisionState(
  rows: unknown[],
  state: SelectionDecisionState,
): SelectionExperimentConclusionSnapshot[] {
  const snapshotById = new Map<string, SelectionExperimentConclusionSnapshot>();
  for (const row of rows) {
    if (!row || typeof row !== 'object' || !('conclusion' in row)) continue;
    const conclusion = (row as { conclusion?: unknown }).conclusion;
    if (!conclusion || typeof conclusion !== 'object' || !('id' in conclusion) || !('snapshot' in conclusion)) continue;
    const id = (conclusion as { id?: unknown }).id;
    if (typeof id !== 'string') continue;
    const parsed = SelectionExperimentConclusionSnapshotSchema.safeParse(
      (conclusion as { snapshot: unknown }).snapshot,
    );
    if (parsed.success) snapshotById.set(id, parsed.data);
  }
  return state.conclusions
    .map(conclusion => snapshotById.get(conclusion.id))
    .filter((snapshot): snapshot is SelectionExperimentConclusionSnapshot => Boolean(snapshot));
}

export function buildExperimentConclusionBlock(
  conclusions: SelectionExperimentConclusionSnapshot[],
): string {
  if (!conclusions.length) return '';
  const blocks = conclusions.map((conclusion) => {
    const evidence = conclusion.evidence as Record<string, unknown>;
    const source = evidence.source as Record<string, unknown> | undefined;
    const sample = evidence.sample as Record<string, unknown> | undefined;
    const observed = source?.adapterKey === 'nicheiq-hosted'
      ? `${sample?.observed ?? 'unknown'} recorded exposures`
      : truncateContextText(String(evidence.observationSummary || 'manual observations recorded'), 220);
    return [
      `- ${ideaDisplayTitle(conclusion.experiment.ideaSnapshot as Record<string, unknown>) ?? conclusion.experiment.ideaId} [${conclusion.experiment.ideaId} rev ${conclusion.experiment.ideaRevision}]`,
      `  Owner outcome: ${humanizeContextKey(conclusion.adjudication.outcome).toLowerCase()}`,
      `  Observed evidence: ${observed}`,
      `  Owner rationale: ${truncateContextText(conclusion.adjudication.rationale, 260)}`,
      `  Precommitted next action: ${truncateContextText(conclusion.adjudication.nextAction, 260)}`,
    ].join('\n');
  });
  return [
    'Owner-recorded experiment conclusions (immutable interpretations of one test; not automatic validation, market evidence, or score changes):',
    ...blocks,
  ].join('\n');
}

export function buildCollaboratorFeedbackBlock(
  votes: CollaboratorVoteFeedback[],
  ideas: Record<string, unknown>[],
): string {
  if (!votes.length) return '';

  const nameCounts = new Map<string, number>();
  for (const idea of ideas) {
    const name = ideaName(idea);
    if (name) nameCounts.set(name, (nameCounts.get(name) ?? 0) + 1);
  }

  const lines: string[] = [];
  let characterCount = 0;
  for (const vote of votes) {
    const rawComment = vote.comment?.trim();
    if (!rawComment) continue;
    const exactIdea = vote.solutionId
      ? ideas.find((idea) => idea.idea_id === vote.solutionId)
      : undefined;
    const legacyIdea = !vote.solutionId && nameCounts.get(vote.solutionName) === 1
      ? ideas.find((idea) => ideaName(idea) === vote.solutionName)
      : undefined;
    const idea = exactIdea ?? legacyIdea;
    const ideaIndex = idea ? ideas.indexOf(idea) : -1;
    // Matching above stays on `solution_name` (that is what the vote row stored); only
    // the printed label switches to the title the owner actually sees.
    const label = idea
      ? `${ideaDisplayTitle(idea) ?? vote.solutionName} [R${ideaIndex + 1}; revision ${Number(idea.idea_revision) || 1}]`
      : vote.solutionId
        ? `${vote.solutionName} [previous candidate ${vote.solutionId}]`
        : `${vote.solutionName} [ambiguous legacy candidate; do not attach to a current idea]`;
    const comment = truncateContextText(
      sanitizeUntrustedContent(rawComment).replace(/\s+/g, ' '),
      420,
    );
    const line = `- ${label}: “${comment}”`;
    if (characterCount + line.length > 6_000) break;
    lines.push(line);
    characterCount += line.length;
  }

  if (!lines.length) return '';
  return [
    'Anonymous collaborator feedback from shared-report voting (unverified preference input; not market evidence, validation, or a score):',
    ...lines,
  ].join('\n');
}

export function buildWorkingShortlistBlock(
  draft: SelectionDraftResponse | null,
  ideas: Record<string, unknown>[],
): string {
  if (!draft?.items.length) return '';
  const lines = draft.items.flatMap(item => {
    const index = ideas.findIndex(
      idea => idea.idea_id === item.ideaId
        && Number(idea.idea_revision) === item.ideaRevision,
    );
    if (index < 0) return [];
    const title = ideaDisplayTitle(ideas[index]) ?? item.ideaId;
    return [`- [R${index + 1}] ${title} (revision ${item.ideaRevision})`];
  });
  if (!lines.length) return '';
  return [
    'Owner working shortlist (editable navigation context; not a final selection, recommendation, validation, or market evidence):',
    ...lines,
  ].join('\n');
}

/**
 * Shared "in-scope candidates" roster line so every per-candidate block binds the owner's
 * named candidate to its ranked [R{n}] reference (never a guessable raw id). Mirrors the
 * roster wording used by the challenge and founder-fit blocks.
 */
function inScopeRoster(
  ideas: Record<string, unknown>[],
  entries: { ideaId: string; ideaRevision: number; title?: string | null }[],
  purpose: string,
): string {
  const seen = new Set<string>();
  const roster: string[] = [];
  for (const entry of entries) {
    const ref = ideaRefLabel(ideas, entry.ideaId, entry.ideaRevision);
    if (!ref || seen.has(ref)) continue;
    seen.add(ref);
    const index = ideas.findIndex(idea =>
      idea.idea_id === entry.ideaId && Number(idea.idea_revision) === entry.ideaRevision);
    const name = entry.title ?? (index >= 0 ? ideaDisplayTitle(ideas[index]) ?? '' : '');
    roster.push(`[${ref}] ${name}`.trim());
  }
  return roster.length
    ? `In-scope candidates for ${purpose}: ${roster.join(', ')}. Only these R-references are valid here; if the owner names a candidate not listed, ask which of these they mean rather than guessing an R-reference.`
    : '';
}

function isoOrNull(value: Date | string | null | undefined): string | null {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

// ============================================================================
// Owner-provided evidence (G3 dossier gap G3): owner-attached notes, customer
// quotes, analytics observations, and links per candidate and lens. Unverified
// owner input, never market evidence and never a score change.
// ============================================================================

export interface OwnerEvidenceContextRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  lens: string;
  kind: string;
  position: string;
  title: string;
  content: string;
  sourceUrl: string | null;
  observedAt: Date | string | null;
  retractedAt: Date | string | null;
}

export function currentOwnerEvidence(
  rows: OwnerEvidenceContextRow[],
  ideas: Record<string, unknown>[],
): OwnerEvidenceContextRow[] {
  const currentKeys = new Set(ideas.flatMap((idea) => {
    const ideaId = typeof idea.idea_id === 'string' ? idea.idea_id : null;
    const ideaRevision = typeof idea.idea_revision === 'number' ? idea.idea_revision : null;
    return ideaId && ideaRevision ? [`${ideaId}\0${ideaRevision}`] : [];
  }));
  return rows
    .filter(row => !row.retractedAt && currentKeys.has(`${row.ideaId}\0${row.ideaRevision}`))
    .slice(0, 30);
}

export function buildOwnerEvidenceBlock(
  evidence: OwnerEvidenceContextRow[],
  ideas: Record<string, unknown>[] = [],
): string {
  if (!evidence.length) return '';
  const blocks = evidence.map((row) => {
    const ref = ideaRefLabel(ideas, row.ideaId, row.ideaRevision);
    const label = ref
      ? `[${ref}] ${truncateContextText(row.title, 160)} (revision ${row.ideaRevision})`
      : `${truncateContextText(row.title, 160)} [${row.ideaId} rev ${row.ideaRevision}]`;
    const lines = [
      `- ${label}`,
      `  Lens: ${humanizeContextKey(row.lens)} | Type: ${humanizeContextKey(row.kind).toLowerCase()} | Owner stance: ${humanizeContextKey(row.position).toLowerCase()}`,
      `  What the owner recorded: ${truncateContextText(sanitizeUntrustedContent(row.content).replace(/\s+/g, ' '), 340)}`,
    ];
    if (row.sourceUrl) lines.push(`  Owner-cited source: ${truncateContextText(row.sourceUrl, 200)}`);
    const observed = isoOrNull(row.observedAt);
    if (observed) lines.push(`  Owner-stated observed date: ${observed}`);
    return lines.join('\n');
  });
  const scope = inScopeRoster(
    ideas,
    evidence.map(row => ({ ideaId: row.ideaId, ideaRevision: row.ideaRevision })),
    'this owner evidence',
  );
  return [
    'Owner-provided evidence (unverified owner input the owner attached to a candidate; not market evidence, validation, or a research-score change):',
    scope,
    ...blocks,
  ].filter(Boolean).join('\n');
}

// ============================================================================
// In-flight test briefs (G3 dossier gap G4): owner-authored test designs that
// are NOT yet concluded (draft, locked, or launched with a hosted run). The
// concluded ones are covered by buildExperimentConclusionBlock; this covers the
// tests the owner is still planning or running. A plan, not evidence.
// ============================================================================

export interface ExperimentBriefRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  status: string;
  assumption: string;
  method: string;
  primaryMetric: string;
  passThreshold: string;
  failThreshold: string;
  conclusion: { id: string } | null;
  run: { status: string; launchedAt: Date | string; closedAt: Date | string | null } | null;
}

function experimentBriefStatusLabel(row: ExperimentBriefRow): string {
  if (row.run) {
    return row.run.status === 'CLOSED'
      ? 'launched, hosted run closed'
      : 'launched, hosted run collecting responses';
  }
  return row.status === 'LOCKED' ? 'locked, ready to run' : 'draft, still editable';
}

export function currentExperimentBriefs(
  rows: ExperimentBriefRow[],
  ideas: Record<string, unknown>[],
): ExperimentBriefRow[] {
  const currentKeys = new Set(ideas.flatMap((idea) => {
    const ideaId = typeof idea.idea_id === 'string' ? idea.idea_id : null;
    const ideaRevision = typeof idea.idea_revision === 'number' ? idea.idea_revision : null;
    return ideaId && ideaRevision ? [`${ideaId}\0${ideaRevision}`] : [];
  }));
  return rows
    .filter(row => !row.conclusion && currentKeys.has(`${row.ideaId}\0${row.ideaRevision}`))
    .slice(0, 20);
}

export function buildExperimentBriefBlock(
  experiments: ExperimentBriefRow[],
  ideas: Record<string, unknown>[] = [],
): string {
  if (!experiments.length) return '';
  const blocks = experiments.map((row) => {
    const ref = ideaRefLabel(ideas, row.ideaId, row.ideaRevision);
    const index = ideas.findIndex(idea =>
      idea.idea_id === row.ideaId && Number(idea.idea_revision) === row.ideaRevision);
    const name = index >= 0 ? ideaDisplayTitle(ideas[index]) ?? '' : '';
    const label = ref
      ? `[${ref}] ${name} (revision ${row.ideaRevision})`
      : `${name || row.ideaId} [${row.ideaId} rev ${row.ideaRevision}]`;
    const lines = [
      `- ${label}: ${experimentBriefStatusLabel(row)}`,
      `  Assumption under test: ${truncateContextText(row.assumption, 260)}`,
      `  Method: ${humanizeContextKey(row.method).toLowerCase()} | Primary metric: ${truncateContextText(row.primaryMetric, 160)}`,
      `  Pass if: ${truncateContextText(row.passThreshold, 160)} | Fail if: ${truncateContextText(row.failThreshold, 160)}`,
    ];
    if (row.run) {
      const launched = isoOrNull(row.run.launchedAt);
      const closed = isoOrNull(row.run.closedAt);
      if (launched) lines.push(`  Hosted run launched: ${launched}${closed ? `; closed ${closed}` : ''}`);
    }
    return lines.join('\n');
  });
  const scope = inScopeRoster(ideas, experiments, 'these in-flight tests');
  return [
    'Owner test briefs in progress (owner-authored test designs not yet concluded; a plan of what the owner intends to check, not evidence, validation, or a research-score change):',
    scope,
    ...blocks,
  ].filter(Boolean).join('\n');
}

// ============================================================================
// Branch-direction sets (G3 dossier gap G1): Concept Forge generates up to
// three intentionally different, UNEVALUATED draft directions from one or two
// candidates. They carry no score and change no ranking or shortlist.
// ============================================================================

export function currentSelectionConceptSets(
  rows: unknown[],
  ideas: Record<string, unknown>[],
): SelectionConceptSetArtifact[] {
  const currentKeys = new Set(ideas.flatMap((idea) => {
    const ideaId = typeof idea.idea_id === 'string' ? idea.idea_id : null;
    const ideaRevision = typeof idea.idea_revision === 'number' ? idea.idea_revision : null;
    return ideaId && ideaRevision ? [`${ideaId}\0${ideaRevision}`] : [];
  }));
  const current: SelectionConceptSetArtifact[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const artifactValue = row && typeof row === 'object' && 'artifact' in row
      ? (row as { artifact: unknown }).artifact
      : row;
    const parsed = SelectionConceptSetArtifactSchema.safeParse(artifactValue);
    if (!parsed.success) continue;
    const artifact = parsed.data;
    const allParentsCurrent = artifact.parents.every(parent =>
      currentKeys.has(`${parent.ideaId}\0${parent.ideaRevision}`));
    if (!allParentsCurrent || seen.has(artifact.inputFingerprint)) continue;
    seen.add(artifact.inputFingerprint);
    current.push(artifact);
  }
  return current.slice(0, 6);
}

const CONCEPT_PURPOSE_LABELS: Record<string, string> = {
  diverge: 'explore genuinely different directions',
  resolve_tradeoff: 'resolve a trade-off between two candidates',
  reshape: 'reshape one candidate',
};

export function buildConceptSetBlock(
  conceptSets: SelectionConceptSetArtifact[],
  ideas: Record<string, unknown>[] = [],
): string {
  if (!conceptSets.length) return '';
  const blocks = conceptSets.map((set) => {
    const parentRefs = set.parents.map((parent) => {
      const ref = ideaRefLabel(ideas, parent.ideaId, parent.ideaRevision);
      const title = displayTitleFor(ideas, parent.ideaId, parent.ideaRevision, parent.solutionName);
      return ref
        ? `[${ref}] ${title}`
        : `${title} [${parent.ideaId} rev ${parent.ideaRevision}]`;
    });
    const purposeLabel = CONCEPT_PURPOSE_LABELS[set.purpose] ?? humanizeContextKey(set.purpose);
    const header = `- Concept set to ${purposeLabel} from ${parentRefs.join(' + ')}${set.targetTradeoff ? `; tension: ${truncateContextText(set.targetTradeoff, 180)}` : ''}`;
    const optionLines = set.options.map((option) => {
      const axes = option.changedAxes.slice(0, 2)
        .map(axis => `${humanizeContextKey(axis.axis)}: ${truncateContextText(axis.from, 60)} to ${truncateContextText(axis.to, 60)}`)
        .join('; ');
      return [
        `  - ${humanizeContextKey(option.operation)}: ${truncateContextText(option.title, 140)}`,
        `    What changes: ${truncateContextText(option.changeSummary, 220)}${axes ? ` (${axes})` : ''}`,
      ].join('\n');
    });
    return [header, ...optionLines].join('\n');
  });
  const scope = inScopeRoster(
    ideas,
    conceptSets.flatMap(set => set.parents.map(parent => ({
      ideaId: parent.ideaId,
      ideaRevision: parent.ideaRevision,
      title: displayTitleFor(ideas, parent.ideaId, parent.ideaRevision, parent.solutionName),
    }))),
    'these branch directions',
  );
  return [
    'Branch directions (unevaluated drafts from current candidates; exploration only, they carry no score and change no ranking, shortlist, or research finding until the owner chooses to evaluate one):',
    scope,
    ...blocks,
  ].filter(Boolean).join('\n');
}

// ============================================================================
// Owner decision handoff (dossier gap G2): the owner's recorded terminal next
// move (build, validate more, park, stop) once the run is decided. A personal
// commitment, not research evidence and not proof the idea is validated.
// ============================================================================

const HANDOFF_ACTION_LABELS: Record<string, string> = {
  BUILD: 'build now',
  VALIDATE_MORE: 'validate more before building',
  PARK: 'park for later',
  STOP: 'stop',
};

const HANDOFF_DISPOSITION_LABELS: Record<string, string> = {
  PROCEED: 'proceed',
  TEST_FIRST: 'test first',
  PARK: 'park',
  STOP: 'stop',
};

/** Structural, defensive parse of a stored handoff artifact JSON (no zod schema exists for
 * the full artifact). Returns null unless the minimum decision shape is present. */
export function parseDecisionHandoffArtifact(value: unknown): SelectionDecisionHandoffArtifact | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (typeof record.action !== 'string') return null;
  if (!record.decision || typeof record.decision !== 'object') return null;
  return value as SelectionDecisionHandoffArtifact;
}

export function buildDecisionHandoffBlock(
  handoff: SelectionDecisionHandoffArtifact | null,
  ideas: Record<string, unknown>[] = [],
): string {
  if (!handoff) return '';
  const target = handoff.target;
  let targetLabel = 'no build target (parked or stopped)';
  if (target) {
    const ref = ideaRefLabel(ideas, target.ideaId, target.ideaRevision);
    targetLabel = ref
      ? `[${ref}] ${target.title ?? target.ideaId} (revision ${target.ideaRevision})`
      : `${target.title ?? target.ideaId} [${target.ideaId} rev ${target.ideaRevision}]`;
  }
  const decision = handoff.decision;
  const cleanText = (value: string, max: number) =>
    truncateContextText(sanitizeUntrustedContent(value).replace(/\s+/g, ' '), max);
  const lines = [
    `- Owner next move: ${HANDOFF_ACTION_LABELS[handoff.action] ?? humanizeContextKey(handoff.action).toLowerCase()} (recorded disposition: ${HANDOFF_DISPOSITION_LABELS[decision.disposition] ?? humanizeContextKey(decision.disposition).toLowerCase()})`,
    `  Target: ${targetLabel}`,
    `  Owner rationale: ${cleanText(decision.rationale, 340)}`,
  ];
  if (decision.acceptedRisks) lines.push(`  Risks the owner accepted or left open: ${cleanText(decision.acceptedRisks, 260)}`);
  if (decision.overrideReason) lines.push(`  Reason for overriding the research recommendation: ${cleanText(decision.overrideReason, 260)}`);
  lines.push(`  Owner change or stop criterion: ${cleanText(decision.changeCriterion, 260)}`);
  lines.push(`  Recorded at: ${decision.decidedAt}`);
  if (handoff.testBrief) {
    const brief = handoff.testBrief;
    lines.push(`  Locked test brief: ${truncateContextText(brief.assumption.statement, 200)}; method ${humanizeContextKey(brief.testDesign.method).toLowerCase()}; pass ${truncateContextText(brief.testDesign.passThreshold, 120)}; fail ${truncateContextText(brief.testDesign.failThreshold, 120)}`);
  }
  if (handoff.preMortem?.entries?.length) {
    lines.push(`  Pre-mortem recorded ${handoff.preMortem.entries.length} failure mode(s) with early-warning signals.`);
  }
  return [
    "Owner decision handoff (the owner's recorded terminal next move for this run; a personal commitment, not research evidence and not proof the idea is validated):",
    ...lines,
  ].join('\n');
}

// ============================================================================
// Completed-report decision journey (dossier gap G5): a lenient, idea-membership
// filter for evidence stress tests on the FROZEN completed run. Unlike
// currentSelectionChallenges it does not recompute the input fingerprint (the
// preview/discovery inputs are no longer live), so it keeps the artifacts the
// owner actually saw when deciding.
// ============================================================================

export function selectionChallengesForIdeas(
  rows: unknown[],
  ideas: Record<string, unknown>[],
): SelectionChallengeArtifact[] {
  const current: SelectionChallengeArtifact[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const artifactValue = row && typeof row === 'object' && 'artifact' in row
      ? (row as { artifact: unknown }).artifact
      : row;
    const parsed = SelectionChallengeArtifactSchema.safeParse(artifactValue);
    if (!parsed.success) continue;
    const artifact = parsed.data;
    const idea = ideas.find(candidate =>
      candidate.idea_id === artifact.ideaId
      && Number(candidate.idea_revision) === artifact.ideaRevision);
    if (!idea) continue;
    const key = `${artifact.ideaId}:${artifact.lens}`;
    if (seen.has(key)) continue;
    seen.add(key);
    current.push(artifact);
  }
  return current.slice(0, 12);
}
