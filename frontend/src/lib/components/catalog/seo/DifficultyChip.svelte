<script lang="ts">
  import type { DifficultyBucket } from "$lib/types/publicCatalog.js";

  // easy / medium / hard chip used in keyword cluster tables. Color-coded:
  //   easy   → success
  //   medium → warning
  //   hard   → error

  interface Props {
    difficulty: DifficultyBucket;
  }

  let { difficulty }: Props = $props();
</script>

<span class="diff tone-{difficulty}">{difficulty}</span>

<style>
  .diff {
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid var(--color-border);
    min-width: 48px;
    text-align: center;
    display: inline-block;
  }
  .tone-easy {
    color: var(--color-success);
    border-color: rgba(34, 197, 94, 0.25);
  }
  .tone-medium {
    color: var(--color-warning, #ca8a04);
    border-color: rgba(202, 138, 4, 0.25);
  }
  .tone-hard {
    color: var(--color-error, #dc2626);
    border-color: rgba(220, 38, 38, 0.25);
  }
</style>
