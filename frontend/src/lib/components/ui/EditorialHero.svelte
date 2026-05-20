<script lang="ts">
  import type { Snippet } from "svelte";

  // Editorial page hero — mono dateline kicker + display H1 + lede, mirroring
  // the catalog CatalogIndexHero. Kicker is a structured segment list (NOT a
  // snippet) so the tone token classes stay locally scoped (no :global leak).
  // Used by settings + billing. Dashboard + /new keep their own inline heroes
  // (their CSS differs — not migrated).

  export type KickerSegment = { text: string; tone?: "accent" | "num" | "muted" };

  interface Props {
    kicker?: KickerSegment[];
    title: string;
    lede?: string;
    actions?: Snippet;
    border?: boolean;
  }

  let { kicker = [], title, lede, actions, border = true }: Props = $props();
</script>

<header class="eh" class:eh-border={border}>
  {#if kicker.length > 0}
    <p class="eh-kicker">
      {#each kicker as seg, i}
        {#if i > 0}<span class="k-dot">·</span>{/if}
        <span class="k-seg k-{seg.tone ?? 'muted'}">{seg.text}</span>
      {/each}
    </p>
  {/if}
  <div class="eh-row">
    <h1 class="eh-h1">{title}</h1>
    {#if actions}
      <div class="eh-actions">{@render actions()}</div>
    {/if}
  </div>
  {#if lede}
    <p class="eh-lede">{lede}</p>
  {/if}
</header>

<style>
  .eh {
    padding: 40px 0 28px;
    margin-bottom: 28px;
  }
  .eh-border {
    border-bottom: 1px solid var(--color-border);
  }
  .eh-kicker {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 14px;
  }
  .k-dot {
    opacity: 0.5;
  }
  .k-accent {
    color: var(--color-accent);
  }
  .k-num {
    color: var(--color-text-primary);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .k-muted {
    color: var(--color-text-muted);
  }
  .eh-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  .eh-h1 {
    font-family: var(--font-display);
    font-size: clamp(1.75rem, 4vw, 2.25rem);
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.1;
    color: var(--color-text-primary);
    margin: 0;
  }
  .eh-actions {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .eh-lede {
    font-size: 15px;
    line-height: 1.6;
    color: var(--color-text-secondary);
    margin: 12px 0 0;
    max-width: 620px;
  }
</style>
