<script lang="ts">
  import type {
    AudienceSegment,
    AudienceSignals,
  } from "$lib/types/publicCatalog.js";
  import AudienceSegmentCard from "./AudienceSegmentCard.svelte";
  import AudienceSignalsSection from "./AudienceSignalsSection.svelte";
  import CatalogBand from "./CatalogBand.svelte";
  import Chip from "./Chip.svelte";

  // Unified Audience-section body. Renders three optional sub-blocks in order:
  //   1. Type-chip strip (categorical tags, pain-page only)
  //   2. Segments band — bordered CatalogBand containing 2- or 3-col grid of
  //      <AudienceSegmentCard> with a small staggered fade-in animation
  //   3. AudienceSignalsSection compact card (dashed-row chip grid)
  //
  // Caller renders the surrounding <SectionDivider> + any anchor wrapper.
  // Caller handles all segment filtering (target_personas, affected_segments,
  // or full set for parent pages) and passes the already-filtered array.

  interface Props {
    /** Pre-filtered segment list. Empty = segments band hidden. */
    segments?: AudienceSegment[];
    /** Audience signals payload. Null/undefined = signals card hidden. */
    signals?: AudienceSignals | null;
    /** Number of columns for the segments band. 3 on idea + pain pages,
     *  2 on sub-niche page (denser layout). */
    segmentColumns?: 2 | 3;
    /** Show per-card source attribution chip — only set true on parent
     *  routes that aggregate segments from multiple sub-niches. */
    showSegmentSource?: boolean;
    /** Optional category chip strip rendered above segments. Used by the
     *  pain page to surface taxonomic tags ("Type") for the pain point. */
    categories?: string[];
  }

  let {
    segments = [],
    signals = null,
    segmentColumns = 3,
    showSegmentSource = false,
    categories = [],
  }: Props = $props();

  const hasCategories = $derived(categories.length > 0);
  const hasSegments = $derived(segments.length > 0);
  const hasSignals = $derived.by(() => {
    if (!signals) return false;
    return (
      (signals.vocabulary?.length ?? 0) > 0 ||
      (signals.frustrations?.length ?? 0) > 0 ||
      (signals.currentTools?.length ?? 0) > 0 ||
      (signals.communityHubs?.length ?? 0) > 0 ||
      (signals.recommendedChannels?.length ?? 0) > 0 ||
      (signals.messagingFrameworks?.length ?? 0) > 0 ||
      !!signals.contentPreferences ||
      !!signals.earlyAdopterTactics
    );
  });
</script>

{#if hasCategories}
  <div class="type-strip">
    <span class="type-label">Type</span>
    <div class="type-chips">
      {#each categories as c}<Chip label={c} />{/each}
    </div>
  </div>
{/if}

{#if hasSegments}
  <CatalogBand>
    <div class="seg-grid" data-columns={segmentColumns}>
      {#each segments as s, i (s.name ?? i)}
        <div
          class="catalog-fade-in"
          style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
        >
          <AudienceSegmentCard segment={s} showSource={showSegmentSource} />
        </div>
      {/each}
    </div>
  </CatalogBand>
{/if}

{#if hasSignals && signals}
  <div class="signals-wrap">
    <AudienceSignalsSection {signals} compact />
  </div>
{/if}

<style>
  .type-strip {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
    margin: 0 0 16px;
  }
  .type-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-accent-muted);
    flex-shrink: 0;
  }
  .type-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .seg-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }
  .seg-grid[data-columns="2"] {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  /* Edge cases (formerly pain-page-only): single segment renders narrow +
     centered; two segments render 2-col. Preserves prior :has() behavior. */
  .seg-grid:has(> :only-child) {
    grid-template-columns: 1fr;
    max-width: 600px;
  }
  .seg-grid:has(> :nth-child(2):last-child) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    max-width: 920px;
  }
  @media (max-width: 768px) {
    .seg-grid,
    .seg-grid[data-columns="2"] {
      grid-template-columns: 1fr;
    }
  }

  .signals-wrap {
    margin-top: 8px;
    margin-bottom: 32px;
  }
</style>
