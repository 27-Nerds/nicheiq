<script lang="ts">
  import type { Report } from '$lib/types/report';
  import { ArrowRight } from 'lucide-svelte';
  import ReportContent from '$lib/components/ReportContent.svelte';

  let { data } = $props();
  const report: Report | null = $derived(data.report);
</script>

<svelte:head>
  {#if report}
    <title>{report.selected_solution_name} - Sample Report - NicheIQ</title>
    <meta name="description" content={report.executive_summary?.slice(0, 160)} />
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
  <!-- Sample report banner -->
  <div class="bg-gradient-to-r from-accent/5 to-secondary/5 border-b border-accent/10">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <p class="text-sm text-text-secondary">
        <span class="font-medium text-text-primary">Sample report</span> from NicheIQ
      </p>
      <a href="/" class="text-sm font-medium text-accent hover:text-accent/80 transition-colors flex items-center gap-1">
        Try NicheIQ <ArrowRight class="w-3.5 h-3.5" />
      </a>
    </div>
  </div>
  <ReportContent {report} showBackLink={false} showShareButton={false} />
{/if}
