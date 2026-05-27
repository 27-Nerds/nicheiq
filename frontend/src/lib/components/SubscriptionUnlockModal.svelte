<script lang="ts">
  import { page } from "$app/state";
  import { invalidateAll, goto } from "$app/navigation";
  import { portal } from "$lib/actions/portal";
  import { subscribeUnlock } from "$lib/stores/subscribeUnlock.svelte";
  import type { SubscriptionPlan } from "$lib/types/billing";
  import { X, AlertCircle, Check, ArrowRight } from "lucide-svelte";
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

  let modalEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLElement | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Derived ──────────────────────────────────────────────
  const busy = $derived(subscribeLoading !== null || portalLoading);
  // Center the grid when there are fewer than 3 plans (mirrors billing page).
  const planGridClass = $derived(
    plans.length === 1
      ? "sm:grid-cols-1 max-w-sm mx-auto"
      : plans.length === 2
        ? "sm:grid-cols-2 max-w-2xl mx-auto"
        : "sm:grid-cols-3",
  );

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

  // ── Lock background scroll while open (matches CategoryItemsModal) ──
  $effect(() => {
    if (!subscribeUnlock.open) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  });

  // ── Focus management ─────────────────────────────────────
  $effect(() => {
    if (subscribeUnlock.open && modalEl) {
      triggerEl = document.activeElement as HTMLElement;
      const focusable = getFocusableElements();
      if (focusable.length > 0) focusable[0].focus();
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
    triggerEl?.focus();
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && !busy) handleClose();
  }

  function getFocusableElements(): HTMLElement[] {
    if (!modalEl) return [];
    return Array.from(
      modalEl.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && subscribeUnlock.open && !busy) {
      handleClose();
      return;
    }
    if (e.key === "Tab" && subscribeUnlock.open) {
      const focusable = getFocusableElements();
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if subscribeUnlock.open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    use:portal
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    aria-label="Unlock the full catalog"
    tabindex="-1"
  >
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in"
      style="animation-duration: 150ms"
    ></div>

    <!-- Panel -->
    <div
      bind:this={modalEl}
      class="relative bg-bg-elevated border border-border rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto animate-fade-slide-in shadow-[0_1px_3px_rgba(24,24,27,0.04),0_8px_24px_-4px_rgba(24,24,27,0.08),0_20px_48px_-8px_rgba(24,24,27,0.06)]"
      style="animation-duration: 200ms"
    >
      {#if showSuccess}
        <div class="p-8 text-center">
          <div
            class="mx-auto w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mb-4 animate-scale-in visible"
          >
            <Check class="w-7 h-7 text-success" />
          </div>
          <h2 class="font-display font-bold text-xl text-text-primary mb-1">
            Subscription completed
          </h2>
          <p class="text-sm text-text-secondary">
            Unlocking shortly… if the catalog is still locked, give it a moment and refresh.
          </p>
          <div class="flex items-center justify-center gap-2 mt-5">
            <SubmitButton
              type="button"
              onclick={refresh}
              loadingText=""
              label="Refresh"
              class="btn-primary !px-4 !py-1.5 !text-sm"
            />
            <button onclick={handleClose} class="btn-secondary !px-4 !py-1.5 !text-sm">
              Close
            </button>
          </div>
        </div>
      {:else}
        <!-- Close -->
        <button
          onclick={handleClose}
          disabled={busy}
          aria-label="Close"
          class="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-bg-hover text-text-muted/60 hover:text-text-primary transition-colors disabled:opacity-50 z-10"
        >
          <X class="w-4 h-4" />
        </button>

        <!-- Header -->
        <div class="px-6 pt-6 pb-2">
          <h2 class="font-display font-bold text-lg text-text-primary tracking-tight">
            Unlock the full catalog
          </h2>
          <p class="text-sm text-text-muted mt-1">
            Subscribe for monthly research credits and full access to every validated idea,
            pain point, and competitive landscape.
          </p>
        </div>

        {#if canceledNotice}
          <p class="text-sm text-text-muted px-6 mt-2">
            Checkout canceled — no charges were made. Pick a plan to try again.
          </p>
        {/if}

        <!-- Plans -->
        <div class="px-6 py-4">
          {#if plansLoading}
            <div class="grid gap-4 sm:grid-cols-3">
              {#each [0, 1, 2] as i}
                <div class="skeleton skeleton-rectangular h-56 rounded-xl" style="animation-delay: {i * 40}ms"></div>
              {/each}
            </div>
          {:else if plansError}
            <div class="flex items-center gap-2 text-sm text-error">
              <AlertCircle class="w-4 h-4 shrink-0" />
              <span>{plansError}</span>
              <a href="/billing#plans" class="ml-auto text-accent hover:underline text-xs shrink-0">Go to billing</a>
            </div>
          {:else if plans.length === 0}
            <div class="text-center py-6 text-sm text-text-muted">
              <p>No plans available right now.</p>
              <a href="/billing#plans" class="text-accent hover:underline mt-1 inline-block">Go to the billing page</a>
            </div>
          {:else}
            <div class="grid gap-4 {planGridClass}">
              {#each plans as plan (plan.id)}
                <PricingCard {plan} variant="compact">
                  {#snippet actions()}
                    <SubmitButton
                      type="button"
                      onclick={() => startSubscribe(plan.id)}
                      loading={subscribeLoading === plan.id}
                      loadingText="Redirecting..."
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
            <p class="text-sm text-error mt-3">
              <span class="inline-block w-1.5 h-1.5 rounded-full bg-error mr-1.5 relative top-[-1px]"></span>
              {actionError}
            </p>
          {/if}

          {#if portalFallback}
            <p class="text-sm text-text-muted mt-3">
              You already have a subscription. <a href="/billing" class="text-accent hover:underline">Manage it on the billing page</a>.
            </p>
          {/if}
        </div>

        <!-- Footer -->
        <div class="px-6 pb-5">
          <div class="border-t border-border pt-3">
            <a
              href="/billing#plans"
              class="inline-flex items-center gap-1 text-sm text-text-muted hover:text-accent transition-colors"
            >
              Compare all plans
              <ArrowRight class="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
