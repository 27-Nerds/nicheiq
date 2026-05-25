<script lang="ts">
  import { invalidateAll, goto } from "$app/navigation";
  import {
    Coins,
    Gift,
    ArrowUpRight,
    ArrowDownRight,
    Clock,
    CheckCircle,
    RefreshCw,
    History,
    Wrench,
    ShoppingCart,
  } from "lucide-svelte";
  import InlineFeedback from "$lib/components/ui/InlineFeedback.svelte";
  import { CORE_STAGES, ADDON_STAGES } from "$lib/config/billable-stages";
  import { DEFAULT_STAGE_COSTS, computeFullResearchCost } from "$lib/types/job";
  import type { StageCosts } from "$lib/types/job";
  import AlertBanner from "$lib/components/ui/AlertBanner.svelte";
  import EditorialHero from "$lib/components/ui/EditorialHero.svelte";
  import type { KickerSegment } from "$lib/components/ui/EditorialHero.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import PricingCard from "$lib/components/ui/PricingCard.svelte";
  import StatStrip, {
    type Stat,
  } from "$lib/components/catalog/seo/StatStrip.svelte";
  import type {
    TokenPackage,
    SubscriptionPlan,
    UserSubscription,
  } from "$lib/types/billing";

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
    available?: number;
    monthlyAllowance?: number;
    purchasedBalance?: number;
    monthlyAllowancePeriodEnd?: string | null;
    totalPurchased: number;
    totalUsed: number;
    recentTransactions: Transaction[];
  }

  let { data } = $props();
  const billing = $derived(data.billing as BillingData);
  const packages = $derived(data.packages as TokenPackage[]);
  const plans = $derived((data.plans as SubscriptionPlan[]) ?? []);
  // Center the grid when there are fewer than 3 plans (a fixed 3-col grid left-aligns 1–2 cards).
  const planGridClass = $derived(
    plans.length === 1
      ? 'sm:grid-cols-1 max-w-sm mx-auto'
      : plans.length === 2
        ? 'sm:grid-cols-2 max-w-3xl mx-auto'
        : 'sm:grid-cols-3',
  );
  const subscription = $derived(
    (data.subscription as UserSubscription | null) ?? null,
  );
  const success = $derived(data.success as boolean);
  const canceled = $derived(data.canceled as boolean);
  const subSuccess = $derived(data.subSuccess as boolean);
  const subCanceled = $derived(data.subCanceled as boolean);
  const stageCosts = $derived((data.stageCosts as StageCosts) ?? DEFAULT_STAGE_COSTS);
  const fullResearchCost = $derived(computeFullResearchCost(stageCosts));

  // Credit split — fall back to balance for back-compat.
  const monthlyAllowance = $derived(billing.monthlyAllowance ?? 0);
  const purchasedBalance = $derived(billing.purchasedBalance ?? billing.balance);

  // Subscription state machine helpers.
  const TERMINAL_STATUSES = ["CANCELED", "INCOMPLETE_EXPIRED"];
  const subStatus = $derived(subscription?.status ?? null);
  const isTerminal = $derived(
    subStatus === null || TERMINAL_STATUSES.includes(subStatus),
  );
  const isActiveLike = $derived(
    subStatus === "ACTIVE" || subStatus === "TRIALING",
  );
  const willCancel = $derived(
    !!subscription?.cancelAtPeriodEnd && isActiveLike,
  );

  function formatPlanDate(dateStr: string | null | undefined): string {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  const trialDaysLeft = $derived.by(() => {
    if (subStatus !== "TRIALING" || !subscription?.currentPeriodEnd) return null;
    const ms =
      new Date(subscription.currentPeriodEnd).getTime() - Date.now();
    return Math.max(0, Math.ceil(ms / 86_400_000));
  });

  const availableCredits = $derived(billing.available ?? billing.balance);

  // Section numbering: plans (if any) + one-time packages (if any) precede
  // the promo / activity / how-it-works dividers.
  const baseSectionNum = $derived(
    (plans.length > 0 ? 1 : 0) + (packages.length > 0 ? 1 : 0),
  );
  const heroKicker = $derived<KickerSegment[]>([
    { text: "BILLING", tone: "accent" },
    { text: String(availableCredits), tone: "num" },
    { text: "credits", tone: "muted" },
  ]);
  const balanceHeroStats = $derived<Stat[]>([
    {
      value: availableCredits,
      label: "Available",
      tone: availableCredits === 0 ? "amber" : "default",
    },
    { value: monthlyAllowance, label: "Monthly", tone: "go" },
    { value: purchasedBalance, label: "Purchased", tone: "default" },
    { value: billing.totalUsed, label: "Used", tone: "amber" },
  ]);

  // Promo code state
  let promoCode = $state("");
  let promoError = $state<string | null>(null);
  let promoSuccess = $state<string | null>(null);
  let isRedeeming = $state(false);

  // Checkout state
  let checkoutLoading = $state<string | null>(null);
  let checkoutError = $state<string | null>(null);

  // Subscription state
  let subscribeLoading = $state<string | null>(null);
  let portalLoading = $state(false);
  let subscriptionError = $state<string | null>(null);

  // Refresh state
  let isRefreshing = $state(false);

  // Dismiss success/canceled banners
  function dismissBanner() {
    goto("/billing", { replaceState: true });
  }

  // Open the Stripe Customer Portal (manage / cancel / switch).
  async function openPortal() {
    if (portalLoading) return;
    portalLoading = true;
    subscriptionError = null;
    try {
      const response = await fetch("/api/billing/portal", { method: "POST" });
      const result = await response.json();
      if (response.ok && result.url) {
        window.location.href = result.url;
      } else {
        subscriptionError =
          result.error || "Unable to open the billing portal. Please try again.";
      }
    } catch {
      subscriptionError = "Network error. Please try again.";
    } finally {
      portalLoading = false;
    }
  }

  // Subscribe to a plan; if already subscribed (409) open the portal instead.
  async function subscribe(planId: string) {
    if (subscribeLoading || portalLoading) return;
    subscribeLoading = planId;
    subscriptionError = null;
    try {
      const response = await fetch("/api/billing/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planId }),
      });
      const result = await response.json();

      if (response.status === 409) {
        // Already has a live subscription — manage via portal.
        await openPortal();
        return;
      }

      if (response.ok && result.url) {
        window.location.href = result.url;
      } else {
        subscriptionError = result.error || "Failed to start subscription.";
      }
    } catch {
      subscriptionError = "Network error. Please try again.";
    } finally {
      subscribeLoading = null;
    }
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

<div class="max-w-5xl mx-auto">
  {#snippet refreshButton()}
    <button
      onclick={refreshData}
      disabled={isRefreshing}
      aria-label="Refresh billing data"
      class="btn-secondary !px-3"
      title="Refresh"
    >
      <RefreshCw class="w-4 h-4 {isRefreshing ? 'animate-spin' : ''}" />
    </button>
  {/snippet}
  <EditorialHero
    kicker={heroKicker}
    title="Research credits"
    lede="Manage your credits and view transaction history"
    actions={refreshButton}
  />

  <!-- Balance Hero -->
  <div class="mb-8">
    <StatStrip stats={balanceHeroStats} emphasis />
    {#if monthlyAllowance > 0 || subscription}
      <p class="text-xs text-text-muted mt-3 flex items-center gap-1.5">
        <Coins class="w-3.5 h-3.5 text-accent" />
        <span class="font-mono tabular-nums text-text-secondary">{monthlyAllowance}</span> monthly
        {#if billing.monthlyAllowancePeriodEnd}
          <span>(resets {formatPlanDate(billing.monthlyAllowancePeriodEnd)})</span>
        {/if}
        <span class="text-text-muted/60">+</span>
        <span class="font-mono tabular-nums text-text-secondary">{purchasedBalance}</span> purchased
      </p>
    {/if}
  </div>

  <!-- Success Banner -->
  {#if success}
    <AlertBanner
      variant="success"
      title="Payment successful!"
      message="Your credits have been added to your account."
      dismissible
      onDismiss={dismissBanner}
      class="mb-8"
    >
    </AlertBanner>
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

  <!-- Subscription Success Banner -->
  {#if subSuccess}
    <AlertBanner
      variant="success"
      title="Subscription active!"
      message="Your plan is set up. Full catalog access is unlocked and monthly credits arrive on your first billing date."
      dismissible
      onDismiss={dismissBanner}
      class="mb-8"
    />
  {/if}

  <!-- Subscription Canceled (checkout abandoned) Banner -->
  {#if subCanceled}
    <AlertBanner
      variant="warning"
      title="Subscription not started"
      message="No charges were made. You can subscribe again when ready."
      dismissible
      onDismiss={dismissBanner}
      class="mb-8"
    />
  {/if}

  <!-- Past Due Banner -->
  {#if subStatus === "PAST_DUE"}
    <AlertBanner
      variant="error"
      title="Payment failed — update your card"
      message="Your last subscription payment didn't go through. Update your payment method to keep your access and monthly credits."
      class="mb-8"
    >
      <SubmitButton
        onclick={openPortal}
        loading={portalLoading}
        loadingText="Opening..."
        label="Update payment method"
        class="btn-primary mt-3"
      />
    </AlertBanner>
  {/if}

  <!-- Info Banner (if no credits) -->
  {#if availableCredits === 0 && !success && !subSuccess}
    <AlertBanner
      variant="info"
      title="You need research credits to start new research"
      message="Subscribe to a plan for monthly credits + full catalog access, buy a one-time credit package, or redeem a promo code."
      class="mb-8"
    />
  {/if}

  <!-- Subscription Plans Section -->
  {#if plans.length > 0}
    <div class="mb-8" id="plans">
      <SectionDivider num={1} label="Subscription plans" />
      <p class="text-sm text-text-muted mb-4">
        Monthly credits that reset each cycle plus full catalog access. Manage,
        switch, or cancel anytime via the billing portal.
      </p>

      {#if subscriptionError}
        <InlineFeedback message={subscriptionError} variant="error" class="mb-4" />
      {/if}

      <!-- Current subscription summary -->
      {#if subscription && isActiveLike}
        <div class="card mb-4 flex flex-wrap items-center justify-between gap-3 py-3 px-4 border-l-2 border-l-accent/40">
          <div class="text-sm">
            {#if subStatus === "TRIALING"}
              <span class="font-semibold text-text-primary">Trial — {trialDaysLeft} {trialDaysLeft === 1 ? "day" : "days"} left</span>
              <span class="text-text-muted"> · monthly credits unlock on {formatPlanDate(subscription.currentPeriodEnd)}</span>
            {:else if willCancel}
              <span class="font-semibold text-warning">Access ends {formatPlanDate(subscription.currentPeriodEnd)}</span>
              <span class="text-text-muted"> · resume anytime via the portal</span>
            {:else}
              <span class="font-semibold text-text-primary">{subscription.planName ?? "Active plan"}</span>
              <span class="text-text-muted"> · renews {formatPlanDate(subscription.currentPeriodEnd)}</span>
            {/if}
          </div>
          <SubmitButton
            onclick={openPortal}
            loading={portalLoading}
            loadingText="Opening..."
            label={willCancel ? "Resume via portal" : "Manage subscription"}
            class="btn-secondary !py-1.5 !text-sm"
          />
        </div>
      {/if}

      <div class="grid gap-4 {planGridClass}">
        {#each plans as plan (plan.id)}
          {@const isCurrent = subscription?.planId === plan.id && isActiveLike}
          <PricingCard {plan} variant="compact">
            {#snippet actions()}
              {#if isCurrent}
                <SubmitButton
                  type="button"
                  disabled
                  loadingText=""
                  label="Current plan"
                  class="btn-secondary w-full"
                />
              {:else if isActiveLike || subStatus === "PAST_DUE"}
                <!-- Live subscription: switching / fixing goes through the portal -->
                <SubmitButton
                  onclick={openPortal}
                  loading={portalLoading}
                  loadingText="Opening..."
                  label={subStatus === "PAST_DUE" ? "Manage via portal" : "Switch via portal"}
                  class="{plan.isPopular ? 'btn-primary' : 'btn-secondary'} w-full"
                />
              {:else if isTerminal}
                <!-- No / terminal subscription: a fresh checkout is allowed -->
                <SubmitButton
                  onclick={() => subscribe(plan.id)}
                  disabled={subscribeLoading !== null || portalLoading}
                  loading={subscribeLoading === plan.id}
                  loadingText="Redirecting..."
                  label={plan.ctaText || "Subscribe"}
                  class="{plan.isPopular ? 'btn-primary' : 'btn-secondary'} w-full"
                />
              {:else}
                <!-- Any other live status (INCOMPLETE / UNPAID / PAUSED) → portal -->
                <SubmitButton
                  onclick={openPortal}
                  loading={portalLoading}
                  loadingText="Opening..."
                  label="Manage via portal"
                  class="{plan.isPopular ? 'btn-primary' : 'btn-secondary'} w-full"
                />
              {/if}
            {/snippet}
          </PricingCard>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Buy Credits Section -->
  {#if packages.length > 0}
    <div class="mb-8">
      <SectionDivider num={plans.length > 0 ? 2 : 1} label="Buy credits (one-time)" />

      {#if checkoutError}
        <InlineFeedback message={checkoutError} variant="error" class="mb-4" />
      {/if}

      <div class="grid gap-4 sm:grid-cols-3">
        {#each packages as pkg (pkg.id)}
          <PricingCard {pkg} variant="compact">
            {#snippet actions()}
              <SubmitButton onclick={() => startCheckout(pkg.id)} disabled={checkoutLoading !== null} loading={checkoutLoading === pkg.id} loadingText="Processing..." icon={ShoppingCart} label={pkg.ctaText || "Buy Now"} class="{pkg.isPopular ? 'btn-primary' : 'btn-secondary'} w-full" />
            {/snippet}
          </PricingCard>
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
                  <span class="font-mono font-bold text-text-primary tabular-nums">{cost}<span class="text-text-muted text-xs font-normal"> credits</span></span>
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
            <span class="font-mono text-sm font-bold text-accent tabular-nums">{fullResearchCost} credits</span>
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
                    <span class="font-mono font-semibold text-text-secondary tabular-nums">{cost}<span class="text-text-muted/70 font-normal"> credits</span></span>
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
      <SectionDivider num={baseSectionNum + 1} label="Redeem promo code" />
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
      <SectionDivider num={baseSectionNum + 2} label="Recent activity" />
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
              style="animation-delay: {Math.min(i, 5) * 50}ms"
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
                    class="text-sm font-semibold font-mono tabular-nums {tx.amount > 0
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

  <!-- How Credits Work — closing colophon, mono step numbers (no tint circles) -->
  <div class="mt-12">
    <SectionDivider num={baseSectionNum + 3} label="How credits work" />
    <div class="grid gap-6 sm:grid-cols-3 mt-2">
      <div class="flex items-start gap-3">
        <span class="hcw-num">01</span>
        <div>
          <p class="font-medium text-text-primary text-sm">Get credits</p>
          <p class="text-xs text-text-muted mt-1">
            Subscribe for monthly credits that reset each cycle, buy one-time
            packages, or redeem a promo code
          </p>
        </div>
      </div>
      <div class="flex items-start gap-3">
        <span class="hcw-num">02</span>
        <div>
          <p class="font-medium text-text-primary text-sm">Use credits</p>
          <p class="text-xs text-text-muted mt-1">
            Credits are deducted as each research step runs — monthly allowance
            is spent first, then your purchased balance
          </p>
        </div>
      </div>
      <div class="flex items-start gap-3">
        <span class="hcw-num">03</span>
        <div>
          <p class="font-medium text-text-primary text-sm">Auto-refund</p>
          <p class="text-xs text-text-muted mt-1">
            Failed stages are automatically refunded
          </p>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .hcw-num {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    padding-top: 1px;
    flex-shrink: 0;
  }
</style>
