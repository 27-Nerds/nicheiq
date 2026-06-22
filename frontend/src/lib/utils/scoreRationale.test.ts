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
