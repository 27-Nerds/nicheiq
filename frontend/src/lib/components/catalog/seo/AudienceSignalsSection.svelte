<script lang="ts">
  import type { AudienceSignals } from "$lib/types/publicCatalog.js";
  import Chip from "./Chip.svelte";

  // Hairline-divided rows rendering all 8 fields of the AudienceSignals
  // payload. 2-col grid on ≥768px so chip rows pair side-by-side; bullet/prose
  // rows span both columns. Rows render only when their data is present;
  // the section hides entirely if every field is empty.

  interface Props {
    signals: AudienceSignals;
    /** Compact mode: lighter chrome, muted (non-accent) labels, tighter
     *  padding. Used on consumer pages where the section sits next to other
     *  bordered content (e.g. /idea/[slug]) and the dense bordered grid would
     *  read as a control panel. Sub-niche page leaves this false (the section
     *  IS the page meat there). */
    compact?: boolean;
  }

  let { signals, compact = false }: Props = $props();

  const hasTools = $derived(signals.currentTools.length > 0);
  const hasFrustrations = $derived(signals.frustrations.length > 0);
  const hasVocabulary = $derived(signals.vocabulary.length > 0);
  const hasCommunityHubs = $derived(signals.communityHubs.length > 0);
  const hasRecommendedChannels = $derived(signals.recommendedChannels.length > 0);
  const hasMessagingFrameworks = $derived(signals.messagingFrameworks.length > 0);
  const hasContentPreferences = $derived(
    !!signals.contentPreferences && signals.contentPreferences.trim().length > 0,
  );
  const hasEarlyAdopterTactics = $derived(
    !!signals.earlyAdopterTactics && signals.earlyAdopterTactics.trim().length > 0,
  );
  const hasAny = $derived(
    hasTools ||
      hasFrustrations ||
      hasVocabulary ||
      hasCommunityHubs ||
      hasRecommendedChannels ||
      hasMessagingFrameworks ||
      hasContentPreferences ||
      hasEarlyAdopterTactics,
  );
</script>

