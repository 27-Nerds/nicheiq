<script lang="ts">
  import type { Report } from "$lib/types/report";
  import { Link2Off, ArrowRight } from "lucide-svelte";
  import ReportContent from "$lib/components/ReportContent.svelte";
  import SharedViewBanner from "$lib/components/share/SharedViewBanner.svelte";
  import SharedViewEndCTA from "$lib/components/share/SharedViewEndCTA.svelte";

  interface Props {
    data: {
      report: Report | null;
      shareToken: string;
      allowIndexing: boolean;
    };
  }

  let { data }: Props = $props();
  const report = $derived(data.report);
</script>

<svelte:head>
  {#if report}
    <title>{report.selected_solution_name} - Shared Report - NicheIQ</title>
    <meta
      name="description"
      content={report.executive_summary?.slice(0, 160)}
    />
  {:else}
    <title>Report Unavailable - NicheIQ</title>
  {/if}
  {#if !data.allowIndexing}
    <meta name="robots" content="noindex, nofollow" />
    <meta name="googlebot" content="noindex, nofollow" />
  {/if}
</svelte:head>

{#if !report}
  <div class="min-h-[60vh] flex items-center justify-center px-4">
    <div class="text-center max-w-md">
      <div
        class="mx-auto w-16 h-16 rounded-full bg-bg-surface flex items-center justify-center mb-6"
      >
        <Link2Off class="w-8 h-8 text-[color:var(--color-text-muted)]" />
      </div>
      <h1 class="text-2xl font-bold text-text-primary mb-2">
        This report is no longer available
      </h1>
      <p class="text-text-secondary mb-6">
        The share link may have expired or been disabled by the report owner.
      </p>
      <a href="/" class="btn-primary inline-flex items-center gap-2">
        Discover NicheIQ
        <ArrowRight class="w-4 h-4" />
      </a>
    </div>
  </div>
{:else}
  <SharedViewBanner variant="report" shareToken={data.shareToken} />

  <ReportContent {report} showBackLink={false} showShareButton={false} />

  <SharedViewEndCTA variant="report" shareToken={data.shareToken} />
{/if}
