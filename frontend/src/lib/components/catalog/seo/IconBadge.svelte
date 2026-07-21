<script lang="ts">
  import type { Snippet } from "svelte";

  // 32-34px square icon-in-box. Used for category icons in heroes &
  // breadcrumbs. The `children` snippet renders an SVG icon component
  // (e.g. lucide-svelte).

  interface Props {
    size?: number;
    children?: Snippet;
  }

  let { size = 32, children }: Props = $props();
</script>

<span class="icon-badge" style="--s: {size}px;">
  {@render children?.()}
</span>

<style>
  .icon-badge {
    width: var(--s);
    height: var(--s);
    border-radius: 6px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    display: grid;
    place-items: center;
    color: var(--color-text-secondary, var(--color-text-primary));
    flex-shrink: 0;
  }
</style>
