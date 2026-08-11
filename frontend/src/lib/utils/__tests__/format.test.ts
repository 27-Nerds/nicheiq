import { describe, expect, it } from "vitest";
import {
  formatCurrency,
  formatMoneyRange,
  humanizeInternalJargon,
  humanizeReportProse,
  leadSentence,
  stripLeadingHeading,
} from "$lib/utils/format";

describe("formatMoneyRange", () => {
  it("re-renders sub-dollar $M values at a sensible unit", () => {
    expect(formatMoneyRange("$0.000227-$0.000454M")).toBe("$227-$454");
    expect(formatMoneyRange("$0.000001-$0.000009M")).toBe("$1-$9");
    expect(formatMoneyRange("$0.000011-$0.000045M")).toBe("$11-$45");
  });

  it("keeps both ends of a range on the unit of the larger end", () => {
    expect(formatMoneyRange("$1.03-$2.06M")).toBe("$1.03M-$2.06M");
    expect(formatMoneyRange("$0.5-$1.2M")).toBe("$0.5M-$1.2M");
    expect(formatMoneyRange("$900-$1,500")).toBe("$0.9K-$1.5K");
  });

  it("formats single values", () => {
    expect(formatMoneyRange("$12K")).toBe("$12K");
    expect(formatMoneyRange("$12000")).toBe("$12K");
    expect(formatMoneyRange("$0.0125M")).toBe("$12.5K");
    expect(formatMoneyRange("$1,030,000")).toBe("$1.03M");
    expect(formatMoneyRange("$2.5B")).toBe("$2.5B");
    expect(formatMoneyRange("$0")).toBe("$0");
  });

  it("keeps at most two decimals", () => {
    expect(formatMoneyRange("$1.23456M")).toBe("$1.23M");
    expect(formatMoneyRange("$0.000227456M")).toBe("$227.46");
  });

  it("preserves trailing qualifiers", () => {
    expect(formatMoneyRange("$0.000227-$0.000454M per year")).toBe("$227-$454 per year");
    expect(formatMoneyRange("$1.03-$2.06M ARR")).toBe("$1.03M-$2.06M ARR");
  });

  it("passes unparseable input through unchanged", () => {
    expect(formatMoneyRange("Not estimated")).toBe("Not estimated");
    expect(formatMoneyRange("N/A")).toBe("N/A");
    expect(formatMoneyRange("$29/mo")).toBe("$29/mo");
    expect(formatMoneyRange("2-5 years")).toBe("2-5 years");
    expect(formatMoneyRange("The calculated SAM is approximately $227-$454")).toBe(
      "The calculated SAM is approximately $227-$454",
    );
  });

  // The appendix's SOM tile shipped "$1-$9 in Year 1; $0.000011-$0.000045M in Year 3":
  // an anchored match normalised the first amount and passed the rest through raw.
  it("re-units every amount in a compound value, not just the first", () => {
    expect(
      formatMoneyRange("$0.000001-$0.000009M in Year 1; $0.000011-$0.000045M in Year 3"),
    ).toBe("$1-$9 in Year 1; $11-$45 in Year 3");
  });

  it("leaves a following number that is not the other end of a range alone", () => {
    expect(formatMoneyRange("$19 - 3 seats included")).toBe("$19 - 3 seats included");
    expect(formatMoneyRange("$50 Million addressable")).toBe("$50 Million addressable");
    expect(formatMoneyRange("$30-$85/month")).toBe("$30-$85/month");
  });

  it("never renders NaN and handles nullish input", () => {
    expect(formatMoneyRange(null)).toBe("");
    expect(formatMoneyRange(undefined)).toBe("");
    expect(formatMoneyRange("")).toBe("");
    expect(formatMoneyRange("$")).toBe("$");
    for (const raw of ["Not estimated", "$", "$29/mo", "", "TBD"]) {
      expect(formatMoneyRange(raw)).not.toMatch(/NaN/);
    }
  });
});

describe("formatCurrency", () => {
  it("normalises backend money strings", () => {
    expect(formatCurrency("$0.000227-$0.000454M")).toBe("$227-$454");
  });

  it("keeps its existing number and nullish behaviour", () => {
    expect(formatCurrency(1030000)).toBe("$1,030,000");
    expect(formatCurrency(null)).toBe("N/A");
    expect(formatCurrency(undefined)).toBe("N/A");
    expect(formatCurrency("Not estimated")).toBe("Not estimated");
  });
});

