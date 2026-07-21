import {
  JobStatus,
  Prisma,
  SelectionExperimentStatus,
  SelectionFinalDecisionDisposition,
  SelectionRecommendationRelation,
} from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { canonicalJsonSha256 } from '../utils/canonicalFingerprint.js';
import {
  getDiscoveryDataForJob,
  getPreviewReportForJob,
  getReportJsonForJob,
} from '../services/assetService.js';
import { prisma } from '../services/db.js';
import {
  selectionAssumptionInclude,
  serializeSelectionAssumption,
  type SelectionAssumptionWithEvidence,
} from '../services/selectionAssumptionService.js';
import { prepareSelectionChallengeInput } from '../services/selectionChallengeService.js';
import {
  materializeSelectionExperimentBrief,
} from '../services/selectionExperimentBriefService.js';
import {
  SelectionChallengeArtifactSchema,
  type SelectionChallengeConsensus,
  type SelectionChallengeLens,
  type SelectionChallengePosition,
} from '../types/selectionChallenge.js';
import {
  SelectionFinalDecisionInputSchema,
  type SelectionFinalDecisionInput,
} from '../types/selectionFinalDecision.js';
import type { FrozenSelectionPreMortem } from '../types/selectionPreMortem.js';
import { ensureIdeaIdentities, ideaName, type IdeaRecord } from '../utils/ideaIdentity.js';

const ParamsSchema = z.object({ jobId: z.string().uuid() });

type ReportRecord = Record<string, unknown>;
type Finalist = {
  ideaId: string;
  ideaRevision: number;
  solutionName: string;
  idea: IdeaRecord;
  reportEvidence: Record<string, unknown> | null;
};
type FinalDecisionRiskPrompt = {
  challengeId: string;
  challengeInputFingerprint: string;
  challengeArtifactFingerprint: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  questionId: string;
  consensus: SelectionChallengeConsensus;
  skeptic: { position: SelectionChallengePosition; summary: string };
  auditor: { position: SelectionChallengePosition; summary: string };
};

const RISK_PRIORITY: Record<SelectionChallengeConsensus, number> = {
  contradicted: 0,
  disputed: 1,
  mixed: 2,
  insufficient: 3,
  supported: 4,
};

export const selectionFinalDecisionsRouter = Router();

function sha256(value: unknown): string {
  return canonicalJsonSha256(value);
}

function normalizeName(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLowerCase();
}

function boundedIdeaSnapshot(idea: IdeaRecord) {
  const keys = [
    'idea_id', 'idea_revision', 'solution_name', 'name', 'headline', 'short_description',
    'description', 'source_pain', 'source_segment', 'value_proposition', 'critic_concern',
    'market_fit_score', 'feasibility_score', 'build_time', 'business_model',
  ];
  return Object.fromEntries(keys.flatMap(key => key in idea ? [[key, idea[key]]] : []));
}

function assumptionSnapshot(assumption: SelectionAssumptionWithEvidence) {
  const serialized = serializeSelectionAssumption(assumption, false);
  return {
    id: serialized.id,
    ideaId: serialized.ideaId,
    ideaRevision: serialized.ideaRevision,
    lens: serialized.lens,
    statement: serialized.statement,
    impactIfFalse: serialized.impactIfFalse,
    falsificationQuestion: serialized.falsificationQuestion,
    impact: serialized.impact,
    ownerState: serialized.ownerState,
    version: serialized.version,
    originChallengeId: serialized.originChallengeId,
    originQuestionId: serialized.originQuestionId,
    direction: serialized.direction,
    evidenceClass: serialized.evidenceClass,
    linkedTests: serialized.experiments,
    updatedAt: serialized.updatedAt.toISOString(),
  };
}

function reportAlternatives(report: ReportRecord): Record<string, unknown>[] {
  return Array.isArray(report.alternative_solutions)
    ? report.alternative_solutions.filter(
        (value): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value),
      )
    : [];
}

