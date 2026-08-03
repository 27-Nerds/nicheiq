import { cleanup, render, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { Report } from "$lib/types/report";
import ReportBrief from "../ReportBrief.svelte";
import ReportEvidenceSummary from "../ReportEvidenceSummary.svelte";
import ReportPlanSummary from "../ReportPlanSummary.svelte";

afterEach(cleanup);

function report(overrides: Partial<Report> = {}): Report {
  return {
    niche: "Kubernetes model serving",
    executive_summary: "A generated summary.",
    selected_solution_name: "Cold Start Atlas",
    selection_rationale: "The recommendation changed after validation.",
    competitor_profiles: [],
    generated_at: "2026-07-25T12:00:00.000Z",
    ...overrides,
  };
}

describe("ReportBrief", () => {
  it("qualifies a positive recommendation when its evidence is limited", () => {
    const view = render(ReportBrief, {
      props: {
        report: report({
          executive_dashboard: {
            recommended_solution_snapshot: {
              name: "Cold Start Atlas",
              tagline: "Tune model cold starts with evidence",
              core_value_prop: "A long generated value proposition.",
              project_type: "SaaS",
            },
            go_no_go_verdict: {
              verdict: "Go",
              rationale: "Market fit 0.72 and feasibility 0.68.",
              risk_level: "Low",
              primary_concern: "Only a small source set was retained",
            },
            core_pain_point: {
              title: "Cold starts are unpredictable",
              severity_score: 0.6,
              commercial_intent_score: 0.6,
              representative_quote: "We cannot tune what we cannot measure.",
              source_platform: "reddit",
            },
            key_metrics: {
              total_keyword_search_volume: 0,
              tier0_keyword_count: 0,
              tier1_keyword_count: 0,
              tier2_keyword_count: 0,
              tier3_keyword_count: 0,
              tier4_keyword_count: 0,
              total_keyword_count: 0,
              primary_competitor_count: 0,
              avg_pain_point_severity: 0,
              avg_commercial_intent: 0,
              social_evidence_threads: 0,
            },
            confidence_score: 0.68,
          },
          selected_solution_details: {
            solution_name: "Cold Start Atlas",
            headline: "Tune model cold starts with evidence",
            short_description: "A concise product promise.",
            description: "A detailed product description.",
          },
          data_quality_summary: {
            overall_data_quality: "LOW",
            quality_caveats: ["No social evidence was retained."],
          },
        }),
        evidenceHref: "/report?view=evidence",
        planHref: "/report?view=plan",
      },
    });

    expect(view.getByText("Go · evidence-limited")).toBeInTheDocument();
    expect(view.getByText("A concise product promise.")).toBeInTheDocument();
    expect(view.getByRole("link", { name: /Review the evidence/ })).toHaveAttribute(
      "href",
      "/report?view=evidence",
    );
    expect(view.queryByText(/market fit 0\.72/i)).not.toBeInTheDocument();
  });

  it("preserves prior reasoning without rewriting arbitrary decimals", () => {
    const view = render(ReportBrief, {
      props: {
        report: report({
          original_selection_reasoning: "Market fit 0.72 and feasibility 0.68.",
        }),
        evidenceHref: "/report?view=evidence",
        planHref: "/report?view=plan",
      },
    });

    expect(view.getByText("Market fit 0.72 and feasibility 0.68.")).toBeInTheDocument();
  });

  it("counts deduplicated quality caveats consistently", () => {
    const repeatedCaveat = "Only a small source set was retained.";
    const view = render(ReportBrief, {
      props: {
        report: report({
          data_quality_summary: {
            overall_data_quality: "HIGH",
            quality_caveats: [repeatedCaveat, repeatedCaveat],
          },
        }),
        evidenceHref: "/report?view=evidence",
        planHref: "/report?view=plan",
      },
    });

    expect(view.getByText("1 documented caveat")).toBeInTheDocument();
    expect(view.getByText(/1 research caveat is documented with the sources/)).toBeInTheDocument();
  });

  it("keeps structured verdict adjustments available without exposing raw score rationale", () => {
    const view = render(ReportBrief, {
      props: {
        report: report({
          executive_dashboard: {
            recommended_solution_snapshot: {
              name: "Cold Start Atlas",
              tagline: "Tune model cold starts with evidence",
              core_value_prop: "A long generated value proposition.",
              project_type: "SaaS",
            },
            go_no_go_verdict: {
              verdict: "Conditional",
              rationale: "Market fit 0.72 and feasibility 0.68.",
              risk_level: "Medium",
              primary_concern: "Validate demand before committing.",
              trend_context: "Declining demand changed the recommendation.",
              payability_context: "The buyer has a low subscription ceiling.",
            },
            core_pain_point: {
              title: "Cold starts are unpredictable",
              severity_score: 0.6,
              commercial_intent_score: 0.6,
              representative_quote: "We cannot tune what we cannot measure.",
              source_platform: "reddit",
            },
            key_metrics: {
              total_keyword_search_volume: 0,
              tier0_keyword_count: 0,
              tier1_keyword_count: 0,
              tier2_keyword_count: 0,
              tier3_keyword_count: 0,
              tier4_keyword_count: 0,
              total_keyword_count: 0,
              primary_competitor_count: 0,
              avg_pain_point_severity: 0,
              avg_commercial_intent: 0,
              social_evidence_threads: 12,
            },
            confidence_score: 0.68,
          },
        }),
        evidenceHref: "/report?view=evidence",
        planHref: "/report?view=plan",
      },
    });

    expect(view.getByText("What changed the verdict")).toBeInTheDocument();
    expect(view.getByText("Declining demand changed the recommendation.")).toBeInTheDocument();
    expect(view.getByText("The buyer has a low subscription ceiling.")).toBeInTheDocument();
    expect(view.queryByText("Market fit 0.72 and feasibility 0.68.")).not.toBeInTheDocument();
  });

  // The blocker used to be the score artifact while the actual refutation sat inside a
  // collapsed accordion, so the stated reason was the least useful one available.
  it("states the red-team refutation as the blocker, not the score artifact", () => {
    const redTeam =
      "FDA already provides searchable refusal data by country/area and product";
    const scoreArtifact = "Limited market fit signals soft product-market alignment";
    const view = render(ReportBrief, {
      props: {
        report: report({
          executive_summary: "OriginSafetyClearanceIndex remains the selected solution.",
          executive_dashboard: {
            go_no_go_verdict: {
              verdict: "No-Go",
              rationale: "Blocked.",
              risk_level: "High",
              primary_concern: scoreArtifact,
              red_team_context: redTeam,
            },
          } as never,
        }),
        evidenceHref: "/report?view=evidence",
        planHref: "/report?view=plan",
      },
    });

    expect(view.getByText(new RegExp(`Main blocker: ${redTeam}`))).toBeInTheDocument();
    // Nothing the verdict recorded is dropped — the score artifact moves to second place.
    expect(view.getByText(new RegExp(`Also unresolved: ${scoreArtifact}`))).toBeInTheDocument();
    // Promoted out of the accordion, so it cannot print twice on one screen.
    expect(view.queryByText("Red-team review")).not.toBeInTheDocument();
  });

  // The generated summary argues for building because it was written before the verdict.
  it("frames the in-full narrative against the verdict it was written before", () => {
    const view = render(ReportBrief, {
      props: {
        report: report({
          executive_summary:
            "OriginSafetyClearanceIndex remains the selected solution and should be tested.",
          selected_solution_details: {
            description: "A generated summary.",
            short_description: "A concise product promise.",
          },
          executive_dashboard: {
            go_no_go_verdict: {
              verdict: "No-Go",
              rationale: "Blocked.",
              risk_level: "High",
              primary_concern: "A blocker.",
            },
          } as never,
        }),
        evidenceHref: "/report?view=evidence",
        planHref: "/report?view=plan",
      },
    });

    expect(view.getByText(/not as a recommendation to build/)).toBeInTheDocument();
    // The generated prose itself is never rewritten.
    expect(
      view.getByText(/remains the selected solution and should be tested/),
    ).toBeInTheDocument();
  });
});

describe("ReportEvidenceSummary", () => {
  it("keeps the decision summary primary and links to explicit full detail", () => {
    const view = render(ReportEvidenceSummary, {
      props: {
        report: report(),
        topic: "demand",
        fullDetailHref: "/report?view=evidence&topic=demand&detail=full",
      },
    });

    expect(
      view.getByRole("heading", { name: "What evidence supports the selected problem?" }),
    ).toBeInTheDocument();
    expect(view.getByText("Niche source coverage unavailable")).toBeInTheDocument();
    expect(view.getByRole("link", { name: /Open research appendix/ })).toHaveAttribute(
      "href",
      "/report?view=evidence&topic=demand&detail=full",
    );
  });

  it("does not imply repeated evidence when an artifact has no social records", () => {
    const view = render(ReportEvidenceSummary, {
      props: {
        report: report({
          research_metadata: { reddit_posts_analyzed: 0 },
          detailed_pain_points: [
            {
              title: "Cold starts are unpredictable",
              description: "A report-retained problem statement.",
              mention_count: 0,
              severity_score: 0.6,
              commercial_intent: 0.6,
              opportunity_level: "medium",
              representative_quotes: [],
              source_platforms: [],
              categories: [],
              source_post_ids: [],
            },
          ],
        }),
        topic: "demand",
      },
    });

    expect(view.getByText("No niche social records")).toBeInTheDocument();
    expect(view.getByText("Problem this idea addresses")).toBeInTheDocument();
    expect(view.getByText(/No selected-solution pain match was retained/i)).toBeInTheDocument();
    expect(view.getByText("Broader niche context")).toBeInTheDocument();
    expect(view.queryByText("What the research repeatedly found")).not.toBeInTheDocument();
    expect(
      view.getByText(/no saved social-evidence records attached/i),
    ).toBeInTheDocument();
  });

  it("keeps the selected problem primary when the niche-wide winner is different", () => {
    const selectedPainTitle = "Cannot balance truck stock against return-trip risk";
    const nicheWinnerTitle = "Cannot maintain one appliance-specific record";
    const view = render(ReportEvidenceSummary, {
      props: {
        report: report({
          executive_dashboard: {
            recommended_solution_snapshot: {
              name: "TruckStockOptimizer",
              tagline: "Right-size truck inventory",
              core_value_prop: "Reduce return trips without excess stock.",
              project_type: "SaaS",
            },
            go_no_go_verdict: {
              verdict: "Conditional",
              rationale: "Validate the inventory workflow.",
              risk_level: "Medium",
              primary_concern: null,
            },
            core_pain_point: {
              title: selectedPainTitle,
              severity_score: 0.81,
              commercial_intent_score: 0.55,
              representative_quote: "I either carry too much or drive back for parts.",
              source_platform: "reddit",
            },
            key_metrics: {
              total_keyword_search_volume: 0,
              tier0_keyword_count: 0,
              tier1_keyword_count: 0,
              tier2_keyword_count: 0,
              tier3_keyword_count: 0,
              tier4_keyword_count: 0,
              total_keyword_count: 0,
              primary_competitor_count: 0,
              avg_pain_point_severity: 0.79,
              avg_commercial_intent: 0.58,
              social_evidence_threads: 119,
            },
            confidence_score: 0.7,
          },
          selected_solution_details: {
            solution_name: "TruckStockOptimizer",
            headline: "Right-size every service truck",
            short_description: "A selected solution.",
            description: "A selected solution.",
            target_personas: ["Owners with 2-50 technicians"],
            pain_points_addressed: [selectedPainTitle],
          },
          niche_context: {
            niche_input: "Appliance repair businesses with 5-20 technicians",
            niche_description: "Growth-stage appliance repair operators.",
            market_segments: ["Growth-stage operators"],
            industry_boundaries: "Appliance repair",
            resolved_primary_audience: "Growth-stage appliance repair operators (5-20 technicians)",
          },
          audience_mapping: {
            primary_target_segment: "Growth-stage appliance repair operators (5-20 technicians)",
          },
          pain_point_analytics: {
            total_pain_points: 2,
            top_pain_point_title: nicheWinnerTitle,
            quadrant_distribution: {
              high_severity_high_wtp: 2,
              high_severity_low_wtp: 0,
              low_severity_high_wtp: 0,
              low_severity_low_wtp: 0,
            },
          },
          detailed_pain_points: [
            {
              title: nicheWinnerTitle,
              description: "The niche-wide highest-ranked problem.",
              mention_count: 20,
              severity_score: 0.9,
              commercial_intent: 0.7,
              opportunity_level: "high",
              representative_quotes: ["Records are fragmented."],
              source_platforms: ["reddit"],
              categories: [],
              source_post_ids: ["global-1"],
            },
            {
              title: selectedPainTitle,
              description: "The problem explicitly linked to the selected idea.",
              mention_count: 12,
              severity_score: 0.81,
              commercial_intent: 0.55,
              opportunity_level: "high",
              representative_quotes: ["I either carry too much or drive back for parts."],
              source_platforms: ["reddit"],
              categories: [],
              source_post_ids: ["selected-1"],
            },
          ],
        }),
        topic: "demand",
      },
    });

    expect(
      view.getByText("Growth-stage appliance repair operators (5-20 technicians)"),
    ).toBeInTheDocument();
    expect(view.queryByText("Owners with 2-50 technicians")).not.toBeInTheDocument();
    expect(view.getByText("119 niche social records reviewed")).not.toHaveClass("positive");

    const selectedGroup = view.getByRole("heading", { name: "Problem this idea addresses" })
      .closest(".finding-group");
    expect(selectedGroup).not.toBeNull();
    expect(within(selectedGroup as HTMLElement).getByText(selectedPainTitle)).toBeInTheDocument();
    expect(within(selectedGroup as HTMLElement).queryByText(nicheWinnerTitle)).not.toBeInTheDocument();
    expect(within(selectedGroup as HTMLElement).getByText(/Severity 81\/100/)).toBeInTheDocument();

    const broaderContext = view.getByRole("heading", { name: "Broader niche context" })
      .closest(".supporting-section");
    expect(broaderContext).not.toBeNull();
    expect(within(broaderContext as HTMLElement).getByText(nicheWinnerTitle)).toBeInTheDocument();
    expect(
      within(broaderContext as HTMLElement).getByText(/not claims about what the selected idea addresses/i),
    ).toBeInTheDocument();
  });

  it("does not substitute a niche-wide problem when no selected pain was retained", () => {
    const nicheWinnerTitle = "A niche-wide problem with no selected-solution link";
    const view = render(ReportEvidenceSummary, {
      props: {
        report: report({
          pain_point_analytics: {
            total_pain_points: 1,
            top_pain_point_title: nicheWinnerTitle,
            quadrant_distribution: {
              high_severity_high_wtp: 1,
              high_severity_low_wtp: 0,
              low_severity_high_wtp: 0,
              low_severity_low_wtp: 0,
            },
          },
          detailed_pain_points: [
            {
              title: nicheWinnerTitle,
              description: "A retained niche problem.",
              mention_count: 4,
              severity_score: 0.8,
              commercial_intent: 0.7,
              opportunity_level: "high",
              representative_quotes: [],
              source_platforms: [],
              categories: [],
              source_post_ids: [],
            },
          ],
        }),
        topic: "demand",
      },
    });

    const selectedGroup = view.getByRole("heading", { name: "Problem this idea addresses" })
      .closest(".finding-group");
    expect(selectedGroup).not.toBeNull();
    expect(
      within(selectedGroup as HTMLElement).getByText(/No selected-solution pain match was retained/i),
    ).toBeInTheDocument();
    expect(within(selectedGroup as HTMLElement).queryByText(nicheWinnerTitle)).not.toBeInTheDocument();
  });

  it("presents retained idea pricing as a hypothesis when structured pricing research is absent", () => {
    const pricingHypothesis = "Test a $39-$79 monthly paid pilot before committing to the model.";
    const view = render(ReportEvidenceSummary, {
      props: {
        report: report({
          selected_solution_details: {
            description: "A generated summary.",
            pricing_strategy: pricingHypothesis,
            tags: { monetization: "subscription" },
          },
        }),
        topic: "market",
      },
    });

    expect(view.getByText("Idea-stage hypothesis")).toBeInTheDocument();
    expect(view.getByRole("heading", { name: "Subscription hypothesis" })).toBeInTheDocument();
    expect(view.getByText(pricingHypothesis)).toBeInTheDocument();
    expect(view.getByText(/Structured pricing and monetization research was not generated/i))
      .toBeInTheDocument();
  });
});

describe("ReportPlanSummary", () => {
  it("shows the action sequence without repeating the legacy acquisition essay", () => {
    const view = render(ReportPlanSummary, {
      props: {
        report: report({
          next_steps: ["Interview five qualified buyers.", "Prototype the critical workflow."],
          acquisition_strategy_summary: "Legacy acquisition essay that should not appear here.",
        }),
        topic: "first-30-days",
      },
    });

    expect(view.getByText("Interview five qualified buyers.")).toBeInTheDocument();
    expect(view.getByText("Sequence only")).toBeInTheDocument();
    expect(view.queryByText("Legacy acquisition essay that should not appear here.")).not.toBeInTheDocument();
    expect(
      view.queryByRole("link", { name: /Open implementation appendix/ })
    ).not.toBeInTheDocument();
  });

  it("links a capped summary to the complete weekly playbook", () => {
    const view = render(ReportPlanSummary, {
      props: {
        report: report({
          go_to_market_blueprint: {
            first_30_days_playbook: {
              week_1_actions: ["W1 A", "W1 B"],
              week_2_actions: ["W2 A", "W2 B"],
              week_3_actions: ["W3 A", "W3 B"],
              week_4_actions: ["W4 A", "W4 B"],
              success_metrics: ["Five interviews completed"],
            },
          } as never,
        }),
        topic: "first-30-days",
        fullDetailHref:
          "/report?view=plan&topic=launch&detail=full#first-30-days-playbook",
      },
    });

    expect(view.getByText("2 additional actions are grouped by week in the full playbook.")).toBeInTheDocument();
    expect(view.getByRole("link", { name: /Open full 30-day playbook/ })).toHaveAttribute(
      "href",
      "/report?view=plan&topic=launch&detail=full#first-30-days-playbook",
    );
  });

  it("uses idea-stage channel hypotheses without calling them a researched channel plan", () => {
    const view = render(ReportPlanSummary, {
      props: {
        report: report({
          selected_solution_details: {
            description: "A generated summary.",
            seo_scalability_score: 0.5,
            tags: { growth_channels: ["content", "community"] },
          },
          acquisition_strategy_summary:
            "The overall SEO scalability assessment is 0.5/10, so validate the channel.",
        }),
        topic: "launch",
      },
    });

    expect(view.getByText("Content")).toBeInTheDocument();
    expect(view.getByText("Community")).toBeInTheDocument();
    expect(view.getByText(/idea-stage channel hypotheses/i)).toBeInTheDocument();
    expect(view.getByText(/SEO scalability assessment is 5\/10/i)).toBeInTheDocument();
    expect(view.queryByText(/SEO scalability assessment is 0\.5\/10/i)).not.toBeInTheDocument();
    expect(view.queryByText("No channel plan was retained.")).not.toBeInTheDocument();
  });
});

describe("ReportPlanSummary build approach", () => {
  // `solution_implementation_overview` is generated as markdown. The full-detail appendix
  // rendered it; this summary printed it as a text node, so `##` and `**` reached the reader.
  it("renders the generated implementation overview as markdown, not literal syntax", () => {
    const view = render(ReportPlanSummary, {
      props: {
        report: report({
          selected_solution_details: { description: "A generated summary." },
          solution_implementation_overview:
            "## Implementation Overview\n\n**Phase 1: MVP Development** (4-6 months)\n",
        }),
        topic: "product",
      },
    });

    expect(view.getByRole("heading", { name: "Implementation Overview" })).toBeInTheDocument();
    expect(view.getByText("Phase 1: MVP Development").tagName).toBe("STRONG");
    expect(view.container.textContent).not.toContain("## Implementation Overview");
    expect(view.container.textContent).not.toContain("**Phase 1");
  });
});
