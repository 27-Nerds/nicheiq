import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import DecisionHelpHarness from "./DecisionHelpHarness.test.svelte";

describe("DecisionHelp", () => {
  afterEach(cleanup);

  it("uses a real labelled button and opens a titled portaled dialog", async () => {
    const view = render(DecisionHelpHarness);
    const trigger = view.getByRole("button", { name: "Help: Why this matters" });

    expect(trigger.tagName).toBe("BUTTON");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    await fireEvent.click(trigger);

    const panel = view.getByRole("dialog", { name: "Why this matters" });
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(trigger.getAttribute("aria-controls")).toBe(panel.id);
    expect(view.getByText("This evidence changes how the shortlist should be judged.")).toBeInTheDocument();
    expect(panel.parentElement).toBe(document.body);
    await waitFor(() => expect(document.activeElement).toBe(panel));
  });

  it("closes on Escape without also dismissing a parent and returns focus to its trigger", async () => {
    const view = render(DecisionHelpHarness);
    const trigger = view.getByRole("button", { name: "Help: Why this matters" });
    await fireEvent.click(trigger);
    const panel = view.getByRole("dialog", { name: "Why this matters" });

    await fireEvent.keyDown(panel, { key: "Escape" });

    expect(view.queryByRole("dialog", { name: "Why this matters" })).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });
});
