import { SelectionDecisionHandoffAction, type SelectionDecisionHandoff } from '@prisma/client';
import { z } from 'zod';
import {
  renderDecisionHandoffMarkdown,
  type SelectionDecisionHandoffArtifact,
} from './selectionDecisionHandoffService.js';
import { FrozenSelectionExperimentBriefSchema } from './selectionExperimentBriefService.js';
import { FrozenSelectionPreMortemSchema } from '../types/selectionPreMortem.js';
import type { GithubRepository } from './githubAppService.js';
import { canonicalJsonSha256 } from '../utils/canonicalFingerprint.js';

const TargetSchema = z.object({
  ideaId: z.string().min(1),
  ideaRevision: z.number().int().positive(),
  title: z.string().nullable(),
  problem: z.string().nullable(),
  audience: z.string().nullable(),
  valueProposition: z.string().nullable(),
  proposedScope: z.array(z.string()),
  technicalApproach: z.string().nullable(),
  estimatedBuildTime: z.string().nullable(),
}).strict();

const ArtifactBaseSchema = z.object({
  jobId: z.string().uuid(),
  finalDecisionId: z.string().uuid(),
  action: z.nativeEnum(SelectionDecisionHandoffAction),
  target: TargetSchema.nullable(),
  decision: z.object({
    disposition: z.enum(['PROCEED', 'TEST_FIRST', 'PARK', 'STOP']),
    recommendationRelation: z.enum(['FOLLOWED', 'OVERRIDDEN', 'DEFERRED', 'REJECTED']),
    rationale: z.string(),
    acceptedRisks: z.string(),
    changeCriterion: z.string(),
    overrideReason: z.string().nullable(),
    decidedAt: z.string(),
  }).strict(),
  evidence: z.object({
    sourceFingerprint: z.string(),
    reportSha256: z.string(),
    recommendationSnapshot: z.record(z.unknown()),
    selectedIdeaSnapshot: z.record(z.unknown()).nullable(),
    alternativesSnapshot: z.record(z.unknown()),
    evidenceSnapshot: z.record(z.unknown()),
  }).strict(),
  executionPolicy: z.object({
    providerDispatchAllowed: z.boolean(),
    allowedOperation: z.enum([
      'CREATE_IMPLEMENTATION_ISSUE',
      'CREATE_VALIDATION_ISSUE',
    ]).nullable(),
    resumeRequiresNewOwnerDecision: z.boolean(),
    terminal: z.boolean(),
  }).strict(),
});

const ArtifactSchema = ArtifactBaseSchema.extend({
  testBrief: FrozenSelectionExperimentBriefSchema.nullable(),
  preMortem: FrozenSelectionPreMortemSchema.nullable(),
}).strict();

const DestinationSchema = z.object({
  repositoryId: z.string().regex(/^\d+$/),
  owner: z.string().min(1),
  name: z.string().min(1),
  fullName: z.string().min(3),
}).strict();

const RequestSchema = z.object({
  title: z.string().min(1).max(256),
  body: z.string().min(1),
}).strict();

export const GithubDispatchPayloadSchema = z.object({
  version: z.literal(1),
  destination: DestinationSchema,
  request: RequestSchema,
}).strict();

export type GithubDispatchPayload = z.infer<typeof GithubDispatchPayloadSchema>;

export interface GithubIssuePreview {
  provider: 'GITHUB';
  adapterVersion: 1;
  connectionId: string;
  payloadFingerprint: string;
  payload: GithubDispatchPayload;
}

function fingerprint(value: unknown): string {
  return canonicalJsonSha256(value);
}

function issueTitle(action: SelectionDecisionHandoffAction, targetTitle: string): string {
  const prefix = action === SelectionDecisionHandoffAction.BUILD ? 'Build' : 'Validate';
  const title = `${prefix}: ${targetTitle}`;
  return title.length <= 256 ? title : `${title.slice(0, 255)}…`;
}

export function materializeGithubIssuePreview(
  handoff: SelectionDecisionHandoff,
  connectionId: string,
  repository: GithubRepository,
): GithubIssuePreview {
  const artifact = ArtifactSchema.parse(handoff.artifact);
  const expectedOperation = handoff.action === SelectionDecisionHandoffAction.BUILD
    ? 'CREATE_IMPLEMENTATION_ISSUE'
    : handoff.action === SelectionDecisionHandoffAction.VALIDATE_MORE
      ? 'CREATE_VALIDATION_ISSUE'
      : null;
  if (
    !expectedOperation
    || !artifact.executionPolicy.providerDispatchAllowed
    || artifact.executionPolicy.allowedOperation !== expectedOperation
    || artifact.action !== handoff.action
    || !artifact.target
    || artifact.target.ideaId !== handoff.ideaId
    || artifact.target.ideaRevision !== handoff.ideaRevision
  ) {
    throw new Error('GITHUB_HANDOFF_NOT_DISPATCHABLE');
  }
  if (handoff.action === SelectionDecisionHandoffAction.VALIDATE_MORE) {
    const evidenceBrief = FrozenSelectionExperimentBriefSchema.safeParse(
      artifact.evidence.evidenceSnapshot.selectedTestBrief,
    );
    if (
      !artifact.testBrief
      || !evidenceBrief.success
      || artifact.testBrief.idea.ideaId !== artifact.target.ideaId
      || artifact.testBrief.idea.ideaRevision !== artifact.target.ideaRevision
      || artifact.testBrief.experimentId !== evidenceBrief.data.experimentId
      || artifact.testBrief.briefFingerprint !== evidenceBrief.data.briefFingerprint
    ) {
      throw new Error('GITHUB_HANDOFF_NOT_DISPATCHABLE');
    }
  } else if (artifact.testBrief !== null) {
    throw new Error('GITHUB_HANDOFF_NOT_DISPATCHABLE');
  }
  if (
    (
      !artifact.preMortem
      || artifact.preMortem.target.ideaId !== artifact.target.ideaId
      || artifact.preMortem.target.ideaRevision !== artifact.target.ideaRevision
    )
  ) {
    throw new Error('GITHUB_HANDOFF_NOT_DISPATCHABLE');
  }
  if (!repository.has_issues) throw new Error('GITHUB_ISSUES_DISABLED');
  const [owner, name, ...extra] = repository.full_name.split('/');
  if (!owner || !name || extra.length || repository.full_name !== `${owner}/${name}`) {
    throw new Error('GITHUB_REPOSITORY_INVALID');
  }
  const targetTitle = artifact.target.title?.trim() || artifact.target.ideaId;
  const adapterVersion = 1 as const;
  const body = `${renderDecisionHandoffMarkdown(
    artifact as SelectionDecisionHandoffArtifact,
    handoff.inputFingerprint,
  ).trimEnd()}\n\n<!-- nicheiq-handoff:${handoff.id} -->\n`;
  const payload = GithubDispatchPayloadSchema.parse({
    version: 1,
    destination: {
      repositoryId: String(repository.id),
      owner,
      name,
      fullName: repository.full_name,
    },
    request: {
      title: issueTitle(handoff.action, targetTitle),
      body,
    },
  });
  return {
    provider: 'GITHUB',
    adapterVersion,
    connectionId,
    payload,
    payloadFingerprint: fingerprint({
      version: adapterVersion,
      handoffInputFingerprint: handoff.inputFingerprint,
      adapter: { key: 'GITHUB', version: adapterVersion },
      connectionId,
      destination: payload.destination,
      request: payload.request,
    }),
  };
}