function reportEvidenceFor(name: string, report: ReportRecord): Record<string, unknown> | null {
  if (normalizeName(String(report.selected_solution_name ?? '')) === normalizeName(name)) {
    return {
      role: 'recommended',
      details: report.selected_solution_details ?? null,
      selectionRationale: report.selection_rationale ?? null,
    };
  }
  const matches = reportAlternatives(report).filter(candidate => {
    const candidateName = candidate.solution_name ?? candidate.name;
    return typeof candidateName === 'string' && normalizeName(candidateName) === normalizeName(name);
  });
  return matches.length === 1 ? { role: 'alternative', details: matches[0] } : null;
}

function exactFinalists(job: {
  id: string;
  solutionIdeas: Prisma.JsonValue | null;
  selectedSolutionIds: string[];
  selectedSolutions: string[];
}, report: ReportRecord): Finalist[] {
  const ideas = ensureIdeaIdentities(job.id, job.solutionIdeas);
  const references = job.selectedSolutionIds.length > 0
    ? job.selectedSolutionIds.map((ideaId, index) => ({ ideaId, selectedName: job.selectedSolutions[index] }))
    : job.selectedSolutions.map((selectedName) => {
        const matches = ideas.filter((idea) => {
          const name = ideaName(idea);
          return name && normalizeName(name) === normalizeName(selectedName);
        });
        if (matches.length !== 1 || !matches[0].idea_id) {
          throw new Error('FINALIST_IDENTITY_UNRESOLVED');
        }
        return { ideaId: matches[0].idea_id, selectedName };
      });
  return references.map(({ ideaId, selectedName }) => {
    const matches = ideas.filter(idea => idea.idea_id === ideaId);
    if (matches.length !== 1) throw new Error('FINALIST_IDENTITY_UNRESOLVED');
    const idea = matches[0];
    const solutionName = ideaName(idea) ?? selectedName;
    if (!solutionName || !Number.isInteger(idea.idea_revision)) {
      throw new Error('FINALIST_IDENTITY_UNRESOLVED');
    }
    return {
      ideaId,
      ideaRevision: idea.idea_revision!,
      solutionName,
      idea,
      reportEvidence: reportEvidenceFor(solutionName, report),
    };
  });
}

function resolveRecommendation(job: {
  selectedSolution: string | null;
  deepResearchRecommendedIdeaId: string | null;
  deepResearchRecommendedIdeaRevision: number | null;
}, finalists: Finalist[]) {
  if (job.deepResearchRecommendedIdeaId && job.deepResearchRecommendedIdeaRevision) {
    const exact = finalists.filter(finalist =>
      finalist.ideaId === job.deepResearchRecommendedIdeaId
      && finalist.ideaRevision === job.deepResearchRecommendedIdeaRevision
    );
    if (exact.length === 1) return { ...exact[0], identityResolution: 'exact' as const };
    throw new Error('RECOMMENDATION_IDENTITY_UNRESOLVED');
  }
  if (!job.selectedSolution) throw new Error('RECOMMENDATION_IDENTITY_UNRESOLVED');
  const matches = finalists.filter(
    finalist => normalizeName(finalist.solutionName) === normalizeName(job.selectedSolution!),
  );
  if (matches.length !== 1) throw new Error('RECOMMENDATION_IDENTITY_UNRESOLVED');
  return { ...matches[0], identityResolution: 'legacy_unique_name' as const };
}

