import { describe, it, expect } from "vitest";
import { scoreRationale } from "./scoreRationale";
import type { SolutionPreview } from "$lib/types/job";

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
    ).toBe("Data (public): FDA registry bulk-downloadable");
    expect(scoreRationale(base({ data_acquisition_notes: "notes only" }), "data_feasibility")).toBe("notes only");
  });

  it("seo uses programmatic_seo_opportunity with a preliminary-estimate caveat", () => {
    expect(scoreRationale(base({ programmatic_seo_opportunity: "~2500 pages" }), "seo")).toBe(
      "~2500 pages (preliminary estimate, refined after keyword research)",
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

  it("market_fit appends the unverified-data-route cap clause", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "restricted" }), "market_fit"),
    ).toBe(
      "strong pain — capped at 0.40 — the data route is unverified (thin early signal; Deep Research validates)",
    );
  });

  it("market_fit appends the thin-wallet-segment cap clause", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", source_segment_payability: 0.2 }), "market_fit"),
    ).toBe(
      "strong pain — capped — this buyer segment rarely pays for tooling (thin early signal; Deep Research validates)",
    );
  });

  it("market_fit appends the shipped-incumbent-parity cap clause", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "shipped" }), "market_fit"),
    ).toBe(
      "strong pain — held at/below 0.45 — a verified incumbent ships this mechanism (thin early signal; Deep Research validates)",
    );
  });

  it("market_fit appends the partial-incumbent-parity cap clause", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "partial" }), "market_fit"),
    ).toBe(
      "strong pain — capped — an incumbent partially covers this position (thin early signal; Deep Research validates)",
    );
  });

  it("market_fit appends the free/DIY-substitute cap clause", () => {
    expect(
      scoreRationale(base({ why_it_works_short: "strong pain", incumbent_parity: "substitute" }), "market_fit"),
    ).toBe(
      "strong pain — capped — a free/DIY route covers the core outcome (thin early signal; Deep Research validates)",
    );
  });

  it("market_fit picks the smallest applicable cap when multiple conditions apply", () => {
    // unverified data route (0.40) is tighter than shipped-parity (0.45)
    expect(
      scoreRationale(
        base({ why_it_works_short: "strong pain", data_access_model: "unofficial", incumbent_parity: "shipped" }),
        "market_fit",
      ),
    ).toBe(
      "strong pain — capped at 0.40 — the data route is unverified (thin early signal; Deep Research validates)",
    );
    // substitute + thin wallet composes to 0.35 (tighter than the plain 0.55 payability cap alone)
    expect(
      scoreRationale(
        base({ why_it_works_short: "strong pain", incumbent_parity: "substitute", source_segment_payability: 0.1 }),
        "market_fit",
      ),
    ).toBe(
      "strong pain — capped — a free/DIY route covers the core outcome (thin early signal; Deep Research validates)",
    );
  });

  it("market_fit uses the cap clause alone (capitalized) when no grounded rationale exists", () => {
    expect(
      scoreRationale(base({ value_proposition: "", data_access_model: "blocked" }), "market_fit"),
    ).toBe("Capped at 0.40 — the data route is unverified (thin early signal; Deep Research validates)");
  });

  it("market_fit has no cap clause when no cap condition is detected", () => {
    expect(scoreRationale(base({ why_it_works_short: "strong pain", data_access_model: "public" }), "market_fit")).toBe(
      "strong pain",
    );
  });

  it("composite prefixes the blend note", () => {
    expect(scoreRationale(base({ why_it_works_short: "strong pain" }), "composite")).toBe(
      "Overall: blends fit, feasibility, novelty & SEO. strong pain",
    );
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
});
