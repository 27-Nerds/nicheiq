import { describe, expect, it } from "vitest";
import type { SolutionPreview } from "$lib/types/job";
import type { RuledOutFinding } from "$lib/types/report";
import {
  aliasesForIdeaName,
  buildIdeaReferences,
  matchIdeaReferences,
} from "./ideaReferences";

function idea(name: string): SolutionPreview {
  return { solution_name: name } as SolutionPreview;
}

describe("ideaReferences", () => {
  it("recognizes compact analyst aliases and a trailing parenthetical scope", () => {
    const references = buildIdeaReferences([
      idea("Liquipedia Gap Detector"),
      idea("The International Scalper Audit Dashboard"),
      idea("ProMatchDesk (CS2+Dota 2)"),
    ], []);

    const matches = matchIdeaReferences(
      "Compare LiquipediaGapDetector, TIScalperAudit, and ProMatchDesk.",
      references,
    ).flatMap((segment) => segment.reference?.label ?? []);

    expect(matches).toEqual([
      "Liquipedia Gap Detector",
      "The International Scalper Audit Dashboard",
      "ProMatchDesk (CS2+Dota 2)",
    ]);
    expect(aliasesForIdeaName("ProMatchDesk (CS2+Dota 2)")).toContain("ProMatchDesk");
  });

  it("maps ruled-out ideas but does not match names embedded in larger words", () => {
    const ruledOut = [{
      pain_title: "Reporting gap",
      idea_name: "MetaDossier",
      reason: "Thin market",
    }] as RuledOutFinding[];
    const references = buildIdeaReferences([], ruledOut);

    expect(matchIdeaReferences("Open MetaDossier.", references)[1]?.reference?.kind)
      .toBe("ruled-out");
    expect(matchIdeaReferences("MetaDossierClone", references))
      .toEqual([{ text: "MetaDossierClone" }]);
  });

  it("leaves ambiguous aliases unlinked", () => {
    const references = buildIdeaReferences([
      idea("Alpha Suite: Teams"),
      idea("Alpha Suite: Enterprise"),
    ], []);

    expect(matchIdeaReferences("Alpha Suite", references))
      .toEqual([{ text: "Alpha Suite" }]);
  });
});
