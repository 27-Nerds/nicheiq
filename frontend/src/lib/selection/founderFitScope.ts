import type {
  FounderFitArtifact,
  FounderFitReference,
  FounderFitResult,
} from "$lib/types/founderFit";

function referenceKey(reference: FounderFitReference): string {
  return `${reference.ideaId}:${reference.ideaRevision}`;
}

/**
 * A founder-fit artifact is one comparison snapshot, not a per-idea cache.
 * Only show it when its complete set of exact candidate revisions matches the
 * routed comparison scope.
 */
export function founderFitMatchesScope(
  artifact: FounderFitArtifact | null | undefined,
  references: FounderFitReference[],
): artifact is FounderFitArtifact {
  if (!artifact || artifact.results.length !== references.length) return false;

  const expected = new Set(references.map(referenceKey));
  const actual = new Set(artifact.results.map(referenceKey));
  if (expected.size !== references.length || actual.size !== artifact.results.length) return false;

  return expected.size === actual.size && [...expected].every((key) => actual.has(key));
}

export function founderFitResultFor(
  artifact: FounderFitArtifact | null | undefined,
  reference: FounderFitReference,
): FounderFitResult | null {
  return artifact?.results.find((result) => (
    result.ideaId === reference.ideaId
    && result.ideaRevision === reference.ideaRevision
  )) ?? null;
}
