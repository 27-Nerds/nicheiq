<script lang="ts">
  import type { AudienceSignals } from "$lib/types/publicCatalog.js";

  // Phase 5.5 — three hairline-divided rows under "Audience signals" section
  // header. Reuses the same visual primitives as the theme list (1px gap on a
  // border-coloured background) so it belongs to the existing rhythm.
  //
  // Rows render only when their data is present — section hides entirely if
  // all three are empty.

  interface Props {
    signals: AudienceSignals;
  }

  let { signals }: Props = $props();

  const hasTools = $derived(signals.currentTools.length > 0);
  const hasFrustrations = $derived(signals.frustrations.length > 0);
  const hasVocabulary = $derived(signals.vocabulary.length > 0);
  const hasAny = $derived(hasTools || hasFrustrations || hasVocabulary);
</script>

{#if hasAny}
  <div class="signals-list">
    {#if hasTools}
      <div class="row">
        <div class="row-head">
          <span class="row-label">Tools they use today</span>
          <span class="row-count">{signals.currentTools.length}</span>
        </div>
        <div class="chips">
          {#each signals.currentTools as t}
            <span class="badge">{t}</span>
          {/each}
        </div>
      </div>
    {/if}
    {#if hasFrustrations}
      <div class="row">
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
    {#if hasVocabulary}
      <div class="row">
        <div class="row-head">
          <span class="row-label">How they describe it</span>
          <span class="row-count">{signals.vocabulary.length}</span>
        </div>
        <div class="chips vocab">
          {#each signals.vocabulary as v}
            <span class="badge mono">{v}</span>
          {/each}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  /* Match the .themes-list visual rhythm: hairline-divided rows inside a
     single rounded container. */
  .signals-list {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1px;
    background: var(--color-border);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }
  .row {
    background: var(--color-surface, #fff);
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
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
    color: var(--color-accent);
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
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
  }
  .badge.mono {
    font-family: var(--font-mono);
    font-size: 10.5px;
  }
  .bullets {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 4px;
  }
  .bullets li {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  .bullets li::before {
    content: "·";
    color: var(--color-text-muted);
    flex-shrink: 0;
    font-weight: 600;
  }
</style>
