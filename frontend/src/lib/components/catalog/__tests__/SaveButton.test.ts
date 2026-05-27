import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import { goto } from "$app/navigation";
import { subscribeUnlock } from "$lib/stores/subscribeUnlock.svelte";
import SaveButton from "../SaveButton.svelte";

// A 403 from the save POST (non-entitled user, non-featured item) should revert
// the optimistic toggle and open the subscribe popup in place — not navigate
// away to /unlock-catalog. (The button only renders on accessible detail pages,
// so this is defence-in-depth; the user is authenticated here.)

describe("SaveButton — 403 from save POST", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    subscribeUnlock.open = false;
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    subscribeUnlock.open = false;
  });

  it("opens the subscribe popup and reverts on a 403 (no navigation)", async () => {
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
      expect(subscribeUnlock.open).toBe(true);
    });
    // No navigation to the unlock hub — the popup is the surface now.
    expect(goto).not.toHaveBeenCalledWith("/unlock-catalog");
    // Reverted to not-saved (a POST that 403s must not leave it showing "Saved").
    expect(screen.queryByText("Saved")).toBeNull();
  });
});
