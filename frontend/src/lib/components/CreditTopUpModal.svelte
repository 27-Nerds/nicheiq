<script lang="ts">
  import { page } from "$app/state";
  import { invalidateAll, goto } from "$app/navigation";
  import { portal } from "$lib/actions/portal";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import type { TokenPackage } from "$lib/types/billing";
  import {
    X,
    Loader2,
    AlertCircle,
    Check,
  } from "lucide-svelte";

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
  let modalEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLElement | null = null;

  // ── Derived ──────────────────────────────────────────────
  const ctx = $derived(creditTopUp.context);
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  const creditsNeeded = $derived(ctx ? Math.max(0, ctx.required - ctx.balance) : 0);

  // Show max 3 packages, sorted by credits ascending
  const displayPackages = $derived.by(() => {
    const sorted = [...packages].sort((a, b) => a.credits - b.credits);
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

  // ── Focus management ─────────────────────────────────────
  $effect(() => {
    if (creditTopUp.open && modalEl) {
      triggerEl = document.activeElement as HTMLElement;
      const focusable = getFocusableElements();
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }
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
    triggerEl?.focus();
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && !checkoutLoading) {
      handleClose();
    }
  }

  function getFocusableElements(): HTMLElement[] {
    if (!modalEl) return [];
    return Array.from(
      modalEl.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && creditTopUp.open && !checkoutLoading) {
      handleClose();
      return;
    }

    if (e.key === "Tab" && creditTopUp.open) {
      const focusable = getFocusableElements();
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  }

  function formatPrice(cents: number): string {
    const dollars = cents / 100;
    return dollars % 1 === 0 ? `$${dollars}` : `$${dollars.toFixed(2)}`;
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if creditTopUp.open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    use:portal
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    aria-label="Add credits"
    tabindex="-1"
  >
    <!-- Backdrop -->
    <div class="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" style="animation-duration: 150ms"></div>

    <!-- Panel -->
    <div
      bind:this={modalEl}
      class="relative bg-bg-elevated border border-border rounded-xl w-full max-w-md max-h-[90vh] overflow-y-auto animate-fade-slide-in shadow-[0_1px_3px_rgba(24,24,27,0.04),0_8px_24px_-4px_rgba(24,24,27,0.08),0_20px_48px_-8px_rgba(24,24,27,0.06)]"
      style="animation-duration: 200ms"
    >
      {#if showSuccess}
        <div class="p-8 text-center">
          <div class="mx-auto w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mb-4 animate-scale-in visible">
            <Check class="w-7 h-7 text-success" />
          </div>
          <h2 class="font-display font-bold text-xl text-text-primary mb-1">You're all set!</h2>
          <p class="text-sm text-text-secondary">
            <span class="font-display font-bold tabular-nums text-text-primary">{successBalance}</span> credits added.
          </p>
        </div>
      {:else}
        <!-- Close -->
        <button
          onclick={handleClose}
          disabled={!!checkoutLoading}
          aria-label="Close"
          class="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-bg-hover text-text-muted/60 hover:text-text-primary transition-colors disabled:opacity-50 z-10"
        >
          <X class="w-4 h-4" />
        </button>

        <!-- Header -->
        <div class="px-5 pt-5 pb-0">
          <h2 class="font-display font-bold text-md text-text-primary tracking-tight">Add credits</h2>
          {#if ctx}
            <p class="text-sm text-text-muted mt-1">
              You need <span class="font-semibold tabular-nums text-accent">{creditsNeeded}</span> more for {ctx.stageName}
            </p>
          {/if}
        </div>

        {#if canceledNotice}
          <p class="text-sm text-text-muted px-5 mt-3">
            Checkout canceled — try again or pick a different package.
          </p>
        {/if}

        <!-- Packages -->
        <div class="px-5 py-4">
          {#if packagesLoading}
            {#each [0, 1] as i}
              <div class="py-3 space-y-2" style="animation-delay: {i * 40}ms">
                <div class="flex justify-between items-baseline">
                  <div class="skeleton skeleton-text w-20 h-3.5"></div>
                  <div class="skeleton skeleton-text w-14 h-4"></div>
                </div>
                <div class="flex justify-between items-center">
                  <div class="skeleton skeleton-text w-16 h-3"></div>
                  <div class="skeleton skeleton-rectangular w-20 h-8"></div>
                </div>
              </div>
              {#if i === 0}<div class="border-t border-border"></div>{/if}
            {/each}
          {:else if packagesError}
            <div class="flex items-center gap-2 text-sm text-error">
              <AlertCircle class="w-4 h-4 shrink-0" />
              <span>{packagesError}</span>
              <a href="/billing" class="ml-auto text-accent hover:underline text-xs shrink-0">Go to billing</a>
            </div>
          {:else if displayPackages.length === 0}
            <div class="text-center py-6 text-sm text-text-muted">
              <p>No packages available.</p>
              <a href="/billing" class="text-accent hover:underline mt-1 inline-block">Go to billing page</a>
            </div>
          {:else}
            {#each displayPackages as pkg, i}
              {@const isRecommended = recommended?.pkg.id === pkg.id}

              {#if i > 0}
                <div class="border-t border-border my-3"></div>
              {/if}

              <div
                class="animate-fade-slide-in {isRecommended ? 'pl-3 border-l-2 border-l-accent' : ''}"
                style="animation-delay: {i * 40}ms"
              >
                <div class="flex items-baseline justify-between">
                  <span class="text-base font-semibold text-text-primary">{pkg.name}</span>
                  <span class="font-display font-bold text-lg tabular-nums text-text-primary">
                    {#if pkg.promoPriceInCents}
                      <span class="text-sm text-text-muted line-through mr-1">{formatPrice(pkg.priceInCents)}</span>
                      <span class="text-success">{formatPrice(pkg.promoPriceInCents)}</span>
                    {:else}
                      {formatPrice(pkg.priceInCents)}
                    {/if}
                  </span>
                </div>

                <div class="flex items-center justify-between mt-1.5">
                  <span class="text-sm text-text-muted">
                    {pkg.credits} credits{#if isRecommended}<span class="text-accent font-medium ml-1.5">· Recommended</span>{/if}
                  </span>
                  <button
                    onclick={() => startCheckout(pkg.id)}
                    disabled={!!checkoutLoading}
                    class="inline-flex items-center gap-1.5
                           {isRecommended ? 'bg-accent text-white hover:bg-accent-hover' : 'bg-bg-surface text-text-primary border border-border hover:border-border-emphasis'}
                           px-3.5 py-1.5 text-sm font-medium rounded-md transition-colors active:scale-[0.97] disabled:opacity-50"
                  >
                    {#if checkoutLoading === pkg.id}
                      <Loader2 class="w-3 h-3 animate-spin" />
                      Redirecting...
                    {:else if isRecommended}
                      Continue
                    {:else}
                      Get credits
                    {/if}
                  </button>
                </div>
              </div>
            {/each}
          {/if}

          {#if checkoutError}
            <p class="text-sm text-error mt-3">
              <span class="inline-block w-1.5 h-1.5 rounded-full bg-error mr-1.5 relative top-[-1px]"></span>
              Something went wrong. Please try again.
            </p>
          {/if}
        </div>

        <!-- Promo code -->
        <div class="px-5 pb-4">
          <div class="border-t border-border pt-3 mt-1">
            {#if !promoExpanded}
              <button
                onclick={() => (promoExpanded = true)}
                class="text-sm text-text-muted hover:text-text-secondary transition-colors"
              >
                Have a code?
              </button>
            {:else}
              <div class="flex items-center gap-2">
                <input
                  type="text"
                  bind:value={promoCode}
                  placeholder="Enter code"
                  disabled={promoLoading}
                  onkeydown={(e) => e.key === "Enter" && redeemPromo()}
                  class="flex-1 text-sm px-2.5 py-1.5 rounded-md border border-border bg-bg-surface
                         focus:outline-none focus:border-accent/40 transition-colors disabled:opacity-50"
                />
                <button
                  onclick={redeemPromo}
                  disabled={!promoCode.trim() || promoLoading}
                  class="text-sm font-medium text-accent border border-accent/30 rounded-md px-2.5 py-1
                         hover:bg-accent/[0.04] active:scale-[0.97] transition-colors disabled:opacity-50"
                >
                  {#if promoLoading}
                    <Loader2 class="w-3 h-3 animate-spin inline" />
                  {:else}
                    Apply
                  {/if}
                </button>
              </div>
              {#if promoError}
                <p class="text-xs text-error mt-1.5">{promoError}</p>
              {/if}
              {#if promoSuccess}
                <p class="text-xs text-success mt-1.5">{promoSuccess}</p>
              {/if}
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
