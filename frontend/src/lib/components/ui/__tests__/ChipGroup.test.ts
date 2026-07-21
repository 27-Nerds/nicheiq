import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import ChipGroup from "../ChipGroup.svelte";

const options = [
  { value: "seo", label: "SEO" },
  { value: "communities", label: "Communities" },
  { value: "audience", label: "Existing audience" },
  { value: "outbound", label: "Outbound" },
];

describe("ChipGroup", () => {
  afterEach(cleanup);

  it("renders aria-pressed chips inside a labeled group", () => {
    const view = render(ChipGroup, {
      props: { options, values: ["seo"], label: "Channels" },
    });

    expect(view.getByRole("group", { name: "Channels" })).toBeInTheDocument();
    expect(view.getByRole("button", { name: "SEO" })).toHaveAttribute("aria-pressed", "true");
    expect(view.getByRole("button", { name: "Outbound" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("toggles chips on click and reports the new selection", async () => {
    const onChange = vi.fn();
    const view = render(ChipGroup, {
      props: { options, values: ["seo"], label: "Channels", onChange },
    });

    await fireEvent.click(view.getByRole("button", { name: "Communities" }));
    expect(onChange).toHaveBeenLastCalledWith(["seo", "communities"]);

    await fireEvent.click(view.getByRole("button", { name: "SEO" }));
    expect(onChange).toHaveBeenLastCalledWith(["communities"]);
    expect(view.getByRole("button", { name: "SEO" })).toHaveAttribute("aria-pressed", "false");
  });

  it("renders the mono counter and disables remaining chips at the cap", async () => {
    const view = render(ChipGroup, {
      props: { options, values: ["seo"], max: 2, label: "Channels" },
    });

    expect(view.getByText("1 / 2")).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Communities" }));
    expect(view.getByText("2 / 2")).toBeInTheDocument();

    const remaining = view.getByRole("button", { name: "Existing audience" });
    expect(remaining).toBeDisabled();
    // Selected chips stay enabled so the pick can be reversed.
    expect(view.getByRole("button", { name: "SEO" })).toBeEnabled();

    await fireEvent.click(remaining);
    expect(remaining).toHaveAttribute("aria-pressed", "false");
  });

  it("re-enables chips when a selection is removed at the cap", async () => {
    const view = render(ChipGroup, {
      props: { options, values: ["seo", "communities"], max: 2, label: "Channels" },
    });

    expect(view.getByRole("button", { name: "Outbound" })).toBeDisabled();

    await fireEvent.click(view.getByRole("button", { name: "SEO" }));
    expect(view.getByText("1 / 2")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Outbound" })).toBeEnabled();
  });

  it("disables every chip when the group is disabled", () => {
    const view = render(ChipGroup, {
      props: { options, values: [], label: "Channels", disabled: true },
    });

    for (const option of options) {
      expect(view.getByRole("button", { name: option.label })).toBeDisabled();
    }
  });
});
