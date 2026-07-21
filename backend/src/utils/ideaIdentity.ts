import { createHash } from 'node:crypto';
import type { IdeaSynthesisPatch } from '../types/ideaSynthesis.js';
import { canonicalJsonSha256 } from './canonicalFingerprint.js';

export type IdeaRecord = Record<string, unknown> & {
  idea_id?: string;
  idea_revision?: number;
  solution_name?: string;
  name?: string;
};

function validIdentity(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function validRevision(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 1;
}

function deterministicIdeaId(
  jobId: string,
  origin: string,
  operationKey: string,
  index: number,
): string {
  const digest = createHash('sha256')
    .update(`nicheiq:idea:v1\0${jobId}\0${origin}\0${operationKey}\0${index}`)
    .digest('hex')
    .slice(0, 32);
  return `idea_${digest}`;
}

/** Hash the exact candidate revision used to author a synthesis proposal. */
export function candidateSnapshotSha256(idea: IdeaRecord): string {
  return canonicalJsonSha256(idea);
}

function withIdentity(idea: IdeaRecord, ideaId: string): IdeaRecord {
  return {
    ...idea,
    idea_id: ideaId,
    idea_revision: validRevision(idea.idea_revision) ? idea.idea_revision : 1,
  };
}

/**
 * Compatibility projection for jobs created before stable idea identity existed.
 * Existing IDs are never replaced. Missing IDs are deterministic for a job and
 * original array position, so changing a display name cannot change identity.
 */
export function ensureIdeaIdentities(jobId: string, ideas: unknown): IdeaRecord[] {
  if (!Array.isArray(ideas)) return [];
  return ideas
    .filter((idea): idea is IdeaRecord => !!idea && typeof idea === 'object' && !Array.isArray(idea))
    .map((idea, index) => withIdentity(
      idea,
      validIdentity(idea.idea_id)
        ? idea.idea_id
        : deterministicIdeaId(jobId, 'legacy_backfill', 'pool', index),
    ));
}

/** Stamp ideas entering persisted storage for the first time, retry-safely. */
export function stampNewIdeaIdentities(
  jobId: string,
  ideas: unknown,
  origin: 'phase1' | 'regeneration' | 'seed',
  operationKey: string,
): IdeaRecord[] {
  if (!Array.isArray(ideas)) return [];
  return ideas
    .filter((idea): idea is IdeaRecord => !!idea && typeof idea === 'object' && !Array.isArray(idea))
    .map((idea, index) => withIdentity(
      idea,
      validIdentity(idea.idea_id)
        ? idea.idea_id
        : deterministicIdeaId(jobId, origin, operationKey, index),
    ));
}

/** A synthesis result is a new candidate, never a revision or replacement of a
 * parent. Ignore any model-supplied identity and stamp code-owned lineage. */
export function stampSynthesizedIdeaIdentity(
  jobId: string,
  idea: unknown,
  operationKey: string,
  proposal: IdeaSynthesisPatch,
  sourceMessageId: string,
): IdeaRecord {
  const record: IdeaRecord =
    idea && typeof idea === 'object' && !Array.isArray(idea)
      ? idea as IdeaRecord
      : {};
  return {
    ...record,
    idea_id: deterministicIdeaId(jobId, 'synthesis', operationKey, 0),
    idea_revision: 1,
    synthesis_operation: proposal.operation,
    synthesized_from: proposal.parents.map((parent) => ({
      idea_id: parent.ideaId,
      idea_revision: parent.ideaRevision,
      solution_name: parent.solutionName,
      contribution: parent.contribution,
    })),
    synthesis_evidence: proposal.evidence,
    synthesis_source_message_id: sourceMessageId,
    source_frame: 'owner_synthesis',
  };
}

export function ideaName(idea: IdeaRecord): string | null {
  const value = idea.solution_name ?? idea.name;
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}
