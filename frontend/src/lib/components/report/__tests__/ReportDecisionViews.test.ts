import { cleanup, render } from "@testing-library/svelte";
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
      view.getByRole("heading", { name: "Is the problem real enough to pay to solve?" }),
    ).toBeInTheDocument();
    expect(view.getByText("Social evidence unavailable")).toBeInTheDocument();
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

    expect(view.getByText("No social evidence")).toBeInTheDocument();
    expect(view.getByText("Problems identified in this report")).toBeInTheDocument();
    expect(view.queryByText("What the research repeatedly found")).not.toBeInTheDocument();
    expect(
      view.getByText(/no saved social-evidence records attached/i),
    ).toBeInTheDocument();
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
});
