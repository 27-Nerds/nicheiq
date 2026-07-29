<script lang="ts">
  import type { Report } from "$lib/types/report";
  import { AlertTriangle, MessageSquare, Share2 } from "lucide-svelte";
  import { page } from "$app/state";

  import ReportContent from "$lib/components/ReportContent.svelte";
  import ShareReportModal from "$lib/components/ShareReportModal.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import CompletedAnalyst from "$lib/components/chat/CompletedAnalyst.svelte";
  import FinalDecisionWorkspace from "$lib/components/decision/FinalDecisionWorkspace.svelte";
  import Sheet from "$lib/components/ui/Sheet.svelte";

  interface Props {
    data: {
      report: Report;
      jobId: string;
    };
  }

  let { data }: Props = $props();
  const report = $derived(data.report);
  const jobId = $derived(data.jobId);

  let shareModalOpen = $state(false);
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
    <title>Report Not Found - NicheIQ</title>
  {/if}
</svelte:head>

{#if !report}
  <div class="min-h-screen flex items-center justify-center">
    <EmptyState
      icon={AlertTriangle}
      title="Report Not Found"
      description="The requested report could not be loaded. It may have been deleted or you may not have permission to view it."
    >
      <a href="/jobs/{jobId}" class="btn-primary">Back to Job Status</a>
    </EmptyState>
  </div>
{:else}
  <ReportContent {report} showBackLink={true} {jobId}>
    {#snippet headerSlot()}
      <div class="header-actions">
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
  <ShareReportModal bind:open={shareModalOpen} {jobId} />
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
