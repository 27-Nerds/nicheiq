import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ShareDiscoveryModal from "../ShareDiscoveryModal.svelte";

const mocks = vi.hoisted(() => ({
  getDiscoveryShareStatus: vi.fn(),
  enableDiscoverySharing: vi.fn(),
  disableDiscoverySharing: vi.fn(),
  regenerateDiscoveryShareToken: vi.fn(),
}));

vi.mock("$lib/api", () => mocks);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ShareDiscoveryModal", () => {
  it("announces while share settings are loading", async () => {
    mocks.getDiscoveryShareStatus.mockReturnValue(new Promise(() => {}));

    render(ShareDiscoveryModal, { props: { open: true, jobId: "job-1" } });

    expect(await screen.findByRole("status")).toHaveTextContent("Loading share settings");
  });

  it("discloses when the discovery link closes", async () => {
    mocks.getDiscoveryShareStatus.mockResolvedValue({
      isShared: false,
      shareToken: null,
      viewCount: 0,
      voteCount: 0,
    });

    const view = render(ShareDiscoveryModal, {
      props: { open: true, jobId: "job-1" },
    });

    expect(await view.findByText(
      "Share findings and let collaborators vote on ranked ideas. This link closes once Deep Research is successfully queued.",
    )).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Enable sharing" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("announces successful link copying", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mocks.getDiscoveryShareStatus.mockResolvedValue({
      isShared: true,
      shareToken: "shared-token",
      viewCount: 0,
      voteCount: 0,
    });

    render(ShareDiscoveryModal, { props: { open: true, jobId: "job-1" } });

    const copy = await screen.findByRole("button", { name: "Copy share link" });
    await fireEvent.click(copy);

    expect(writeText).toHaveBeenCalledWith(
      "http://localhost:3000/shared/discovery/shared-token",
    );
    expect(await screen.findByRole("button", { name: "Share link copied" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("returns focus to the discovery Share trigger after Escape", async () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Share";
    document.body.appendChild(trigger);
    mocks.getDiscoveryShareStatus.mockResolvedValue({
      isShared: false,
      shareToken: null,
      viewCount: 0,
      voteCount: 0,
    });

    render(ShareDiscoveryModal, {
      props: { open: true, jobId: "job-1", restoreFocusTo: trigger },
    });

    const dialog = await screen.findByRole("dialog", { name: "Share discovery" });
    await waitFor(() => expect(document.activeElement).toBe(dialog));
    await fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => expect(document.activeElement).toBe(trigger));
    trigger.remove();
  });
});
