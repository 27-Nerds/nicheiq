<script lang="ts">
  import type { AudienceSegment } from "$lib/types/publicCatalog.js";

  interface Props {
    segment: AudienceSegment;
  }

  let { segment }: Props = $props();
</script>

<article class="seg">
  {#if segment.sizeLabel}
    <span class="lbl">{segment.sizeLabel}</span>
  {/if}
  <h4>{segment.name}</h4>
  {#if segment.bullets.length > 0}
    <ul>
      {#each segment.bullets as it}
        <li>{it}</li>
      {/each}
    </ul>
  {/if}
  {#if segment.expertiseLevel || segment.budgetSensitivity}
    <div class="seg-meta">
      {#if segment.expertiseLevel}<span>{segment.expertiseLevel}</span>{/if}
      {#if segment.expertiseLevel && segment.budgetSensitivity}<span class="dot">·</span>{/if}
      {#if segment.budgetSensitivity}<span>{segment.budgetSensitivity} budget</span>{/if}
    </div>
  {/if}
</article>

<style>
  .seg {
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lbl {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-accent);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  h4 {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.3;
    color: var(--color-text-primary);
    margin: 0;
  }
  /* Real list markers (not ::before pseudo-elements) so screen readers
     announce "list of N items" — required for a11y. ::marker colors the dot. */
  ul {
    list-style: disc;
    list-style-position: outside;
    display: grid;
    gap: 4px;
    margin: 2px 0 0;
    padding-left: 14px;
  }
  li {
    font-size: 12.5px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.45;
  }
  li::marker {
    color: var(--color-text-muted);
  }
  /* Footer meta line — expertise level + budget sensitivity. Mono so it reads
     as a quiet badge rather than another bullet. */
  .seg-meta {
    margin-top: auto;
    padding-top: 8px;
    border-top: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .seg-meta .dot {
    color: var(--color-text-muted);
    opacity: 0.6;
  }
</style>
