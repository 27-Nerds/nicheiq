<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import type { AudienceData, InfluencerProfile } from "$lib/types/discovery";

  interface Props {
    audience: AudienceData;
    influencers: InfluencerProfile[];
  }

  let { audience, influencers }: Props = $props();

  let showMore = $state(false);

  const primarySegment = $derived(
    audience.segments.find(s => s.segment_name === audience.primary_target) ?? audience.segments[0]
  );

  const secondarySegments = $derived(
    audience.segments.filter(s => s !== primarySegment)
  );

  const topInfluencers = $derived(influencers.slice(0, 3));

  function sizeVariant(size: string): "success" | "accent" | "muted" {
    if (size === "Large") return "success";
    if (size === "Medium") return "accent";
    return "muted";
  }
</script>

<section class="audience">
  <div class="section-header-meta">
    <div class="section-header-bar"></div>
    <span class="audience-label">Who Would Pay For This</span>
  </div>

  <!-- Primary target segment (detailed) -->
  {#if primarySegment}
    <div class="audience-primary">
      <div class="audience-primary-header">
        <h3 class="audience-seg-name">{primarySegment.segment_name}</h3>
        <Badge variant={sizeVariant(primarySegment.size_estimate)} size="sm">{primarySegment.size_estimate}</Badge>
        <Badge variant="accent" size="sm">Primary target</Badge>
      </div>
      <p class="audience-seg-attrs">
        {primarySegment.expertise_level} &middot; {primarySegment.budget_sensitivity} budget sensitivity &middot; {primarySegment.discovery_channels.slice(0, 3).join(", ")}
      </p>
      {#if primarySegment.motivation_drivers?.length}
        <p class="audience-seg-motiv">
          Motivated by: {primarySegment.motivation_drivers.slice(0, 2).join("; ")}
        </p>
      {/if}
    </div>
  {/if}

  <!-- Secondary segments (compact — one line each) -->
  {#if secondarySegments.length > 0}
    <div class="audience-secondary">
      {#each secondarySegments as seg (seg.segment_name)}
        <div class="audience-seg-compact">
          <span class="audience-seg-compact-name">{seg.segment_name}</span>
          <Badge variant={sizeVariant(seg.size_estimate)} size="sm">{seg.size_estimate}</Badge>
          <span class="audience-seg-compact-attrs">{seg.expertise_level} &middot; {seg.budget_sensitivity} budget sensitivity</span>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Tools currently used (gap signal) -->
  {#if audience.tools_currently_used?.length}
    <p class="audience-tools">
      Currently using: <em>{audience.tools_currently_used.join(", ")}</em>
    </p>
  {/if}

  <!-- Expandable section: influencers, hubs, vocabulary -->
  {#if showMore}
    <!-- Influencer strip -->
    {#if topInfluencers.length > 0}
      <div class="audience-influencers">
        <span class="audience-inf-label">Key voices:</span>
        {#each topInfluencers as inf, i}
          <span class="audience-inf-item">
            <strong>{inf.name}</strong> ({inf.content_focus.length > 30 ? inf.content_focus.slice(0, 27) + '...' : inf.content_focus}){#if i < topInfluencers.length - 1}<span class="audience-sep">&middot;</span>{/if}
          </span>
        {/each}
      </div>
    {/if}

    <!-- Community hubs -->
    {#if audience.community_hubs?.length}
      <div class="audience-hubs">
        {#each audience.community_hubs as hub}
          <Badge variant="muted" size="sm">{hub}</Badge>
        {/each}
      </div>
    {/if}

    <!-- Vocabulary as mono tag list (weight variation, not heatmap) -->
    {#if audience.common_vocabulary?.length}
      <div class="audience-vocab">
        {#each audience.common_vocabulary as term, i}
          <span class="audience-vocab-term" class:audience-vocab-top={i < 5}>{term}</span>
        {/each}
      </div>
    {/if}
  {/if}

  {#if topInfluencers.length > 0 || audience.community_hubs?.length || audience.common_vocabulary?.length}
    <button
      type="button"
      class="audience-expand"
      onclick={() => { showMore = !showMore; }}
    >
      {showMore ? "Show less" : "Show more intelligence \u2192"}
    </button>
  {/if}
</section>

<style>
  .audience {
    margin: var(--space-5) 0;
  }

  .audience-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  /* Primary segment */
  .audience-primary {
    margin-top: var(--space-3);
    padding: var(--space-4);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .audience-primary-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-bottom: var(--space-2);
  }

  .audience-seg-name {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .audience-seg-attrs {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: 0;
  }

  .audience-seg-motiv {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    margin: var(--space-1) 0 0;
  }

  /* Secondary segments */
  .audience-secondary {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }

  .audience-seg-compact {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .audience-seg-compact-name {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: var(--text-sm);
    color: var(--color-text-primary);
  }

  .audience-seg-compact-attrs {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  /* Tools gap signal */
  .audience-tools {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: var(--space-3) 0 0;
  }

  .audience-tools em {
    color: var(--color-text-primary);
  }

  /* Influencer strip */
  .audience-influencers {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem;
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin-top: var(--space-3);
  }

  .audience-inf-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    margin-right: var(--space-1);
  }

  .audience-inf-item strong {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .audience-sep {
    color: var(--color-text-muted);
    opacity: 0.4;
    margin: 0 0.125rem;
  }

  /* Community hubs */
  .audience-hubs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-top: var(--space-3);
  }

  /* Vocabulary tags */
  .audience-vocab {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-top: var(--space-3);
  }

  .audience-vocab-term {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 400;
    color: var(--color-text-muted);
    padding: 0.125rem var(--space-2);
    background: var(--color-bg-surface);
    border-radius: var(--radius-sm);
  }

  .audience-vocab-top {
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  /* Expand button */
  .audience-expand {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-text-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
    margin-top: var(--space-2);
    display: block;
  }

  .audience-expand:hover {
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
  }

  .audience-expand:active {
    transform: scale(0.98);
  }
</style>
