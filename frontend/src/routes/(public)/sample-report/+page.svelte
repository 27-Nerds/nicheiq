<script lang="ts">
  import type { Report } from "$lib/types/report";
  import { ArrowRight } from "lucide-svelte";
  import ReportContent from "$lib/components/ReportContent.svelte";
  import SharedViewBanner from "$lib/components/share/SharedViewBanner.svelte";
  import SharedViewEndCTA from "$lib/components/share/SharedViewEndCTA.svelte";

  let { data } = $props();
  const report: Report | null = $derived(data.report);
</script>

<svelte:head>
  {#if report}
    <title>{report.selected_solution_name} - Sample Report - NicheIQ</title>
    <meta
      name="description"
      content={report.executive_summary?.slice(0, 160)}
    />
  {:else}
    <title>Sample Report - NicheIQ</title>
  {/if}
</svelte:head>

{#if !report}
  <div class="min-h-[60vh] flex items-center justify-center px-6">
    <div class="text-center max-w-md">
      <h1 class="font-display text-2xl font-bold text-text-primary mb-4">
        Sample Report Coming Soon
      </h1>
      <p class="text-text-secondary mb-6">
        We're preparing a sample report for you. Check back soon!
      </p>
      <a href="/" class="btn-primary inline-flex items-center gap-2">
        Discover NicheIQ <ArrowRight class="w-4 h-4" />
      </a>
    </div>
  </div>
{:else}
  <SharedViewBanner variant="sample" />
  <ReportContent {report} showBackLink={false} showShareButton={false} />
  <SharedViewEndCTA variant="sample" />
{/if}
