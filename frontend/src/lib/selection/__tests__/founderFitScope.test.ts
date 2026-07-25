import { describe, expect, it } from "vitest";
import type { FounderFitArtifact, FounderFitReference } from "$lib/types/founderFit";
import { founderFitMatchesScope, founderFitResultFor } from "../founderFitScope";

function artifact(references: FounderFitReference[]): FounderFitArtifact {
  return {
    version: 1,
    inputFingerprint: "fingerprint",
    profileSnapshot: {} as FounderFitArtifact["profileSnapshot"],
    ideaSnapshots: [],
    model: "test-model",
    createdAt: "2026-07-22T12:00:00.000Z",
    results: references.map((reference) => ({
      ...reference,
      ideaTitle: reference.ideaId,
      verdict: "fits",
      summary: "Fits",
      strongestAdvantage: "Reach",
      blockingConflict: null,
      decisionChangingUnknown: "Demand",
      sensitivity: "Budget",
      dimensions: [],
      suggestedExperiment: {} as FounderFitArtifact["results"][number]["suggestedExperiment"],
    })),
  };
}

describe("founderFitMatchesScope", () => {
  it("matches the complete set of exact candidate revisions regardless of order", () => {
    const references = [
      { ideaId: "idea-a", ideaRevision: 2 },
      { ideaId: "idea-b", ideaRevision: 4 },
    ];

    expect(founderFitMatchesScope(artifact([...references].reverse()), references)).toBe(true);
  });

  it("rejects partial, additional, stale, and duplicate candidate revisions", () => {
    const references = [
      { ideaId: "idea-a", ideaRevision: 2 },
      { ideaId: "idea-b", ideaRevision: 4 },
    ];

    expect(founderFitMatchesScope(artifact(references.slice(0, 1)), references)).toBe(false);
    expect(founderFitMatchesScope(artifact([...references, { ideaId: "idea-c", ideaRevision: 1 }]), references)).toBe(false);
    expect(founderFitMatchesScope(artifact([{ ideaId: "idea-a", ideaRevision: 1 }, references[1]]), references)).toBe(false);
    expect(founderFitMatchesScope(artifact([references[0], references[0]]), references)).toBe(false);
  });
});

describe("founderFitResultFor", () => {
  it("resolves by idea id and revision together", () => {
    const saved = artifact([
      { ideaId: "idea-a", ideaRevision: 1 },
      { ideaId: "idea-a", ideaRevision: 2 },
    ]);

    expect(founderFitResultFor(saved, { ideaId: "idea-a", ideaRevision: 2 })?.ideaRevision).toBe(2);
    expect(founderFitResultFor(saved, { ideaId: "idea-a", ideaRevision: 3 })).toBeNull();
  });
});
