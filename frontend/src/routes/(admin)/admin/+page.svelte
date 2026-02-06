<script lang="ts">
  import {
    Users,
    Briefcase,
    CheckCircle,
    XCircle,
    Coins,
    TrendingUp,
  } from "lucide-svelte";

  let { data } = $props();

  const stats = $derived(data.stats);
</script>

<svelte:head>
  <title>Admin Dashboard | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <h2 class="text-2xl font-bold text-text-primary mb-6">Dashboard</h2>

  {#if stats}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-secondary/10">
            <Users class="w-5 h-5 text-secondary" />
          </div>
          <span class="text-sm text-text-muted">Total Users</span>
        </div>
        <p class="text-3xl font-bold text-text-primary">
          {stats.totalUsers.toLocaleString()}
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-accent/10">
            <Briefcase class="w-5 h-5 text-accent" />
          </div>
          <span class="text-sm text-text-muted">Active Jobs</span>
        </div>
        <p class="text-3xl font-bold text-text-primary">
          {stats.activeJobs.toLocaleString()}
        </p>
        <p class="text-xs text-text-muted mt-1">
          {stats.totalJobs.toLocaleString()} total
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-success/10">
            <CheckCircle class="w-5 h-5 text-success" />
          </div>
          <span class="text-sm text-text-muted">Completed</span>
        </div>
        <p class="text-3xl font-bold text-success">
          {stats.completedJobs.toLocaleString()}
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-error/10">
            <XCircle class="w-5 h-5 text-error" />
          </div>
          <span class="text-sm text-text-muted">Failed</span>
        </div>
        <p class="text-3xl font-bold text-error">
          {stats.failedJobs.toLocaleString()}
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-accent/10">
            <Coins class="w-5 h-5 text-accent" />
          </div>
          <span class="text-sm text-text-muted">Credits Purchased</span>
        </div>
        <p class="text-3xl font-bold text-text-primary">
          {stats.totalCreditsPurchased.toLocaleString()}
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-warning/10">
            <TrendingUp class="w-5 h-5 text-warning" />
          </div>
          <span class="text-sm text-text-muted">Credits Used</span>
        </div>
        <p class="text-3xl font-bold text-text-primary">
          {stats.totalCreditsUsed.toLocaleString()}
        </p>
      </div>
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load dashboard stats.</p>
    </div>
  {/if}
</div>
