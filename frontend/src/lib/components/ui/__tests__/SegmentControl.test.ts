import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import SegmentControl from "../SegmentControl.svelte";

const options = [
  { value: "desirability", label: "Desirability" },
  { value: "usability", label: "Usability" },
  { value: "feasibility", label: "Feasibility" },
];

const cardOptions = [
  { value: "explore", label: "Explore directions", description: "Push buyer, workflow, and scope apart." },
  { value: "resolve", label: "Resolve the trade-off", description: "Keep, combine, or give up strengths." },
];

describe("SegmentControl", () => {
  afterEach(cleanup);

  it("renders radiogroup semantics with a roving tabindex on the checked option", () => {
    const view = render(SegmentControl, {
      props: { options, value: "usability", label: "Assumption type" },
    });

    const group = view.getByRole("radiogroup", { name: "Assumption type" });
    const radios = view.getAllByRole("radio");
    expect(group).toBeInTheDocument();
    expect(radios).toHaveLength(3);
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
    expect(radios[1]).toHaveAttribute("tabindex", "0");
    expect(radios[0]).toHaveAttribute("tabindex", "-1");
    expect(radios[2]).toHaveAttribute("tabindex", "-1");
  });

  it("falls back to the first option as the tab stop when nothing is selected", () => {
    const view = render(SegmentControl, {
      props: { options, label: "Assumption type" },
    });

    const radios = view.getAllByRole("radio");
    expect(radios[0]).toHaveAttribute("tabindex", "0");
    expect(radios[1]).toHaveAttribute("tabindex", "-1");
  });

  it("selects on click and reports the change", async () => {
    const onChange = vi.fn();
    const view = render(SegmentControl, {
      props: { options, value: "desirability", label: "Assumption type", onChange },
    });

    await fireEvent.click(view.getByRole("radio", { name: "Feasibility" }));

    expect(view.getByRole("radio", { name: "Feasibility" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(onChange).toHaveBeenCalledWith("feasibility");
  });

  it("moves selection and focus with arrow keys, wrapping at the edges", async () => {
    const onChange = vi.fn();
    const view = render(SegmentControl, {
      props: { options, value: "desirability", label: "Assumption type", onChange },
    });
    const radios = view.getAllByRole("radio");

    await fireEvent.keyDown(radios[0], { key: "ArrowRight" });
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
    expect(document.activeElement).toBe(radios[1]);

    await fireEvent.keyDown(radios[1], { key: "ArrowLeft" });
    expect(radios[0]).toHaveAttribute("aria-checked", "true");

    await fireEvent.keyDown(radios[0], { key: "ArrowUp" });
    expect(radios[2]).toHaveAttribute("aria-checked", "true");
    expect(document.activeElement).toBe(radios[2]);

    await fireEvent.keyDown(radios[2], { key: "ArrowDown" });
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
    expect(onChange).toHaveBeenCalledTimes(4);
  });

  it("supports Home and End", async () => {
    const view = render(SegmentControl, {
      props: { options, value: "usability", label: "Assumption type" },
    });
    const radios = view.getAllByRole("radio");

    await fireEvent.keyDown(radios[1], { key: "End" });
    expect(radios[2]).toHaveAttribute("aria-checked", "true");

    await fireEvent.keyDown(radios[2], { key: "Home" });
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
  });

  it("renders card density with descriptions and still selects", async () => {
    const view = render(SegmentControl, {
      props: { options: cardOptions, density: "card", label: "Purpose" },
    });

    expect(view.getByText("Push buyer, workflow, and scope apart.")).toBeInTheDocument();

    const resolve = view.getByRole("radio", { name: /Resolve the trade-off/ });
    await fireEvent.click(resolve);
    expect(resolve).toHaveAttribute("aria-checked", "true");
  });

  it("ignores interaction while disabled", async () => {
    const onChange = vi.fn();
    const view = render(SegmentControl, {
      props: { options, value: "desirability", label: "Assumption type", disabled: true, onChange },
    });
    const radios = view.getAllByRole("radio");

    expect(radios[0]).toBeDisabled();
    await fireEvent.click(radios[2]);
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
    expect(onChange).not.toHaveBeenCalled();
  });
});