describe("humanizeInternalJargon", () => {
  it("replaces the raw data_access_model field name", () => {
    expect(humanizeInternalJargon("Data route unproven (data_access_model: unverified)")).toBe(
      "Data route unproven (data route: unverified)",
    );
  });

  it("replaces the raw field names the quality caveats print", () => {
    expect(
      humanizeInternalJargon(
        "is not in the selected solution's pain_points_addressed list.",
      ),
    ).toBe("is not in the selected solution's addressed problems list.");
    expect(
      humanizeInternalJargon("dashboard niche-relevant volume (1,490) vs seo_analytics total volume"),
    ).toBe("dashboard niche-relevant volume (1,490) vs SEO analytics total volume");
  });

  it("glosses the PainPoint repr the coverage checker interpolates into a caveat", () => {
    expect(
      humanizeInternalJargon(
        "severity_score=0.9 willingness_to_pay_score=0.6 representative_quote=\"I am burnt "
          + "the F out.\" source_platform='Reddit r/gamedev'",
      ),
    ).toBe(
      "severity score=0.9 commercial-intent score=0.6 representative quote=\"I am burnt "
        + "the F out.\" source platform='Reddit r/gamedev'",
    );
  });

  /**
   * THE FIFTH REPR KEY. `title` has no underscore, so the map's four snake_case names covered
   * four fifths of the dump and the suite's `INTERNAL_TOKEN` regex — which matched a
   * snake_case identifier — reported it complete.
   *
   * It cannot share the `=` lookahead the other four use. Over the 2,223,988 distinct strings
   * under `output/`, `\btitle\s*=` occurs in 6 and only one is this repr; two of the rest are
   * product advice a bare rule would corrupt, and both are asserted below.
   */
  it("glosses the repr's title, and only inside the repr", () => {
    expect(
      humanizeInternalJargon(
        "Core pain point 'title='Burnout and Mental Health Struggles' severity_score=0.9'",
      ),
    ).toBe("Core pain point 'problem title='Burnout and Mental Health Struggles' severity score=0.9'");

    // Captured shapes: an HTML snippet the SEO recommendations hand the reader — whose `=` is
    // TIGHT, so it satisfies the shared lookahead exactly — and an Open Graph example.
    const snippet = '<a href="/picky-eaters-guide/" title="Picky Eater Solutions">Learn more</a>';
    expect(humanizeInternalJargon(snippet)).toBe(snippet);
    const og = 'Example: og:title = "Ingredient Transparency Checklist"';
    expect(humanizeInternalJargon(og)).toBe(og);
  });

  /**
   * `humanizeInternalJargon` is the body of `humanizeReportProse`, an unconditional
   * FIELD-BLIND deep walk, so a bare word rule for `severity_score` reaches a `technical_
   * approach` that names it as a column of a schema the PRODUCT would define. This is the
   * only occurrence of any of the four repr names WITHOUT a following `=` in every distinct
   * prose string under `output/`, and half-translating a schema list is exactly the defect
   * that kept the research vocabulary out of this table.
   */
  it("leaves a field name alone when it is a column of the product's own schema", () => {
    const schema =
      "using a structured JSON schema (complaint, workaround, severity_score, pay_signal, "
      + "source_url).";
    expect(humanizeInternalJargon(schema)).toBe(schema);
  });

  it("renames WTP to commercial intent and labels the scale", () => {
    expect(humanizeInternalJargon("Pains show an average WTP score of 0.43 overall.")).toBe(
      "Pains show an average commercial-intent score of 43/100 overall.",
    );
    expect(humanizeInternalJargon("The pricing aligns with the 0.32 average WTP score.")).toBe(
      "The pricing aligns with the average commercial-intent score of 32/100.",
    );
    expect(humanizeInternalJargon("WTP scores averaging 0.50 support a subscription.")).toBe(
      "Commercial-intent score of 50/100 support a subscription.",
    );
    expect(humanizeInternalJargon("Average WTP of 0.40 with high budget sensitivity")).toBe(
      "Average commercial-intent score of 40/100 with high budget sensitivity",
    );
    expect(humanizeInternalJargon("Limited willingness-to-pay (WTP score 0.35)")).toBe(
      "Limited willingness-to-pay (commercial-intent score of 35/100)",
    );
    expect(humanizeInternalJargon("Given the moderate WTP (0.35) and teacher resistance")).toBe(
      "Given the moderate commercial-intent score of 35/100 and teacher resistance",
    );
  });

  it("renames a bare WTP mention with no adjacent score", () => {
    expect(humanizeInternalJargon("ranked by severity and WTP")).toBe(
      "ranked by severity and commercial intent",
    );
  });

  it("leaves an out-of-range number attached to WTP alone", () => {
    expect(humanizeInternalJargon("WTP score 43")).toBe("commercial intent score 43");
  });

  it("rewrites internal gate names, keeping the numbers exact", () => {
    expect(
      humanizeInternalJargon("Search demand sits below the 5,000-search stop-condition threshold"),
    ).toBe("Search demand sits below our 5,000-search minimum-demand bar");
    expect(humanizeInternalJargon("TAM is far below the $50M Income Potential threshold")).toBe(
      "TAM is far below the $50M scale bar we use for venture-scale opportunities",
    );
    expect(
      humanizeInternalJargon("Volume is far below the 100,000-search STRIVE threshold"),
    ).toBe("Volume is far below our 100,000-search high-growth bar");
    expect(humanizeInternalJargon("The market meets 3 of 6 STRIVE criteria")).toBe(
      "The market meets 3 of 6 market-readiness criteria",
    );
  });

  it("labels a score that leads the acronym with no 'score' noun", () => {
    expect(humanizeInternalJargon("Freemium-Lite best fits the 0.43 average WTP, mixed budget")).toBe(
      "Freemium-Lite best fits the average commercial-intent score of 43/100, mixed budget",
    );
    expect(humanizeInternalJargon("The 0.43 average WTP falls in the 0.30-0.49 discount band")).toBe(
      "The average commercial-intent score of 43/100 falls in the 0.30-0.49 discount band",
    );
  });

  it("rewrites the viability gate's criterion names", () => {
    expect(
      humanizeInternalJargon(
        "Weak viability under the mandatory stop rule: the SAM fails the Income Potential"
          + " criterion, and only 1 of 3 STRIVE criteria is met, with Enterable the only"
          + " additional criterion supported; this does not overcome the stop condition.",
      ),
    ).toBe(
      "Weak viability under our mandatory minimum-demand rule: the SAM fails the venture-scale"
        + " revenue bar, and only 1 of 3 market-readiness criteria is met, with market-entry"
        + " feasibility the only additional criterion supported; this does not overcome the"
        + " blocker.",
    );
  });

  it("re-units money quoted inside prose so a sentence cannot contradict its tile", () => {
    expect(
      humanizeInternalJargon("the calculated SAM is approximately $0.000227-$0.000454M"),
    ).toBe("the calculated SAM is approximately $227-$454");
  });

  it("relabels aggregate keyword volume as category reach", () => {
    expect(
      humanizeInternalJargon("The dataset shows exceptional aggregate demand—2,264,020 searches"),
    ).toBe("The dataset shows exceptional category reach—2,264,020 searches");
  });

  it("passes unmatched text and nullish input through untouched", () => {
    const clean = "Search volume is thin and the buyer segment is price sensitive.";
    expect(humanizeInternalJargon(clean)).toBe(clean);
    expect(humanizeInternalJargon(null)).toBe("");
    expect(humanizeInternalJargon(undefined)).toBe("");
    expect(humanizeInternalJargon("")).toBe("");
  });

  it("is idempotent, so a call site that already humanised loses nothing", () => {
    const raw = "Average WTP of 0.40 below the 5,000-search stop-condition threshold";
    expect(humanizeInternalJargon(humanizeInternalJargon(raw))).toBe(humanizeInternalJargon(raw));
  });
});

