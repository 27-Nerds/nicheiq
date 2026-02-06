<script lang="ts">
  import type { Report } from "$lib/types/report";
  import { Link2Off, ArrowRight } from "lucide-svelte";
  import ReportContent from "$lib/components/ReportContent.svelte";

  interface Props {
    data: {
      report: Report | null;
      shareToken: string;
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
  <meta name="robots" content="noindex, nofollow" />
  <meta name="googlebot" content="noindex, nofollow" />
</svelte:head>

{#if !report}
  <div class="min-h-[60vh] flex items-center justify-center px-4">
    <div class="text-center max-w-md">
      <div
        class="mx-auto w-16 h-16 rounded-full bg-zinc-100 flex items-center justify-center mb-6"
      >
        <Link2Off class="w-8 h-8 text-zinc-400" />
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
  <!-- Shared report banner -->
  <div
    class="bg-gradient-to-r from-accent/5 to-secondary/5 border-b border-accent/10"
  >
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <p class="text-sm text-text-secondary">
        <span class="font-medium text-text-primary">Shared report</span> from NicheIQ
      </p>
      <a
        href="/"
        class="text-sm font-medium text-accent hover:text-accent/80 transition-colors flex items-center gap-1"
      >
        Try NicheIQ
        <ArrowRight class="w-3.5 h-3.5" />
      </a>
    </div>
  </div>

  <ReportContent {report} showBackLink={false} showShareButton={false} />
{/if}
