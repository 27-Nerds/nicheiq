import { getDiscoveryDataForJob } from './assetService.js';
import { prisma } from './db.js';
import { loadCurrentSelectionContext } from './currentSelectionContext.js';
import { buildSelectionDecisionState } from './selectionDecisionStateService.js';
import type { SelectionDecisionState } from '../types/selectionDecisionState.js';

export async function loadOwnedSelectionDecisionState(
  jobId: string,
  userId: string,
  decisionTools: boolean,
): Promise<SelectionDecisionState | null> {
  const job = await prisma.job.findFirst({
    where: { id: jobId, userId },
    select: {
      id: true,
      status: true,
      selectionDraft: true,
      selectionDraftVersion: true,
      selectionDecisionProfile: true,
      selectionFounderFit: true,
      selectionChallenges: {
        select: {
          id: true,
          ideaId: true,
          ideaRevision: true,
          lens: true,
          inputFingerprint: true,
          artifact: true,
        },
        orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
      },
      selectionOwnerEvidence: {
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
          createdAt: true,
          retractedAt: true,
        },
        orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
      },
      selectionAssumptions: {
        select: {
          id: true,
          ideaId: true,
          ideaRevision: true,
          lens: true,
          statement: true,
          impact: true,
          ownerState: true,
          version: true,
          originChallengeId: true,
          originQuestionId: true,
          experiments: {
            select: { id: true },
            orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
          },
        },
        orderBy: [{ createdAt: 'asc' }, { id: 'asc' }],
      },
      selectionExperiments: {
        select: {
          id: true,
          ideaId: true,
          ideaRevision: true,
          assumptionId: true,
          status: true,
          originChallengeId: true,
          originChallenge: {
            select: {
              id: true,
              ideaId: true,
              ideaRevision: true,
              lens: true,
            },
          },
          run: { select: { status: true } },
          conclusion: {
            select: {
              id: true,
              ideaId: true,
              ideaRevision: true,
              outcome: true,
              createdAt: true,
              snapshot: true,
            },
          },
        },
        orderBy: [
          { conclusion: { createdAt: 'desc' } },
          { createdAt: 'desc' },
          { id: 'desc' },
        ],
      },
    },
  });
  if (!job) return null;

  const [selection, discoveryData] = await Promise.all([
    loadCurrentSelectionContext(prisma, job.id),
    getDiscoveryDataForJob(job.id).catch(() => null),
  ]);
  if (!selection) return null;

  return buildSelectionDecisionState({
    jobId: job.id,
    status: job.status,
    solutionIdeas: selection.canonical.candidates,
    selectionDraft: job.selectionDraft,
    selectionDraftVersion: job.selectionDraftVersion,
    selectionDecisionProfile: job.selectionDecisionProfile,
    selectionFounderFit: job.selectionFounderFit,
    challenges: job.selectionChallenges,
    ownerEvidence: job.selectionOwnerEvidence,
    assumptions: job.selectionAssumptions,
    experiments: job.selectionExperiments,
    previewReport: selection.runArtifacts.verification === 'verified'
      ? selection.runArtifacts.previewReport
      : null,
    discoveryData,
    decisionTools,
  });
}
