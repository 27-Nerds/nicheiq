<script lang="ts">
  import { invalidateAll } from '$app/navigation';
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
    Sparkles,
    CreditCard
  } from 'lucide-svelte';

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

  let { data } = $props();
  const billing = $derived(data.billing as BillingData);

  // Promo code state
  let promoCode = $state('');
  let promoError = $state<string | null>(null);
  let promoSuccess = $state<string | null>(null);
  let isRedeeming = $state(false);

  // Refresh state
  let isRefreshing = $state(false);

  async function redeemPromoCode() {
    if (!promoCode.trim() || isRedeeming) return;

    isRedeeming = true;
    promoError = null;
    promoSuccess = null;

    try {
      const response = await fetch('/api/billing/redeem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: promoCode.trim() }),
      });

      const result = await response.json();

      if (response.ok) {
        promoSuccess = result.message;
        promoCode = '';
        // Refresh the page data to update balance
        await invalidateAll();
      } else {
        promoError = result.error || 'Failed to redeem promo code';
      }
    } catch (error) {
      promoError = 'Network error. Please try again.';
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
      case 'PURCHASE':
      case 'PROMO_REDEMPTION':
        return { icon: ArrowUpRight, class: 'text-success bg-success/10' };
      case 'JOB_DEDUCTION':
        return { icon: ArrowDownRight, class: 'text-warning bg-warning/10' };
      case 'REFUND':
        return { icon: ArrowUpRight, class: 'text-accent bg-accent/10' };
      case 'ADMIN_ADJUSTMENT':
        return { icon: Sparkles, class: 'text-secondary bg-secondary/10' };
      default:
        return { icon: Clock, class: 'text-text-muted bg-bg-elevated' };
    }
  }

  function formatTransactionType(type: string): string {
    switch (type) {
      case 'PURCHASE':
        return 'Purchase';
      case 'JOB_DEDUCTION':
        return 'Research Job';
      case 'PROMO_REDEMPTION':
        return 'Promo Code';
      case 'REFUND':
        return 'Refund';
      case 'ADMIN_ADJUSTMENT':
        return 'Adjustment';
      default:
        return type;
    }
  }

  function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function formatRelativeDate(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  }
</script>

<svelte:head>
  <title>Billing - NicheIQ</title>
</svelte:head>