const jobSelect = Prisma.validator<Prisma.JobSelect>()({
  id: true,
  status: true,
  solutionIdeas: true,
  selectedSolution: true,
  selectedSolutions: true,
  selectedSolutionIds: true,
  deepResearchRecommendedIdeaId: true,
  deepResearchRecommendedIdeaRevision: true,
  selectionRationale: true,
  selectionDecisionProfile: true,
  selectionFounderFit: true,
  completedAt: true,
  selectionFinalDecision: true,
  selectionChallenges: {
    select: {
      id: true,
      ideaId: true,
      ideaRevision: true,
      lens: true,
      inputFingerprint: true,
      artifact: true,
    },
    orderBy: { createdAt: 'desc' },
  },
  selectionExperiments: {
    where: { status: SelectionExperimentStatus.LOCKED },
    include: { conclusion: true, run: true },
    orderBy: { createdAt: 'asc' },
  },
  selectionOwnerEvidence: {
    where: { retractedAt: null },
    select: {
      id: true,
      ideaId: true,
      ideaRevision: true,
      lens: true,
      kind: true,
      position: true,
      title: true,
      content: true,
      sourceUrl: true,
      observedAt: true,
      inputFingerprint: true,
      createdAt: true,
      retractedAt: true,
    },
    orderBy: { createdAt: 'asc' },
  },
  selectionAssumptions: {
    include: selectionAssumptionInclude,
    orderBy: [{ ownerState: 'asc' }, { createdAt: 'asc' }],
  },
});
async function loadSources(jobId: string, userId: string) {
  const job = await prisma.job.findFirst({ where: { id: jobId, userId }, select: jobSelect });
  if (!job) return null;
  if (job.status !== JobStatus.COMPLETED) throw new Error('REPORT_NOT_COMPLETE');
  const reportValue = await getReportJsonForJob(job.id);
  if (!reportValue || typeof reportValue !== 'object' || Array.isArray(reportValue)) {
    throw new Error('REPORT_NOT_AVAILABLE');
  }
  const report = reportValue as ReportRecord;
  const finalists = exactFinalists(job, report);
  if (finalists.length === 0) throw new Error('FINALIST_IDENTITY_UNRESOLVED');
  const recommendation = resolveRecommendation(job, finalists);
  const reportSha256 = sha256(report);
  const finalistKeys = new Set(finalists.map(item => `${item.ideaId}:${item.ideaRevision}`));
  const [previewReport, discoveryData] = await Promise.all([
    getPreviewReportForJob(job.id).catch(() => null),
    getDiscoveryDataForJob(job.id).catch(() => null),
  ]);
  const currentChallengeArtifacts: Array<{
    id: string;
    artifactFingerprint: string;
  }> = [];
  const riskPrompts: FinalDecisionRiskPrompt[] = [];
  for (const finalist of finalists) {
    const candidateRows = job.selectionChallenges.filter(row =>
      row.ideaId === finalist.ideaId && row.ideaRevision === finalist.ideaRevision
    );
    const lenses = [...new Set(candidateRows.map(row => row.lens.toLowerCase() as SelectionChallengeLens))];
    for (const lens of lenses) {
      const prepared = prepareSelectionChallengeInput({
        lens,
        idea: finalist.idea,
        previewReport,
        discoveryData,
        ownerEvidence: job.selectionOwnerEvidence,
      });
      const row = candidateRows.find(candidate =>
        candidate.lens.toLowerCase() === lens
        && candidate.inputFingerprint === prepared.inputFingerprint
      );
      if (!row) continue;
      const parsed = SelectionChallengeArtifactSchema.safeParse(row.artifact);
      if (
        !parsed.success
        || parsed.data.ideaId !== finalist.ideaId
        || parsed.data.ideaRevision !== finalist.ideaRevision
        || parsed.data.lens !== lens
        || parsed.data.inputFingerprint !== row.inputFingerprint
      ) continue;
      const artifactFingerprint = sha256(parsed.data);
      currentChallengeArtifacts.push({ id: row.id, artifactFingerprint });
      const question = [...parsed.data.questions]
        .filter(item => item.consensus !== 'supported')
        .sort((left, right) => RISK_PRIORITY[left.consensus] - RISK_PRIORITY[right.consensus])[0];
      if (!question) continue;
      riskPrompts.push({
        challengeId: row.id,
        challengeInputFingerprint: row.inputFingerprint,
        challengeArtifactFingerprint: artifactFingerprint,
        ideaId: finalist.ideaId,
        ideaRevision: finalist.ideaRevision,
        lens,
        questionId: question.questionId,
        consensus: question.consensus,
        skeptic: { position: question.skeptic.position, summary: question.skeptic.summary },
        auditor: { position: question.auditor.position, summary: question.auditor.summary },
      });
    }
  }
  const finalistExperiments = job.selectionExperiments.filter(
    experiment => finalistKeys.has(`${experiment.ideaId}:${experiment.ideaRevision}`),
  );
  const conclusionSnapshots = finalistExperiments.flatMap(experiment => experiment.conclusion ? [{
    id: experiment.conclusion.id,
    experimentId: experiment.id,
    ideaId: experiment.conclusion.ideaId,
    ideaRevision: experiment.conclusion.ideaRevision,
    outcome: experiment.conclusion.outcome,
    nextAction: experiment.conclusion.nextActionSnapshot,
    ownerRationale: experiment.conclusion.ownerRationale,
    createdAt: experiment.conclusion.createdAt.toISOString(),
    snapshot: experiment.conclusion.snapshot,
  }] : []);
  const lockedTestBriefs = finalistExperiments.flatMap(experiment => {
    if (experiment.conclusion) return [];
    const brief = materializeSelectionExperimentBrief(experiment);
    if (!brief.lockedAt) throw new Error('TEST_BRIEF_INVALID');
    return [{
      experiment,
      brief,
      briefFingerprint: sha256(brief),
      runStatus: experiment.run?.status ?? null,
    }];
  });
  const ownerEvidenceSnapshots = (job.selectionOwnerEvidence ?? [])
    .filter(item => finalistKeys.has(`${item.ideaId}:${item.ideaRevision}`))
    .map(item => ({
      id: item.id,
      ideaId: item.ideaId,
      ideaRevision: item.ideaRevision,
      lens: item.lens.toLowerCase(),
      kind: item.kind,
      position: item.position,
      title: item.title,
      observedAt: item.observedAt?.toISOString() ?? null,
      createdAt: item.createdAt.toISOString(),
      recordFingerprint: item.inputFingerprint,
    }));
  const assumptionSnapshots = job.selectionAssumptions
    .filter(assumption =>
      finalistKeys.has(`${assumption.ideaId}:${assumption.ideaRevision}`)
      && assumption.ownerState !== 'RETIRED'
    )
    .map(assumptionSnapshot);
  const sourceFingerprint = sha256({
    version: 5,
    reportSha256,
    recommendation: [recommendation.ideaId, recommendation.ideaRevision],
    finalists: finalists.map(item => [item.ideaId, item.ideaRevision]),
    conclusions: conclusionSnapshots.map(item => [item.id, item.outcome]),
    lockedTestBriefs: lockedTestBriefs.map(item => [
      item.brief.experimentId,
      item.brief.idea.ideaId,
      item.brief.idea.ideaRevision,
      item.briefFingerprint,
    ]),
    ownerEvidence: ownerEvidenceSnapshots.map(item => [item.id, item.recordFingerprint]),
    challenges: currentChallengeArtifacts.map(item => [item.id, item.artifactFingerprint]),
    assumptions: assumptionSnapshots.map(item => [item.id, sha256(item)]),
  });
  return {
    job,
    report,
    finalists,
    recommendation,
    reportSha256,
    conclusionSnapshots,
    lockedTestBriefs,
    ownerEvidenceSnapshots,
    assumptionSnapshots,
    riskPrompts,
    sourceFingerprint,
  };
}

