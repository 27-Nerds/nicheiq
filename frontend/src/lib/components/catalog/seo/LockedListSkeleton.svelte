<script lang="ts">
  // Content-free, blurred placeholders for the locked tail of a teaser list.
  // Renders NO real or fake text — only shaped bars — so there is nothing to
  // reveal in DevTools and nothing for crawlers to index. The real data for
  // these positions is stripped server-side in the loader; this is purely the
  // cosmetic "there's more behind the wall" affordance.
  //
  // Emits a flat sequence of card/row elements (no wrapper) so the parent can
  // place them inside its own grid (`idea`) or list block (`pain`).

  interface Props {
    /** How many items are locked (the rendered count is capped by `max`). */
    count: number;
    variant: 'idea' | 'pain';
    /** Cap on rendered placeholders so a huge niche doesn't draw 100 bars. */
    max?: number;
  }

  let { count, variant, max = 5 }: Props = $props();

  const items = $derived(
    Array.from({ length: Math.max(0, Math.min(count, max)) }, (_, i) => i),
  );
</script>

{#each items as i (i)}
  {#if variant === 'idea'}
    <div class="sk sk-card" aria-hidden="true">
      <span class="sk-bar sk-meta"></span>
      <span class="sk-bar sk-title"></span>
      <span class="sk-bar sk-line"></span>
      <span class="sk-bar sk-line sk-short"></span>
      <div class="sk-foot">
        <span class="sk-chip"></span>
        <span class="sk-chip"></span>
      </div>
    </div>
  {:else}
    <div class="sk sk-row" aria-hidden="true">
      <span class="sk-bar sk-rank"></span>
      <span class="sk-bar sk-rowtitle"></span>
      <span class="sk-bar sk-num"></span>
      <span class="sk-bar sk-sev"></span>
    </div>
  {/if}
{/each}

<style>
  /* Cosmetic blur only — these elements carry no data (see component comment). */
  .sk {
    filter: blur(5px);
    opacity: 0.5;
    user-select: none;
    pointer-events: none;
  }
  .sk-bar {
    display: block;
    height: 12px;
    border-radius: 4px;
    background: var(--color-border);
  }

  /* idea — mirrors IdeaCardV2's box */
  .sk-card {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface);
  }
  .sk-meta {
    width: 38%;
    height: 8px;
  }
  .sk-title {
    width: 70%;
    height: 16px;
  }
  .sk-line {
    width: 100%;
  }
  .sk-short {
    width: 60%;
  }
  .sk-foot {
    display: flex;
    gap: 6px;
    margin-top: 4px;
    padding-top: 12px;
    border-top: 1px solid var(--color-border);
  }
  .sk-chip {
    display: block;
    width: 56px;
    height: 18px;
    border-radius: 999px;
    background: var(--color-border);
  }

  /* pain — mirrors a PainPointRankTable row (CatalogTable padding: 18px 20px) */
  .sk-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 18px 20px;
    border-bottom: 1px solid var(--color-border);
  }
  .sk-row:last-child {
    border-bottom: none;
  }
  .sk-rank {
    flex: none;
    width: 20px;
  }
  .sk-rowtitle {
    flex: 1;
    height: 14px;
  }
  .sk-num {
    flex: none;
    width: 48px;
  }
  .sk-sev {
    flex: none;
    width: 80px;
  }
</style>
