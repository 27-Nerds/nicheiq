<script lang="ts">
  import type { AudienceSignals } from "$lib/types/publicCatalog.js";
  import Chip from "./Chip.svelte";

  // Hairline-divided rows rendering all 8 fields of the AudienceSignals
  // payload. 2-col grid on ≥768px so chip rows pair side-by-side; bullet/prose
  // rows span both columns. Rows render only when their data is present;
  // the section hides entirely if every field is empty.

  interface Props {
    signals: AudienceSignals;
  }

  let { signals }: Props = $props();

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
  <div class="signals-list">
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
  /* 2-col grid on ≥768px. Chip rows (.half) take one column each; bullet and
     prose rows (.full) span both. Hairline borders match the .themes-list
     visual rhythm — 1px gap on a border-coloured background. */
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
</style>