function publicSources(sources: NonNullable<Awaited<ReturnType<typeof loadSources>>>) {
  const verdict = (sources.report.executive_dashboard as ReportRecord | undefined)?.go_no_go_verdict ?? null;
  return {
    sourceFingerprint: sources.sourceFingerprint,
    recommendation: {
      ideaId: sources.recommendation.ideaId,
      ideaRevision: sources.recommendation.ideaRevision,
      solutionName: sources.recommendation.solutionName,
      identityResolution: sources.recommendation.identityResolution,
      selectionRationale: sources.report.selection_rationale ?? sources.job.selectionRationale,
      verdict,
      generatedAt: sources.report.generated_at ?? sources.job.completedAt?.toISOString() ?? null,
    },
    finalists: sources.finalists.map(finalist => ({
      ideaId: finalist.ideaId,
      ideaRevision: finalist.ideaRevision,
      solutionName: finalist.solutionName,
      reportEvidence: finalist.reportEvidence,
    })),
    conclusions: sources.conclusionSnapshots,
    lockedTestBriefs: sources.lockedTestBriefs.map(item => ({
      ...item.brief,
      briefFingerprint: item.briefFingerprint,
      runStatus: item.runStatus,
      conclusionId: null,
    })),
    riskPrompts: sources.riskPrompts,
    ownerEvidence: sources.ownerEvidenceSnapshots,
    assumptions: sources.assumptionSnapshots,
  };
}

