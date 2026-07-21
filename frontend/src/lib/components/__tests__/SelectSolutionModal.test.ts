import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import SelectSolutionModal from "../SelectSolutionModal.svelte";

afterEach(() => cleanup());

describe("SelectSolutionModal", () => {
  it("submits the owner's trimmed selection rationale", async () => {
    const onConfirm = vi.fn();
    const { getByRole } = render(SelectSolutionModal, {
      props: {
        open: true,
        solutionNames: ["Workflow Copilot"],
        onConfirm,
        onCancel: vi.fn(),
      },
    });

    await fireEvent.input(getByRole("textbox", { name: /Why are you choosing this shortlist/ }), {
      target: { value: "  Best match for our audience and budget.  " },
    });
    await fireEvent.click(getByRole("button", { name: "Start Deep Research" }));

    expect(onConfirm).toHaveBeenCalledWith("Best match for our audience and budget.");
  });
});
