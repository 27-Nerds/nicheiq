<script lang="ts">
  import { page } from "$app/state";
  import { invalidateAll, goto } from "$app/navigation";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import type { TokenPackage } from "$lib/types/billing";
  import { Loader2 } from "lucide-svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  // ── Local state ──────────────────────────────────────────
  let packages = $state<TokenPackage[]>([]);
  let packagesLoading = $state(false);
  let packagesError = $state("");

  let checkoutLoading = $state<string | null>(null);
  let checkoutError = $state("");

  let promoExpanded = $state(false);
  let promoCode = $state("");
  let promoLoading = $state(false);
  let promoError = $state("");
  let promoSuccess = $state("");

  let showSuccess = $state(false);
  let successBalance = $state(0);
  let canceledNotice = $state(false);

  let stripeReturnHandled = $state(false);

  // ── Derived ──────────────────────────────────────────────
  const ctx = $derived(creditTopUp.context);
  const creditsNeeded = $derived(ctx ? Math.max(0, ctx.required - ctx.balance) : 0);

  // Subscription-awareness — read from the (app) layout's page.data so call
  // sites don't have to pass it.
  const monthlyAllowance = $derived(
    (page.data.monthlyAllowance as number) ?? 0,
  );
  const monthlyAllowancePeriodEnd = $derived(
    (page.data.monthlyAllowancePeriodEnd as string | null) ?? null,
  );
  const subscription = $derived(
    (page.data.subscription as { status?: string } | null) ?? null,
  );
  const isSubscriber = $derived(
    subscription?.status === "ACTIVE" || subscription?.status === "TRIALING",
  );
  const monthlyResetDate = $derived(
    monthlyAllowancePeriodEnd
      ? new Date(monthlyAllowancePeriodEnd).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        })
      : null,
  );
  // A subscriber who has exhausted their monthly allowance.
  const monthlyExhausted = $derived(
    isSubscriber && monthlyAllowance === 0,
  );

  // Show max 3 packages, sorted by credits ascending. Shortfall-aware: the window
  // always includes the smallest package that covers the need, even when that
  // package sits beyond the first three.
  const displayPackages = $derived.by(() => {
    const sorted = [...packages].sort((a, b) => a.credits - b.credits);
    const coverIdx = sorted.findIndex((p) => p.credits >= creditsNeeded);
    // Nothing covers — show the largest packages so "Best value" is the true largest.
    if (coverIdx === -1) return sorted.slice(-3);
    if (coverIdx >= 3) return sorted.slice(coverIdx - 2, coverIdx + 1);
    return sorted.slice(0, 3);
  });

  // Smart recommendation: cheapest package covering the need, or largest as "Best value"
  const recommended = $derived.by(() => {
    if (displayPackages.length === 0 || !ctx) return null;
    const covers = displayPackages.find((p) => p.credits >= creditsNeeded);
    if (covers) return { pkg: covers, label: "Covers your need" };
    // No package covers — recommend the largest
    const largest = displayPackages[displayPackages.length - 1];
    return { pkg: largest, label: "Best value" };
  });

  const overlayTitle = $derived(showSuccess ? "You're all set!" : "Add credits");
  const overlayDescription = $derived(
    !showSuccess && ctx
      ? `You need ${creditsNeeded} more for ${ctx.stageName}`
      : undefined,
  );

  // ── Fetch packages on open ───────────────────────────────
  $effect(() => {
    if (!creditTopUp.open) return;

    // Use cached packages if available
    if (creditTopUp.cachedPackages) {
      packages = creditTopUp.cachedPackages;
      return;
    }

    packagesLoading = true;
    packagesError = "";

    fetch("/api/billing/packages")
      .then((res) => res.json())
      .then((data) => {
        packages = data.packages || [];
        creditTopUp.cachedPackages = packages;
      })
      .catch(() => {
        packagesError = "Failed to load packages.";
      })
      .finally(() => {
        packagesLoading = false;
      });
  });

  // ── Stripe return detection ──────────────────────────────
  $effect(() => {
    if (stripeReturnHandled) return;
    const params = page.url.searchParams;

    if (params.has("credits_added")) {
      stripeReturnHandled = true;
      handleCreditsAdded();
    } else if (params.has("checkout_canceled")) {
      stripeReturnHandled = true;
      handleCheckoutCanceled();
    }
  });

  // ── Auto-close on success ────────────────────────────────
  $effect(() => {
    if (!showSuccess) return;
    const timer = setTimeout(() => {
      showSuccess = false;
      creditTopUp.open = false;
    }, 2000);
    return () => clearTimeout(timer);
  });

  // ── Handlers ─────────────────────────────────────────────
  async function handleCreditsAdded() {
    await invalidateAll();
    successBalance = (page.data.creditBalance as number) ?? 0;
    showSuccess = true;
    creditTopUp.open = true;

    // Clean URL params
    const cleanUrl = page.url.pathname;
    const params = new URLSearchParams(page.url.search);
    params.delete("credits_added");
    params.delete("session_id");
    const qs = params.toString();
    goto(qs ? `${cleanUrl}?${qs}` : cleanUrl, { replaceState: true });
  }

  async function handleCheckoutCanceled() {
    canceledNotice = true;
    creditTopUp.open = true;

    // Clean URL params
    const cleanUrl = page.url.pathname;
    const params = new URLSearchParams(page.url.search);
    params.delete("checkout_canceled");
    const qs = params.toString();
    goto(qs ? `${cleanUrl}?${qs}` : cleanUrl, { replaceState: true });
  }

  async function startCheckout(packageId: string) {
    if (checkoutLoading) return;

    checkoutLoading = packageId;
    checkoutError = "";

    try {
      const returnUrl = window.location.pathname + window.location.search;
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ packageId, returnUrl }),
      });

      const data = await res.json();
      if (res.ok && data.url) {
        window.location.href = data.url;
      } else {
        checkoutError = data.error || "Failed to start checkout.";
      }
    } catch {
      checkoutError = "Network error. Please try again.";
    } finally {
      checkoutLoading = null;
    }
  }

  async function redeemPromo() {
    if (!promoCode.trim() || promoLoading) return;

    promoLoading = true;
    promoError = "";
    promoSuccess = "";

    try {
      const res = await fetch("/api/billing/redeem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: promoCode.trim() }),
      });

      const data = await res.json();
      if (res.ok) {
        promoSuccess = data.message || `${data.creditsGranted} credits added!`;
        promoCode = "";
        await invalidateAll();
        const freshBalance = (page.data.creditBalance as number) ?? 0;
        if (ctx && freshBalance >= ctx.required) {
          // Balance now sufficient — show success and auto-close
          successBalance = freshBalance;
          showSuccess = true;
        }
      } else {
        promoError = data.error || "Invalid promo code.";
      }
    } catch {
      promoError = "Network error. Please try again.";
    } finally {
      promoLoading = false;
    }
  }

  function handleClose() {
    if (checkoutLoading) return;
    creditTopUp.open = false;
    canceledNotice = false;
    promoExpanded = false;
    promoCode = "";
    promoError = "";
    promoSuccess = "";
    checkoutError = "";
  }

  function formatPrice(cents: number): string {
    const dollars = cents / 100;
    return dollars % 1 === 0 ? `$${dollars}` : `$${dollars.toFixed(2)}`;
  }
