<script lang="ts">
  // 4-column bordered stat strip used on index/category/idea hero blocks.
  // Tone optionally tints the number color (e.g., "go" green for GO count).
  // `emphasis` widens the first tile (1.4fr vs 1fr) and gives it an alt
  // background — matches the catalog v2 mock pattern where the totals anchor
  // gets primary visual weight.

  type Tone = "default" | "go" | "amber" | "info";

  export interface Stat {
    value: string | number;
    label: string;
    tone?: Tone;
  }

  interface Props {
    stats: Stat[];
    emphasis?: boolean;
  }

  let { stats, emphasis = false }: Props = $props();
</script>

<div
  class="stat-strip"
  class:emphasis
  style="--cols: {stats.length};"
>
  {#each stats as s}
    <div class="stat">
      <div class="n tone-{s.tone ?? 'default'}">{s.value}</div>
      <div class="l">{s.label}</div>
    </div>
  {/each}
</div>

<style>
  .stat-strip {
    display: grid;
    grid-template-columns: repeat(var(--cols, 4), 1fr);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    overflow: hidden;
  }
  /* Emphasis: first column gets 1.4fr, alt bg, larger numeric. */
  .stat-strip.emphasis {
    grid-template-columns: 1.4fr repeat(calc(var(--cols, 4) - 1), 1fr);
  }
  .stat-strip.emphasis .stat:first-child {
    background: var(--color-bg-elevated, #fafafa);
  }
  .stat-strip.emphasis .stat:first-child .n {
    font-size: 28px;
  }
  .stat {
    padding: 16px 20px;
    border-right: 1px solid var(--color-border);
  }
  .stat:last-child {
    border-right: none;
  }
  .n {
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1;
    margin-bottom: 4px;
    color: var(--color-text-primary);
  }
  .tone-go {
    color: var(--color-success);
  }
  .tone-amber {
    color: var(--color-accent);
  }
  .tone-info {
    color: var(--color-info);
  }
  .l {
    font-size: 11px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
  }

  @media (max-width: 900px) {
    .stat-strip {
      grid-template-columns: repeat(2, 1fr);
    }
    .stat:nth-child(2n) {
      border-right: none;
    }
    .stat:nth-child(n + 3) {
      border-top: 1px solid var(--color-border);
    }
  }
</style>