{#if hasAny}
  <div class="signals-list" class:compact>
    {#if compact}
      <div class="signals-deck">
        <span class="signals-deck-badge">Audience signals</span>
        <p class="signals-deck-text">
          What this audience uses, where they are, and how to talk to them — pulled from the source research.
        </p>
      </div>
    {/if}
    {#if hasTools}
      <div class="row half">
        <div class="row-head">
          <span class="row-label">Tools they use today</span>
          <span class="row-count">{signals.currentTools.length}</span>
        </div>
        <div class="chips">
          {#each signals.currentTools as t}
            <Chip label={t} />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasCommunityHubs}
      <div class="row half">
        <div class="row-head">
          <span class="row-label">Where they gather</span>
          <span class="row-count">{signals.communityHubs.length}</span>
        </div>
        <div class="chips">
          {#each signals.communityHubs as c}
            <Chip label={c} />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasVocabulary}
      <div class="row half">
        <div class="row-head">
          <span class="row-label">How they describe it</span>
          <span class="row-count">{signals.vocabulary.length}</span>
        </div>
        <div class="chips vocab">
          {#each signals.vocabulary as v}
            <Chip label={v} mono />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasRecommendedChannels}
      <div class="row half">
        <div class="row-head">
          <span class="row-label">Where to reach them</span>
          <span class="row-count">{signals.recommendedChannels.length}</span>
        </div>
        <div class="chips">
          {#each signals.recommendedChannels as c}
            <Chip label={c} />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasFrustrations}
      <div class="row full">
        <div class="row-head">
          <span class="row-label">Frustrations with current tools</span>
          <span class="row-count">{signals.frustrations.length}</span>
        </div>
        <ul class="bullets">
          {#each signals.frustrations as f}
            <li>{f}</li>
          {/each}
        </ul>
      </div>
    {/if}
    {#if hasMessagingFrameworks}
      <div class="row full">
        <div class="row-head">
          <span class="row-label">Messaging that resonates</span>
          <span class="row-count">{signals.messagingFrameworks.length}</span>
        </div>
        <ul class="bullets">
          {#each signals.messagingFrameworks as m}
            <li>{m}</li>
          {/each}
        </ul>
      </div>
    {/if}
    {#if hasContentPreferences}
      <div class="row full">
        <div class="row-head">
          <span class="row-label">Content they value</span>
        </div>
        <p class="prose">{signals.contentPreferences}</p>
      </div>
    {/if}
    {#if hasEarlyAdopterTactics}
      <div class="row full">
        <div class="row-head">
          <span class="row-label">Early-adopter tactics</span>
        </div>
        <p class="prose">{signals.earlyAdopterTactics}</p>
      </div>
    {/if}
  </div>
{/if}

<style>
  /* DEFAULT — sub-niche page idiom. 2-col grid with 1px-gap-on-border-bg
     trick so each row reads as a tile in a control panel. Accent-colored
     mono labels work because the section IS the focal block on that page. */
  .signals-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1px;
    background: var(--color-border);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }
  @media (max-width: 768px) {
    .signals-list {
      grid-template-columns: 1fr;
    }
  }
  .row {
    background: var(--color-surface, #fff);
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .row.full {
    grid-column: 1 / -1;
  }
  .row-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .row-label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-accent-muted);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .row-count {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-feature-settings: "tnum" 1;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .bullets {
    list-style: disc;
    list-style-position: outside;
    margin: 0;
    padding-left: 18px;
    display: grid;
    gap: 4px;
  }
  .bullets li {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
  }
  .bullets li::marker {
    color: var(--color-text-muted);
  }
  .prose {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    margin: 0;
    max-width: 780px;
  }

  /* COMPACT — consumer-page idiom (e.g. /idea/[slug]). Editorial cadence,
     not control-panel. Single hairline-bordered container with internal
     hairline dividers. Muted (non-accent) mono labels so 8 repetitions
     don't oversaturate the page's accent color. The deck-note intro strip
     frames the block as supplementary research notes, not a primary panel.

     Layout: CSS grid 2-col on desktop. Deck and prose rows span both
     columns (grid-column: 1 / -1); chip rows take their natural slot. */
  .signals-list.compact {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0;
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }
  @media (max-width: 768px) {
    .signals-list.compact {
      grid-template-columns: 1fr;
    }
  }
  .signals-list.compact > .signals-deck {
    grid-column: 1 / -1;
    padding: 14px 20px 12px;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-elevated, #fff);
  }
  .signals-list.compact > .signals-deck .signals-deck-badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
    border-radius: 3px;
    padding: 2px 8px;
    margin-bottom: 8px;
    background: var(--color-bg-base, #fafafa);
    white-space: nowrap;
  }
  .signals-list.compact > .signals-deck .signals-deck-text {
    margin: 0;
    font-style: italic;
    font-size: 13px;
    line-height: 1.6;
    color: var(--color-text-muted);
    max-width: 780px;
  }
  .signals-list.compact > .row {
    background: var(--color-surface, #fff);
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid var(--color-border);
  }
  .signals-list.compact > .row.full {
    grid-column: 1 / -1;
  }
  /* Vertical hairline between paired half rows on desktop. The right column
     (odd-position half rows in 2-col grid) gets a left-border to create the
     central divider, except for the first half row in each row-pair. */
  @media (min-width: 768px) {
    .signals-list.compact > .row.half:nth-of-type(odd) + .row.half {
      border-left: 1px solid var(--color-border);
    }
  }
  .signals-list.compact .row-label {
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    font-size: 10px;
  }
  .signals-list.compact .row-count {
    font-size: 10px;
  }
  .signals-list.compact .bullets li,
  .signals-list.compact .prose {
    font-size: 12.5px;
    line-height: 1.55;
  }
</style>
