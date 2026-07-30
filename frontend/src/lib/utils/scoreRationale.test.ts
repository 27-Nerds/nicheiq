import { describe, it, expect, afterEach } from "vitest";
import { scoreRationale, setServedCapThresholds, DEFAULT_CAP_THRESHOLDS } from "./scoreRationale";
import type { SolutionPreview } from "$lib/types/job";
import type { SelectionCapThresholds } from "$lib/types/selectionMetricExplanation";

const base = (over: Partial<SolutionPreview>): SolutionPreview =>
  ({ solution_name: "X", description: "d", value_proposition: "vp", ...over }) as SolutionPreview;

describe("scoreRationale", () => {
  it("market_fit prefers why_it_works_short, then why_it_works, then value_proposition", () => {
    expect(scoreRationale(base({ why_it_works_short: "short", why_it_works: "long" }), "market_fit")).toBe("short");
    expect(scoreRationale(base({ why_it_works: "long" }), "market_fit")).toBe("long");
    expect(scoreRationale(base({ value_proposition: "vp only" }), "market_fit")).toBe("vp only");
  });

  it("technical_feasibility uses technical_approach then data_acquisition_notes", () => {
    expect(scoreRationale(base({ technical_approach: "ta" }), "technical_feasibility")).toBe("ta");
    expect(scoreRationale(base({ data_acquisition_notes: "dn" }), "technical_feasibility")).toBe("dn");
  });

  it("data_feasibility prefixes the access model and surfaces the data note", () => {
    expect(
      scoreRationale(base({ data_acquisition_notes: "FDA registry bulk-downloadable", data_access_model: "public" }), "data_feasibility"),
    ).toBe("Data access: Public. FDA registry bulk-downloadable");
    expect(scoreRationale(base({ data_acquisition_notes: "notes only" }), "data_feasibility")).toBe("notes only");
  });

  it("seo uses programmatic_seo_opportunity with a preliminary-estimate caveat", () => {
    expect(scoreRationale(base({ programmatic_seo_opportunity: "~2500 pages" }), "seo")).toBe(
      "~2500 pages Keyword demand has not been checked in depth yet.",
    );
  });

  it("novelty contrasts conventional vs innovation when both present", () => {
    expect(
      scoreRationale(base({ conventional_approach: "generic directory", innovation_angle: "cross-references lab logs" }), "novelty"),
    ).toBe("Differs from the usual (generic directory) — cross-references lab logs");
    expect(scoreRationale(base({ innovation_angle: "just the angle" }), "novelty")).toBe("just the angle");
  });

  it("solo_dev shows build time and only appends an ops note when it flags a burden", () => {
    expect(scoreRationale(base({ estimated_development_time: "6-8 weeks" }), "solo_dev")).toBe("Est. build: 6-8 weeks");
    expect(
      scoreRationale(base({ estimated_development_time: "6 weeks", data_acquisition_notes: "needs cold-start seeding" }), "solo_dev"),
    ).toBe("Est. build: 6 weeks. needs cold-start seeding");
    // a neutral data note (no ops keyword) is NOT appended to solo-dev
    expect(
      scoreRationale(base({ estimated_development_time: "6 weeks", data_acquisition_notes: "official public API" }), "solo_dev"),
    ).toBe("Est. build: 6 weeks");
  });

  it("market_fit appends the unverified-data-route cap clause when the cap bound", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "restricted", market_fit_score: 0.4 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because the required data route is not verified. Deep Research can verify this early signal",
    );
  });

  it("market_fit appends the thin-wallet-segment cap clause when the cap bound", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", source_segment_payability: 0.2, market_fit_score: 0.55 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because this buyer segment shows weak evidence of paying for tools. Deep Research can verify this early signal",
    );
  });

  it("market_fit appends the shipped-incumbent-parity cap clause when the cap bound", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "shipped", market_fit_score: 0.45 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because a verified incumbent already provides the core mechanism. Deep Research can verify this early signal",
    );
  });

  it("does not mislabel an adversarial evidence cap as an incumbent", () => {
    expect(
      scoreRationale(
        base({
          why_it_works_short: "strong pain",
          incumbent_parity: "shipped by evidence: the proposed data source does not cover the buyer",
          red_team_verdict: "killed",
          market_fit_score: 0.45,
        }),
        "market_fit",
      ),
    ).toBe(
      "strong pain — the fit signal was reduced because adversarial evidence challenged the core mechanism. Deep Research can verify this early signal",
    );
  });

  it("market_fit appends the partial-incumbent-parity cap clause when the cap bound", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "partial", market_fit_score: 0.55 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because an incumbent already covers part of this position. Deep Research can verify this early signal",
    );
  });

  it("market_fit appends the free/DIY-substitute cap clause when the cap bound", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "substitute", market_fit_score: 0.5 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because a free or do-it-yourself route already covers the core outcome. Deep Research can verify this early signal",
    );
  });

  it("market_fit picks the smallest applicable cap when multiple conditions apply", () => {
    // unverified data route (0.40) is tighter than shipped-parity (0.45)
    expect(
      scoreRationale(
        base({ why_it_works_short: "strong pain", data_access_model: "unofficial", incumbent_parity: "shipped", market_fit_score: 0.4 }),
        "market_fit",
      ),
    ).toBe(
      "strong pain — the fit signal was reduced because the required data route is not verified. Deep Research can verify this early signal",
    );
    // substitute + thin wallet composes to 0.35 (tighter than the plain 0.55 payability cap alone)
    expect(
      scoreRationale(
        base({ why_it_works_short: "strong pain", incumbent_parity: "substitute", source_segment_payability: 0.1, market_fit_score: 0.35 }),
        "market_fit",
      ),
    ).toBe(
      "strong pain — the fit signal was reduced because a free or do-it-yourself route already covers the core outcome. Deep Research can verify this early signal",
    );
  });

  it("market_fit uses the cap clause alone (capitalized) when no grounded rationale exists", () => {
    expect(
      scoreRationale(base({ value_proposition: "", data_access_model: "blocked", market_fit_score: 0.4 }), "market_fit"),
    ).toBe("The fit signal was reduced because the required data route is not verified. Deep Research can verify this early signal");
  });

  it("market_fit omits the cap clause when the score sits well below the cap (cap never bound)", () => {
    // 0.30 with an unverified data route: the 0.40 ceiling never bit, so no "capped at" assertion.
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "restricted", market_fit_score: 0.3 }), "market_fit"),
    ).toBe("strong pain");
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "shipped", market_fit_score: 0.2 }), "market_fit"),
    ).toBe("strong pain");
  });

  it("market_fit omits the cap clause when the score is missing (assertion can't be verified)", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "restricted" }), "market_fit"),
    ).toBe("strong pain");
  });

  it("market_fit keeps the cap clause within the rounding epsilon below the cap", () => {
    // 0.396 >= 0.40 - 0.005 → the cap plausibly bound.
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "restricted", market_fit_score: 0.396 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because the required data route is not verified. Deep Research can verify this early signal",
    );
  });

  it("market_fit has no cap clause when no cap condition is detected", () => {
    expect(scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "public" }), "market_fit")).toBe(
      "strong pain",
    );
  });

  it("composite uses the grounded idea rationale without exposing its formula", () => {
    expect(scoreRationale(base({ why_it_works_short: "strong pain" }), "composite")).toBe("strong pain");
  });

  it("returns null when no grounded text exists (never fabricates)", () => {
    expect(scoreRationale(base({}), "seo")).toBeNull();
    expect(scoreRationale(base({}), "data_feasibility")).toBeNull();
    expect(scoreRationale(base({}), "solo_dev")).toBeNull();
    expect(scoreRationale(null, "market_fit")).toBeNull();
  });

  it("normalizes whitespace and clamps to <= 240 chars", () => {
    const long = "a ".repeat(300);
    const out = scoreRationale(base({ programmatic_seo_opportunity: long }), "seo")!;
    expect(out.length).toBeLessThanOrEqual(240);
    expect(scoreRationale(base({ why_it_works_short: "  spaced   out  \n text " }), "market_fit")).toBe("spaced out text");
  });

  it("clamps at a word boundary — never mid-word", () => {
    const long = Array.from({ length: 40 }, (_, i) => `investigation${i}`).join(" ");
    const out = scoreRationale(base({ why_it_works_short: long }), "market_fit")!;
    expect(out.length).toBeLessThanOrEqual(240);
    expect(out.endsWith("…")).toBe(true);
    // The kept prefix must be followed by a space in the source, i.e. it ends on a whole word.
    expect(long.startsWith(out.slice(0, -1) + " ")).toBe(true);
  });

  it("returns the unclamped rationale with { full: true }", () => {
    const long = "a ".repeat(300).trim();
    expect(scoreRationale(base({ why_it_works_short: long }), "market_fit", { full: true })).toBe(long);
  });
});

