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
  data-cols={stats.length}
>
  {#each stats as s, i}
    <div
      class="stat catalog-fade-in"
      style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
    >
      <div class="n tone-{s.tone ?? 'default'}">{s.value}</div>
      <div class="l">{s.label}</div>
    </div>
  {/each}
</div>

<style>
  .stat-strip {
    display: grid;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-bg-elevated);
    overflow: hidden;
  }
  .stat-strip[data-cols="2"] {
    grid-template-columns: repeat(2, 1fr);
  }
  .stat-strip[data-cols="3"] {
    grid-template-columns: repeat(3, 1fr);
  }
  .stat-strip[data-cols="4"] {
    grid-template-columns: repeat(4, 1fr);
  }
  .stat-strip[data-cols="5"] {
    grid-template-columns: repeat(5, 1fr);
  }
  /* Emphasis: first column gets 1.4fr, alt bg, larger numeric. */
  .stat-strip.emphasis[data-cols="2"] {
    grid-template-columns: 1.4fr 1fr;
  }
  .stat-strip.emphasis[data-cols="3"] {
    grid-template-columns: 1.4fr 1fr 1fr;
  }
  .stat-strip.emphasis[data-cols="4"] {
    grid-template-columns: 1.4fr 1fr 1fr 1fr;
  }
  .stat-strip.emphasis[data-cols="5"] {
    grid-template-columns: 1.4fr 1fr 1fr 1fr 1fr;
  }
  /* First-tile tint: page-bg color (#FAFAFA) against the white container
     produces the subtle ~2% contrast the mock relies on. The previous token
     `--color-bg-elevated` resolves to white — identical to the container —
     so no tint was visible. */
  .stat-strip.emphasis .stat:first-child {
    background: var(--color-bg-base);
  }
  .stat-strip.emphasis .stat:first-child .n {
    font-size: 28px;
  }
  .stat {
    padding: 18px 22px;
    border-right: 1px solid var(--color-border);
  }
  .stat:last-child {
    border-right: none;
  }
  /* Mono numerals — JetBrains Mono via --font-mono — give the strip its
     "almanac" voice. tabular-nums guarantees lining figures align between
     tiles regardless of digit shape. */
  .n {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1;
    margin-bottom: 6px;
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
  /* Labels use the catalog's mono kicker scale (10px / 0.08em / 600) so the
     strip rhymes with `.nc-kicker`, `.theme-num`, and the section dividers. */
  .l {
    font-size: 10px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
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