function requestFingerprint(jobId: string, input: SelectionFinalDecisionInput): string {
  return sha256({ fingerprintSchema: 'selection-final-decision-v1', jobId, input });
}

function freezePreMortem(
  input: Extract<SelectionFinalDecisionInput, { disposition: 'PROCEED' | 'TEST_FIRST' }>,
  selected: Finalist,
  riskPrompts: FinalDecisionRiskPrompt[],
): FrozenSelectionPreMortem {
  return {
    version: 1,
    target: {
      ideaId: selected.ideaId,
      ideaRevision: selected.ideaRevision,
    },
    entries: input.preMortem.map(entry => {
      if (!entry.origin) return { ...entry, origin: null };
      const prompt = riskPrompts.find(item =>
        item.challengeId === entry.origin?.challengeId
        && item.questionId === entry.origin.questionId
        && item.ideaId === selected.ideaId
        && item.ideaRevision === selected.ideaRevision
      );
      if (!prompt) throw new Error('PRE_MORTEM_ORIGIN_STALE');
      return {
        failureMode: entry.failureMode,
        earlyWarningSignal: entry.earlyWarningSignal,
        mitigation: entry.mitigation,
        origin: {
          kind: 'SELECTION_CHALLENGE_QUESTION' as const,
          challengeId: prompt.challengeId,
          challengeInputFingerprint: prompt.challengeInputFingerprint,
          challengeArtifactFingerprint: prompt.challengeArtifactFingerprint,
          questionId: prompt.questionId,
          lens: prompt.lens,
          consensus: prompt.consensus,
          skeptic: prompt.skeptic,
          auditor: prompt.auditor,
        },
      };
    }),
  };
}

function relationFor(
  disposition: SelectionFinalDecisionDisposition,
  selected: Finalist | null,
  recommendation: Finalist,
): SelectionRecommendationRelation {
  if (disposition === SelectionFinalDecisionDisposition.PARK) return SelectionRecommendationRelation.DEFERRED;
  if (disposition === SelectionFinalDecisionDisposition.STOP) return SelectionRecommendationRelation.REJECTED;
  return selected?.ideaId === recommendation.ideaId && selected.ideaRevision === recommendation.ideaRevision
    ? SelectionRecommendationRelation.FOLLOWED
    : SelectionRecommendationRelation.OVERRIDDEN;
}

