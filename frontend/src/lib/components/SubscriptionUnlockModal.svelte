<script lang="ts">
  import { page } from "$app/state";
  import { invalidateAll, goto } from "$app/navigation";
  import { subscribeUnlock } from "$lib/stores/subscribeUnlock.svelte";
  import type { SubscriptionPlan } from "$lib/types/billing";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import PricingCard from "$lib/components/ui/PricingCard.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  // ── Local state ──────────────────────────────────────────
  let plans = $state<SubscriptionPlan[]>([]);
  let plansLoading = $state(false);
  let plansError = $state("");

  let subscribeLoading = $state<string | null>(null);
  let portalLoading = $state(false);
  let actionError = $state("");
  let portalFallback = $state(false); // portal had no Stripe customer (400) — link to /billing

  let showSuccess = $state(false);
  let canceledNotice = $state(false);
  let stripeReturnHandled = $state(false);
  let unlockParamHandled = $state(false);

  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Derived ──────────────────────────────────────────────
  const busy = $derived(subscribeLoading !== null || portalLoading);
  const planCols = $derived(Math.min(plans.length, 3) || 3);

  // ── Fetch plans on open ──────────────────────────────────
  $effect(() => {
    if (!subscribeUnlock.open) return;

    if (subscribeUnlock.cachedPlans) {
      plans = subscribeUnlock.cachedPlans;
      return;
    }

    plansLoading = true;
    plansError = "";

    fetch("/api/billing/plans")
      .then((res) => res.json())
      .then((data) => {
        plans = data.plans || [];
        subscribeUnlock.cachedPlans = plans;
      })
      .catch(() => {
        plansError = "Failed to load plans.";
      })
      .finally(() => {
        plansLoading = false;
      });
  });

  // ── Stripe return + ?unlock detection ────────────────────
  $effect(() => {
    const params = page.url.searchParams;
    // Billing owns its own sub_success / sub_canceled banners — never auto-handle
    // (or consume the guard) there now that this modal is mounted globally.
    const onBilling = page.url.pathname === "/billing";

    if (!stripeReturnHandled && !onBilling) {
      if (params.has("sub_success")) {
        stripeReturnHandled = true;
        handleSubSuccess();
      } else if (params.has("sub_canceled")) {
        stripeReturnHandled = true;
        handleSubCanceled();
      }
    }

    // Auto-open from a 403 redirect to /ideas?unlock=1. Separate one-shot guard so
    // it can't consume Stripe-return handling. Logged-in only — the subscribe
    // endpoint needs a session; logged-out visitors just get the URL cleaned.
    if (!unlockParamHandled && params.has("unlock")) {
      unlockParamHandled = true;
      if (page.data.session?.user) subscribeUnlock.open = true;
      stripParams("unlock");
    }
  });

  // Clear any pending retry timer when the component is torn down.
  $effect(() => {
    return () => {
      if (retryTimer) clearTimeout(retryTimer);
    };
  });

  // ── Handlers ─────────────────────────────────────────────
  // Entitlement flips on the Stripe webhook, which can lag the redirect. Run one
  // immediate refresh, then a single delayed retry; the success state also offers
  // a manual Refresh. We never assert "active" — only "completed / unlocking".
  async function handleSubSuccess() {
    showSuccess = true;
    subscribeUnlock.open = true;
    await invalidateAll();
    stripParams("sub_success", "session_id");
    retryTimer = setTimeout(() => {
      invalidateAll();
    }, 4000);
  }

  function handleSubCanceled() {
    canceledNotice = true;
    subscribeUnlock.open = true;
    stripParams("sub_canceled");
  }

  // Strip the named result params, preserving any others (mirrors CreditTopUpModal).
  function stripParams(...keys: string[]) {
    const params = new URLSearchParams(page.url.search);
    keys.forEach((k) => params.delete(k));
    const qs = params.toString();
    const cleanUrl = page.url.pathname;
    goto(qs ? `${cleanUrl}?${qs}` : cleanUrl, { replaceState: true });
  }

  // Current page path with result params stripped, so a re-checkout can't
  // duplicate or forge them.
  function currentReturnUrl(): string {
    const params = new URLSearchParams(window.location.search);
    for (const p of [
      "sub_success",
      "sub_canceled",
      "credits_added",
      "checkout_canceled",
      "session_id",
      "unlock",
    ]) {
      params.delete(p);
    }
    const qs = params.toString();
    return window.location.pathname + (qs ? `?${qs}` : "");
  }

  async function startSubscribe(planId: string) {
    if (busy) return;
    subscribeLoading = planId;
    actionError = "";
    portalFallback = false;

    try {
      const res = await fetch("/api/billing/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planId, returnUrl: currentReturnUrl() }),
      });

      if (res.status === 409) {
        // Already a live (but not necessarily entitled) subscription — manage via portal.
        subscribeLoading = null;
        await openPortal();
        return;
      }

      const data = await res.json();
      if (res.ok && data.url) {
        window.location.href = data.url;
      } else {
        actionError = data.error || "Failed to start subscription.";
      }
    } catch {
      actionError = "Network error. Please try again.";
    } finally {
      subscribeLoading = null;
    }
  }

  async function openPortal() {
    if (portalLoading) return;
    portalLoading = true;
    actionError = "";
    portalFallback = false;

    try {
      const res = await fetch("/api/billing/portal", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.url) {
        window.location.href = data.url;
      } else if (data.code === "NO_CUSTOMER") {
        portalFallback = true;
      } else {
        actionError = data.error || "Unable to open the billing portal.";
      }
    } catch {
      actionError = "Network error. Please try again.";
    } finally {
      portalLoading = false;
    }
  }

  function refresh() {
    invalidateAll();
  }

  function handleClose() {
    if (busy) return;
    subscribeUnlock.open = false;
    showSuccess = false;
    canceledNotice = false;
    actionError = "";
    portalFallback = false;
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  }
</script>

