import { describe, expect, it } from "vitest";
import { overlapWarningText, shortlistOverlaps } from "../overlapWarnings";

const GROUPS = [
  { idea_names: ["ScopeShield Post Kit", "RevisionScopeTranslator"], shared_product: "vague-note to exact-edit translator" },
  { idea_names: ["Deadline Radar", "Delivery Clock"], shared_product: "due-date tracker" },
];

/** Shorthand for a shortlisted idea whose display title matches its internal name. */
const same = (...names: string[]) => names.map((name) => ({ name, label: name }));

describe("shortlistOverlaps", () => {
  it("reports a group only once two of its members are shortlisted", () => {
    expect(shortlistOverlaps(GROUPS, same("ScopeShield Post Kit"))).toEqual([]);
    expect(shortlistOverlaps(GROUPS, same("ScopeShield Post Kit", "RevisionScopeTranslator"))).toEqual([
      {
        ideaNames: ["ScopeShield Post Kit", "RevisionScopeTranslator"],
        sharedProduct: "vague-note to exact-edit translator",
      },
    ]);
  });

  it("names the ideas the way the rest of the page does", () => {
    // overlap_groups is keyed on solution_name; the page shows headlines. Printing
    // "ConsolidatorAI and MultiEntityConsolidationCalc" beside chips reading
    // "Auto-consolidate 50+ QuickBooks/Xero trial balances" left nothing to match on.
    const groups = [{
      idea_names: ["ConsolidatorAI", "MultiEntityConsolidationCalc"],
      shared_product: "Multi-entity consolidation and elimination platform",
    }];
    const shortlisted = [
      { name: "ConsolidatorAI", label: "Auto-consolidate 50+ QuickBooks/Xero trial balances" },
      { name: "MultiEntityConsolidationCalc", label: "Multi-entity consolidation worksheets from SEC filings" },
    ];
    expect(shortlistOverlaps(groups, shortlisted)[0].ideaNames).toEqual([
      "Auto-consolidate 50+ QuickBooks/Xero trial balances",
      "Multi-entity consolidation worksheets from SEC filings",
    ]);
  });

  it("falls back to the internal name when an idea has no display title", () => {
    const groups = [{ idea_names: ["A", "B"], shared_product: "one thing" }];
    expect(shortlistOverlaps(groups, [{ name: "A", label: "" }, { name: "B", label: "Bee" }])[0].ideaNames)
      .toEqual(["A", "Bee"]);
  });

  it("narrows to the shortlisted members, not the whole group", () => {
    const groups = [{ idea_names: ["A", "B", "C"], shared_product: "one thing" }];
    expect(shortlistOverlaps(groups, same("A", "C"))[0].ideaNames).toEqual(["A", "C"]);
  });

  it("reports every colliding group", () => {
    const shortlisted = same("ScopeShield Post Kit", "RevisionScopeTranslator", "Deadline Radar", "Delivery Clock");
    expect(shortlistOverlaps(GROUPS, shortlisted)).toHaveLength(2);
  });

  it("treats a missing or empty group list as no warning", () => {
    expect(shortlistOverlaps(undefined, same("A", "B"))).toEqual([]);
    expect(shortlistOverlaps(null, same("A", "B"))).toEqual([]);
    expect(shortlistOverlaps([], same("A", "B"))).toEqual([]);
  });
});

describe("overlapWarningText", () => {
  it("names the ideas and the product they share", () => {
    expect(overlapWarningText({ ideaNames: ["A", "B"], sharedProduct: "a thing" })).toBe(
      "A and B are variants of the same product (a thing). Researching both spends two slots on one question.",
    );
  });

  it("omits the parenthetical rather than printing an empty one", () => {
    expect(overlapWarningText({ ideaNames: ["A", "B"], sharedProduct: "  " })).toBe(
      "A and B are variants of the same product. Researching both spends two slots on one question.",
    );
  });
});
