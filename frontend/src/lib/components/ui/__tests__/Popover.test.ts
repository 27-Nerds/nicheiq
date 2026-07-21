import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import PopoverHarness from "./PopoverHarness.test.svelte";

describe("Popover", () => {
  afterEach(cleanup);

  it("loops forward focus through portaled panel content and its WorkspaceOverlay trigger", async () => {
    const view = render(PopoverHarness);
    const trigger = view.getByRole("button", { name: "Open keyboard details" });
    const background = view.getByRole("button", { name: "Workspace background" });
    await fireEvent.click(trigger);

    const panel = view.getByRole("dialog", { name: "Keyboard details" });
    const first = view.getByRole("button", { name: "First panel action" });
    const last = view.getByRole("link", { name: "Last panel action" });
    await waitFor(() => expect(document.activeElement).toBe(panel));

    await fireEvent.keyDown(panel, { key: "Tab" });
    expect(document.activeElement).toBe(first);

    last.focus();
    await fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(trigger);

    await fireEvent.keyDown(trigger, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    expect(document.activeElement).not.toBe(background);
  });

  it("loops reverse focus without escaping to the page background", async () => {
    const view = render(PopoverHarness);
    const trigger = view.getByRole("button", { name: "Open keyboard details" });
    await fireEvent.click(trigger);

    const panel = view.getByRole("dialog", { name: "Keyboard details" });
    const first = view.getByRole("button", { name: "First panel action" });
    const last = view.getByRole("link", { name: "Last panel action" });
    await waitFor(() => expect(document.activeElement).toBe(panel));

    await fireEvent.keyDown(panel, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(trigger);

    await fireEvent.keyDown(trigger, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);

    first.focus();
    await fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(trigger);
  });

  it("contains focus between the panel and trigger when content has no controls", async () => {
    const view = render(PopoverHarness, { props: { withActions: false } });
    const trigger = view.getByRole("button", { name: "Open keyboard details" });
    await fireEvent.click(trigger);

    const panel = view.getByRole("dialog", { name: "Keyboard details" });
    await waitFor(() => expect(document.activeElement).toBe(panel));

    await fireEvent.keyDown(panel, { key: "Tab" });
    expect(document.activeElement).toBe(trigger);

    await fireEvent.keyDown(trigger, { key: "Tab" });
    expect(document.activeElement).toBe(panel);

    await fireEvent.keyDown(panel, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(trigger);
  });

  it("returns focus on Escape and still closes on outside click", async () => {
    const view = render(PopoverHarness);
    const trigger = view.getByRole("button", { name: "Open keyboard details" });
    const background = view.getByRole("button", { name: "Workspace background" });
    await fireEvent.click(trigger);

    let panel = view.getByRole("dialog", { name: "Keyboard details" });
    await fireEvent.keyDown(panel, { key: "Escape" });
    expect(view.queryByRole("dialog", { name: "Keyboard details" })).toBeNull();
    expect(document.activeElement).toBe(trigger);

    await fireEvent.click(trigger);
    panel = view.getByRole("dialog", { name: "Keyboard details" });
    await waitFor(() => expect(document.activeElement).toBe(panel));
    await fireEvent.mouseDown(background);
    expect(view.queryByRole("dialog", { name: "Keyboard details" })).toBeNull();
  });
});
