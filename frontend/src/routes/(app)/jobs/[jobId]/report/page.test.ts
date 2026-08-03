import { cleanup, render, within } from "@testing-library/svelte";
import { page } from "$app/state";
import { afterNavigate, replaceState } from "$app/navigation";
import { vi } from "vitest";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Report } from "$lib/types/report";
import { localReportDate } from "$lib/utils/reportDates";
import ReportPage from "./+page.svelte";
import { load } from "./+page";

const report: Report = {
  niche: "Kubernetes model serving",
  executive_summary: "A generated summary.",
  selected_solution_name: "Cold Start Atlas",
  selection_rationale: "A grounded recommendation.",
  competitor_profiles: [],
  generated_at: "2026-07-25T12:00:00.000Z",
};

describe("completed report page", () => {
  beforeEach(() => {
    (page as any).url = new URL("http://localhost/jobs/job-1/report");
    (page as any).data = {
      ...page.data,
      featureAccess: {
        analyst: false,
        decisionTools: false,
      },
    };
  });

  afterEach(cleanup);

  it("offers the existing authenticated JSON artifact as a download", () => {
    const view = render(ReportPage, {
      props: {
        data: {
          report,
          jobId: "job-1",
        },
      },
    });

    const exportLink = view.getByRole("link", {
      name: "Export data",
    });
    expect(exportLink).toHaveAttribute(
      "href",
      "/api/jobs/job-1/reportjson",
    );
    expect(exportLink).toHaveAttribute("download");
    expect(exportLink).toHaveTextContent("Export data");
    expect(exportLink).toHaveTextContent("JSON");
    expect(view.container.querySelector("main")).not.toBeInTheDocument();
  });

  it("returns a typed not-ready state instead of throwing into the global error page", async () => {
    const result = await load({
      params: { jobId: "job-1" },
      fetch: async () => new Response(JSON.stringify({ error: "Deep Research is still running." }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    } as any);

    expect(result).toMatchObject({
      report: null,
      reportState: "not_ready",
      message: "Deep Research is still running.",
      jobId: "job-1",
    });
  });

  it("keeps an in-progress report inside the job recovery flow", () => {
    const view = render(ReportPage, {
      props: {
        data: {
          report: null,
          reportState: "not_ready",
          message: "Deep Research is still running.",
          jobId: "job-1",
        },
      },
    });

    expect(view.getByRole("heading", { name: "Deep Research report is not ready" })).toBeInTheDocument();
    expect(view.getByText("Deep Research is still running.")).toBeInTheDocument();
    expect(view.getByRole("link", { name: "View research progress" }))
      .toHaveAttribute("href", "/jobs/job-1");
  });

  it("surfaces the report provenance and links directly to methods and limitations", () => {
    const view = render(ReportPage, {
      props: {
        data: {
          report: {
            ...report,
            selected_solution_details: {
              description: "A generated summary.",
              idea_id: "idea-cold-start-atlas",
              idea_revision: 4,
            },
            data_quality_summary: {
              overall_data_quality: "MEDIUM",
              quality_caveats: [],
            },
            research_metadata: {
              reddit_posts_analyzed: 12,
              twitter_threads_analyzed: 2,
              generic_posts_analyzed: 3,
              collection_date: "2026-07-24T09:30:00.000Z",
            },
          },
          jobId: "job-1",
        },
      },
    });

    const receipt = view.getByLabelText("Research provenance summary");
    expect(within(receipt).getByText("Medium")).toBeInTheDocument();
    expect(within(receipt).getByText("17")).toBeInTheDocument();
    // Dates are framed in the reader's own timezone so the report cannot name a
    // different calendar day than the job page for the same run. The label
    // itself is unit-tested in utils/__tests__/reportDates.test.ts.
    expect(
      within(receipt).getByText(localReportDate("2026-07-24T09:30:00.000Z")!),
    ).toBeInTheDocument();
    // The raw idea slug stays in the tooltip; the visible copy is human-readable.
    expect(within(receipt).getByText("Revision 4")).toHaveAttribute(
      "title",
      "idea-cold-start-atlas · revision 4",
    );
    expect(within(receipt).queryByText(/idea-cold-start-atlas/)).not.toBeInTheDocument();
    expect(within(receipt).getByRole("link", { name: "Review methods & limitations" }))
      .toHaveAttribute("href", "/jobs/job-1/report?view=evidence&topic=sources");
  });

  // Only the verdict is guaranteed now; a degraded supporting section must be
  // named to the reader, not silently blanked and not back-filled.
  it("names dashboard sections the pipeline could not generate", () => {
    const degraded: Report = {
      ...report,
      executive_dashboard: {
        go_no_go_verdict: {
          verdict: "Conditional",
          rationale: "Demand is thin.",
          risk_level: "High",
          primary_concern: "Beachhead demand is unproven.",
        },
        unavailable_sections: ["recommended_solution_snapshot", "key_metrics"],
      } as Report["executive_dashboard"],
    };

    const view = render(ReportPage, {
      props: { data: { report: degraded, jobId: "job-1" } },
    });

    const note = view.getByText(/Not generated for this report/);
    expect(note).toHaveTextContent("Recommended solution snapshot");
    expect(note).toHaveTextContent("Headline metrics");
    // Raw field keys never reach the reader, and nothing is invented in their place.
    expect(view.queryByText(/recommended_solution_snapshot/)).not.toBeInTheDocument();
    expect(view.queryByText(/^Unknown$/)).not.toBeInTheDocument();
  });

  // The reported complaint: every view repainted the same full-height identity
  // header, so switching views produced no visible change. Only the Brief — the
  // view whose job is to introduce the recommendation — carries it now.
  it("carries the full identity block on the brief only", () => {
    const identityReport: Report = {
      ...report,
      research_metadata: { collection_date: "2026-07-24T09:30:00.000Z" },
    };

    const brief = render(ReportPage, {
      props: { data: { report: identityReport, jobId: "job-1" } },
    });
    expect(brief.getByLabelText("Research provenance summary")).toBeInTheDocument();
    expect(brief.getByLabelText("Report context")).toBeInTheDocument();
    cleanup();

    for (const view of ["evidence", "plan"]) {
      (page as any).url = new URL(`http://localhost/jobs/job-1/report?view=${view}`);
      const rendered = render(ReportPage, {
        props: { data: { report: identityReport, jobId: "job-1" } },
      });
      expect(rendered.queryByLabelText("Research provenance summary")).not.toBeInTheDocument();
      expect(rendered.queryByLabelText("Report context")).not.toBeInTheDocument();
      // The title stays as a compact one-line identity.
      expect(rendered.getByRole("heading", { level: 1 })).toHaveTextContent("Cold Start Atlas");
      cleanup();
    }
  });

  // Each view must open with a heading of its own, otherwise the nav gives no
  // evidence it did anything.
  it("gives every view a distinct heading at the top of its content", () => {
    const headings: Record<string, string> = {
      brief: "The recommendation",
      evidence: "Trace each conclusion to its evidence",
      plan: "Turn the recommendation into an executable plan",
    };
    const seen = new Set<string>();

    for (const [view, heading] of Object.entries(headings)) {
      (page as any).url = new URL(`http://localhost/jobs/job-1/report?view=${view}`);
      const rendered = render(ReportPage, {
        props: { data: { report, jobId: "job-1" } },
      });
      expect(rendered.getByText(heading)).toBeInTheDocument();
      seen.add(heading);
      cleanup();
    }

    expect(seen.size).toBe(3);
  });

  // The verdict is computed last, so the plan view used to ship a dated launch plan
  // for an idea the same report had already killed.
  it("gates the plan view on a No-Go verdict and names the real blocker", () => {
    (page as any).url = new URL("http://localhost/jobs/job-1/report?view=plan");
    const rendered = render(ReportPage, {
      props: {
        data: {
          report: {
            ...report,
            next_steps: ["Set up the landing page with email capture."],
            executive_dashboard: {
              go_no_go_verdict: {
                verdict: "No-Go",
                rationale: "Blocked.",
                risk_level: "High",
                primary_concern: "Limited market fit signals soft product-market alignment",
                red_team_context:
                  "FDA already provides searchable refusal data by country/area and product",
              },
            } as Report["executive_dashboard"],
          },
          jobId: "job-1",
        },
      },
    });

    expect(
      rendered.getByText("What this idea would have to prove first"),
    ).toBeInTheDocument();
    expect(
      rendered.queryByText("Turn the recommendation into an executable plan"),
    ).not.toBeInTheDocument();
    const gate = rendered.getByLabelText("The research concluded No-Go on this idea");
    expect(
      within(gate).getByText(/Before committing budget, resolve this/),
    ).toHaveTextContent("FDA already provides searchable refusal data");
    expect(within(gate).getByRole("link", { name: /how the verdict was reached/ }))
      .toHaveAttribute("href", "/jobs/job-1/report?view=brief");
  });

  it("leaves the plan view untouched under a Go verdict", () => {
    (page as any).url = new URL("http://localhost/jobs/job-1/report?view=plan");
    const rendered = render(ReportPage, {
      props: {
        data: {
          report: {
            ...report,
            next_steps: ["Set up the landing page with email capture."],
            executive_dashboard: {
              go_no_go_verdict: {
                verdict: "Go",
                rationale: "Supported.",
                risk_level: "Low",
                primary_concern: "A residual risk.",
              },
            } as Report["executive_dashboard"],
          },
          jobId: "job-1",
        },
      },
    });

    expect(
      rendered.getByText("Turn the recommendation into an executable plan"),
    ).toBeInTheDocument();
    expect(rendered.queryByText(/Before committing budget/)).not.toBeInTheDocument();
  });

  // Query-param navigation would otherwise leave the reader parked at the top of
  // an unchanged header, so these links opt out of SvelteKit's scroll reset and
  // the component parks the viewport on the incoming view instead.
  it("opts view and topic navigation out of the default scroll reset", () => {
    (page as any).url = new URL("http://localhost/jobs/job-1/report?view=evidence");
    const rendered = render(ReportPage, {
      props: { data: { report, jobId: "job-1" } },
    });

    const viewNav = within(rendered.getAllByLabelText("Report views")[0]);
    for (const label of ["Brief", "Evidence", "Plan"]) {
      expect(viewNav.getByRole("link", { name: new RegExp(label) }))
        .toHaveAttribute("data-sveltekit-noscroll");
    }

    for (const link of within(rendered.getByLabelText("Evidence topics")).getAllByRole("link")) {
      expect(link).toHaveAttribute("data-sveltekit-noscroll");
    }

    // Leaving the report entirely must still reset scroll normally.
    expect(rendered.getByRole("link", { name: "Back to job" }))
      .not.toHaveAttribute("data-sveltekit-noscroll");
  });

  it("does not present missing social-source counts as a measured zero", () => {
    const view = render(ReportPage, {
      props: {
        data: {
          report: {
            ...report,
            research_metadata: {
              collection_date: "2026-07-24T09:30:00.000Z",
            },
          },
          jobId: "job-1",
        },
      },
    });

    const receipt = view.getByLabelText("Research provenance summary");
    expect(within(receipt).getByText("Not available")).toBeInTheDocument();
    expect(within(receipt).queryByText("0")).not.toBeInTheDocument();
    expect(within(receipt).queryByText("Selected revision")).not.toBeInTheDocument();
  });

  it("keeps the pre-selection idea-pool assessment collapsed and identifies it as non-final", () => {
    (page as any).url = new URL(
      "http://localhost/jobs/job-1/report?view=evidence&topic=sources",
    );
    const earlierAssessment =
      "Cold Start Atlas was killed during the earlier portfolio review.";
    const view = render(ReportPage, {
      props: {
        data: {
          report: {
            ...report,
            idea_portfolio_summary: earlierAssessment,
          },
          jobId: "job-1",
        },
      },
    });

    const summary = view.getByText("Earlier idea-pool assessment");
    const disclosure = summary.closest("details");
    expect(disclosure).not.toBeNull();
    expect(disclosure).not.toHaveAttribute("open");
    expect(within(disclosure as HTMLElement).getByText(/before the shortlist was selected/i))
      .toBeInTheDocument();
    expect(within(disclosure as HTMLElement).getByText(/not the final verdict/i))
      .toBeInTheDocument();
    expect(within(disclosure as HTMLElement).getByText(earlierAssessment)).toBeInTheDocument();
  });
  // The batch of honesty fixes landed on the summary components only, so the
  // appendix — the one place a careful reader goes — kept printing internal
  // names. The seam is the report entering ReportContent, not each call site.
  it("humanises internal names and money in the detail=full appendix", async () => {
    (page as any).url = new URL(
      "http://localhost/jobs/job-1/report?view=evidence&topic=market&detail=full",
    );
    const view = render(ReportPage, {
      props: {
        data: {
          report: {
            ...report,
            market_sizing: {
              total_addressable_market: "$1.03-$2.06M",
              serviceable_available_market: "$0.000227-$0.000454M",
              serviceable_obtainable_market_y1: "$0.000001-$0.000009M",
              market_viability_verdict: "Weak",
              growth_drivers: [],
              risk_factors: [
                "Average WTP of 0.40 below the $50M Income Potential threshold",
              ],
              viability_rationale:
                "Weak viability under the mandatory stop rule: the calculated SAM is"
                + " approximately $0.000227-$0.000454M and fails the Income Potential"
                + " criterion, with Enterable the only supported STRIVE criterion.",
            } as any,
          },
          jobId: "job-1",
        },
      },
    });

    const html = view.container.innerHTML;
    expect(html).not.toMatch(/\$0\.0002/);
    expect(html).not.toMatch(/\bWTP\b/);
    expect(html).not.toMatch(/Income Potential/);
    expect(html).not.toMatch(/mandatory stop rule/);
    expect(html).not.toMatch(/\bEnterable\b/);
    expect(html).not.toMatch(/\bSTRIVE\b/);
    expect(view.getByText("$227-$454")).toBeInTheDocument();
    expect(view.getByText("$1-$9")).toBeInTheDocument();
    // The funnel labels the amounts the way the summary card does.
    expect(view.getByText("Reachable market")).toBeInTheDocument();
  });

  // An unknown slug used to render the first available topic while the address
  // bar kept the bad value, so the page disagreed with its own URL.
  it("normalises an unknown topic slug to the topic it actually renders", async () => {
    vi.mocked(replaceState).mockClear();
    vi.mocked(afterNavigate).mockClear();
    (page as any).url = new URL(
      "http://localhost/jobs/job-1/report?view=evidence&topic=quality",
    );
    render(ReportPage, {
      props: {
        data: {
          report: {
            ...report,
            detailed_pain_points: [
              { title: "Cold starts stall", description: "It is slow." } as any,
            ],
          },
          jobId: "job-1",
        },
      },
    });

    // The component registers the normalisation with afterNavigate rather than an
    // effect, because effects flush before SvelteKit's router is initialized.
    const onNavigated = vi.mocked(afterNavigate).mock.calls.at(-1)?.[0] as () => void;
    expect(onNavigated).toBeTypeOf("function");
    onNavigated();

    await vi.waitFor(() =>
      expect(replaceState).toHaveBeenCalledWith(
        "/jobs/job-1/report?view=evidence&topic=demand",
        expect.anything(),
      ),
    );
  });

  it("leaves a valid topic slug alone", async () => {
    vi.mocked(replaceState).mockClear();
    vi.mocked(afterNavigate).mockClear();
    (page as any).url = new URL(
      "http://localhost/jobs/job-1/report?view=evidence&topic=sources",
    );
    render(ReportPage, { props: { data: { report, jobId: "job-1" } } });

    (vi.mocked(afterNavigate).mock.calls.at(-1)?.[0] as () => void)();
    await Promise.resolve();
    expect(replaceState).not.toHaveBeenCalled();
  });
});
