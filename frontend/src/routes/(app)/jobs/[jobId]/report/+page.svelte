<script lang="ts">
  import type { Report } from "$lib/types/report";
  import { Download, MessageSquare, Share2 } from "lucide-svelte";
  import { page } from "$app/state";

  import ReportContent from "$lib/components/ReportContent.svelte";
  import ShareReportModal from "$lib/components/ShareReportModal.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import CompletedAnalyst from "$lib/components/chat/CompletedAnalyst.svelte";
  import FinalDecisionWorkspace from "$lib/components/decision/FinalDecisionWorkspace.svelte";
  import Sheet from "$lib/components/ui/Sheet.svelte";

  interface Props {
    data: {
      report: Report | null;
      jobId: string;
      reportState?: "ready" | "not_ready" | "not_found";
      message?: string;
    };
  }

  let { data }: Props = $props();
  const report = $derived(data.report);
  const jobId = $derived(data.jobId);

  let shareModalOpen = $state(false);
  let shareTrigger = $state<HTMLButtonElement>();
  let decisionLabOpen = $state(false);
  let analystOpen = $state(false);
  // The post-research Decision Lab rides the same admin grant as the optional
  // selection checks. Its endpoints (final-decision, decision-handoff, GitHub
  // dispatch) all 403 without it, so the entry point is hidden too.
  const decisionTools = $derived(page.data.featureAccess?.decisionTools === true);
  const analyst = $derived(page.data.featureAccess?.analyst === true);
</script>

<svelte:head>
  {#if report}
    <title>{report.selected_solution_name} - NicheIQ Report</title>
    <meta
      name="description"
      content={report.executive_summary?.slice(0, 160)}
    />
{:else}
    <title>{data.reportState === "not_ready" ? "Report in progress" : "Report unavailable"} - NicheIQ</title>
  {/if}
</svelte:head>

{#if !report}
  <div class="min-h-screen flex items-center justify-center">
    <EmptyState
      title={data.reportState === "not_ready" ? "Deep Research report is not ready" : "Report unavailable"}
      description={data.message ?? "The requested report could not be loaded. It may have been deleted or you may not have permission to view it."}
    >
      <a href="/jobs/{jobId}" class="btn-primary">
        {data.reportState === "not_ready" ? "View research progress" : "Back to job"}
      </a>
    </EmptyState>
  </div>
{:else}
  <ReportContent {report} showBackLink={true} {jobId}>
    {#snippet headerSlot()}
      <div class="header-actions">
        <a
          href="/api/jobs/{jobId}/reportjson"
          download
          class="report-action"
          title="Downloads the complete report data as a JSON file"
        >
          <Download class="w-4 h-4" aria-hidden="true" />
          <span>Export data</span>
          <span class="report-action-format" aria-hidden="true">JSON</span>
        </a>
        {#if analyst}
          <button
            type="button"
            class="report-action"
            aria-haspopup="dialog"
            aria-expanded={analystOpen}
            onclick={() => (analystOpen = true)}
          >
            <MessageSquare class="w-4 h-4" aria-hidden="true" />
            <span>Ask analyst</span>
          </button>
        {/if}
        <button
          bind:this={shareTrigger}
          type="button"
          onclick={() => (shareModalOpen = true)}
          class="report-action"
          aria-haspopup="dialog"
          aria-expanded={shareModalOpen}
        >
          <Share2 class="w-4 h-4" aria-hidden="true" />
          <span>Share</span>
        </button>
      </div>
    {/snippet}
    {#snippet decisionSlot()}
      {#if decisionTools}
        <FinalDecisionWorkspace {jobId} bind:open={decisionLabOpen} />
      {/if}
    {/snippet}
  </ReportContent>

  <Sheet open={analyst && analystOpen} title="Report analyst" onClose={() => (analystOpen = false)}>
    {#if analyst && analystOpen}
      <CompletedAnalyst {jobId} compact />
    {/if}
  </Sheet>
  <ShareReportModal bind:open={shareModalOpen} {jobId} restoreFocusTo={shareTrigger} />
{/if}

<style>
  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .report-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-3);
    font-family: var(--font-body);
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition:
      color var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default);
  }

  .report-action:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-hover);
  }

  .report-action:active {
    background: var(--color-bg-subtle);
  }

  .report-action:focus-visible {
    outline: 2px solid var(--color-accent-dark);
    outline-offset: 2px;
  }

  .report-action-format {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.05em;
    color: var(--color-text-secondary);
  }

  @media (max-width: 640px) {
    .header-actions {
      min-width: 0;
      justify-content: flex-end;
    }

    .report-action {
      min-height: var(--space-12);
      flex: 0 1 auto;
      justify-content: center;
      padding-inline: var(--space-3);
    }
  }
</style>
