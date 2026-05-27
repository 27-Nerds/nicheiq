import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { tick } from "svelte";
import { render } from "@testing-library/svelte";
import { page } from "$app/state";
import { subscribeUnlock } from "$lib/stores/subscribeUnlock.svelte";
import SubscriptionUnlockModal from "../SubscriptionUnlockModal.svelte";

// The modal is mounted globally (root layout), so its URL effect must be
// path-aware: auto-open on ?unlock for logged-in users, ignore it for logged-out
// visitors, and never hijack /billing's own sub_success/sub_canceled banners.

const origUrl = page.url;
const origSession = page.data.session;

beforeEach(() => {
  vi.clearAllMocks();
  subscribeUnlock.open = false;
  // Opening the modal triggers a plans fetch — stub it.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ plans: [] }) })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  page.url = origUrl;
  page.data.session = origSession;
  subscribeUnlock.open = false;
});

describe("SubscriptionUnlockModal — URL triggers", () => {
  it("auto-opens for a logged-in user on ?unlock", async () => {
    page.url = new URL("http://localhost/ideas?unlock=1") as typeof page.url;
    render(SubscriptionUnlockModal);
    await vi.waitFor(() => expect(subscribeUnlock.open).toBe(true));
  });

  it("does NOT auto-open for a logged-out visitor on ?unlock", async () => {
    page.url = new URL("http://localhost/ideas?unlock=1") as typeof page.url;
    page.data.session = null;
    render(SubscriptionUnlockModal);
    await tick();
    expect(subscribeUnlock.open).toBe(false);
  });

  it("does NOT auto-open on /billing?sub_success (billing owns its banner)", async () => {
    page.url = new URL("http://localhost/billing?sub_success=true") as typeof page.url;
    render(SubscriptionUnlockModal);
    await tick();
    expect(subscribeUnlock.open).toBe(false);
  });
});
