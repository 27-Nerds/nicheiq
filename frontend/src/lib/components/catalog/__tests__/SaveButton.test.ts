import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import { goto } from "$app/navigation";
import SaveButton from "../SaveButton.svelte";

// The save POST returns 403 when a non-entitled user tries to save a
// non-featured item. The button should revert and route to /unlock-catalog
// rather than fail silently (defence-in-depth — the button normally only
// renders on accessible detail pages).

describe("SaveButton — 403 from save POST", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("routes to /unlock-catalog and reverts on a 403", async () => {
    const itemId = "idea-123";
    const fetchMock = vi.fn((_url: string, init?: { method?: string }) => {
      const method = init?.method ?? "GET";
      if (method === "GET") {
        // status endpoint → not currently saved
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ [itemId]: false }) });
      }
      // POST → 403 (not entitled to save this item)
      return Promise.resolve({ ok: false, status: 403 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(SaveButton, { props: { itemType: "idea", itemId, returnTo: "/idea/x" } });

    const btn = await screen.findByRole("button", { name: /save this idea/i });
    await fireEvent.click(btn);

    await vi.waitFor(() => {
      expect(goto).toHaveBeenCalledWith("/unlock-catalog");
    });
    // Reverted to not-saved (a POST that 403s must not leave it showing "Saved").
    expect(screen.queryByText("Saved")).toBeNull();
  });
});