describe("humanizeReportProse", () => {
  it("reaches prose the appendix renders through untouched section components", () => {
    const humanized = humanizeReportProse({
      market_sizing: {
        serviceable_obtainable_market_y1: "$0.000001-$0.000009M",
        viability_rationale: "Fails the Income Potential criterion under the mandatory stop rule.",
        risk_factors: ["Average WTP of 0.40 with mixed budget sensitivity"],
      },
      data_quality_summary: {
        quality_caveats: ["The verifier did not confirm it (data_access_model: unverified)."],
      },
    });

    expect(humanized.market_sizing.serviceable_obtainable_market_y1).toBe("$1-$9");
    expect(humanized.market_sizing.viability_rationale).toBe(
      "Fails the venture-scale revenue bar under our mandatory minimum-demand rule.",
    );
    expect(humanized.market_sizing.risk_factors[0]).toBe(
      "Average commercial-intent score of 40/100 with mixed budget sensitivity",
    );
    expect(humanized.data_quality_summary.quality_caveats[0]).toBe(
      "The verifier did not confirm it (data route: unverified).",
    );
  });

  it("leaves machine-valued keys and unmatched reports alone", () => {
    const source = {
      idea_id: "WTP-4",
      source_url: "https://example.com/a?tab=WTP",
      niche: "Independent live music venues",
    };
    expect(humanizeReportProse(source)).toBe(source);
  });

  /**
   * A user's own words are never rewritten, and `selftext` is Reddit's name for them. The
   * walk is FIELD-BLIND, so the guard has to be in place before a rule reaches the key, not
   * after somebody reads a reworded quotation in a shipped report — which is how `body` and
   * `quote` got onto the list.
   */
  it("never rewrites a scraped post's own text", () => {
    const source = {
      social_content: [{
        selftext: "Our WTP was low so we shipped the free tier.",
        body: "Same here, WTP never justified the build.",
      }],
      rationale: "Average WTP of 0.40 across the set.",
    };
    const humanized = humanizeReportProse(source);
    expect(humanized.social_content[0].selftext).toBe(source.social_content[0].selftext);
    expect(humanized.social_content[0].body).toBe(source.social_content[0].body);
    // …while the prose around it still is.
    expect(humanized.rationale).toBe("Average commercial-intent score of 40/100 across the set.");
  });
});

