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
    expect(state.notices).toEqual([]);
  });

  it("falls back to the exact saved shortlist when linked refs are stale or malformed", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/risks?idea=idea-beta:3&idea=broken"),
      job({ selectionDraft: { version: 7, items: [{ ideaId: "idea-alpha", ideaRevision: 2 }] } }),
      solutions,
    );

    expect(state.ideas.map((candidate) => candidate.solution_name)).toEqual(["Alpha"]);
    expect(state.notices.join(" ")).toContain("invalid, unavailable, or out of date");
    expect(state.notices.join(" ")).toContain("saved shortlist");
  });

  it("uses a clearly labelled preview when neither refs nor a shortlist exist", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/tests"),
      job(),
      solutions,
    );

    expect(state.ideas.map((candidate) => candidate.solution_name)).toEqual(["Alpha", "Beta"]);
    expect(state.notices).toContain("No shortlist is saved yet. Showing the current leading candidates as a preview.");
  });

  it("falls back safely from unsupported query state and explains each adjustment", () => {
    const state = resolveSelectionWorkspace(
      new URL("https://nicheiq.test/jobs/job-1/selection/alternatives?lens=money&view=score&mode=random"),
      job({ selectionDraft: { version: 1, items: [{ ideaId: "idea-gamma", ideaRevision: 1 }] } }),
      solutions,
    );

    expect(state.lens).toBe("demand");
    expect(state.compareView).toBe("market");
    expect(state.alternativeMode).toBe("recommended");
    expect(state.notices).toHaveLength(3);
  });
});

