<script lang="ts">
  import { invalidateAll, goto } from "$app/navigation";
  import {
    Coins,
    Gift,
    ArrowUpRight,
    ArrowDownRight,
    Clock,
    CheckCircle,
    AlertCircle,
    RefreshCw,
    Loader2,
    History,
    Wrench,
    CreditCard,
    ShoppingCart,
    Star,
  } from "lucide-svelte";
  import CategoryBar from "$lib/components/ui/CategoryBar.svelte";
  import InlineFeedback from "$lib/components/ui/InlineFeedback.svelte";
  import { CORE_STAGES, ADDON_STAGES } from "$lib/config/billable-stages";
  import { DEFAULT_STAGE_COSTS, computeFullResearchCost } from "$lib/types/job";
  import type { StageCosts } from "$lib/types/job";
  import AlertBanner from "$lib/components/ui/AlertBanner.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import FeatureCard from "$lib/components/ui/FeatureCard.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  interface Transaction {
    id: string;
    type: string;
    amount: number;
    balanceAfter: number;
    description: string | null;
    createdAt: string;
  }

  interface BillingData {
    balance: number;
    totalPurchased: number;
    totalUsed: number;
    recentTransactions: Transaction[];
  }

  interface TokenPackage {
    id: string;
    name: string;
    description: string | null;
    credits: number;
    priceInCents: number;
    isPopular: boolean;
  }

  let { data } = $props();
  const billing = $derived(data.billing as BillingData);
  const packages = $derived(data.packages as TokenPackage[]);
  const success = $derived(data.success as boolean);
  const canceled = $derived(data.canceled as boolean);
  const stageCosts = $derived((data.stageCosts as StageCosts) ?? DEFAULT_STAGE_COSTS);
  const fullResearchCost = $derived(computeFullResearchCost(stageCosts));

  // Promo code state
  let promoCode = $state("");
  let promoError = $state<string | null>(null);
  let promoSuccess = $state<string | null>(null);
  let isRedeeming = $state(false);

  // Checkout state
  let checkoutLoading = $state<string | null>(null);
  let checkoutError = $state<string | null>(null);

  // Refresh state
  let isRefreshing = $state(false);

  // Dismiss success/canceled banners
  function dismissBanner() {
    goto("/billing", { replaceState: true });
  }

  async function redeemPromoCode() {
    if (!promoCode.trim() || isRedeeming) return;

    isRedeeming = true;
    promoError = null;
    promoSuccess = null;

    try {
      const response = await fetch("/api/billing/redeem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: promoCode.trim() }),
      });

      const result = await response.json();

      if (response.ok) {
        promoSuccess = result.message;
        promoCode = "";
        // Refresh the page data to update balance
        await invalidateAll();
      } else {
        promoError = result.error || "Failed to redeem promo code";
      }
    } catch (error) {
      promoError = "Network error. Please try again.";
    } finally {
      isRedeeming = false;
    }
  }

  async function refreshData() {
    isRefreshing = true;
    await invalidateAll();
    isRefreshing = false;
  }

  function getTransactionIcon(type: string) {
    switch (type) {
      case "PURCHASE":
      case "PROMO_REDEMPTION":
        return { icon: ArrowUpRight, class: "text-success bg-success/10" };
      case "JOB_DEDUCTION":
        return { icon: ArrowDownRight, class: "text-warning bg-warning/10" };
      case "REFUND":
        return { icon: ArrowUpRight, class: "text-accent bg-accent/10" };
      case "ADMIN_ADJUSTMENT":
        return { icon: Wrench, class: "text-secondary bg-secondary/10" };
      default:
        return { icon: Clock, class: "text-text-muted bg-bg-elevated" };
    }
  }

  function formatTransactionType(type: string): string {
    switch (type) {
      case "PURCHASE":
        return "Purchase";
      case "JOB_DEDUCTION":
        return "Research Job";
      case "PROMO_REDEMPTION":
        return "Promo Code";
      case "REFUND":
        return "Refund";
      case "ADMIN_ADJUSTMENT":
        return "Adjustment";
      default:
        return type;
    }
  }

  function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatRelativeDate(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  }

  function formatPrice(cents: number): string {
    return `$${(cents / 100).toFixed(2)}`;
  }

  async function startCheckout(packageId: string) {
    if (checkoutLoading) return;

    checkoutLoading = packageId;
    checkoutError = null;

    try {
      const response = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ packageId }),
      });

      const result = await response.json();

      if (response.ok && result.url) {
        // Redirect to Stripe Checkout
        window.location.href = result.url;
      } else {
        checkoutError = result.error || "Failed to start checkout";
      }
    } catch (error) {
      checkoutError = "Network error. Please try again.";
    } finally {
      checkoutLoading = null;
    }
  }
