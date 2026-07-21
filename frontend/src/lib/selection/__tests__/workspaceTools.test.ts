import { describe, expect, it } from "vitest";
import type { SolutionPreview } from "$lib/types/job";
import { workspaceIdeaKey } from "$lib/selection/workspaceTools";

function idea(overrides: Partial<SolutionPreview> = {}): SolutionPreview {
  return {
    solution_name: "Signal desk",
    idea_id: "idea-a",
    idea_revision: 2,
    ...overrides,
  } as SolutionPreview;
}

describe("workspaceIdeaKey", () => {
  it("keys on the backend idea id so a renamed idea keeps its shortlist slot", () => {
    expect(workspaceIdeaKey(idea())).toBe("idea-a");
    expect(workspaceIdeaKey(idea({ solution_name: "Renamed" }))).toBe("idea-a");
  });

  it("falls back to the name only when no id exists (legacy rows)", () => {
    expect(workspaceIdeaKey(idea({ idea_id: undefined }))).toBe("Signal desk");
  });
});