describe("stripLeadingHeading", () => {
  it("drops a leading heading that only repeats its section title", () => {
    expect(stripLeadingHeading("## CAC Breakdown\n\n| Channel |\n", "CAC Breakdown")).toBe(
      "| Channel |\n",
    );
  });

  it("keeps a heading that says something else, and handles nullish input", () => {
    expect(stripLeadingHeading("## Channel mix\n\nBody", "CAC Breakdown")).toBe(
      "## Channel mix\n\nBody",
    );
    expect(stripLeadingHeading(null, "CAC Breakdown")).toBe("");
  });
});

describe("leadSentence", () => {
  // The report deck fell back to the full executive_summary (1,093 chars on the audited
  // run) because tagline and short_description were both empty.
  const SUMMARY =
    "HouseNutIndex is a pre-show settlement benchmark solution for independent music "
    + "rooms, addressing the market opportunity to make artist payouts more transparent. "
    + "It translates public wage and business-cost data into versioned benchmark ranges.";

  it("returns the opening sentence of a long passage", () => {
    const out = leadSentence(SUMMARY);
    expect(out.endsWith("more transparent.")).toBe(true);
    expect(out.length).toBeLessThanOrEqual(240);
  });

  it("returns short text unchanged", () => {
    const short = "Model and defend house-nut deductions before show day.";
    expect(leadSentence(short)).toBe(short);
  });

  it("does not split on a decimal or an abbreviation", () => {
    const out = leadSentence(
      "A tool for U.S. independent rooms sized at $1.03M today, serving operators who "
      + "need defensible numbers before a contract is signed and a show is booked. "
      + "A second sentence follows here.",
    );
    expect(out).toContain("U.S.");
    expect(out).toContain("$1.03M");
  });

  it("clamps on a word boundary when the first sentence is itself too long", () => {
    const out = leadSentence(`${"word ".repeat(80)}end.`, 60);
    expect(out.length).toBeLessThanOrEqual(61);
    expect(out.endsWith("\u2026")).toBe(true);
    expect(out).not.toMatch(/\s\u2026$/);
  });

  it("returns empty string for empty input", () => {
    expect(leadSentence(null)).toBe("");
    expect(leadSentence("   ")).toBe("");
  });
});

describe("formatMoneyRange suffix propagation", () => {
  // "$400-$3K" rendered as "$400K-$3K" in a live report — inverted and 1000x out —
  // because the high bound's K was applied to a bare low bound.
  it("does not propagate a suffix that would invert the range", () => {
    // Was "$400K-$3K": inverted and 1000x out. The range still picks ONE unit from the
    // larger bound, so 400-3,000 reads "$0.4K-$3K" — consistent with "$1.03M-$2.06M",
    // and correctly ordered, which is what actually matters.
    expect(formatMoneyRange("$400-$3K")).toBe("$0.4K-$3K");
  });

  it("still propagates a shared suffix when the range stays ordered", () => {
    expect(formatMoneyRange("$1.03-$2.06M")).toBe("$1.03M-$2.06M");
  });

  it("leaves an explicit two-suffix range alone", () => {
    expect(formatMoneyRange("$80K-$170K")).toBe("$80K-$170K");
  });

  it("never renders a low bound above its high bound", () => {
    for (const input of ["$400-$3K", "$5-$2K", "$900-$1K", "$1.03-$2.06M"]) {
      const out = formatMoneyRange(input);
      const nums = [...out.matchAll(/\$([\d.]+)([KMB])?/g)].map(
        ([, n, s]) => parseFloat(n) * ({ K: 1e3, M: 1e6, B: 1e9 }[s ?? ""] ?? 1),
      );
      if (nums.length === 2) expect(nums[0]).toBeLessThanOrEqual(nums[1]);
    }
  });
});
