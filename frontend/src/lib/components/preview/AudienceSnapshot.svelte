<script lang="ts">
  import type { AudienceMapping } from "$lib/types/report";

  interface Props {
    data: AudienceMapping;
  }

  let { data }: Props = $props();

  let showAllSegments = $state(false);

  const segments = $derived(
    showAllSegments
      ? (data.audience_segments ?? [])
      : (data.audience_segments?.slice(0, 3) ?? []),
  );
  const communities = $derived(data.community_hubs?.slice(0, 6) ?? []);
  const vocabulary = $derived(data.common_vocabulary?.slice(0, 6) ?? []);
  const totalSegments = $derived(data.audience_segments?.length ?? 0);
  const hiddenSegmentCount = $derived(Math.max(0, totalSegments - segments.length));
  const hiddenCommunityCount = $derived(
    Math.max(0, (data.community_hubs?.length ?? 0) - communities.length),
  );
  const hiddenVocabularyCount = $derived(
    Math.max(0, (data.common_vocabulary?.length ?? 0) - vocabulary.length),
  );
  const primarySegment = $derived(
    data.primary_target_segment || segments[0]?.segment_name || "Audience segments",
  );
</script>

<div class="audience-snapshot">
  <div class="audience-snapshot__hero">
    <div>
      <p class="audience-snapshot__eyebrow">Primary audience</p>
      <h3>{primarySegment}</h3>
      {#if data.segment_prioritization_rationale}
        <p>{data.segment_prioritization_rationale}</p>
      {:else}
        <p>Segments with the clearest pain concentration and discovery signal from the research run.</p>
      {/if}
    </div>

    <dl class="audience-snapshot__stats" aria-label="Audience summary">
      <div>
        <dt>Segments</dt>
        <dd>{data.audience_segments?.length ?? 0}</dd>
      </div>
      <div>
        <dt>Communities</dt>
        <dd>{data.community_hubs?.length ?? 0}</dd>
      </div>
      <div>
        <dt>Signals</dt>
        <dd>{(data.messaging_frameworks?.length ?? 0) + (data.common_vocabulary?.length ?? 0)}</dd>
      </div>
    </dl>
  </div>

  {#if segments.length > 0}
    <div class="audience-snapshot__segments">
      {#each segments as segment, i}
        <article class="audience-segment" class:audience-segment--primary={i === 0}>
          <div class="audience-segment__top">
            <span class="audience-segment__rank">{String(i + 1).padStart(2, "0")}</span>
            {#if segment.size_estimate}
              <span class="audience-segment__size">{segment.size_estimate}</span>
            {/if}
          </div>
          <h4 title={segment.segment_name}>{segment.segment_name}</h4>
          {#if segment.pain_point_alignment?.length}
            <p>{segment.pain_point_alignment.slice(0, 2).join(" · ")}</p>
          {/if}
          <div class="audience-segment__meta">
            {#if segment.expertise_level}
              <span class="audience-segment__stat">
                <span class="audience-segment__stat-key">Expertise</span>
                {segment.expertise_level}
              </span>
            {/if}
            {#if segment.budget_sensitivity}
              <span class="audience-segment__stat">
                <span class="audience-segment__stat-key">Price sensitivity</span>
                {segment.budget_sensitivity}
              </span>
            {/if}
          </div>
        </article>
      {/each}
    </div>
    {#if totalSegments > 3}
      <div class="audience-snapshot__disclosure">
        <p class="audience-snapshot__truncation">
          {#if hiddenSegmentCount > 0}
            Showing the first {segments.length} of {totalSegments} captured segments.
          {:else}
            Showing all {totalSegments} captured segments.
          {/if}
        </p>
        <button
          type="button"
          class="audience-snapshot__toggle"
          aria-expanded={showAllSegments}
          onclick={() => (showAllSegments = !showAllSegments)}
        >
          {showAllSegments ? "Show fewer" : `Show all ${totalSegments} segments`}
        </button>
      </div>
    {/if}
  {:else}
    <p class="audience-snapshot__empty">
      No audience segments were captured in this report.
    </p>
  {/if}

  {#if communities.length > 0 || vocabulary.length > 0}
    <div class="audience-snapshot__signal-row">
      {#if communities.length > 0}
        <div class="audience-signal-group">
          <span class="audience-signal-label">Where they gather</span>
          <div class="audience-signal-tags">
            {#each communities as hub}
              <span title={hub}>{hub}</span>
            {/each}
            {#if hiddenCommunityCount > 0}<span>+{hiddenCommunityCount} more</span>{/if}
          </div>
        </div>
      {/if}
      {#if vocabulary.length > 0}
        <div class="audience-signal-group">
          <span class="audience-signal-label">Language</span>
          <div class="audience-signal-tags">
            {#each vocabulary as term}
              <span title={term}>{term}</span>
            {/each}
            {#if hiddenVocabularyCount > 0}<span>+{hiddenVocabularyCount} more</span>{/if}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .audience-snapshot {
    display: grid;
    gap: var(--space-4);
  }

  .audience-snapshot__hero {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-4);
    align-items: start;
    padding-bottom: var(--space-3);
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
  }

  .audience-snapshot__eyebrow,
  .audience-signal-label {
    display: block;
    margin: 0 0 var(--space-1);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.07em;
    line-height: 1;
    text-transform: uppercase;
  }

  .audience-snapshot h3 {
    max-width: 46ch;
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: 800;
    letter-spacing: -0.012em;
    line-height: 1.18;
    text-wrap: balance;
  }

  .audience-snapshot__hero p {
    max-width: 74ch;
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
    text-wrap: pretty;
  }

  .audience-snapshot__stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(3.8rem, 1fr));
    gap: 0;
    min-width: 16rem;
    overflow: hidden;
    margin: 0;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-bg-surface) 70%, var(--color-bg-elevated));
  }

  .audience-snapshot__stats div {
    padding: var(--space-2) var(--space-3);
    border-right: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
  }

  .audience-snapshot__stats div:last-child {
    border-right: 0;
  }

  .audience-snapshot__stats dt {
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    font-weight: 700;
    line-height: 1;
  }

  .audience-snapshot__stats dd {
    margin: var(--space-1) 0 0;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-md);
    font-weight: 800;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }

  .audience-snapshot__segments {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-2);
  }

  .audience-segment {
    min-width: 0;
    padding: var(--space-3);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 36%, transparent);
    border-radius: var(--radius-md);
    background:
      color-mix(in srgb, var(--color-bg-elevated) 84%, var(--color-bg-surface));
  }

  .audience-segment--primary {
    border-color: color-mix(in srgb, var(--color-accent) 30%, var(--color-border));
    background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-elevated));
  }

  .audience-segment__top,
  .audience-segment__meta,
  .audience-snapshot__signal-row,
  .audience-signal-tags {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
  }

  .audience-segment__top {
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .audience-segment__rank {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
  }

  .audience-segment__size {
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: 700;
  }

  .audience-segment h4 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-13);
    font-weight: 800;
    line-height: 1.22;
    text-wrap: balance;
    overflow-wrap: anywhere;
  }

  .audience-segment p {
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-11);
    line-height: 1.43;
    text-wrap: pretty;
  }

  .audience-segment__meta {
    gap: var(--space-2) var(--space-4);
    margin-top: var(--space-2);
    padding-top: var(--space-2);
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 22%, transparent);
  }

  .audience-segment__stat {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    color: var(--color-text-secondary);
    font-size: var(--text-11);
    font-weight: 700;
    line-height: 1.05;
  }

  .audience-segment__stat-key {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.07em;
    line-height: 1;
    text-transform: uppercase;
  }

  .audience-signal-tags span {
    max-width: 100%;
    padding: var(--space-1) var(--space-2);
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
    border-radius: var(--radius-full);
    color: var(--color-text-muted);
    background: color-mix(in srgb, var(--color-bg-surface) 76%, var(--color-bg-elevated));
    font-size: var(--text-xs);
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .audience-snapshot__signal-row {
    gap: var(--space-3) var(--space-5);
    padding-top: var(--space-1);
  }

  .audience-signal-group {
    min-width: min(100%, 18rem);
  }

  .audience-signal-tags {
    gap: var(--space-2);
  }

  .audience-snapshot__disclosure {
    display: flex;
    align-items: baseline;
    gap: var(--space-1) var(--space-3);
    flex-wrap: wrap;
  }

  .audience-snapshot__toggle {
    margin: 0;
    padding: 0;
    border: 0;
    background: none;
    cursor: pointer;
    color: var(--color-accent-dark);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 600;
    line-height: var(--leading-normal);
  }

  .audience-snapshot__toggle:hover {
    text-decoration: underline;
  }

  .audience-snapshot__toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .audience-snapshot__truncation,
  .audience-snapshot__empty {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }

  .audience-snapshot__empty {
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  @media (max-width: 860px) {
    .audience-snapshot__hero {
      grid-template-columns: minmax(0, 1fr);
    }

    .audience-snapshot__stats {
      min-width: 0;
      width: 100%;
    }

    .audience-snapshot__segments {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
