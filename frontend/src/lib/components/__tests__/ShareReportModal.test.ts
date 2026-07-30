import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
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
  it("announces while share settings are loading", async () => {
    mocks.getShareStatus.mockReturnValue(new Promise(() => {}));

    render(ShareReportModal, { props: { open: true, jobId: "job-1" } });

    expect(await screen.findByRole("status")).toHaveTextContent("Loading share settings");
  });

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
    expect(screen.getByRole("switch", { name: "Disable sharing" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("announces successful link copying", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mocks.getShareStatus.mockResolvedValue({
      isShared: true,
      shareToken: "shared-token",
      viewCount: 0,
    });

    render(ShareReportModal, { props: { open: true, jobId: "job-1" } });

    const copy = await screen.findByRole("button", { name: "Copy share link" });
    await fireEvent.click(copy);

    expect(writeText).toHaveBeenCalledWith("http://localhost:3000/shared/shared-token");
    expect(await screen.findByRole("button", { name: "Share link copied" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("returns focus to the report Share trigger after Escape", async () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Share";
    document.body.appendChild(trigger);
    mocks.getShareStatus.mockResolvedValue({
      isShared: false,
      shareToken: null,
      viewCount: 0,
    });

    render(ShareReportModal, {
      props: { open: true, jobId: "job-1", restoreFocusTo: trigger },
    });

    const dialog = await screen.findByRole("dialog", { name: "Share report" });
    await waitFor(() => expect(document.activeElement).toBe(dialog));
    await fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => expect(document.activeElement).toBe(trigger));
    trigger.remove();
  });
});