function statusFor(error: unknown): { status: number; message: string } | null {
  if (!(error instanceof Error)) return null;
  const messages: Record<string, string> = {
    REPORT_NOT_COMPLETE: 'Deep Research must be complete before recording the owner decision',
    REPORT_NOT_AVAILABLE: 'The completed report is not available',
    FINALIST_IDENTITY_UNRESOLVED: 'The Deep Research finalist identities could not be resolved safely',
    RECOMMENDATION_IDENTITY_UNRESOLVED: 'The Deep Research recommendation could not be resolved safely',
    TEST_BRIEF_INVALID: 'A locked test brief is incomplete and cannot be carried into the owner decision',
    PRE_MORTEM_ORIGIN_STALE: 'A saved risk changed; review the pre-mortem before confirming',
  };
  return messages[error.message] ? { status: 409, message: messages[error.message] } : null;
}

selectionFinalDecisionsRouter.get('/:jobId/final-decision', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = ParamsSchema.parse(req.params);
    const sources = await loadSources(jobId, req.user!.id);
    if (!sources) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    res.setHeader('Cache-Control', 'private, no-store');
    res.json({ decision: sources.job.selectionFinalDecision, ...publicSources(sources) });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Invalid job reference' });
      return;
    }
    const known = statusFor(error);
    if (known) {
      res.status(known.status).json({ error: known.message });
      return;
    }
    console.error('Failed to load final selection decision:', error);
    res.status(500).json({ error: 'Failed to load owner decision' });
  }
});