<FormOverlay
  open={subscribeUnlock.open}
  eyebrow="Subscription"
  title={showSuccess ? "Subscription completed" : "Unlock the full catalog"}
  description={showSuccess
    ? undefined
    : "Subscribe for monthly research credits and full access to every validated idea, pain point, and competitive landscape."}
  onRequestClose={handleClose}
>
  {#if showSuccess}
    <p class="unlock-note" role="status">
      Unlocking shortly. If the catalog is still locked, give it a moment and refresh.
    </p>
  {:else}
    {#if canceledNotice}
      <p class="unlock-note">Checkout canceled: no charges were made. Pick a plan to try again.</p>
    {/if}

    {#if plansLoading}
      <div class="plan-grid" data-cols="3">
        {#each [0, 1, 2] as i}
          <div class="skeleton skeleton-rectangular plan-skeleton" style="animation-delay: {i * 40}ms"></div>
        {/each}
      </div>
    {:else if plansError}
      <p class="unlock-error" role="alert">
        {plansError}
        <a href="/billing#plans" class="unlock-link">Go to billing</a>
      </p>
    {:else if plans.length === 0}
      <EmptyState title="No plans available right now.">
        <a href="/billing#plans" class="unlock-link">Go to the billing page</a>
      </EmptyState>
    {:else}
      <div class="plan-grid" data-cols={planCols}>
        {#each plans as plan (plan.id)}
          <PricingCard {plan} variant="compact">
            {#snippet actions()}
              <SubmitButton
                type="button"
                onclick={() => startSubscribe(plan.id)}
                loading={subscribeLoading === plan.id}
                loadingText="Redirecting…"
                label={plan.ctaText || "Subscribe"}
                disabled={busy}
                class="{plan.isPopular ? 'btn-primary' : 'btn-secondary'} w-full"
              />
            {/snippet}
          </PricingCard>
        {/each}
      </div>
    {/if}

    {#if actionError}
      <p class="unlock-error" role="alert">{actionError}</p>
    {/if}

    {#if portalFallback}
      <p class="unlock-note">
        You already have a subscription.
        <a href="/billing" class="unlock-link">Manage it on the billing page</a>.
      </p>
    {/if}

    <a href="/billing#plans" class="unlock-compare">Compare all plans →</a>
  {/if}

  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" onclick={handleClose} disabled={busy}>
      Close
    </button>
  {/snippet}
  {#snippet footer()}
    {#if showSuccess}
      <SubmitButton
        type="button"
        onclick={refresh}
        loadingText=""
        label="Refresh"
        minWidth="9.5rem"
        class=""
      />
    {/if}
  {/snippet}
</FormOverlay>

<style>
  .unlock-note {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .unlock-link {
    color: var(--color-accent-dark);
    text-decoration: none;
  }

  .unlock-link:hover {
    text-decoration: underline;
  }

  .unlock-error {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin: 0;
    color: var(--color-error-text);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .unlock-error .unlock-link {
    margin-left: auto;
    flex: 0 0 auto;
    font-size: var(--text-sm);
  }

  .plan-grid {
    display: grid;
    gap: 1rem;
  }

  .plan-grid[data-cols="1"] {
    max-width: 24rem;
    margin-inline: auto;
    width: 100%;
  }

  @media (min-width: 640px) {
    .plan-grid[data-cols="2"] {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      max-width: 42rem;
      margin-inline: auto;
      width: 100%;
    }

    .plan-grid[data-cols="3"] {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  .plan-skeleton {
    height: 14rem;
    border-radius: var(--radius-lg);
  }

  .unlock-compare {
    justify-self: start;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color var(--duration-fast) var(--ease-default);
  }

  .unlock-compare:hover {
    color: var(--color-text-secondary);
  }

  .unlock-compare:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>
