import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import ConfirmGate from "../ConfirmGate.svelte";

const baseProps = {
  label: "Evaluate direction",
  confirmLabel: "Confirm evaluation",
  variant: "paid" as const,
  costLine: "2 CREDITS · 42 LEFT",
};

describe("ConfirmGate", () => {
  afterEach(cleanup);

  it("arms on trigger click and fires onConfirm exactly once", async () => {
    const onConfirm = vi.fn();
    const view = render(ConfirmGate, { props: { ...baseProps, onConfirm } });

    await fireEvent.click(view.getByRole("button", { name: "Evaluate direction" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(view.getByText("2 CREDITS · 42 LEFT")).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Confirm evaluation" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    // Confirming disarms: the gate returns to the rest trigger.
    expect(view.queryByRole("button", { name: "Confirm evaluation" })).not.toBeInTheDocument();
    expect(view.getByRole("button", { name: "Evaluate direction" })).toBeInTheDocument();
  });

  it("shows the consequence line for the free variant", async () => {
    const view = render(ConfirmGate, {
      props: {
        label: "Lock decision",
        confirmLabel: "Confirm lock",
        variant: "free" as const,
        consequence: "BECOMES IMMUTABLE",
        onConfirm: vi.fn(),
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Lock decision" }));
    expect(view.getByText("BECOMES IMMUTABLE")).toBeInTheDocument();
  });

  it("disarms on outside click without firing onConfirm", async () => {
    const onConfirm = vi.fn();
    const view = render(ConfirmGate, { props: { ...baseProps, onConfirm } });

    await fireEvent.click(view.getByRole("button", { name: "Evaluate direction" }));
    expect(view.getByRole("button", { name: "Confirm evaluation" })).toBeInTheDocument();

    await fireEvent.click(document.body);
    expect(view.queryByRole("button", { name: "Confirm evaluation" })).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("stays armed on clicks inside the gate", async () => {
    const view = render(ConfirmGate, { props: { ...baseProps, onConfirm: vi.fn() } });

    await fireEvent.click(view.getByRole("button", { name: "Evaluate direction" }));
    await fireEvent.click(view.getByText("2 CREDITS · 42 LEFT"));
    expect(view.getByRole("button", { name: "Confirm evaluation" })).toBeInTheDocument();
  });

  it("disarms on cancel without firing onConfirm", async () => {
    const onConfirm = vi.fn();
    const view = render(ConfirmGate, { props: { ...baseProps, onConfirm } });

    await fireEvent.click(view.getByRole("button", { name: "Evaluate direction" }));
    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));

    expect(view.getByRole("button", { name: "Evaluate direction" })).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("blocks confirm while busy", async () => {
    const onConfirm = vi.fn();
    const view = render(ConfirmGate, { props: { ...baseProps, onConfirm } });

    await fireEvent.click(view.getByRole("button", { name: "Evaluate direction" }));
    await view.rerender({ ...baseProps, onConfirm, busy: true });

    const confirm = view.getByRole("button", { name: "Confirm evaluation" });
    expect(confirm).toBeDisabled();
    await fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("disarms on Escape and returns focus to the trigger", async () => {
    const onConfirm = vi.fn();
    const view = render(ConfirmGate, { props: { ...baseProps, onConfirm } });

    await fireEvent.click(view.getByRole("button", { name: "Evaluate direction" }));
    const confirm = view.getByRole("button", { name: "Confirm evaluation" });
    confirm.focus();
    await fireEvent.keyDown(confirm, { key: "Escape" });

    const trigger = await view.findByRole("button", { name: "Evaluate direction" });
    expect(view.queryByRole("button", { name: "Confirm evaluation" })).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  it("stops Escape from bubbling past the armed gate", async () => {
    const outerKeydown = vi.fn();
    document.body.addEventListener("keydown", outerKeydown);
    const view = render(ConfirmGate, { props: { ...baseProps, onConfirm: vi.fn() } });

    await fireEvent.click(view.getByRole("button", { name: "Evaluate direction" }));
    const cancel = view.getByRole("button", { name: "Cancel" });
    await fireEvent.keyDown(cancel, { key: "Escape" });

    expect(outerKeydown).not.toHaveBeenCalled();
    expect(view.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
    document.body.removeEventListener("keydown", outerKeydown);
  });

  it("blocks arming while disabled or busy", async () => {
    const onConfirm = vi.fn();
    const view = render(ConfirmGate, {
      props: { ...baseProps, onConfirm, disabled: true },
    });

    const trigger = view.getByRole("button", { name: "Evaluate direction" });
    expect(trigger).toBeDisabled();
    await fireEvent.click(trigger);
    expect(view.queryByRole("button", { name: "Confirm evaluation" })).not.toBeInTheDocument();
  });
});
