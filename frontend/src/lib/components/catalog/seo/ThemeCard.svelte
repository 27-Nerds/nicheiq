<script lang="ts">
  import type { Theme } from "$lib/types/publicCatalog.js";

  interface Props {
    theme: Theme;
    /** 1-based theme index for the "Theme NN" label. Padded to 2 digits. */
    index: number;
  }

  let { theme, index }: Props = $props();

  const formattedIndex = $derived(String(index).padStart(2, "0"));
  // Normalize crew output ('High'/'Medium'/'Low') to the upper-case pill label.
  const frequencyLabel = $derived(
    theme.frequency ? theme.frequency.toUpperCase() : null,
  );
  // Right-rail chips — prefer the new explicit field; fall back to the legacy
  // `sources` alias for rows projected before the rename.
  const segmentChips = $derived(
    theme.primaryUserSegments && theme.primaryUserSegments.length > 0
      ? theme.primaryUserSegments
      : theme.sources,
  );
</script>

<article class="theme-card">
  <div class="body">
    <div class="meta-row">
      <span class="theme-label">Theme {formattedIndex}</span>
      {#if frequencyLabel}
        <span class="dot">·</span>
        <span class="frequency-pill" data-frequency={frequencyLabel.toLowerCase()}>
          {frequencyLabel}
        </span>
      {/if}
      {#if theme.mentionCount != null}
        <span class="dot">·</span>
        <span class="mentions">{theme.mentionCount.toLocaleString()} mentions</span>
      {/if}
      {#if theme.severity != null}
        <span class="dot">·</span>
        <span class="severity-num">{theme.severity}</span>
      {/if}
    </div>
    <h4>{theme.title}</h4>
    {#if theme.description}
      <p class="theme-desc">{theme.description}</p>
    {/if}
  </div>
  {#if segmentChips && segmentChips.length > 0}
    <div class="sources">
      {#each segmentChips as s}
        <span class="badge">{s}</span>
      {/each}
    </div>
  {/if}
</article>

<style>
  .theme-card {
    background: var(--color-surface, #fff);
    padding: 18px 20px;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 18px;
    align-items: flex-start;
  }
  .meta-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
    flex-wrap: wrap;
  }
  .theme-label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-accent);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .dot {
    color: var(--color-text-muted);
    font-size: 11px;
  }
  .mentions {
    font-size: 11px;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
  }
  /* Frequency pill — same mono-uppercase rhythm as the theme label, but tonally
     muted so the section header still wins focus. Color shifts subtly per tier. */
  .frequency-pill {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .frequency-pill[data-frequency="high"] {
    color: var(--color-accent);
  }
  .frequency-pill[data-frequency="low"] {
    opacity: 0.7;
  }
  .severity-num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-primary);
    font-weight: 600;
    font-feature-settings: "tnum" 1;
  }
  h4 {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.35;
    margin: 0 0 6px;
    color: var(--color-text-primary);
  }
  /* Theme definition prose — matches the audience segment bullet typography. */
  .theme-desc {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.55;
    margin: 4px 0 0;
    max-width: 680px;
  }
  .sources {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    justify-content: flex-end;
    max-width: 200px;
  }
  .badge {
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
  }
</style>
