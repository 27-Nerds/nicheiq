<script lang="ts">
  // leader / challenger / niche competitor position chip.
  // Renders nothing when position is null (fail-safe per degradation contract).

  interface Props {
    position: "leader" | "challenger" | "niche" | null | undefined;
  }

  let { position }: Props = $props();
</script>

{#if position}
  <span class="pos tone-{position}">{position}</span>
{/if}

<style>
  .pos {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    padding: 3px 7px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    white-space: nowrap;
    background: var(--color-surface, #fff);
    display: inline-block;
  }
  .tone-leader {
    color: var(--color-success);
    border-color: rgba(34, 197, 94, 0.25);
  }
  .tone-challenger {
    color: var(--color-accent);
    border-color: var(--color-border-accent);
  }
  .tone-niche {
    color: var(--color-info);
    border-color: rgba(59, 130, 246, 0.25);
  }
</style>
