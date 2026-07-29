import { canonicalJsonSha256 } from './canonicalFingerprint.js';

export interface ExactSelectionRef {
  ideaId: string;
  ideaRevision: number;
}

/** Public confirmation fingerprint: ordered exact refs only, never display/profile data. */
export function exactSelectionFingerprint(refs: ExactSelectionRef[]): string {
  return canonicalJsonSha256(refs.map(ref => ({
    ideaId: ref.ideaId,
    ideaRevision: ref.ideaRevision,
  })));
}

/** Python work contract: compact sorted-key JSON over these exact snake-case fields. */
export function workerSelectionFingerprint(
  refs: Array<{ idea_id: string; idea_revision: number; solution_name: string }>,
): string {
  return canonicalJsonSha256(refs.map(ref => ({
    idea_id: ref.idea_id,
    idea_revision: ref.idea_revision,
    solution_name: ref.solution_name.trim().replace(/\s+/g, ' '),
  })));
}
