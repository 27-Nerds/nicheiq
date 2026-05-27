import { page } from '$app/state';
import type { SubscriptionPlan } from '$lib/types/billing';

// Drives the catalog "Subscribe to unlock" popup. Mirrors creditTopUp.svelte.ts.
// No context object: the gate only renders for non-entitled users, so opening
// the modal always means "show the plans".
let _open = $state(false);
let _cachedPlans = $state<SubscriptionPlan[] | null>(null);

export const subscribeUnlock = {
  get open() { return _open; },
  set open(v: boolean) { _open = v; },
  get cachedPlans() { return _cachedPlans; },
  set cachedPlans(v: SubscriptionPlan[] | null) { _cachedPlans = v; },
  show() {
    _open = true;
  },
  // Shared CTA handler for every "subscribe to unlock" link/button. Logged-in
  // users get the popup in place; logged-out users fall through to the anchor's
  // href (/unlock-catalog → register), preserving the no-JS path. `page` is read
  // only here, inside a client click handler — never during SSR.
  requestUnlock(e?: MouseEvent) {
    if (page.data.session?.user) {
      e?.preventDefault();
      _open = true;
    }
  },
};
