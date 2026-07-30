import { cleanup, render } from "@testing-library/svelte";
import { page } from "$app/state";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Report } from "$lib/types/report";
import ReportPage from "./+page.svelte";

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

    expect(view.getByRole("link", { name: "Download JSON" })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/reportjson",
    );
    expect(view.getByRole("link", { name: "Download JSON" })).toHaveAttribute("download");
    expect(view.container.querySelector("main")).not.toBeInTheDocument();
  });
});