describe("scoreRationale cap-threshold injection", () => {
  afterEach(() => setServedCapThresholds(null));

  const raised: SelectionCapThresholds = {
    ...DEFAULT_CAP_THRESHOLDS,
    parityShippedMarketFitCap: 0.6,
    payabilityLowThreshold: 0.25,
    payabilityMarketFitCap: 0.7,
  };

  it("uses served thresholds for the epsilon gate without exposing the number", () => {
    setServedCapThresholds(raised);
    // 0.5 is >= default 0.45 but BELOW the served 0.60 cap → hint omitted (never bit).
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "shipped", market_fit_score: 0.5 }), "market_fit"),
    ).toBe("strong pain");
    // At the served ceiling the qualitative explanation appears.
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "shipped", market_fit_score: 0.6 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because a verified incumbent already provides the core mechanism. Deep Research can verify this early signal",
    );
  });

  it("uses the served payability_low_threshold to decide LOW payability", () => {
    setServedCapThresholds(raised);
    // 0.3 is below default 0.35 but NOT below the served 0.25 → no payability cap.
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", source_segment_payability: 0.3, market_fit_score: 0.7 }), "market_fit"),
    ).toBe("strong pain");
    // 0.2 < served 0.25 → capped at served payability cap 0.70.
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", source_segment_payability: 0.2, market_fit_score: 0.7 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because this buyer segment shows weak evidence of paying for tools. Deep Research can verify this early signal",
    );
  });

  it("per-call opts.capThresholds wins over served values", () => {
    setServedCapThresholds(raised);
    expect(
      scoreRationale(
        base({ why_it_works_short: "strong pain", incumbent_parity: "shipped", market_fit_score: 0.45 }),
        "market_fit",
        { capThresholds: DEFAULT_CAP_THRESHOLDS },
      ),
    ).toBe(
      "strong pain — the fit signal was reduced because a verified incumbent already provides the core mechanism. Deep Research can verify this early signal",
    );
  });

  it("falls back to the Python defaults after the served values are cleared", () => {
    setServedCapThresholds(raised);
    setServedCapThresholds(null);
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "shipped", market_fit_score: 0.45 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because a verified incumbent already provides the core mechanism. Deep Research can verify this early signal",
    );
  });

  it("hardcoded data-route 0.40 cap is unaffected by injected thresholds", () => {
    setServedCapThresholds({ ...DEFAULT_CAP_THRESHOLDS, paritySubstituteMarketFitCap: 0.9 });
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "restricted", market_fit_score: 0.4 }), "market_fit"),
    ).toBe(
      "strong pain — the fit signal was reduced because the required data route is not verified. Deep Research can verify this early signal",
    );
  });
});
