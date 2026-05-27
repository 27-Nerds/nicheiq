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
};