</script>

<svelte:head>
  <title>Billing - NicheIQ</title>
</svelte:head>

<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  {#snippet refreshButton()}
    <button
      onclick={refreshData}
      disabled={isRefreshing}
      aria-label="Refresh billing data"
      class="btn-secondary"
      title="Refresh"
    >
      <RefreshCw class="w-4 h-4 {isRefreshing ? 'animate-spin' : ''}" />
    </button>
  {/snippet}
  <PageHeader
    icon={CreditCard}
    title="Research Credits"
    subtitle="Manage your credits and view transaction history"
    actions={refreshButton}
  />

  <!-- Balance Card -->
  <FeatureCard icon={Coins} class="mb-8">
    <div>
      <p
        class="text-xs font-mono uppercase tracking-wider text-text-muted mb-2"
      >
        Available Credits
      </p>
      <div class="flex items-baseline gap-2">
        <span class="text-5xl font-display font-bold text-text-primary"
          >{billing.balance}</span
        >
        <span class="text-lg text-text-muted">credits</span>
      </div>
      <div class="flex items-center gap-4 mt-3 text-sm">
        <span class="text-text-muted">
          <span class="font-display font-bold text-success"
            >{billing.totalPurchased}</span
          >
          <span class="text-xs uppercase tracking-wide">earned</span>
        </span>
        <span class="text-text-muted">
          <span class="font-display font-bold text-warning"
            >{billing.totalUsed}</span
          >
          <span class="text-xs uppercase tracking-wide">used</span>
        </span>
      </div>
    </div>
  </FeatureCard>

  <!-- Success Banner -->
  {#if success}
    <AlertBanner
      variant="success"
      title="Payment successful!"
      message="Your credits have been added to your account."
      dismissible
      onDismiss={dismissBanner}
      class="mb-8"
    />
  {/if}

  <!-- Canceled Banner -->
  {#if canceled}
    <AlertBanner
      variant="warning"
      title="Payment canceled"
      message="No charges were made. You can try again when ready."
      dismissible
      onDismiss={dismissBanner}
      class="mb-8"
    />
  {/if}

  <!-- Info Banner (if no credits) -->
  {#if billing.balance === 0 && !success}
    <AlertBanner
      variant="info"
      title="You need research credits to start new research"
      message="Purchase a credit package below or redeem a promo code to get started."
      class="mb-8"
    />
  {/if}

  <!-- Buy Credits Section -->
  {#if packages.length > 0}
    <div class="mb-8">
      <CategoryBar title="Buy Credits" color="accent" margin="mb-4" />

      {#if checkoutError}
        <InlineFeedback message={checkoutError} variant="error" class="mb-4" />
      {/if}

      <div class="grid gap-4 sm:grid-cols-3">
        {#each packages as pkg (pkg.id)}
          <div
            class="card relative {pkg.isPopular
              ? 'border-accent/50 bg-accent/5'
              : ''}"
          >
            {#if pkg.isPopular}
              <div class="absolute -top-3 left-1/2 -translate-x-1/2">
                <span
                  class="px-3 py-1 text-xs font-semibold bg-accent text-white rounded-full flex items-center gap-1"
                >
                  <Star class="w-3 h-3" />
                  Most Popular
                </span>
              </div>
            {/if}

            <div class="text-center pt-2">
              <h3 class="text-lg font-display font-bold text-text-primary">
                {pkg.name}
              </h3>
              {#if pkg.description}
                <p class="text-sm text-text-muted mt-1">{pkg.description}</p>
              {/if}

              <div class="my-4">
                <span class="text-3xl font-display font-bold text-text-primary"
                  >{formatPrice(pkg.priceInCents)}</span
                >
              </div>

              <div
                class="flex items-center justify-center gap-2 text-sm text-text-muted mb-1"
              >
                <Coins class="w-4 h-4 text-accent" />
                <span class="font-semibold text-text-primary"
                  >{pkg.credits}</span
                >
                <span>credits</span>
              </div>

              {#if fullResearchCost > 0}
                <p class="text-xs text-text-muted mb-4">
                  ~{Math.floor(pkg.credits / fullResearchCost)} full research runs<a
                    href="#credit-costs"
                    class="text-accent"
                    aria-label="See credit cost breakdown"
                  >*</a>
                </p>
              {:else}
                <div class="mb-4"></div>
              {/if}

              <SubmitButton onclick={() => startCheckout(pkg.id)} disabled={checkoutLoading !== null} loading={checkoutLoading === pkg.id} loadingText="Processing..." icon={ShoppingCart} label="Buy Now" class="{pkg.isPopular ? 'btn-primary' : 'btn-secondary'} w-full" />
            </div>
          </div>
        {/each}
      </div>

      {#if fullResearchCost > 0}
        <div id="credit-costs" class="card mt-4 py-3 px-4 border-l-2 border-l-accent/30">
          <p class="text-xs uppercase tracking-wider text-accent/60 font-mono mb-2">* Credit costs per stage</p>

          <!-- Core stages: horizontal row -->
          <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            {#each CORE_STAGES as stage}
              {@const cost = stageCosts[stage.key]}
              {@const Icon = stage.icon}
              <span class="inline-flex items-center gap-1.5">
                <Icon class="w-3.5 h-3.5 text-accent/70" />
                <span class="text-text-secondary">{stage.label}</span>
                {#if cost === 0}
                  <span class="badge-sm badge-success inline-flex items-center gap-0.5">
                    <CheckCircle class="w-2.5 h-2.5" /> Free
                  </span>
                {:else}
                  <span class="font-mono font-bold text-text-primary">{cost}<span class="text-text-muted text-xs font-normal">cr</span></span>
                {/if}
              </span>
            {/each}
          </div>

          <!-- Summary row -->
          <div class="border-t border-accent/15 mt-2 pt-2 flex items-center justify-between">
            <span class="text-sm text-text-secondary flex items-center gap-1.5">
              <Coins class="w-3.5 h-3.5 text-accent" />
              Full research
            </span>
            <span class="font-mono text-sm font-bold text-accent">{fullResearchCost} credits</span>
          </div>

          <!-- Add-ons -->
          <div class="border-t border-border/10 mt-2 pt-2">
            <span class="text-xs text-text-muted/50 font-mono">Add-ons</span>
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs mt-1">
              {#each ADDON_STAGES as stage}
                {@const cost = stageCosts[stage.key]}
                {@const Icon = stage.icon}
                <span class="inline-flex items-center gap-1">
                  <Icon class="w-3 h-3 text-secondary/60" />
                  <span class="text-text-muted">{stage.label}</span>
                  {#if cost === 0}
                    <span class="badge-sm badge-success inline-flex items-center gap-0.5 text-xs">
                      <CheckCircle class="w-2.5 h-2.5" /> Free
                    </span>
                  {:else}
                    <span class="font-mono font-semibold text-text-secondary">{cost}<span class="text-text-muted/70 font-normal">cr</span></span>
                  {/if}
                </span>
              {/each}
            </div>
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <div class="grid gap-8 md:grid-cols-2">
    <!-- Promo Code Section -->
    <div class="card">
      <CategoryBar title="Redeem Promo Code" color="secondary" />
      <p class="text-sm text-text-muted mb-4">
        Enter your code to receive credits
      </p>

      <div class="space-y-4">
        <div>
          <input
            type="text"
            bind:value={promoCode}
            placeholder="Enter promo code"
            class="input w-full uppercase tracking-wider"
            maxlength="50"
            disabled={isRedeeming}
            onkeydown={(e) => e.key === "Enter" && redeemPromoCode()}
          />
        </div>

        {#if promoError}
          <InlineFeedback message={promoError} variant="error" />
        {/if}

        {#if promoSuccess}
          <InlineFeedback message={promoSuccess} variant="success" />
        {/if}

        <SubmitButton
          onclick={redeemPromoCode}
          disabled={!promoCode.trim()}
          loading={isRedeeming}
          loadingText="Redeeming..."
          icon={Gift}
          label="Redeem Code"
        />
      </div>
    </div>

    <!-- Recent Transactions -->
    <div class="card">
      <CategoryBar title="Recent Activity" color="accent" />
      <p class="text-sm text-text-muted mb-4">Your latest transactions</p>

      {#if billing.recentTransactions.length === 0}
        <div class="text-center py-8 text-text-muted">
          <History class="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p class="text-sm">No transactions yet</p>
        </div>
      {:else}
        <div class="space-y-3">
          {#each billing.recentTransactions as tx, i}
            {@const txInfo = getTransactionIcon(tx.type)}
            {@const TxIcon = txInfo.icon}
            <div
              class="flex items-center gap-3 p-3 rounded-lg bg-bg-elevated/50 border border-border/50 animate-fade-slide-in"
              style="animation-delay: {i * 50}ms"
            >
              <div class="p-2 rounded-lg {txInfo.class}">
                <TxIcon class="w-4 h-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-sm font-medium text-text-primary truncate">
                    {formatTransactionType(tx.type)}
                  </span>
                  <span
                    class="text-sm font-semibold {tx.amount > 0
                      ? 'text-success'
                      : 'text-warning'}"
                  >
                    {tx.amount > 0 ? "+" : ""}{tx.amount}
                  </span>
                </div>
                <div class="flex items-center justify-between gap-2 mt-0.5">
                  <span
                    class="text-xs text-text-muted truncate"
                    title={tx.description || ""}
                  >
                    {tx.description || "-"}
                  </span>
                  <span
                    class="text-xs text-text-muted shrink-0"
                    title={formatDate(tx.createdAt)}
                  >
                    {formatRelativeDate(tx.createdAt)}
                  </span>
                </div>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  <div class="my-8 h-px bg-border"></div>

  <!-- How It Works -->
  <div class="card bg-bg-elevated/50">
    <h3 class="text-lg font-semibold text-text-primary mb-4">
      How Credits Work
    </h3>
    <div class="grid gap-4 sm:grid-cols-3">
      <div class="flex items-start gap-3">
        <div
          class="w-8 h-8 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-semibold text-sm shrink-0"
        >
          1
        </div>
        <div>
          <p class="font-medium text-text-primary text-sm">Get Credits</p>
          <p class="text-xs text-text-muted mt-1">
            Redeem promo codes or purchase credit packages
          </p>
        </div>
      </div>
      <div class="flex items-start gap-3">
        <div
          class="w-8 h-8 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-semibold text-sm shrink-0"
        >
          2
        </div>
        <div>
          <p class="font-medium text-text-primary text-sm">Use Credits</p>
          <p class="text-xs text-text-muted mt-1">
            Credits are deducted when each research step runs
          </p>
        </div>
      </div>
      <div class="flex items-start gap-3">
        <div
          class="w-8 h-8 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-semibold text-sm shrink-0"
        >
          3
        </div>
        <div>
          <p class="font-medium text-text-primary text-sm">Auto-Refund</p>
          <p class="text-xs text-text-muted mt-1">
            Failed stages are automatically refunded
          </p>
        </div>
      </div>
    </div>
  </div>
</div>
