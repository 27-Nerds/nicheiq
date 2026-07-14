<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import { ChevronDown, ChevronRight, Download, FileText } from "lucide-svelte";

  let { data } = $props();

  const stats = $derived(data.reportStats);

  let expandedJobId = $state<string | null>(null);

  function toggleExpand(jobId: string) {
    expandedJobId = expandedJobId === jobId ? null : jobId;
  }

  function formatDuration(seconds: number | null): string {
    if (!seconds) return "N/A";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  type StatusVariant = "success" | "error" | "warning" | "info" | "muted";

  function statusVariant(status: string): StatusVariant {
    const map: Record<string, StatusVariant> = {
      COMPLETED: "success",
      FAILED: "error",
      RUNNING: "info",
      QUEUED: "warning",
      PENDING: "muted",
      CANCELLED: "muted",
    };
    return map[status] || "muted";
  }

  function errorCodeVariant(code: string | null): StatusVariant {
    if (!code) return "muted";
    const map: Record<string, StatusVariant> = {
      RATE_LIMIT: "warning",
      API_AUTH_ERROR: "error",
      NETWORK_ERROR: "warning",
      TIMEOUT: "warning",
      VALIDATION_ERROR: "error",
      WORKER_CRASH: "error",
      SERVICE_UNAVAILABLE: "warning",
      INTERNAL_ERROR: "error",
    };
    return map[code] || "muted";
  }

  function parseErrorDetails(details: unknown): Record<string, unknown> | null {
    if (!details) return null;
    if (typeof details === "object") return details as Record<string, unknown>;
    if (typeof details === "string") {
      try {
        return JSON.parse(details);
      } catch {
        return null;
      }
    }
    return null;
  }

  function formatCost(usd: number | null | undefined): string {
    if (usd == null) return "—";
    // Per-stage LLM costs are often sub-cent — keep 4 decimals below $1.
    return `$${usd.toFixed(usd < 1 ? 4 : 2)}`;
  }

  function formatTokens(n: number | null | undefined): string {
    return (n ?? 0).toLocaleString();
  }

  function costSourceVariant(source: string | undefined): StatusVariant {
    const map: Record<string, StatusVariant> = {
      actual: "success",
      estimated: "muted",
      mixed: "warning",
    };
    return source ? map[source] || "muted" : "muted";
  }
</script>

<svelte:head>
  <title>Report Stats | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <h2 class="text-2xl font-bold text-text-primary mb-6">Report Stats</h2>

  {#if stats}
    <!-- Overview Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <p class="text-sm text-text-muted mb-1">Success Rate</p>
        <p class="text-3xl font-bold text-success">{stats.successRate}%</p>
        <div class="mt-2 h-2 bg-bg-elevated rounded-full overflow-hidden">
          <div
            class="h-full bg-success rounded-full"
            style="width: {stats.successRate}%"
          ></div>
        </div>
      </div>
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <p class="text-sm text-text-muted mb-1">Failure Rate</p>
        <p class="text-3xl font-bold text-error">{stats.failureRate}%</p>
        <div class="mt-2 h-2 bg-bg-elevated rounded-full overflow-hidden">
          <div
            class="h-full bg-error rounded-full"
            style="width: {stats.failureRate}%"
          ></div>
        </div>
      </div>
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <p class="text-sm text-text-muted mb-1">Avg Duration</p>
        <p class="text-3xl font-bold text-text-primary">
          {formatDuration(stats.avgDurationSeconds)}
        </p>
        <p class="text-xs text-text-muted mt-1">
          {stats.completedJobs} completed of {stats.totalJobs} total
        </p>
      </div>
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <p class="text-sm text-text-muted mb-1">Total Spend</p>
        <p class="text-3xl font-bold text-text-primary">
          {formatCost(stats.totalCostUsd)}
        </p>
        <p class="text-xs text-text-muted mt-1">
          {formatCost(stats.avgCostUsd)} avg · {stats.costedJobs} runs tracked
        </p>
        <p class="text-xs text-text-muted mt-1">
          {formatCost(stats.totalChatCostUsd)} chat cost · {formatCost(stats.avgChatCostUsd)} avg · {stats.chatCostedJobs} runs tracked
        </p>
      </div>
    </div>

    <!-- Failures by Stage -->
    {#if stats.failuresByStage.length > 0}
      <div class="bg-bg-surface border border-border rounded-xl p-5 mb-8">
        <h3 class="text-lg font-semibold text-text-primary mb-4">
          Failures by Stage
        </h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-border">
                <th class="text-left py-2 pr-4 text-text-muted font-medium"
                  >Stage</th
                >
                <th class="text-right py-2 text-text-muted font-medium"
                  >Failures</th
                >
              </tr>
            </thead>
            <tbody>
              {#each stats.failuresByStage as item}
                <tr class="border-b border-border/50">
                  <td class="py-2 pr-4 text-text-primary">{item.stage}</td>
                  <td class="py-2 text-right text-error font-medium"
                    >{item.count}</td
                  >
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
              <th class="w-8 py-2"></th>
              <th class="text-left py-2 pr-4 text-text-muted font-medium"
                >Niche</th
              >
              <th class="text-left py-2 pr-4 text-text-muted font-medium"
                >User</th
              >
              <th class="text-left py-2 pr-4 text-text-muted font-medium"
                >Status</th
              >
              <th class="text-left py-2 pr-4 text-text-muted font-medium"
                >Stage</th
              >
              <th class="text-left py-2 pr-4 text-text-muted font-medium">Created</th
              >
              <th class="text-right py-2 text-text-muted font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {#each stats.recentJobs as job}
              {@const isFailed = job.status === "FAILED"}
              {@const isExpanded = expandedJobId === job.id}
              <tr
                class="border-b border-border/50 cursor-pointer hover:bg-bg-elevated/50"
                onclick={() => toggleExpand(job.id)}
              >
                <td class="py-2 pl-2 w-8">
                  {#if isExpanded}
                    <ChevronDown size={16} class="text-text-muted" />
                  {:else}
                    <ChevronRight size={16} class="text-text-muted" />
                  {/if}
                </td>
                <td class="py-2 pr-4 text-text-primary max-w-48 truncate"
                  >{job.niche}</td
                >
                <td class="py-2 pr-4 text-text-secondary"
                  >{job.user?.email || "N/A"}</td
                >
                <td class="py-2 pr-4">
                  <Badge variant={statusVariant(job.status)} size="sm"
                    >{job.status}</Badge
                  >
                </td>
                <td class="py-2 pr-4 text-text-secondary"
                  >{job.currentStageName || "-"}</td
                >
                <td class="py-2 pr-4 text-text-muted">{formatDate(job.createdAt)}</td
                >
                <td class="py-2 text-right text-text-secondary">
                  {formatCost(job.costUsd)}
                  {#if job.chatCostUsd}
                    <span class="block text-xs text-text-muted"
                      >+{formatCost(job.chatCostUsd)} chat</span
                    >
                  {/if}
                </td>
              </tr>

              {#if isExpanded}
                {@const details = parseErrorDetails(job.errorDetails)}
                <tr class="border-b border-border/50 bg-bg-elevated/30">
                  <td colspan="7" class="px-4 py-4">
                    <div class="space-y-3 text-sm">
                      {#if isFailed}
                        <!-- Error Code & Stage -->
                        <div class="flex flex-wrap gap-x-8 gap-y-2">
                          {#if job.errorCode}
                            <div>
                              <span class="text-text-muted">Error Code:</span>
                              <Badge
                                variant={errorCodeVariant(job.errorCode)}
                                size="sm"
                                class="ml-2">{job.errorCode}</Badge
                              >
                            </div>
                          {/if}
                          {#if job.errorStage}
                            <div>
                              <span class="text-text-muted">Failed Stage:</span>
                              <span class="text-text-primary ml-2"
                                >{job.errorStage}</span
                              >
                            </div>
                          {/if}
                          {#if job.workerId}
                            <div>
                              <span class="text-text-muted">Worker:</span>
                              <span
                                class="text-text-secondary ml-2 font-mono text-xs"
                                >{job.workerId}</span
                              >
                            </div>
                          {/if}
                        </div>

                        <!-- User-facing message -->
                        {#if details?.userMessage}
                          <div>
                            <span class="text-text-muted">Summary:</span>
                            <span class="text-text-primary ml-2"
                              >{details.userMessage}</span
                            >
                          </div>
                        {/if}

                        <!-- Stop reason -->
                        {#if job.stopReason}
                          <div class="flex items-center gap-2">
                            <span class="text-text-muted">Stop Reason:</span>
                            <Badge
                              variant={errorCodeVariant(job.stopReason)}
                              size="sm">{job.stopReason}</Badge
                            >
                            {#if job.stopReasonDetails}
                              <span class="text-text-secondary"
                                >{job.stopReasonDetails}</span
                              >
                            {/if}
                          </div>
                        {/if}

                        <!-- Raw error message -->
                        {#if job.errorMessage}
                          <div>
                            <span class="text-text-muted block mb-1"
                              >Raw Error:</span
                            >
                            <pre
                              class="max-h-48 overflow-auto whitespace-pre-wrap text-xs text-text-secondary bg-bg-surface border border-border rounded-lg p-3 font-mono">{job.errorMessage}</pre>
                          </div>
                        {/if}
                      {/if}

                      <!-- Pricing breakdown -->
                      {#if job.costSummary}
                        <div>
                          <div
                            class="flex flex-wrap items-center gap-x-6 gap-y-1 mb-2"
                          >
                            <span class="text-text-muted">Pricing breakdown:</span>
                            <span class="text-text-primary font-medium"
                              >{formatCost(job.costSummary.total_cost)}</span
                            >
                            <Badge
                              variant={costSourceVariant(
                                job.costSummary.total_cost_source,
                              )}
                              size="sm"
                              >{job.costSummary.total_cost_source ||
                                "estimated"}</Badge
                            >
                            <span class="text-text-secondary text-xs">
                              {formatTokens(job.costSummary.total_prompt_tokens)} in
                              · {formatTokens(
                                job.costSummary.total_completion_tokens,
                              )} out · {formatTokens(
                                job.costSummary.total_tokens,
                              )} total tokens
                            </span>
                          </div>
                          {#if job.costSummary.stage_breakdown?.length}
                            <div class="overflow-x-auto">
                              <table class="w-full text-xs">
                                <thead>
                                  <tr class="border-b border-border">
                                    <th
                                      class="text-left py-1.5 pr-4 text-text-muted font-medium"
                                      >Stage</th
                                    >
                                    <th
                                      class="text-left py-1.5 pr-4 text-text-muted font-medium"
                                      >Model</th
                                    >
                                    <th
                                      class="text-right py-1.5 pr-4 text-text-muted font-medium"
                                      >Tokens (in/out)</th
                                    >
                                    <th
                                      class="text-right py-1.5 pr-4 text-text-muted font-medium"
                                      >Cost</th
                                    >
                                    <th
                                      class="text-left py-1.5 text-text-muted font-medium"
                                      >Source</th
                                    >
                                  </tr>
                                </thead>
                                <tbody>
                                  {#each job.costSummary.stage_breakdown as row}
                                    <tr class="border-b border-border/50">
                                      <td class="py-1.5 pr-4 text-text-primary"
                                        >{row.stage}</td
                                      >
                                      <td
                                        class="py-1.5 pr-4 text-text-secondary font-mono"
                                        >{row.model}</td
                                      >
                                      <td
                                        class="py-1.5 pr-4 text-right text-text-secondary"
                                        >{formatTokens(row.prompt_tokens)} / {formatTokens(
                                          row.completion_tokens,
                                        )}</td
                                      >
                                      <td
                                        class="py-1.5 pr-4 text-right text-text-primary"
                                        >{formatCost(row.total_cost)}</td
                                      >
                                      <td class="py-1.5 text-text-muted"
                                        >{row.cost_source}</td
                                      >
                                    </tr>
                                  {/each}
                                </tbody>
                              </table>
                            </div>
                          {/if}
                        </div>
                      {/if}

                      <!-- Download buttons -->
                      <div class="flex gap-3 pt-1">
                        <a
                          href="/api/admin/jobs/{job.id}/checkpoint"
                          download
                          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-text-secondary hover:bg-bg-elevated transition-colors"
                          onclick={(e) => e.stopPropagation()}
                        >
                          <Download size={14} />
                          Download Checkpoint
                        </a>
                        <a
                          href="/api/admin/jobs/{job.id}/logs"
                          download
                          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-text-secondary hover:bg-bg-elevated transition-colors"
                          onclick={(e) => e.stopPropagation()}
                        >
                          <FileText size={14} />
                          Download Logs
                        </a>
                      </div>
                    </div>
                  </td>
                </tr>
              {/if}
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
