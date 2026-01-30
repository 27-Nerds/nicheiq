<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';

  let { data } = $props();

  const stats = $derived(data.reportStats);

  function formatDuration(seconds: number | null): string {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }

  type StatusVariant = 'success' | 'error' | 'warning' | 'info' | 'muted';

  function statusVariant(status: string): StatusVariant {
    const map: Record<string, StatusVariant> = {
      COMPLETED: 'success',
      FAILED: 'error',
      RUNNING: 'info',
      QUEUED: 'warning',
      PENDING: 'muted',
      CANCELLED: 'muted',
    };
    return map[status] || 'muted';
  }
</script>

<svelte:head>
  <title>Report Stats | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <h2 class="text-2xl font-bold text-text-primary mb-6">Report Stats</h2>

  {#if stats}
    <!-- Overview Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <p class="text-sm text-text-muted mb-1">Success Rate</p>
        <p class="text-3xl font-bold text-success">{stats.successRate}%</p>
        <div class="mt-2 h-2 bg-bg-elevated rounded-full overflow-hidden">
          <div class="h-full bg-success rounded-full" style="width: {stats.successRate}%"></div>
        </div>
      </div>
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <p class="text-sm text-text-muted mb-1">Failure Rate</p>
        <p class="text-3xl font-bold text-error">{stats.failureRate}%</p>
        <div class="mt-2 h-2 bg-bg-elevated rounded-full overflow-hidden">
          <div class="h-full bg-error rounded-full" style="width: {stats.failureRate}%"></div>
        </div>
      </div>
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <p class="text-sm text-text-muted mb-1">Avg Duration</p>
        <p class="text-3xl font-bold text-text-primary">{formatDuration(stats.avgDurationSeconds)}</p>
        <p class="text-xs text-text-muted mt-1">{stats.completedJobs} completed of {stats.totalJobs} total</p>
      </div>
    </div>

    <!-- Failures by Stage -->
    {#if stats.failuresByStage.length > 0}
      <div class="bg-bg-surface border border-border rounded-xl p-5 mb-8">
        <h3 class="text-lg font-semibold text-text-primary mb-4">Failures by Stage</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-border">
                <th class="text-left py-2 pr-4 text-text-muted font-medium">Stage</th>
                <th class="text-right py-2 text-text-muted font-medium">Failures</th>
              </tr>
            </thead>
            <tbody>
              {#each stats.failuresByStage as item}
                <tr class="border-b border-border/50">
                  <td class="py-2 pr-4 text-text-primary">{item.stage}</td>
                  <td class="py-2 text-right text-error font-medium">{item.count}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- Recent Jobs -->
    <div class="bg-bg-surface border border-border rounded-xl p-5">
      <h3 class="text-lg font-semibold text-text-primary mb-4">Recent Jobs</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left py-2 pr-4 text-text-muted font-medium">Niche</th>
              <th class="text-left py-2 pr-4 text-text-muted font-medium">User</th>
              <th class="text-left py-2 pr-4 text-text-muted font-medium">Status</th>
              <th class="text-left py-2 pr-4 text-text-muted font-medium">Stage</th>
              <th class="text-left py-2 text-text-muted font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {#each stats.recentJobs as job}
              <tr class="border-b border-border/50">
                <td class="py-2 pr-4 text-text-primary max-w-48 truncate">{job.niche}</td>
                <td class="py-2 pr-4 text-text-secondary">{job.user?.email || 'N/A'}</td>
                <td class="py-2 pr-4">
                  <Badge variant={statusVariant(job.status)} size="sm">{job.status}</Badge>
                </td>
                <td class="py-2 pr-4 text-text-secondary">{job.currentStageName || '-'}</td>
                <td class="py-2 text-text-muted">{formatDate(job.createdAt)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load report stats.</p>
    </div>
  {/if}
</div>