</script>

<FormOverlay
  open={creditTopUp.open}
  eyebrow="Billing"
  title={overlayTitle}
  description={overlayDescription}
  onRequestClose={handleClose}
>
  {#if showSuccess}
    <p class="topup-success" role="status">
      <strong>{successBalance}</strong> credits added.
    </p>
  {:else}
    {#if monthlyExhausted}
      <p class="topup-note">
        {#if monthlyResetDate}
          Your monthly credits reset on <strong>{monthlyResetDate}</strong>. Top up below to keep going now.
        {:else}
          Your monthly credits are used up. Top up below to keep going now.
        {/if}
      </p>
    {:else if !isSubscriber}
      <p class="topup-note">
        <a href="/billing#plans" class="topup-link">Subscribe to save</a>: get monthly credits + full catalog access.
      </p>
    {/if}

    {#if canceledNotice}
      <p class="topup-note">
        Checkout canceled. Try again or pick a different package.
      </p>
    {/if}

    <!-- Packages -->
    <div class="topup-packages">
      {#if packagesLoading}
        <div class="topup-loading">
          <Loader2 class="w-5 h-5 animate-spin" aria-hidden="true" />
        </div>
      {:else if packagesError}
        <p class="topup-error" role="alert">
          {packagesError}
          <a href="/billing" class="topup-link">Go to billing</a>
        </p>
      {:else if displayPackages.length === 0}
        <EmptyState title="No packages available.">
          <a href="/billing" class="topup-link">Go to the billing page</a>
        </EmptyState>
      {:else}
        {#each displayPackages as pkg, i}
          {@const isRecommended = recommended?.pkg.id === pkg.id}

          {#if i > 0}
            <hr class="pkg-rule" />
          {/if}

          <div class="pkg-row">
            <div class="pkg-line">
              <span class="pkg-name">{pkg.name}</span>
              <span class="pkg-price">
                {#if pkg.promoPriceInCents}
                  <s class="pkg-price-old">{formatPrice(pkg.priceInCents)}</s>
                  <span class="pkg-price-promo">{formatPrice(pkg.promoPriceInCents)}</span>
                {:else}
                  {formatPrice(pkg.priceInCents)}
                {/if}
              </span>
            </div>

            <div class="pkg-line">
              <span class="pkg-credits">
                {pkg.credits} credits{#if isRecommended}<span class="pkg-recommended"> · {recommended?.label}</span>{/if}
              </span>
              {#if isRecommended}
                <SubmitButton
                  type="button"
                  onclick={() => startCheckout(pkg.id)}
                  loading={checkoutLoading === pkg.id}
                  loadingText="Redirecting…"
                  label="Continue"
                  disabled={!!checkoutLoading}
                  minWidth="8.5rem"
                  class=""
                />
              {:else}
                <button
                  type="button"
                  class="pkg-btn"
                  onclick={() => startCheckout(pkg.id)}
                  disabled={!!checkoutLoading}
                  aria-busy={checkoutLoading === pkg.id || undefined}
                >
                  {#if checkoutLoading === pkg.id}
                    <Loader2 class="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                    Redirecting…
                  {:else}
                    Get credits
                  {/if}
                </button>
              {/if}
            </div>
            {#if isRecommended && pkg.credits < creditsNeeded}
              <p class="pkg-shortfall">Covers {pkg.credits} of {creditsNeeded} needed</p>
            {/if}
          </div>
        {/each}
      {/if}

      {#if checkoutError}
        <p class="topup-error" role="alert">Something went wrong. Please try again.</p>
      {/if}
    </div>

    <!-- Promo code -->
    <div class="topup-promo">
      {#if !promoExpanded}
        <button type="button" class="promo-toggle" onclick={() => (promoExpanded = true)}>
          Have a code?
        </button>
      {:else}
        <div class="promo-row">
          <label class="sr-only" for="topup-promo-code">Promo code</label>
          <input
            id="topup-promo-code"
            type="text"
            bind:value={promoCode}
            placeholder="Enter code"
            disabled={promoLoading}
            onkeydown={(e) => e.key === "Enter" && redeemPromo()}
            class="promo-input"
          />
          <button
            type="button"
            class="promo-apply"
            onclick={redeemPromo}
            disabled={!promoCode.trim() || promoLoading}
            aria-busy={promoLoading || undefined}
          >
            {#if promoLoading}
              <Loader2 class="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
            {:else}
              Apply
            {/if}
          </button>
        </div>
        {#if promoError}
          <p class="promo-error" role="alert">{promoError}</p>
        {/if}
        {#if promoSuccess}
          <p class="promo-success" role="status">{promoSuccess}</p>
        {/if}
      {/if}
    </div>
  {/if}
</FormOverlay>

<style>
  .topup-success {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.5;
  }

  .topup-success strong {
    color: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .topup-note {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .topup-note strong {
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  .topup-link {
    color: var(--color-accent-dark);
    text-decoration: none;
  }

  .topup-link:hover {
    text-decoration: underline;
  }

  .topup-packages {
    display: grid;
    gap: 0.75rem;
  }

  .topup-loading {
    display: flex;
    justify-content: center;
    padding: 1.5rem 0;
    color: var(--color-text-muted);
  }

  .pkg-rule {
    margin: 0;
    border: 0;
    border-top: 1px solid var(--color-border);
  }

  .pkg-row {
    display: grid;
    gap: 0.5rem;
  }

  .pkg-line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .pkg-name {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .pkg-price {
    font-family: var(--font-mono);
    font-size: var(--text-13);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    color: var(--color-text-primary);
  }

  .pkg-price-old {
    margin-right: 0.35rem;
    font-weight: 500;
    color: var(--color-text-muted);
  }

  .pkg-price-promo {
    color: var(--color-success-text);
  }

  .pkg-credits {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  .pkg-recommended {
    font-weight: 600;
    color: var(--color-accent-dark);
  }

  /* Honesty sub-line when no package covers the shortfall — information, not a fault. */
  .pkg-shortfall {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  .pkg-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-height: 2.1rem;
    min-width: 8.5rem;
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .pkg-btn:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .pkg-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .pkg-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .topup-error {
    margin: 0;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    color: var(--color-error-text);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .topup-error .topup-link {
    margin-left: auto;
    flex: 0 0 auto;
    font-size: var(--text-sm);
  }

  .topup-promo {
    padding-top: 0.9rem;
    border-top: 1px solid var(--color-border);
  }

  .promo-toggle {
    padding: 0;
    border: 0;
    background: none;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }

  .promo-toggle:hover {
    color: var(--color-text-secondary);
  }

  .promo-toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .promo-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .promo-input {
    flex: 1;
    min-width: 0;
    min-height: 2.35rem;
    padding: 0 0.65rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-13);
    line-height: 1.45;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      box-shadow var(--duration-fast) var(--ease-default);
  }

  .promo-input::placeholder {
    color: var(--color-text-muted);
  }

  .promo-input:hover:not(:disabled) {
    border-color: var(--color-input-border-hover);
  }

  .promo-input:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }

  .promo-input:disabled {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }

  .promo-apply {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    min-height: 2.35rem;
    min-width: 4.5rem;
    padding: 0 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 600;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .promo-apply:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .promo-apply:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .promo-apply:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .promo-error {
    margin: 0.5rem 0 0;
    color: var(--color-error-text);
    font-size: var(--text-sm);
  }

  .promo-success {
    margin: 0.5rem 0 0;
    color: var(--color-success-text);
    font-size: var(--text-sm);
  }
</style>
