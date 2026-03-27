<script lang="ts">
  import type { Report } from "$lib/types/report";
  import { AlertTriangle, Share2 } from "lucide-svelte";

  import ReportContent from "$lib/components/ReportContent.svelte";
  import ShareReportModal from "$lib/components/ShareReportModal.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";

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
      <button onclick={() => (shareModalOpen = true)} class="share-btn">
        <Share2 class="w-4 h-4" />
        <span>Share</span>
      </button>
    {/snippet}
  </ReportContent>

  <ShareReportModal bind:open={shareModalOpen} {jobId} />
{/if}

<style>
  .share-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.875rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
  }

  .share-btn:hover {
    color: var(--color-text-primary);
    border-color: var(--color-accent);
    background: rgba(229, 90, 40, 0.05);
  }
</style>
