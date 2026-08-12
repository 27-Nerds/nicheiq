import { describe, expect, it } from "vitest";
import type { SolutionPreview } from "$lib/types/job";
import type { AlternativeSolution, IdeaValidation } from "$lib/types/report";

type RedTeamFindingField<T extends { red_team_findings?: unknown }> =
  Pick<T, "red_team_findings">;

const explicitNull = {
  solutionPreview: { red_team_findings: null } satisfies RedTeamFindingField<SolutionPreview>,
  ideaValidation: { red_team_findings: null } satisfies RedTeamFindingField<IdeaValidation>,
  alternativeSolution: { red_team_findings: null } satisfies RedTeamFindingField<AlternativeSolution>,
};

const omitted = {
  solutionPreview: {} satisfies RedTeamFindingField<SolutionPreview>,
  ideaValidation: {} satisfies RedTeamFindingField<IdeaValidation>,
  alternativeSolution: {} satisfies RedTeamFindingField<AlternativeSolution>,
};

describe("red-team finding field nullability", () => {
  it("accepts the producer's explicit null across all three report surfaces", () => {
    expect(Object.values(explicitNull).every(
      (record) => record.red_team_findings === null,
    )).toBe(true);
  });

  it("keeps omission distinct from an explicit null across all three surfaces", () => {
    expect(Object.values(omitted).every(
      (record) => !("red_team_findings" in record),
    )).toBe(true);
  });
});
