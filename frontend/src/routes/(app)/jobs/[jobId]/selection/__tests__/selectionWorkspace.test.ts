import { describe, expect, it } from "vitest";
import type { Job, SolutionPreview } from "$lib/types/job";
import { resolveSelectionWorkspace } from "../selectionWorkspace";

function idea(id: string, revision: number, name: string): SolutionPreview {
  return {
    idea_id: id,
    idea_revision: revision,
    solution_name: name,
    description: `${name} description`,
    value_proposition: `${name} value`,
  };
}

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    niche: "Test niche",
    status: "AWAITING_SELECTION",
    currentStage: 1,
    currentStageName: null,
    stagesCompleted: 1,
    totalStages: 2,
    progressPercent: 50,
    errorMessage: null,
    createdAt: "2026-07-20T00:00:00.000Z",
    startedAt: null,
    completedAt: null,
    ...overrides,
  };
}

const solutions = [
  idea("idea-alpha", 2, "Alpha"),
  idea("idea-beta", 4, "Beta"),
  idea("idea-gamma", 1, "Gamma"),
];

describe("resolveSelectionWorkspace", () => {
  it("resolves exact current revisions from repeated idea parameters", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/compare?idea=idea-beta:4&idea=idea-alpha:2&view=founder"),
      job(),
      solutions,
    );

    expect(state.ideas.map((candidate) => candidate.solution_name)).toEqual(["Beta", "Alpha"]);
    expect(state.refs).toEqual([
      { ideaId: "idea-beta", ideaRevision: 4 },
      { ideaId: "idea-alpha", ideaRevision: 2 },
    ]);
    expect(state.compareView).toBe("founder");
    expect(state.scopeSource).toBe("url");
    expect(state.notices).toEqual([]);
  });

  it("does not replace stale linked revisions with the saved shortlist", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/risks?idea=idea-beta:3&idea=broken"),
      job({ selectionDraft: { version: 7, items: [{ ideaId: "idea-alpha", ideaRevision: 2 }] } }),
      solutions,
    );

    expect(state.ideas).toEqual([]);
    expect(state.scopeSource).toBe("url");
    expect(state.notices.join(" ")).toContain("invalid, unavailable, or out of date");
    // The saved shortlist is NOT substituted in, and the unresolvable ref is
    // dropped from the canonical URL (so the "out of date" notice can clear)
    // rather than re-emitted sticky.
    expect(state.canonicalQuery).not.toContain("idea-alpha");
    expect(state.canonicalQuery).not.toContain("idea=idea-beta");
  });

  it("keeps valid exact revisions authoritative when a link mixes valid and stale refs", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/compare?idea=idea-beta:4&idea=idea-alpha:1"),
      job({ selectionDraft: { version: 7, items: [{ ideaId: "idea-alpha", ideaRevision: 2 }] } }),
      solutions,
    );

    expect(state.ideas.map((candidate) => candidate.solution_name)).toEqual(["Beta"]);
    expect(state.refs).toEqual([{ ideaId: "idea-beta", ideaRevision: 4 }]);
    expect(state.scopeSource).toBe("url");
  });

  it("seeds a bare route from the saved draft and pins exact revisions into workspace links", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/compare"),
      job({ selectionDraft: { version: 7, items: [{ ideaId: "idea-alpha", ideaRevision: 2 }] } }),
      solutions,
    );

    expect(state.ideas.map((candidate) => candidate.solution_name)).toEqual(["Alpha"]);
    expect(state.scopeSource).toBe("draft");
    expect(state.canonicalQuery).toContain("idea=idea-alpha%3A2");
  });

  it("blocks a non-empty draft when any exact reference is unavailable", () => {
    const seed = {
      ...idea("idea-seed", 1, "Submitted idea"),
      source_frame: "user_seed",
      generation_operation_id: "validate",
    };
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/review"),
      job({
        entryMode: "validate_idea",
        selectionDraft: {
          version: 8,
          items: [{ ideaId: "idea-missing", ideaRevision: 2 }],
        },
      }),
      [seed, ...solutions],
    );

    expect(state.ideas).toEqual([]);
    expect(state.refs).toEqual([]);
    expect(state.scopeSource).toBe("blocked");
    expect(state.notices.join(" ")).toContain("unavailable or out of date");
    expect(state.canonicalQuery).not.toContain("idea-seed");
  });

  it("blocks a catalog with duplicate exact candidate identities", () => {
    const duplicateA = idea("idea-duplicate", 3, "First product");
    const duplicateB = idea("idea-duplicate", 3, "Different product");
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/review"),
      job({
        selectionDraft: {
          version: 4,
          items: [{ ideaId: "idea-duplicate", ideaRevision: 3 }],
        },
      }),
      [duplicateA, duplicateB],
    );

    expect(state.ideas).toEqual([]);
    expect(state.refs).toEqual([]);
    expect(state.scopeSource).toBe("blocked");
    expect(state.notices.join(" ")).toContain("identities are ambiguous");
  });

  it("blocks a validation catalog with multiple strict submitted-idea candidates", () => {
    const seedV1 = {
      ...idea("idea-seed-v1", 1, "Submitted idea v1"),
      source_frame: "user_seed",
      generation_operation_id: "validate",
    };
    const seedV2 = {
      ...idea("idea-seed-v2", 2, "Submitted idea v2"),
      source_frame: "user_seed",
      generation_operation_id: "validate",
    };
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/review"),
      job({ entryMode: "validate_idea" }),
      [seedV1, seedV2],
    );

    expect(state.ideas).toEqual([]);
    expect(state.refs).toEqual([]);
    expect(state.scopeSource).toBe("blocked");
    expect(state.notices.join(" ")).toContain("More than one current candidate");
  });

  it("uses a clearly labelled preview when neither refs nor a shortlist exist", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/tests"),
      job(),
      solutions,
    );

    expect(state.ideas.map((candidate) => candidate.solution_name)).toEqual(["Alpha", "Beta"]);
    expect(state.scopeSource).toBe("preview");
    expect(state.canonicalQuery).toContain("idea=idea-alpha%3A2");
    expect(state.canonicalQuery).toContain("idea=idea-beta%3A4");
    expect(state.notices).toContain("No shortlist is saved yet. Showing current candidates as a preview.");
  });

  it("builds a draftless preview from research scores instead of backend order", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/tests"),
      job(),
      [
        { ...idea("seed", 1, "Pinned seed"), adjusted_composite_score: 0.2 },
        { ...idea("leader", 1, "Leader"), adjusted_composite_score: 0.9 },
        { ...idea("runner", 1, "Runner-up"), adjusted_composite_score: 0.8 },
      ],
    );

    expect(state.ideas.map((candidate) => candidate.solution_name)).toEqual([
      "Leader",
      "Runner-up",
    ]);
  });

  it("falls back safely from unsupported query state and explains each adjustment", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/alternatives?lens=money&view=score&mode=random"),
      job({ selectionDraft: { version: 1, items: [{ ideaId: "idea-gamma", ideaRevision: 1 }] } }),
      solutions,
    );

    expect(state.lens).toBe("demand");
    expect(state.compareView).toBe("market");
    expect(state.alternativeMode).toBe("diverge");
    expect(state.notices).toHaveLength(3);
  });

  it("maps legacy alternative links to real generator purposes", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/alternatives?idea=idea-alpha:2&idea=idea-beta:4&mode=recommended"),
      job(),
      solutions,
    );

    expect(state.alternativeMode).toBe("resolve_tradeoff");
    expect(state.canonicalQuery).toContain("mode=resolve_tradeoff");
    expect(state.notices.join(" ")).toContain("older variants link");
  });

  it("does not offer trade-off resolution without at least two current candidates", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/alternatives?idea=idea-alpha:2&mode=resolve_tradeoff"),
      job(),
      solutions,
    );

    expect(state.alternativeMode).toBe("diverge");
    expect(state.notices.join(" ")).toContain("at least two current candidates");
  });
});
