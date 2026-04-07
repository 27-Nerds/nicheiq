<script lang="ts">
  import { CheckCircle } from "lucide-svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";

  interface Props {
    nicheName: string;
    nicheDescription?: string;
    discussionCount: number;
    painPointCount: number;
    solutionCount: number;
    segmentCount: number;
  }

  let {
    nicheName,
    nicheDescription,
    discussionCount,
    painPointCount,
    solutionCount,
    segmentCount,
  }: Props = $props();
</script>

<div class="overview">
  {#if nicheDescription}
    <p class="overview-summary">{nicheDescription}</p>
  {/if}

  <HeroStrip>
    {#snippet primary()}
      <HeroPrimary icon={CheckCircle} label="Discovery" sublabel="Complete" color="success" />
    {/snippet}
    <HeroMetric value={discussionCount} label="Posts analyzed" color="neutral" />
    <HeroMetric value={painPointCount} label="Pain points" color="accent" />
    <HeroMetric value={solutionCount} label="Opportunities" color="success" />
    <HeroMetric value={segmentCount} label="Segments" color="neutral" />
  </HeroStrip>

</div>

<style>
  .overview {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .overview-summary {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.65;
    max-width: 640px;
  }

</style>
