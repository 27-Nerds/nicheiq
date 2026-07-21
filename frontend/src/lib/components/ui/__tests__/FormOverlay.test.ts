import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import FormOverlayAnnotationHarness from "./FormOverlayAnnotationHarness.test.svelte";
import FormOverlayHarness from "./FormOverlayHarness.test.svelte";

describe("FormOverlay", () => {
  afterEach(() => {
    cleanup();
    document.documentElement.style.overflow = "";
    document.documentElement.style.paddingRight = "";
  });

  it("renders a named portaled dialog with visible context and an annotation anchor", () => {
    const view = render(FormOverlayHarness, { props: { open: true } });
    const dialog = view.getByRole("dialog", { name: "Decision profile" });

    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("data-annotation-anchor")).toBe("decision-profile-form");
    expect(view.getByText("Decision setup")).toBeInTheDocument();
    expect(view.getByText("Set the constraints that should shape this decision.")).toBeInTheDocument();
    expect(dialog.closest("[data-form-overlay]")?.parentElement).toBe(document.body);
    expect(dialog.querySelectorAll("[data-form-overlay-scroll-body]")).toHaveLength(1);
    expect(dialog.querySelector("[data-annotation-surface]")).toBeNull();
  });

  it.each([true, false])(
    "mounts the exact modal annotation surface for editable=%s without falling back to the page",
    (editable) => {
      const view = render(FormOverlayAnnotationHarness, { props: { editable } });
      const dialog = view.getByRole("dialog", { name: "Decision profile" });
      const surface = dialog.querySelector<HTMLElement>(
        '[data-annotation-surface="decision-profile-form"]',
      );

      expect(surface).not.toBeNull();
      expect(surface?.dataset.annotationAnchor).toBe("decision-profile-form");
      expect(surface?.parentElement).toBe(dialog);
      expect(surface?.querySelector("[data-form-overlay-scroll-body]")).not.toBeNull();
      expect(surface?.querySelector("footer")).not.toBeNull();
      expect(document.querySelector('[data-annotation-surface="research:page"]')).toBeNull();
    },
  );

  it("locks scroll, focuses the dialog, and traps focus across body and footer controls", async () => {
    const view = render(FormOverlayHarness, { props: { open: true } });
    const dialog = view.getByRole("dialog", { name: "Decision profile" });
    const close = view.getByRole("button", { name: "Close Decision profile" });
    const save = view.getByRole("button", { name: "Save profile" });

    expect(document.documentElement.style.overflow).toBe("hidden");
    await waitFor(() => expect(document.activeElement).toBe(dialog));

    save.focus();
    await fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(close);

    await fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(save);
  });

  it("moves focus onto the frame on open so Escape closes without any prior click", async () => {
    const onRequestClose = vi.fn();
    const view = render(FormOverlayHarness, { props: { open: true, onRequestClose } });
    const dialog = view.getByRole("dialog", { name: "Decision profile" });

    // Focus lands on the frame itself right after open (rAF-deferred), so the
    // keydown target is wherever the browser sends keys: the active element.
    await waitFor(() => expect(document.activeElement).toBe(dialog));
    await fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Escape" });

    expect(onRequestClose).toHaveBeenCalledTimes(1);
  });

  it("routes Escape, backdrop, and close-button dismissal through one callback", async () => {
    const onRequestClose = vi.fn();
    const view = render(FormOverlayHarness, { props: { open: true, onRequestClose } });
    const dialog = view.getByRole("dialog", { name: "Decision profile" });

    await fireEvent.keyDown(dialog, { key: "Escape" });
    await fireEvent.click(document.querySelector("[data-form-overlay-backdrop]") as HTMLElement);
    await fireEvent.click(view.getByRole("button", { name: "Close Decision profile" }));

    expect(onRequestClose).toHaveBeenCalledTimes(3);
  });

  it("restores focus and pre-existing background accessibility state on close", async () => {
    const parentModal = document.createElement("div");
    parentModal.setAttribute("role", "dialog");
    parentModal.inert = false;
    parentModal.setAttribute("aria-hidden", "false");
    const opener = document.createElement("button");
    opener.textContent = "Open decision profile";
    parentModal.appendChild(opener);
    document.body.appendChild(parentModal);
    opener.focus();

    const view = render(FormOverlayHarness, { props: { open: false } });
    await view.rerender({ open: true });

    await waitFor(() => expect(parentModal.inert).toBe(true));
    expect(parentModal.getAttribute("aria-hidden")).toBe("true");

    await view.rerender({ open: false });
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(parentModal.inert).toBe(false);
    expect(parentModal.getAttribute("aria-hidden")).toBe("false");
    expect(document.documentElement.style.overflow).toBe("");

    parentModal.remove();
  });

  it("does not restore focus into a disabled or aria-hidden opener", async () => {
    const opener = document.createElement("button");
    opener.textContent = "Open decision profile";
    document.body.appendChild(opener);
    opener.focus();

    const view = render(FormOverlayHarness, { props: { open: false } });
    await view.rerender({ open: true });
    await waitFor(() => expect(document.activeElement).not.toBe(opener));

    await view.rerender({ open: false });
    opener.disabled = true;
    opener.setAttribute("aria-hidden", "true");
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

    expect(document.activeElement).not.toBe(opener);
    opener.remove();
  });

  it("closes dirty overlays only on the second attempt, showing the warning in between", async () => {
    const onRequestClose = vi.fn();
    const view = render(FormOverlayHarness, {
      props: {
        open: true,
        onRequestClose,
        dirty: true,
        closeWarning: "You have unsaved changes. Close again to discard them.",
      },
    });
    const dialog = view.getByRole("dialog", { name: "Decision profile" });

    await fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onRequestClose).not.toHaveBeenCalled();
    expect(
      view.getByText("You have unsaved changes. Close again to discard them."),
    ).toBeInTheDocument();

    await fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onRequestClose).toHaveBeenCalledTimes(1);
  });

  it("arms the close gate from any dismissal path and closes via the discard button", async () => {
    const onRequestClose = vi.fn();
    const view = render(FormOverlayHarness, {
      props: {
        open: true,
        onRequestClose,
        dirty: true,
        closeWarning: "Unsaved changes.",
      },
    });

    await fireEvent.click(document.querySelector("[data-form-overlay-backdrop]") as HTMLElement);
    expect(onRequestClose).not.toHaveBeenCalled();

    const discard = view.getByRole("button", { name: "Discard changes" });
    await fireEvent.click(discard);
    expect(onRequestClose).toHaveBeenCalledTimes(1);
  });

  it("closes clean overlays on the first attempt even when a closeWarning is configured", async () => {
    const onRequestClose = vi.fn();
    const view = render(FormOverlayHarness, {
      props: {
        open: true,
        onRequestClose,
        dirty: false,
        closeWarning: "Unsaved changes.",
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Close Decision profile" }));
    expect(onRequestClose).toHaveBeenCalledTimes(1);
    expect(view.queryByText("Unsaved changes.")).not.toBeInTheDocument();
  });

  it("keeps parent overlay isolation intact while a nested form overlay opens and closes", async () => {
    const parent = render(FormOverlayHarness, {
      props: { open: true, title: "Parent workspace" },
    });
    const parentLayer = document.querySelector('[data-form-overlay]') as HTMLElement;
    const pageContainer = parent.container;

    expect(pageContainer.inert).toBe(true);
    parentLayer.inert = false;
    const nested = render(FormOverlayHarness, {
      props: { open: true, title: "Nested decision" },
    });

    await waitFor(() => expect(parentLayer.inert).toBe(true));
    nested.unmount();
    await waitFor(() => expect(parentLayer.inert).toBe(false));
    expect(pageContainer.inert).toBe(true);

    parent.unmount();
    expect(pageContainer.inert).toBeFalsy();
    expect(pageContainer.getAttribute("aria-hidden")).toBeNull();
  });
});