<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <!-- Header -->
  <div class="mb-8 flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-text-primary flex items-center gap-3">
        <div class="p-2 rounded-xl bg-accent/10 border border-accent/20">
          <CreditCard class="w-6 h-6 text-accent" />
        </div>
        Research Credits
      </h1>
      <p class="text-text-muted mt-1">
        Manage your credits and view transaction history
      </p>
    </div>
    <button
      onclick={refreshData}
      disabled={isRefreshing}
      class="btn-secondary"
      title="Refresh"
    >
      <RefreshCw class="w-4 h-4 {isRefreshing ? 'animate-spin' : ''}" />
    </button>
  </div>

  <!-- Balance Card -->
  <div class="card bg-gradient-to-br from-accent/5 via-bg-surface to-secondary/5 border-accent/20 mb-8">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
      <div>
        <p class="text-sm text-text-muted mb-1">Available Credits</p>
        <div class="flex items-baseline gap-2">
          <span class="text-5xl font-bold text-text-primary">{billing.balance}</span>
          <span class="text-lg text-text-muted">credits</span>
        </div>
        <div class="flex items-center gap-4 mt-3 text-sm">
          <span class="text-text-muted">
            <span class="font-medium text-success">{billing.totalPurchased}</span> earned
          </span>
          <span class="text-text-muted">
            <span class="font-medium text-warning">{billing.totalUsed}</span> used
          </span>
        </div>
      </div>
      <div class="p-4 rounded-2xl bg-accent/10 border border-accent/20">
        <Coins class="w-12 h-12 text-accent" />
      </div>
    </div>
  </div>

  <!-- Info Banner (if no credits) -->
  {#if billing.balance === 0}
    <div class="mb-8 p-4 rounded-lg bg-warning/5 border border-warning/20">
      <div class="flex items-start gap-3">
        <AlertCircle class="w-5 h-5 text-warning shrink-0 mt-0.5" />
        <div>
          <p class="text-sm font-medium text-text-primary">
            You need research credits to start new research
          </p>
          <p class="text-sm text-text-muted mt-1">
            Redeem a promo code below to get started, or contact us for credit packages.
          </p>
        </div>
      </div>
    </div>
  {/if}

  <div class="grid gap-8 md:grid-cols-2">
    <!-- Promo Code Section -->
    <div class="card">
      <div class="flex items-center gap-3 mb-4">
        <div class="p-2 rounded-lg bg-secondary/10 border border-secondary/20">
          <Gift class="w-5 h-5 text-secondary" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-text-primary">Redeem Promo Code</h2>
          <p class="text-sm text-text-muted">Enter your code to receive credits</p>
        </div>
      </div>

      <div class="space-y-4">
        <div>
          <input
            type="text"
            bind:value={promoCode}
            placeholder="Enter promo code"
            class="input w-full uppercase tracking-wider"
            maxlength="50"
            disabled={isRedeeming}
            onkeydown={(e) => e.key === 'Enter' && redeemPromoCode()}
          />
        </div>

        {#if promoError}
          <div class="flex items-center gap-2 text-sm text-error">
            <AlertCircle class="w-4 h-4" />
            {promoError}
          </div>
        {/if}

        {#if promoSuccess}
          <div class="flex items-center gap-2 text-sm text-success">
            <CheckCircle class="w-4 h-4" />
            {promoSuccess}
          </div>
        {/if}

        <button
          onclick={redeemPromoCode}
          disabled={!promoCode.trim() || isRedeeming}
          class="btn-primary w-full"
        >
          {#if isRedeeming}
            <Loader2 class="w-4 h-4 animate-spin" />
            Redeeming...
          {:else}
            <Gift class="w-4 h-4" />
            Redeem Code
          {/if}
        </button>
      </div>
    </div>

    <!-- Recent Transactions -->
    <div class="card">
      <div class="flex items-center gap-3 mb-4">
        <div class="p-2 rounded-lg bg-accent/10 border border-accent/20">
          <History class="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-text-primary">Recent Activity</h2>
          <p class="text-sm text-text-muted">Your latest transactions</p>
        </div>
      </div>

      {#if billing.recentTransactions.length === 0}
        <div class="text-center py-8 text-text-muted">
          <History class="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p class="text-sm">No transactions yet</p>
        </div>
      {:else}
        <div class="space-y-3">
          {#each billing.recentTransactions as tx}
            {@const txInfo = getTransactionIcon(tx.type)}
            {@const TxIcon = txInfo.icon}
            <div class="flex items-center gap-3 p-3 rounded-lg bg-bg-elevated/50 border border-border/50">
              <div class="p-2 rounded-lg {txInfo.class}">
                <TxIcon class="w-4 h-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-sm font-medium text-text-primary truncate">
                    {formatTransactionType(tx.type)}
                  </span>
                  <span class="text-sm font-semibold {tx.amount > 0 ? 'text-success' : 'text-warning'}">
                    {tx.amount > 0 ? '+' : ''}{tx.amount}
                  </span>
                </div>
                <div class="flex items-center justify-between gap-2 mt-0.5">
                  <span class="text-xs text-text-muted truncate" title={tx.description || ''}>
                    {tx.description || '-'}
                  </span>
                  <span class="text-xs text-text-muted shrink-0" title={formatDate(tx.createdAt)}>
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

  <!-- How It Works -->
  <div class="mt-8 card bg-bg-elevated/50">
    <h3 class="text-lg font-semibold text-text-primary mb-4">How Credits Work</h3>
    <div class="grid gap-4 sm:grid-cols-3">
      <div class="flex items-start gap-3">
        <div class="w-8 h-8 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-semibold text-sm shrink-0">
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
        <div class="w-8 h-8 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-semibold text-sm shrink-0">
          2
        </div>
        <div>
          <p class="font-medium text-text-primary text-sm">Start Research</p>
          <p class="text-xs text-text-muted mt-1">
            Each research job costs 1 credit
          </p>
        </div>
      </div>
      <div class="flex items-start gap-3">
        <div class="w-8 h-8 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-semibold text-sm shrink-0">
          3
        </div>
        <div>
          <p class="font-medium text-text-primary text-sm">Auto-Refund</p>
          <p class="text-xs text-text-muted mt-1">
            Failed jobs are automatically refunded
          </p>
        </div>
      </div>
    </div>
  </div>
</div>
