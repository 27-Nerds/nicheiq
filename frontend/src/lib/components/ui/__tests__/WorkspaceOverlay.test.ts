import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { readFileSync } from "node:fs";
import WorkspaceOverlayHarness from "./WorkspaceOverlayHarness.test.svelte";

const TOKENS_SOURCE = readFileSync("src/lib/styles/tokens.css", "utf8");
const JOB_PAGE_SOURCE = readFileSync("src/routes/(app)/jobs/[jobId]/+page.svelte", "utf8");
const SELECTION_LAYOUT_SOURCE = readFileSync(
  "src/routes/(app)/jobs/[jobId]/selection/+layout.svelte",
  "utf8",
);

describe("WorkspaceOverlay — Escape contract", () => {
  afterEach(() => {
    cleanup();
    document.documentElement.style.overflow = "";
    document.documentElement.style.paddingRight = "";
  });

  it("promotes a requested dock to an isolated modal side sheet below 1400px", async () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }) as typeof window.matchMedia;

    try {
      const view = render(WorkspaceOverlayHarness, {
        props: { onClose: vi.fn(), modal: false },
      });

      const dialog = await view.findByRole("dialog", { name: "Analyst conversation" });
      expect(dialog).toHaveAttribute("aria-modal", "true");
      expect(dialog.closest(".workspace-overlay")).toHaveAttribute(
        "data-workspace-overlay-presentation",
        "side-sheet",
      );
      expect(document.querySelector(".workspace-overlay__scrim")).not.toBeNull();
      expect(document.documentElement.style.overflow).toBe("hidden");
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it("routes Escape to onEscape when provided, leaving onClose untouched", async () => {
    const onClose = vi.fn();
    const onEscape = vi.fn();
    const view = render(WorkspaceOverlayHarness, { props: { onClose, onEscape } });

    await fireEvent.keyDown(view.getByRole("dialog", { name: "Analyst conversation" }), {
      key: "Escape",
    });

    expect(onEscape).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("falls back to onClose on Escape when no onEscape is given (additive API)", async () => {
    const onClose = vi.fn();
    const view = render(WorkspaceOverlayHarness, { props: { onClose } });

    await fireEvent.keyDown(view.getByRole("dialog", { name: "Analyst conversation" }), {
      key: "Escape",
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("scrim click still calls onClose even when onEscape is set", async () => {
    const onClose = vi.fn();
    const onEscape = vi.fn();
    render(WorkspaceOverlayHarness, { props: { onClose, onEscape } });

    const scrim = document.querySelector<HTMLElement>(".workspace-overlay__scrim");
    expect(scrim).not.toBeNull();
    await fireEvent.click(scrim!);

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onEscape).not.toHaveBeenCalled();
  });

  it("routes Escape to onEscape in the docked (non-modal) window too", async () => {
    const onClose = vi.fn();
    const onEscape = vi.fn();
    const view = render(WorkspaceOverlayHarness, { props: { onClose, onEscape, modal: false } });

    // Non-modal frame has no dialog role; the keydown handler sits on the frame.
    const frame = document.querySelector<HTMLElement>(".workspace-overlay__frame");
    expect(frame).not.toBeNull();
    await fireEvent.keyDown(frame!, { key: "Escape" });

    expect(onEscape).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
    expect(view.getByRole("button", { name: "Inside control" })).toBeInTheDocument();
  });
});

describe("WorkspaceOverlay — dock reservation contract", () => {
  it("uses one tokenized dock width and reserves that width plus its inset", () => {
    expect(TOKENS_SOURCE).toContain("--analyst-dock-width: 26rem");
    expect(TOKENS_SOURCE).toContain(
      "--analyst-dock-clearance: calc(var(--analyst-dock-width) + var(--analyst-dock-inset))",
    );
  });

  it("makes both reserved shells responsive to their actual inline size", () => {
    for (const source of [JOB_PAGE_SOURCE, SELECTION_LAYOUT_SOURCE]) {
      expect(source).toContain("container: analyst-workspace / inline-size");
      expect(source).toContain("@container analyst-workspace (max-width: 60rem)");
    }

    expect(JOB_PAGE_SOURCE).toContain(":global(.workbench .opp-row)");
    expect(JOB_PAGE_SOURCE).toContain(":global(.workbench .brief-head)");
    expect(JOB_PAGE_SOURCE).toContain(".selection-market-read__facts");
    expect(SELECTION_LAYOUT_SOURCE).toContain(":global(.lens-rail > div)");
    expect(SELECTION_LAYOUT_SOURCE).toContain(":global(.experiment-row)");
    expect(SELECTION_LAYOUT_SOURCE).toContain(":global(.review-grid)");
  });
});
