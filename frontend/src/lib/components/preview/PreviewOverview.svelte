<script lang="ts">
  interface Props {
    nicheName: string;
    nicheDescription?: string;
    discussionCount: number;
    painPointCount: number;
    solutionCount: number;
    segmentCount: number;
  }

  let {
    nicheDescription,
  }: Props = $props();
</script>

<div class="overview">
  {#if nicheDescription}
    <p class="overview-summary">{nicheDescription}</p>
  {/if}
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
