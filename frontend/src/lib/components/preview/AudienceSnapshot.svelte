<script lang="ts">
  import type { AudienceMapping } from "$lib/types/report";

  interface Props {
    data: AudienceMapping;
  }

  let { data }: Props = $props();

  const segments = $derived(data.audience_segments?.slice(0, 3) ?? []);
  const communities = $derived(data.community_hubs?.slice(0, 6) ?? []);
  const vocabulary = $derived(data.common_vocabulary?.slice(0, 6) ?? []);
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
          <h4>{segment.segment_name}</h4>
          {#if segment.pain_point_alignment?.length}
            <p>{segment.pain_point_alignment.slice(0, 2).join(" · ")}</p>
          {/if}
          <div class="audience-segment__meta">
            {#if segment.expertise_level}
              <span>{segment.expertise_level}</span>
            {/if}
            {#if segment.budget_sensitivity}
              <span>{segment.budget_sensitivity}</span>
            {/if}
          </div>
        </article>
      {/each}
    </div>
  {/if}

  {#if communities.length > 0 || vocabulary.length > 0}
    <div class="audience-snapshot__signal-row">
      {#if communities.length > 0}
        <div class="audience-signal-group">
          <span class="audience-signal-label">Where they gather</span>
          <div class="audience-signal-tags">
            {#each communities as hub}
              <span>{hub}</span>
            {/each}
          </div>
        </div>
      {/if}
      {#if vocabulary.length > 0}
        <div class="audience-signal-group">
          <span class="audience-signal-label">Language</span>
          <div class="audience-signal-tags">
            {#each vocabulary as term}
              <span>{term}</span>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .audience-snapshot {
    display: grid;
    gap: 0.86rem;
  }

  .audience-snapshot__hero {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: start;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
  }

  .audience-snapshot__eyebrow,
  .audience-signal-label {
    display: block;
    margin: 0 0 0.28rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.58rem;
    font-weight: 760;
    letter-spacing: 0.06em;
    line-height: 1;
    text-transform: uppercase;
  }

  .audience-snapshot h3 {
    max-width: 46ch;
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 780;
    letter-spacing: -0.012em;
    line-height: 1.18;
    text-wrap: balance;
  }

  .audience-snapshot__hero p {
    max-width: 74ch;
    margin: 0.34rem 0 0;
    color: var(--color-text-secondary);
    font-size: 0.78rem;
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
    border-radius: 0.62rem;
    background: color-mix(in srgb, var(--color-bg-surface) 70%, white);
  }

  .audience-snapshot__stats div {
    padding: 0.54rem 0.62rem;
    border-right: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
  }

  .audience-snapshot__stats div:last-child {
    border-right: 0;
  }

  .audience-snapshot__stats dt {
    color: var(--color-text-muted);
    font-size: 0.56rem;
    font-weight: 720;
    line-height: 1;
  }

  .audience-snapshot__stats dd {
    margin: 0.18rem 0 0;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 0.92rem;
    font-weight: 820;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }

  .audience-snapshot__segments {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.5rem;
  }

  .audience-segment {
    min-width: 0;
    padding: 0.7rem 0.72rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 36%, transparent);
    border-radius: 0.62rem;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0.22)),
      color-mix(in srgb, var(--color-bg-elevated) 84%, var(--color-bg-surface));
  }

  .audience-segment--primary {
    border-color: color-mix(in srgb, var(--color-accent) 30%, var(--color-border));
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--color-accent) 5%, transparent), transparent 62%),
      color-mix(in srgb, var(--color-bg-elevated) 90%, var(--color-bg-surface));
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
    gap: 0.4rem;
    margin-bottom: 0.42rem;
  }

  .audience-segment__rank {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.58rem;
    font-weight: 820;
  }

  .audience-segment__size {
    color: var(--color-text-secondary);
    font-size: 0.58rem;
    font-weight: 680;
  }

  .audience-segment h4 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: 0.82rem;
    font-weight: 760;
    line-height: 1.22;
    text-wrap: balance;
  }

  .audience-segment p {
    margin: 0.34rem 0 0;
    color: var(--color-text-secondary);
    font-size: 0.68rem;
    line-height: 1.43;
    text-wrap: pretty;
  }

  .audience-segment__meta {
    gap: 0.28rem;
    margin-top: 0.5rem;
  }

  .audience-segment__meta span,
  .audience-signal-tags span {
    max-width: 100%;
    padding: 0.16rem 0.42rem;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
    border-radius: 999px;
    color: var(--color-text-muted);
    background: color-mix(in srgb, var(--color-bg-surface) 76%, white);
    font-size: 0.58rem;
    font-weight: 620;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .audience-snapshot__signal-row {
    gap: 0.76rem 1.2rem;
    padding-top: 0.04rem;
  }

  .audience-signal-group {
    min-width: min(100%, 18rem);
  }

  .audience-signal-tags {
    gap: 0.32rem;
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
