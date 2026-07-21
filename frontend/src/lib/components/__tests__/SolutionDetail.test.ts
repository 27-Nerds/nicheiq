import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import SolutionDetail from "../SolutionDetail.svelte";
import type { SolutionPreview } from "$lib/types/job";

afterEach(() => cleanup());

function solution(overrides: Partial<SolutionPreview> = {}): SolutionPreview {
  return {
    idea_id: "idea-1",
    idea_revision: 2,
    solution_name: "Signal Desk",
    description: "A guided tapering companion.",
    value_proposition: "Keep the weight off after GLP-1.",
    ...overrides,
  };
}

function renderDetail(props: { solution: SolutionPreview; jobId?: string }) {
  return render(SolutionDetail, {
    props: {
      open: true,
      solutions: [props.solution],
      currentIndex: 0,
      onNavigate: vi.fn(),
      onClose: vi.fn(),
      ...props,
    },
  });
}

describe("SolutionDetail export links", () => {
  it("links to the exact stored revision's md and json exports when jobId is present", () => {
    const { getByRole } = renderDetail({ solution: solution(), jobId: "job-1" });

    const md = getByRole("link", { name: /\.md/i });
    expect(md).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/md?revision=2",
    );
    const json = getByRole("link", { name: /\.json/i });
    expect(json).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/json?revision=2",
    );
  });

  it("defaults the export revision to 1 for legacy candidates without a stored revision", () => {
    const { getByRole } = renderDetail({
      solution: solution({ idea_revision: undefined }),
      jobId: "job-1",
    });

    expect(getByRole("link", { name: /\.md/i })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/md?revision=1",
    );
  });

  it("hides export links without a job or an idea identity", () => {
    const noJob = renderDetail({ solution: solution() });
    expect(noJob.queryByRole("link", { name: /\.md/i })).not.toBeInTheDocument();

    cleanup();

    const noIdentity = renderDetail({ solution: solution({ idea_id: undefined }), jobId: "job-1" });
    expect(noIdentity.queryByRole("link", { name: /\.md/i })).not.toBeInTheDocument();
  });
});