selectionFinalDecisionsRouter.post('/:jobId/final-decision', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = ParamsSchema.parse(req.params);
    const input = SelectionFinalDecisionInputSchema.parse(req.body);
    const fingerprint = requestFingerprint(jobId, input);
    const sources = await loadSources(jobId, req.user!.id);
    if (!sources) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (sources.job.selectionFinalDecision) {
      if (sources.job.selectionFinalDecision.requestFingerprint === fingerprint) {
        res.json({ decision: sources.job.selectionFinalDecision });
        return;
      }
      res.status(409).json({ error: 'An immutable owner decision already exists for this report' });
      return;
    }
    if (input.sourceFingerprint !== sources.sourceFingerprint) {
      res.status(409).json({ error: 'Decision inputs changed; refresh the memo before confirming' });
      return;
    }

    const hasTarget = input.disposition === SelectionFinalDecisionDisposition.PROCEED
      || input.disposition === SelectionFinalDecisionDisposition.TEST_FIRST;
    const selected = hasTarget
      ? sources.finalists.find(finalist =>
          finalist.ideaId === input.ideaId && finalist.ideaRevision === input.ideaRevision
        ) ?? null
      : null;
    if (hasTarget && !selected) {
      res.status(409).json({ error: 'The selected idea revision is not a Deep Research finalist' });
      return;
    }
    const selectedTestBrief = input.disposition === SelectionFinalDecisionDisposition.TEST_FIRST
      ? sources.lockedTestBriefs.find(item => item.brief.experimentId === input.testExperimentId) ?? null
      : null;
    if (input.disposition === SelectionFinalDecisionDisposition.TEST_FIRST && !selectedTestBrief) {
      res.status(409).json({ error: 'The selected locked test brief is no longer eligible for this decision' });
      return;
    }
    if (
      selectedTestBrief
      && (
        selectedTestBrief.brief.idea.ideaId !== selected?.ideaId
        || selectedTestBrief.brief.idea.ideaRevision !== selected?.ideaRevision
      )
    ) {
      res.status(409).json({ error: 'This test brief belongs to a different candidate revision' });
      return;
    }
    const relation = relationFor(input.disposition, selected, sources.recommendation);
    const overrideReason = 'overrideReason' in input ? input.overrideReason ?? null : null;
    if (relation === SelectionRecommendationRelation.OVERRIDDEN && !overrideReason) {
      res.status(400).json({ error: 'Explain why you are overriding the research recommendation' });
      return;
    }
    if (relation !== SelectionRecommendationRelation.OVERRIDDEN && overrideReason) {
      res.status(400).json({ error: 'An override reason is only valid when choosing another finalist' });
      return;
    }

    const allIdeas = ensureIdeaIdentities(sources.job.id, sources.job.solutionIdeas);
    const finalistIds = new Set(sources.finalists.map(item => item.ideaId));
    const preMortemSnapshot = hasTarget && selected
      ? freezePreMortem(input, selected, sources.riskPrompts)
      : null;
    const decisionData = {
      jobId,
      disposition: input.disposition,
      selectedIdeaId: selected?.ideaId ?? null,
      selectedIdeaRevision: selected?.ideaRevision ?? null,
      testExperimentId: selectedTestBrief?.brief.experimentId ?? null,
      testExperimentSnapshot: selectedTestBrief
        ? {
            ...selectedTestBrief.brief,
            briefFingerprint: selectedTestBrief.briefFingerprint,
            runStatusAtDecision: selectedTestBrief.runStatus,
          } as Prisma.InputJsonValue
        : Prisma.DbNull,
      preMortemSnapshot: preMortemSnapshot
        ? preMortemSnapshot as Prisma.InputJsonValue
        : Prisma.DbNull,
      recommendationRelation: relation,
      rationale: input.rationale,
      acceptedRisks: input.acceptedRisks,
      changeCriterion: input.changeCriterion,
      overrideReason,
      requestFingerprint: fingerprint,
      sourceFingerprint: sources.sourceFingerprint,
      recommendationSnapshot: {
        ...publicSources(sources).recommendation,
        reportEvidence: sources.recommendation.reportEvidence,
      } as Prisma.InputJsonValue,
      selectedIdeaSnapshot: selected ? {
        ...boundedIdeaSnapshot(selected.idea),
        reportEvidence: selected.reportEvidence,
      } as Prisma.InputJsonValue : Prisma.JsonNull,
      alternativesSnapshot: {
        deepResearchedFinalists: sources.finalists
          .filter(item => item.ideaId !== selected?.ideaId)
          .map(item => ({
            ideaId: item.ideaId,
            ideaRevision: item.ideaRevision,
            solutionName: item.solutionName,
            reportEvidence: item.reportEvidence,
          })),
        discoveryOnlyAlternatives: allIdeas
          .filter(idea => idea.idea_id && !finalistIds.has(idea.idea_id))
          .map(boundedIdeaSnapshot),
      } as Prisma.InputJsonValue,
      evidenceSnapshot: {
        reportVerdict: publicSources(sources).recommendation.verdict,
        phaseOneRationale: sources.job.selectionRationale,
        decisionProfile: sources.job.selectionDecisionProfile,
        founderFit: sources.job.selectionFounderFit,
        experimentConclusions: sources.conclusionSnapshots,
        selectedTestBrief: selectedTestBrief ? {
          ...selectedTestBrief.brief,
          briefFingerprint: selectedTestBrief.briefFingerprint,
          runStatusAtDecision: selectedTestBrief.runStatus,
        } : null,
        ownerEvidence: sources.ownerEvidenceSnapshots,
        assumptions: selected
          ? sources.assumptionSnapshots.filter(assumption =>
              assumption.ideaId === selected.ideaId
              && assumption.ideaRevision === selected.ideaRevision
            )
          : [],
      } as Prisma.InputJsonValue,
      reportSha256: sources.reportSha256,
      decidedByUserId: req.user!.id,
    };

    try {
      const decision = await prisma.selectionFinalDecision.create({ data: decisionData });
      res.status(201).json({ decision });
    } catch (error) {
      if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
        const existing = await prisma.selectionFinalDecision.findUnique({ where: { jobId } });
        if (existing?.requestFingerprint === fingerprint) {
          res.json({ decision: existing });
          return;
        }
        res.status(409).json({ error: 'Another owner decision was recorded first' });
        return;
      }
      throw error;
    }
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    const known = statusFor(error);
    if (known) {
      res.status(known.status).json({ error: known.message });
      return;
    }
    console.error('Failed to record final selection decision:', error);
    res.status(500).json({ error: 'Failed to record owner decision' });
  }
});
