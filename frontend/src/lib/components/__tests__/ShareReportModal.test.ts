import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ShareReportModal from "../ShareReportModal.svelte";

const mocks = vi.hoisted(() => ({
  getShareStatus: vi.fn(),
  enableSharing: vi.fn(),
  disableSharing: vi.fn(),
  regenerateShareToken: vi.fn(),
}));

vi.mock("$lib/api", () => mocks);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ShareReportModal", () => {
  it("states the private exclusions and offers a preview of an active shared report", async () => {
    mocks.getShareStatus.mockResolvedValue({
      isShared: true,
      shareToken: "shared-token",
      viewCount: 2,
    });

    render(ShareReportModal, { props: { open: true, jobId: "job-1" } });

    expect(
      await screen.findByText(
        "Anyone with the link can view report findings and sources. Analyst conversations, Decision Lab records, and annotations stay private.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Preview shared report" })).toHaveAttribute(
      "href",
      "http://localhost:3000/shared/shared-token",
    );
  });
});
