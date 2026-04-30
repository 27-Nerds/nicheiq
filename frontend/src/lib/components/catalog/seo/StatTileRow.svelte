<script lang="ts">
  interface Tile {
    value: string | number;
    label: string;
  }

  interface Props {
    tiles: Tile[];
  }

  let { tiles }: Props = $props();
</script>

<div class="stat-tile-row" role="list">
  {#each tiles as tile, i}
    <div class="stat-tile" class:has-divider={i > 0} role="listitem">
      <div class="stat-tile-value font-mono tabular-nums">{tile.value}</div>
      <div class="stat-tile-label font-mono">{tile.label}</div>
    </div>
  {/each}
</div>

<style>
  .stat-tile-row {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0;
    margin: 1.5rem 0;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    overflow: hidden;
  }

  @media (min-width: 640px) {
    .stat-tile-row {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .stat-tile {
    padding: 1.25rem 1rem;
    text-align: left;
  }

  /* Hairline separators between tiles. On mobile (2-col), every odd index gets
     a left divider; on desktop (4-col), every non-first gets one. */
  .stat-tile.has-divider {
    border-left: 1px solid var(--color-border);
  }

  /* On mobile, the second row's first tile (index 2) has the wrong divider —
     suppress it. */
  @media (max-width: 639px) {
    .stat-tile:nth-child(odd).has-divider {
      border-left: none;
    }
    .stat-tile:nth-child(n + 3) {
      border-top: 1px solid var(--color-border);
    }
  }

  .stat-tile-value {
    font-size: 2rem;
    font-weight: 500;
    color: var(--color-text-primary);
    line-height: 1;
    letter-spacing: -0.02em;
  }

  @media (min-width: 768px) {
    .stat-tile-value {
      font-size: 2.5rem;
    }
  }

  .stat-tile-label {
    margin-top: 0.5rem;
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
</style>
