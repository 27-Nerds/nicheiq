<script lang="ts">
  import { onMount } from "svelte";
  import { invalidateAll, goto, replaceState } from "$app/navigation";
  import {
    Coins,
    Gift,
    CheckCircle,
    RefreshCw,
    History,
    ShoppingCart,
    RotateCw,
    ArrowRight,
    ChevronDown,
  } from "lucide-svelte";
  import InlineFeedback from "$lib/components/ui/InlineFeedback.svelte";
  import { CORE_STAGES, ADDON_STAGES } from "$lib/config/billable-stages";
  import { DEFAULT_STAGE_COSTS, computeFullResearchCost } from "$lib/types/job";
  import type { StageCosts } from "$lib/types/job";
  import AlertBanner from "$lib/components/ui/AlertBanner.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import AccountSidebar from "$lib/components/layout/AccountSidebar.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import PricingCard from "$lib/components/ui/PricingCard.svelte";
  import PlanCard from "$lib/components/ui/PlanCard.svelte";
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
  // Max-widths match the landing pricing grid so the shared PlanCard renders at the same size.
  const planGridClass = $derived(
    plans.length === 1
      ? 'sm:grid-cols-1 max-w-md mx-auto'
      : plans.length === 2
        ? 'sm:grid-cols-2 max-w-3xl mx-auto'
        : 'sm:grid-cols-3 max-w-4xl mx-auto',
  );
  const packageGridClass = $derived(
    packages.length === 1
      ? 'sm:grid-cols-1 max-w-xs'
      : packages.length === 2
        ? 'sm:grid-cols-2 max-w-2xl'
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
  const loadError = $derived(data.loadError as boolean);

  // Low-credit banner CTA target: the plan area (in Overview) when unsubscribed
  // (and plans exist), otherwise the Buy-credits panel.
  const lowCreditHref = $derived(
    isTerminal && plans.length > 0
      ? "#overview"
      : packages.length > 0
        ? "#buy"
        : plans.length > 0
          ? "#overview"
          : "#buy",
  );

  const balanceHeroStats = $derived<Stat[]>([
    // A spend/balance is not a warning — keep the numbers neutral (no orange tint).
    { value: availableCredits, label: "Available", tone: "default" },
    { value: monthlyAllowance, label: "Monthly", tone: "go" },
    { value: purchasedBalance, label: "Purchased", tone: "default" },
    { value: billing.totalUsed, label: "Used", tone: "default" },
  ]);

  // Billing-history row helpers.
  // Dot: credit-IN (purchase / promo / refund → positive) = success green;
  // a job deduction (negative) = muted.
  const txDotColor = (tx: Transaction): string =>
    tx.amount > 0
      ? "var(--color-success-text)"
      : "var(--color-text-muted)";

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

  // "What a run costs" collapsible (collapsed by default — returning users
  // rarely need the per-stage breakdown).
  let costsOpen = $state(false);

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

  // Auto-start checkout when arriving with ?plan=<id> (set by the landing
  // pricing CTA via returnTo). One-shot: the param is stripped via shallow
  // replaceState before the redirect so back-navigation from Stripe can't
  // re-trigger. Reads window.location, not page.url — the hash is never sent
  // to the server, so page.url.hash can be empty at hydration.
  onMount(() => {
    const url = new URL(window.location.href);
    const planId = url.searchParams.get("plan");
    if (!planId) return;
    url.searchParams.delete("plan");
    replaceState(`${url.pathname}${url.search}${url.hash}`, {});

    if (!plans.some((p) => p.id === planId)) return;
    // Live subscription — never auto-redirect; the Switch-via-portal CTAs are visible.
    if (!isTerminal) return;
    subscribe(planId);
  });

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
  <title>Research credits - NicheIQ</title>
</svelte:head>

<div class="acct-page">
  <AccountSidebar />
  <main class="acct-main">
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
    <PageHeader
      breadcrumbItems={[{ label: "Dashboard", href: "/dashboard" }]}
      breadcrumbCurrent="Billing"
      title="Research credits"
      subtitle="What you have, and how to get more."
      actions={refreshButton}
    />

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

  <!-- Load-error Banner (billing fetch failed — credits are safe) -->
  {#if loadError}
    <AlertBanner
      variant="error"
      title="Couldn't load your billing"
      message="This is a loading problem — your credits are safe. Try again in a moment."
      class="mb-8"
    >
      <button type="button" onclick={() => location.reload()} class="btn-secondary mt-3">
        <RotateCw class="w-4 h-4" /> Retry
      </button>
    </AlertBanner>
  {/if}

  <!-- Info Banner (if no credits) — with a working CTA into Plans / Buy credits -->
  {#if availableCredits === 0 && !success && !subSuccess && !loadError}
    <AlertBanner
      variant="info"
      title="You need research credits to start new research"
      message="Subscribe to a plan for monthly credits + full catalog access, buy a one-time credit package, or redeem a promo code."
      class="mb-8"
    >
      <a href={lowCreditHref} class="banner-cta mt-3">
        {isTerminal && plans.length > 0 ? "See plans" : "Buy credits"}
        <ArrowRight class="w-3.5 h-3.5" />
      </a>
    </AlertBanner>
  {/if}

  <!-- OVERVIEW · balance ledger + plan -->
  <section id="overview" class="wb-panel">
    <div class="wb-head">
      <h2 class="wb-title">Credits &amp; plan</h2>
      <span class="wb-meta">{availableCredits} available</span>
    </div>

    <StatStrip stats={balanceHeroStats} emphasis />
    {#if monthlyAllowance > 0 || subscription}
      <p class="balance-note">
        <Coins class="w-3.5 h-3.5 text-accent" />
        <span class="font-mono tabular-nums text-text-secondary">{monthlyAllowance}</span> monthly
        {#if billing.monthlyAllowancePeriodEnd}
          <span>(resets {formatPlanDate(billing.monthlyAllowancePeriodEnd)})</span>
        {/if}
        <span class="text-text-muted/60">+</span>
        <span class="font-mono tabular-nums text-text-secondary">{purchasedBalance}</span> purchased
      </p>
    {/if}

    {#if plans.length > 0}
      <div class="wb-sub" id="plans">
        <p class="wb-sublabel">Your plan</p>
        <p class="text-sm text-text-muted mb-4">
          Monthly credits that reset each cycle plus full catalog access. Manage,
          switch, or cancel anytime via the billing portal.
        </p>

      {#if subscriptionError}
        <InlineFeedback message={subscriptionError} variant="error" class="mb-4" />
      {/if}

      <!-- Current subscription summary -->
      {#if subscription && isActiveLike}
        <div class="card mb-4 flex flex-wrap items-center justify-between gap-3 py-3 px-4">
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
            label={willCancel ? "Resume plan" : "Manage subscription"}
            class="btn-secondary !py-1.5 !text-sm"
          />
        </div>
      {/if}

      <div class="grid gap-4 {planGridClass}">
        {#each plans as plan (plan.id)}
          {@const isCurrent = subscription?.planId === plan.id && isActiveLike}
          <PlanCard {plan}>
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
                  label={subStatus === "PAST_DUE" ? "Manage via portal" : "Switch plan"}
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
          </PlanCard>
        {/each}
      </div>
      </div>
    {/if}
  </section>

  <!-- BUY · one-time packages + collapsible run-cost breakdown -->
  {#if packages.length > 0}
    <section id="buy" class="wb-panel">
      <div class="wb-head">
        <h2 class="wb-title">Buy credits</h2>
        <span class="wb-meta">One-time top-up</span>
      </div>

      {#if checkoutError}
        <InlineFeedback message={checkoutError} variant="error" class="mb-4" />
      {/if}

      <div class="grid gap-4 {packageGridClass}">
        {#each packages as pkg (pkg.id)}
          <PricingCard {pkg} variant="compact">
            {#snippet actions()}
              <SubmitButton onclick={() => startCheckout(pkg.id)} disabled={checkoutLoading !== null} loading={checkoutLoading === pkg.id} loadingText="Processing..." icon={ShoppingCart} label={pkg.ctaText || "Buy"} class="{pkg.isPopular ? 'btn-primary' : 'btn-secondary'} w-full" />
            {/snippet}
          </PricingCard>
        {/each}
      </div>

      {#if fullResearchCost > 0}
        <div id="credit-costs" class="card mt-4 py-3 px-4">
          <button
            type="button"
            class="costs-toggle"
            onclick={() => (costsOpen = !costsOpen)}
            aria-expanded={costsOpen}
            aria-controls="credit-costs-body"
          >
            <span class="costs-toggle-label">What a run costs</span>
            <span class="costs-toggle-meta">
              <span class="font-mono tabular-nums text-text-primary">{fullResearchCost}</span> credits full research
              <ChevronDown class="w-3.5 h-3.5 {costsOpen ? 'chev-open' : ''}" />
            </span>
          </button>

          {#if costsOpen}
            <div id="credit-costs-body" class="mt-3">
              <!-- Core stages: horizontal row -->
              <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                {#each CORE_STAGES as stage}
                  {@const cost = stageCosts[stage.key]}
                  {@const Icon = stage.icon}
                  <span class="inline-flex items-center gap-1.5">
                    <Icon class="w-3.5 h-3.5 text-text-muted" />
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
              <div class="border-t border-border/60 mt-2 pt-2 flex items-center justify-between">
                <span class="text-sm text-text-secondary flex items-center gap-1.5">
                  <Coins class="w-3.5 h-3.5 text-text-muted" />
                  Full research
                </span>
                <span class="font-mono text-sm font-bold text-text-primary tabular-nums">{fullResearchCost} credits</span>
              </div>

              <!-- Add-ons -->
              <div class="border-t border-border/40 mt-2 pt-2">
                <span class="text-xs text-text-muted font-mono">Add-ons</span>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs mt-1">
                  {#each ADDON_STAGES as stage}
                    {@const cost = stageCosts[stage.key]}
                    {@const Icon = stage.icon}
                    <span class="inline-flex items-center gap-1">
                      <Icon class="w-3 h-3 text-text-muted" />
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
    </section>
  {/if}

  <!-- HISTORY · one divided list panel (dashboard .list recipe) -->
  <section id="history" class="wb-section">
    <div class="wb-head">
      <h2 class="wb-title">Billing history</h2>
      {#if billing.recentTransactions.length > 0}
        <span class="wb-meta">{billing.recentTransactions.length} recent</span>
      {/if}
    </div>

    {#if billing.recentTransactions.length === 0}
      <div class="text-center py-8 text-text-muted">
        <History class="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p class="text-sm">No transactions yet</p>
      </div>
    {:else}
      <div class="tx-list">
        <div class="tx-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th class="tx-desc-col">Description</th>
                <th class="num">Amount</th>
                <th style="text-align: right">Date</th>
              </tr>
            </thead>
            <tbody>
              {#each billing.recentTransactions as tx (tx.id)}
                <tr>
                  <td class="cell-primary tx-type-cell">
                    <span class="tx-dot" style:background={txDotColor(tx)}></span>
                    {formatTransactionType(tx.type)}
                  </td>
                  <td class="cell-muted tx-desc-col" title={tx.description || ""}>{tx.description || "—"}</td>
                  <td
                    class="num tx-amount-cell"
                    class:tx-amount-pos={tx.amount > 0}
                  >{tx.amount > 0 ? "+" : ""}{tx.amount}</td>
                  <td class="cell-muted text-right tx-date-cell" title={formatDate(tx.createdAt)}>{formatRelativeDate(tx.createdAt)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  </section>

  <!-- REDEEM · promo code -->
  <section class="wb-panel">
    <div class="wb-head">
      <h2 class="wb-title">Redeem a code</h2>
    </div>
    <p class="text-sm text-text-muted mb-4">
      Enter a promo code to add credits to your balance.
    </p>

    <div class="redeem-row flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          bind:value={promoCode}
          placeholder="Enter promo code"
          aria-label="Promo code"
          class="input min-w-0 flex-1 uppercase tracking-wider"
          maxlength="50"
          disabled={isRedeeming}
          onkeydown={(e) => e.key === "Enter" && redeemPromoCode()}
        />
        <SubmitButton
          onclick={redeemPromoCode}
          disabled={!promoCode.trim()}
          loading={isRedeeming}
          loadingText="Redeeming..."
          icon={Gift}
          label="Redeem code"
          class="btn-primary redeem-button"
        />
      </div>

      {#if promoError}
        <InlineFeedback message={promoError} variant="error" class="mt-3" />
      {/if}

      {#if promoSuccess}
        <InlineFeedback message={promoSuccess} variant="success" class="mt-3" />
      {/if}
  </section>

  <!-- HOW CREDITS WORK · closing colophon, mono step numbers (no tint circles) -->
  <section class="wb-section wb-section--colophon">
    <div class="wb-head">
      <h2 class="wb-title">How credits work</h2>
    </div>
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
  </section>
  </main>
</div>

<style>
  /* ── Account shell (verbatim with the settings page for a consistent shell) ── */
  .acct-page {
    display: grid;
    grid-template-columns: 300px 1fr;
    min-height: calc(100dvh - 3.5rem);
    background: var(--color-bg-base);
  }
  .acct-main {
    padding: var(--space-8) clamp(var(--space-6), 4vw, var(--space-10)) var(--space-16);
    max-width: 60rem;
    min-width: 0;
  }
  @media (max-width: 900px) {
    .acct-page { grid-template-columns: 1fr; }
    .acct-main { padding: var(--space-6) var(--space-5) var(--space-12); max-width: none; }
  }

  /* ── Workbench panels (job-page "Ranked candidates" framed-panel idiom) ── */
  .wb-panel {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
    padding: var(--space-6);
    scroll-margin-top: 4.5rem;
  }
  /* History / colophon read as framed sections without a boxed card wrapper —
     the divided list (and the colophon grid) carry their own chrome. */
  .wb-section { scroll-margin-top: 4.5rem; }
  .wb-section--colophon { margin-top: var(--space-4); }
  .wb-panel + .wb-panel,
  .wb-panel + .wb-section,
  .wb-section + .wb-panel { margin-top: var(--space-6); }

  .wb-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .wb-title {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
  }
  .wb-meta {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* Plan sub-block inside the Overview panel, divided off the balance ledger.
     Keeps the #plans deep-link target (used by unlock/top-up CTAs). */
  .wb-sub {
    margin-top: var(--space-6);
    padding-top: var(--space-6);
    border-top: 1px solid var(--color-border);
    scroll-margin-top: 4.5rem;
  }
  .wb-sublabel {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin-bottom: var(--space-2);
  }

  /* Monthly + purchased split line under the balance ledger. */
  .balance-note {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    margin-top: var(--space-3);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

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

  /* Ghost link CTA inside the low-credit banner (accent-dark text + arrow). */
  .banner-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-accent-dark);
    transition: color 0.13s ease;
  }
  .banner-cta:hover { color: var(--color-accent-hover); }
  .banner-cta:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  /* "What a run costs" collapsible header. */
  .costs-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    width: 100%;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    text-align: left;
  }
  .costs-toggle-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .costs-toggle:hover .costs-toggle-label { color: var(--color-text-secondary); }
  .costs-toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
    border-radius: var(--radius-sm);
  }
  .costs-toggle-meta {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .costs-toggle-meta :global(.chev-open) { transform: rotate(180deg); }
  .costs-toggle-meta :global(svg) { transition: transform 0.15s ease; }

  /* ── Billing-history table (.data-table recipe, DESIGN_SYSTEM.md §5.3) ──
     .data-table td's color is unlayered global CSS, so a Tailwind text-color
     utility can't win against it (cascade layers rank utilities below
     unlayered rules) — these scoped classes out-specificity it instead. */
  .tx-list {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    background: var(--color-bg-elevated);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }
  .tx-scroll { overflow-x: auto; }
  .cell-primary { color: var(--color-text-primary); }
  .cell-muted { color: var(--color-text-muted); }
  .tx-type-cell {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-weight: 600;
    white-space: nowrap;
  }
  .tx-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .tx-desc-col {
    max-width: 22rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tx-amount-cell {
    font-weight: 700;
    /* A deduction is not a warning — negative uses text-secondary, not orange. */
    color: var(--color-text-secondary);
  }
  .tx-amount-pos { color: var(--color-success-text); }
  .tx-date-cell { white-space: nowrap; }

  :global(.redeem-button) {
    flex-shrink: 0;
    width: 100%;
  }
  @media (min-width: 640px) {
    :global(.redeem-button) {
      width: auto;
      min-width: 12rem;
    }
  }

  @media (max-width: 560px) {
    .tx-desc-col { display: none; }
  }

  /* Reduced-motion: kill the refresh spinner + chevron rotation transition. */
  @media (prefers-reduced-motion: reduce) {
    :global(.animate-spin) { animation: none !important; }
    .costs-toggle-meta :global(svg) { transition: none !important; }
  }
</style>
