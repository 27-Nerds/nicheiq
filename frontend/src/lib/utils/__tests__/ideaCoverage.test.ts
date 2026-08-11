import { describe, expect, it } from "vitest";
import { buildCoverageChecklist, detectIdeaCoverage } from "../ideaCoverage";

describe("detectIdeaCoverage - audience", () => {
  it("matches via the curated role-noun list", () => {
    const result = detectIdeaCoverage("A dashboard for wedding photographers");
    expect(result.audience).toBe(true);
    expect(result.generic).toBe(false);
  });

  it("matches via the role-suffix pattern for a word outside the curated list", () => {
    // "florists" ends in -ists and isn't in the curated ROLE_NOUNS set.
    const result = detectIdeaCoverage("An ordering tool built for local florists");
    expect(result.audience).toBe(true);
  });

  it("matches via a preposition frame when the noun isn't in any word list", () => {
    const result = detectIdeaCoverage("An app for the local bakery down the street");
    expect(result.audience).toBe(true);
  });

  it("flags the generic-only gate when the only signal is a generic term", () => {
    const result = detectIdeaCoverage("An app for people");
    expect(result.audience).toBe(false);
    expect(result.generic).toBe(true);
  });

  it("does not flag generic when a specific role word is also present", () => {
    const result = detectIdeaCoverage("An app for busy freelancers, built for everyone on the team");
    expect(result.audience).toBe(true);
    expect(result.generic).toBe(false);
  });

  it("is false with no audience signal at all", () => {
    const result = detectIdeaCoverage("A tool that saves time and money");
    expect(result.audience).toBe(false);
    expect(result.generic).toBe(false);
  });

  it("does not treat an abstract goal head-NP after 'for' as an audience", () => {
    // The live E2E false positive: "UX validation" is a purpose, not a buyer —
    // the abstract-noun check must see the head NP's last word ("validation"),
    // not the words past the "of" boundary.
    const result = detectIdeaCoverage("An AI tool for UX validation of web interfaces");
    expect(result.audience).toBe(false);
    expect(result.generic).toBe(false);
  });

  it("still counts a real audience head-NP that ends in a plain plural", () => {
    const result = detectIdeaCoverage("A billing helper for small SaaS companies");
    expect(result.audience).toBe(true);
  });
});

describe("detectIdeaCoverage - problem", () => {
  it("matches via the pain lexicon", () => {
    const result = detectIdeaCoverage("Wedding photographers struggling to organize client galleries");
    expect(result.problem).toBe(true);
  });

  it("matches via a causal frame with no pain-lexicon word present", () => {
    const result = detectIdeaCoverage(
      "Photographers export galleries by hand instead of syncing automatically",
    );
    expect(result.problem).toBe(true);
  });

  it("is false with no pain language at all", () => {
    const result = detectIdeaCoverage("A dashboard for wedding photographers");
    expect(result.problem).toBe(false);
  });
});

describe("detectIdeaCoverage - delivery", () => {
  it("matches via a form noun", () => {
    const result = detectIdeaCoverage("A Chrome extension for community managers");
    expect(result.delivery).toBe(true);
  });

  it("matches via a delivery verb frame even without a form noun", () => {
    const result = detectIdeaCoverage("A system that plugs into your CRM automatically");
    expect(result.delivery).toBe(true);
  });

  it("fails when 'tool' is the only delivery-shaped word", () => {
    const result = detectIdeaCoverage("A tool for freelance photographers who miss deadlines");
    expect(result.delivery).toBe(false);
  });

  it("fails when 'platform' is the only delivery-shaped word", () => {
    const result = detectIdeaCoverage("A platform for freelance photographers who miss deadlines");
    expect(result.delivery).toBe(false);
  });

  it("fails when 'software' is the only delivery-shaped word", () => {
    const result = detectIdeaCoverage("Software for freelance photographers who miss deadlines");
    expect(result.delivery).toBe(false);
  });
});

describe("detectIdeaCoverage - combined", () => {
  it("reports all three met on a complete pitch", () => {
    const result = detectIdeaCoverage(
      "A Chrome extension for wedding photographers who struggle to organize client galleries and miss payment deadlines",
    );
    expect(result).toEqual({ audience: true, problem: true, delivery: true, generic: false });
  });

  it("reports nothing met on a bare vague pitch", () => {
    const result = detectIdeaCoverage("An AI tool for productivity");
    expect(result.audience).toBe(false);
    expect(result.problem).toBe(false);
    expect(result.delivery).toBe(false);
  });
});

describe("buildCoverageChecklist", () => {
  it("uses canonical labels for a fully-met idea", () => {
    expect(
      buildCoverageChecklist({ audience: true, problem: true, delivery: true, generic: false }),
    ).toEqual([
      { label: "Who it's for", met: true },
      { label: "Problem it solves", met: true },
      { label: "How it works", met: true },
    ]);
  });

  it("swaps in the generic-only and tool-only hints when unmet", () => {
    expect(
      buildCoverageChecklist({ audience: false, problem: false, delivery: false, generic: true }),
    ).toEqual([
      { label: "Name a narrower group", met: false },
      { label: "Problem it solves", met: false },
      { label: "Say what form it takes", met: false },
    ]);
  });
});
