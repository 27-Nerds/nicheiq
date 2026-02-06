<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    minWidth?: number;
    gap?: "sm" | "md" | "lg";
    children: Snippet;
    class?: string;
  }

  let {
    minWidth = 240,
    gap = "md",
    children,
    class: className = "",
  }: Props = $props();

  const gapValues = {
    sm: "0.5rem",
    md: "0.75rem",
    lg: "1rem",
  };
</script>

<div
  class="card-grid {className}"
  style="--grid-min-width: {minWidth}px; --grid-gap: {gapValues[gap]}"
>
  {@render children()}
</div>

<style>
  .card-grid {
    display: grid;
    grid-template-columns: repeat(
      auto-fit,
      minmax(var(--grid-min-width, 240px), 1fr)
    );
    gap: var(--grid-gap, 0.75rem);
  }

  @media (max-width: 768px) {
    .card-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
