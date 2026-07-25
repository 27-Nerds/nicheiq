import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import WorkspaceOverlayHarness from "./WorkspaceOverlayHarness.test.svelte";

describe("WorkspaceOverlay — Escape contract", () => {
  afterEach(() => {
    cleanup();
    document.documentElement.style.overflow = "";
    document.documentElement.style.paddingRight = "";
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
