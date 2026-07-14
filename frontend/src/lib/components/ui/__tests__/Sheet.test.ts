import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/svelte";
import Sheet from "../Sheet.svelte";
import SheetHarness from "./SheetHarness.test.svelte";

describe("Sheet — responsive dialog primitive", () => {
  afterEach(() => {
    cleanup();
    document.documentElement.style.overflow = "";
  });

  it("renders nothing when closed", () => {
    const { queryByRole } = render(Sheet, {
      props: { open: false, title: "Niche checkpoint", onClose: vi.fn(), children: undefined as never },
    });
    expect(queryByRole("dialog")).toBeNull();
  });

  it("announces itself as a modal dialog labelled by its title", async () => {
    const { getByRole } = render(SheetHarness, { props: { open: true, onClose: vi.fn() } });

    const dialog = getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-label")).toBe("Niche checkpoint");
  });

  it("locks document scroll while open so the page behind can't drift", () => {
    render(SheetHarness, { props: { open: true, onClose: vi.fn() } });
    expect(document.documentElement.style.overflow).toBe("hidden");
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    const { getByRole } = render(SheetHarness, { props: { open: true, onClose } });

    await fireEvent.keyDown(getByRole("dialog"), { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on the close button", async () => {
    const onClose = vi.fn();
    const { getByLabelText } = render(SheetHarness, { props: { open: true, onClose } });

    await fireEvent.click(getByLabelText("Close Niche checkpoint"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("traps Tab inside the panel — focus can't escape to the page behind", async () => {
    const { getByRole, getByText } = render(SheetHarness, { props: { open: true, onClose: vi.fn() } });

    const dialog = getByRole("dialog");
    const lastFocusable = getByText("Inner action");
    lastFocusable.focus();

    await fireEvent.keyDown(dialog, { key: "Tab" });

    // Wrapped back to the first focusable (the close button), not out of the dialog.
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Close Niche checkpoint");
  });
});
