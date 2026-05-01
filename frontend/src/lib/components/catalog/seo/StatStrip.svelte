<script lang="ts">
  // 4-column bordered stat strip used on index/category/idea hero blocks.
  // Tone optionally tints the number color (e.g., "go" green for GO count).

  type Tone = "default" | "go" | "amber" | "info";

  export interface Stat {
    value: string | number;
    label: string;
    tone?: Tone;
  }

  interface Props {
    stats: Stat[];
  }

  let { stats }: Props = $props();
</script>

<div class="stat-strip" style="--cols: {stats.length};">
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
