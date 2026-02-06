<script lang="ts">
  import {
    Loader2,
    ExternalLink,
    RotateCw,
    X,
    AlertCircle,
    CheckCircle,
    MoreVertical,
    Download,
  } from "lucide-svelte";
  import type { Snippet } from "svelte";

  interface StopReasonDetails {
    qualityTier?: string;
    confidenceScore?: number;
    metrics?: {
      painPointCount?: number;
      quoteDensity?: number;
      sourceCoverage?: number;
    };
    recommendation?: string;
  }

  interface Job {
    id: string;
    niche: string;
    status: string;
    currentStage: number;
    currentStageName: string | null;
    stagesCompleted: number;
    totalStages: number;
    progressPercent: number;
    errorMessage: string | null;
    createdAt: string;
    startedAt: string | null;
    completedAt: string | null;
    hasReport: boolean;
    hasLandingPage: boolean;
    creditRefunded?: boolean;
    queuePosition?: number | null;
    aheadCount?: number;
    totalQueued?: number;
    stopReason?: string | null;
    stopReasonDetails?: StopReasonDetails | null;
    allowedProjectTypes?: string[] | null;
  }

  interface Props {
    job: Job;
    onCancel?: (job: Job) => void;
    onResume?: (job: Job) => void;
    isCancelling?: boolean;
    isResuming?: boolean;
    animationDelay?: number;
    isMenuOpen?: boolean;
    onMenuToggle?: (jobId: string, event: MouseEvent) => void;
  }

  let {
    job,
    onCancel,
    onResume,
    isCancelling = false,
    isResuming = false,
    animationDelay = 0,
    isMenuOpen = false,
    onMenuToggle,
  }: Props = $props();

  const TOTAL_STAGES = 16;
  const HIDDEN_STAGES = [6.5];

  // Derived state
  const isRunning = $derived(job.status.toUpperCase() === "RUNNING");
  const isQueued = $derived(
    ["PENDING", "QUEUED"].includes(job.status.toUpperCase()),
  );
  const isCompleted = $derived(job.status.toUpperCase() === "COMPLETED");
  const isFailed = $derived(job.status.toUpperCase() === "FAILED");

  // Human-readable error for failed jobs
  const humanError = $derived(getHumanReadableError(job));
  const isQualityGate = $derived(humanError.isQualityGate);
  const stageCounts = $derived(getAdjustedStageCounts(job));

  // Project type labels
  const PROJECT_TYPE_LABELS: Record<string, string> = {
    saas: "SaaS",
    directory: "Directory",
    aggregator: "Aggregator",
    "comparison-tool": "Comparison Tool",
    marketplace: "Marketplace",
  };
  const ALL_PROJECT_TYPE_COUNT = Object.keys(PROJECT_TYPE_LABELS).length;

  const showAllTypes = $derived(
    !job.allowedProjectTypes ||
      job.allowedProjectTypes.length === 0 ||
      job.allowedProjectTypes.length === ALL_PROJECT_TYPE_COUNT,
  );

  // Border and dot colors based on state
  const borderClass = $derived(
    isRunning
      ? "border-l-warning"
      : isQueued
        ? "border-l-secondary"
        : isCompleted
          ? "border-l-success"
          : isFailed
            ? isQualityGate
              ? "border-l-warning"
              : "border-l-error"
            : "border-l-border",
  );

  const dotClass = $derived(
    isRunning
      ? "bg-warning animate-pulse"
      : isQueued
        ? "bg-secondary"
        : isCompleted
          ? "bg-success"
          : isFailed
            ? isQualityGate
              ? "bg-warning"
              : "bg-error"
            : "bg-text-muted",
  );

  // Stage name overrides for parallel stages
  const STAGE_NAME_OVERRIDES: Record<string, string> = {
    "Pain Point Analysis": "Pain Point & Audience Analysis",
    "Audience Mapping": "Pain Point & Audience Analysis",
  };

  function getDisplayStageName(stageName: string | null): string {
    if (!stageName) return "Starting";
    return STAGE_NAME_OVERRIDES[stageName] || stageName;
  }

  function getAdjustedStageCounts(job: Job): {
    completed: number;
    total: number;
  } {
    const hiddenCount = HIDDEN_STAGES.length;
    const total = (job.totalStages || TOTAL_STAGES) - hiddenCount;
    const hiddenCompleted =
      job.currentStage > 6.5 || job.status.toUpperCase() === "COMPLETED"
        ? hiddenCount
        : 0;
    const completed = job.stagesCompleted - hiddenCompleted;
    return { completed: Math.max(0, completed), total };
  }

  function formatNicheTitle(niche: string): string {
    return niche
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ");
  }

  function formatElapsedTime(startedAt: string | null): string {
    if (!startedAt) return "";
    const start = new Date(startedAt);
    const now = new Date();
    const diffMs = now.getTime() - start.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "just started";
    if (diffMins === 1) return "1 min elapsed";
    return `${diffMins} min elapsed`;
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
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;

    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    });
  }

  function formatDate(dateStr: string) {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function getHumanReadableError(job: Job): {
    summary: string;
    suggestion: string;
    isQualityGate?: boolean;
  } {
    if (job.stopReason === "INSUFFICIENT_DATA") {
      return {
        summary: "Insufficient discussion data found",
        suggestion:
          job.stopReasonDetails?.recommendation || "Try a broader niche topic",
        isQualityGate: true,
      };
    }

    const errorMessage = job.errorMessage;
    if (!errorMessage) {
      return {
        summary: "Research failed",
        suggestion: "Try again or contact support.",
      };
    }

    const error = errorMessage.toLowerCase();

    if (
      error.includes("cannot be empty") ||
      error.includes("niche description")
    ) {
      return {
        summary: "Invalid niche",
        suggestion: "Please provide a more descriptive niche.",
      };
    }
    if (
      error.includes("no social content") ||
      error.includes("no reddit") ||
      error.includes("no twitter")
    ) {
      return {
        summary: "No discussions found",
        suggestion: "Try a broader or more popular niche topic.",
      };
    }
    if (error.includes("cancelled") || error.includes("canceled")) {
      return {
        summary: "Cancelled",
        suggestion: "You cancelled this research.",
      };
    }
    if (error.includes("insufficient") && error.includes("credit")) {
      return {
        summary: "Insufficient credits",
        suggestion: "Purchase more credits to continue researching.",
      };
    }
    if (error.includes("timeout") || error.includes("timed out")) {
      return {
        summary: "Research took too long",
        suggestion: "Try with a more specific niche.",
      };
    }
    if (
      error.includes("no results") ||
      error.includes("not found") ||
      error.includes("no data")
    ) {
      return {
        summary: "No data found for this niche",
        suggestion: "Try a different or broader niche.",
      };
    }
    if (
      error.includes("quality gate") ||
      error.includes("confidence") ||
      error.includes("threshold")
    ) {
      return {
        summary: "Quality check failed",
        suggestion:
          "The research didn't meet quality standards. Your credit was refunded.",
      };
    }
    if (error.includes("requires") && error.includes("stage")) {
      return {
        summary: "Pipeline error",
        suggestion: "An internal error occurred. Your credit was refunded.",
      };
    }
    if (error.includes("dataforseo")) {
      return {
        summary: "SEO data unavailable",
        suggestion: "External SEO service issue. Try again later.",
      };
    }
    if (
      error.includes("rate limit") ||
      error.includes("quota") ||
      error.includes("429")
    ) {
      return {
        summary: "Service temporarily busy",
        suggestion: "Wait a few minutes and try again.",
      };
    }
    if (
      error.includes("400") ||
      error.includes("invalid_request") ||
      error.includes("unsupported_parameter")
    ) {
      return {
        summary: "Configuration issue",
        suggestion:
          "This is on our end. Your credit was refunded automatically.",
      };
    }
    if (
      error.includes("401") ||
      error.includes("403") ||
      error.includes("authentication") ||
      error.includes("api key")
    ) {
      return {
        summary: "Service connection issue",
        suggestion: "This is on our end. Try again later.",
      };
    }
    if (
      error.includes("500") ||
      error.includes("502") ||
      error.includes("503") ||
      error.includes("server")
    ) {
      return {
        summary: "Server error",
        suggestion: "Our systems are having issues. Try again later.",
      };
    }

    return {
      summary: "Research failed",
      suggestion: "Try again or contact support if the issue persists.",
    };
  }

  function handleCancel() {
    if (onCancel && !isCancelling) {
      onCancel(job);
    }
  }

  function handleResume() {
    if (onResume && !isResuming) {
      onResume(job);
    }
  }

  function handleMenuToggle(event: MouseEvent) {
    if (onMenuToggle) {
      onMenuToggle(job.id, event);
    }
  }

  // Queue position text
  const queuePositionText = $derived(
    job.queuePosition === 1
      ? "Next up"
      : job.queuePosition
        ? `Position ${job.queuePosition}`
        : "Queued",
  );
</script>

{#snippet projectTypeBadges()}
  <div class="flex flex-wrap items-center gap-1 mt-2">
    {#if showAllTypes}
      <span
        class="text-[11px] px-2 py-0.5 rounded bg-bg-surface border border-border text-text-muted"
        >All types</span
      >
    {:else}
      {#each job.allowedProjectTypes ?? [] as typeValue}
        <span
          class="text-[11px] px-2 py-0.5 rounded bg-accent/5 border border-accent/20 text-accent"
        >
          {PROJECT_TYPE_LABELS[typeValue] ?? typeValue}
        </span>
      {/each}
    {/if}
  </div>
{/snippet}

{#snippet relativeDate(dateStr: string)}
  <span class="text-xs text-text-muted shrink-0" title={formatDate(dateStr)}>
    {formatRelativeDate(dateStr)}
  </span>
{/snippet}

{#snippet cancelButton()}
  <button
    onclick={handleCancel}
    disabled={isCancelling}
    class="p-1.5 rounded-md text-text-muted hover:text-error hover:bg-error/5 transition-colors"
    title="Cancel"
    aria-label="Cancel research"
  >
    {#if isCancelling}
      <Loader2 class="w-4 h-4 animate-spin" />
    {:else}
      <X class="w-4 h-4" />
    {/if}
  </button>
{/snippet}

{#snippet jobCardHeader(rightBadge: Snippet)}
  <div class="flex items-center justify-between gap-4">
    <div class="flex items-center gap-2.5 min-w-0 flex-1 w-0">
      <span class="w-2 h-2 rounded-full {dotClass} shrink-0"></span>
      <h3 class="text-base font-semibold text-text-primary truncate min-w-0">
        {formatNicheTitle(job.niche)}
      </h3>
    </div>
    {@render rightBadge()}
  </div>
{/snippet}

<div
  class="card relative hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-2 {borderClass} cursor-pointer animate-fade-slide-in {isMenuOpen
    ? 'z-50'
    : ''}"
  style="animation-delay: {animationDelay}ms"
>
  <!-- Stretched link: covers entire card for native <a> click behavior -->
  <a
    href="/jobs/{job.id}"
    class="absolute inset-0 z-0 rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
    aria-label="View details for {formatNicheTitle(job.niche)}"
    onclick={(e: MouseEvent) => {
      const sel = window.getSelection();
      if (sel && sel.toString().length > 0) e.preventDefault();
    }}
  ></a>
  <div class="relative z-10 pointer-events-none">
    {#if isRunning}
      <!-- RUNNING STATE -->
      {#snippet runningBadge()}
        {#if job.startedAt}
          <span class="text-xs font-medium text-warning shrink-0">
            {formatElapsedTime(job.startedAt)}
          </span>
        {/if}
      {/snippet}
      {@render jobCardHeader(runningBadge)}
      {@render projectTypeBadges()}

      <!-- Progress bar -->
      <div class="flex items-center gap-3">
        <div class="flex-1 h-1.5 bg-bg-surface rounded-full overflow-hidden">
          <div
            class="h-full bg-warning rounded-full transition-all duration-300 animate-shimmer"
            style="width: {job.progressPercent}%"
          ></div>
        </div>
        <span class="text-xs text-text-muted whitespace-nowrap">
          {getDisplayStageName(job.currentStageName)} ({stageCounts.completed}/{stageCounts.total})
        </span>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-2 mt-3 pointer-events-auto">
        {@render cancelButton()}
      </div>
    {:else if isQueued}
      <!-- QUEUED STATE -->
      {#snippet queueBadge()}
        <span
          class="text-xs px-2 py-0.5 bg-secondary/10 text-secondary rounded-full font-medium shrink-0"
        >
          {queuePositionText}
        </span>
      {/snippet}
      {@render jobCardHeader(queueBadge)}
      {@render projectTypeBadges()}

      <!-- Footer -->
      <div class="flex items-center justify-end gap-2 mt-3 pointer-events-auto">
        {@render cancelButton()}
      </div>
    {:else if isCompleted}
      <!-- COMPLETED STATE -->
      {#snippet completedBadge()}
        {@render relativeDate(job.completedAt || job.createdAt)}
      {/snippet}
      {@render jobCardHeader(completedBadge)}
      {@render projectTypeBadges()}

      <!-- Footer -->
      <div class="flex items-center justify-end gap-2 mt-3 pointer-events-auto">
        <a href="/jobs/{job.id}/report" class="btn-primary text-sm py-2 px-4">
          View Report
        </a>
        {#if job.hasLandingPage}
          <a
            href="/api/jobs/{job.id}/landingpage"
            target="_blank"
            rel="noopener noreferrer"
            class="btn-secondary text-sm py-2 px-4"
          >
            Landing Page
            <ExternalLink class="w-3.5 h-3.5" />
          </a>
        {/if}
        <!-- Overflow menu for downloads -->
        <div class="relative" data-menu-container>
          <button
            onclick={handleMenuToggle}
            class="p-2 rounded-md text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
            aria-label="More options"
          >
            <MoreVertical class="w-4 h-4" />
          </button>
          {#if isMenuOpen}
            <div
              class="absolute right-0 top-full mt-1 bg-bg-elevated border border-border rounded-lg shadow-lg py-1 min-w-[160px] z-50"
            >
              <a
                href="/api/jobs/{job.id}/reportjson"
                download
                class="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
              >
                <Download class="w-4 h-4" /> Export JSON
              </a>
              {#if job.hasLandingPage}
                <a
                  href="/api/jobs/{job.id}/landingpage?download=true"
                  download
                  class="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
                >
                  <Download class="w-4 h-4" /> Export HTML
                </a>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {:else if isFailed}
      <!-- FAILED STATE -->
      {#snippet failedBadge()}
        {@render relativeDate(job.createdAt)}
      {/snippet}
      {@render jobCardHeader(failedBadge)}
      {@render projectTypeBadges()}

      <!-- Error box -->
      {#if job.errorMessage || job.stopReason}
        <div
          class="mt-3 p-3 rounded-lg {isQualityGate
            ? 'bg-warning/5 border border-warning/10'
            : 'bg-error/5 border border-error/10'}"
        >
          <div class="flex items-start gap-2">
            <AlertCircle
              class="w-4 h-4 shrink-0 mt-0.5 {isQualityGate
                ? 'text-warning'
                : 'text-error'}"
            />
            <div class="flex-1">
              <p
                class="text-sm font-medium {isQualityGate
                  ? 'text-warning'
                  : 'text-error'}"
              >
                {humanError.summary}
              </p>
              <p class="text-xs text-text-muted mt-0.5">
                {humanError.suggestion}
              </p>
            </div>
          </div>
        </div>
      {/if}

      <!-- Footer -->
      <div
        class="flex items-center justify-between gap-2 mt-3 pointer-events-auto"
      >
        <!-- Credit refund indicator -->
        <div>
          {#if job.creditRefunded || isQualityGate}
            <div class="flex items-center gap-1.5">
              <CheckCircle class="w-3.5 h-3.5 text-success" />
              <span class="text-xs text-success font-medium"
                >Credit refunded</span
              >
            </div>
          {/if}
        </div>
        <!-- Actions -->
        <div class="flex items-center gap-2">
          <button
            onclick={handleResume}
            disabled={isResuming}
            class="btn-primary flex items-center gap-2"
            title="Resume from last checkpoint (no credit charge)"
          >
            <RotateCw class="w-4 h-4 {isResuming ? 'animate-spin' : ''}" />
            {isResuming ? "Resuming..." : "Resume"}
          </button>
        </div>
      </div>
    {/if}
  </div>
</div>
