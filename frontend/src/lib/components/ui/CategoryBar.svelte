<script lang="ts">
  import type { Snippet } from "svelte";

  type BarColor = "accent" | "secondary" | "warning" | "success" | "error";

  interface Props {
    title: string;
    color: BarColor;
    count?: number;
    margin?: string;
    children?: Snippet;
    class?: string;
  }

  let {
    title,
    color,
    count,
    margin = "mb-2",
    children,
    class: className = "",
  }: Props = $props();

  const colorMap: Record<BarColor, { bar: string; badge: string }> = {
    accent: {
      bar: "bg-accent",
      badge: "text-accent bg-accent/10",
    },
    secondary: {
      bar: "bg-secondary",
      badge: "text-secondary bg-secondary/10",
    },
    warning: {
      bar: "bg-warning",
      badge: "text-warning bg-warning/10",
    },
    success: {
      bar: "bg-success",
      badge: "text-success bg-success/10",
    },
    error: {
      bar: "bg-error",
      badge: "text-error bg-error/10",
    },
  };

  const colors = $derived(colorMap[color]);
</script>

<div class="flex items-center gap-3 {margin} {className}">
  <div class="w-1 h-6 rounded-full {colors.bar}"></div>
  <h2
    class="text-sm font-display font-semibold text-text-primary uppercase tracking-wide"
  >
    {title}
  </h2>
  {#if count !== undefined}
    <span
      class="text-xs font-mono {colors.badge} px-2 py-0.5 rounded-full"
    >
      {count}
    </span>
  {/if}
  {#if children}
    {@render children()}
  {/if}
</div>
