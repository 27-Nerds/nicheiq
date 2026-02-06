<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";

  type IconColor = "accent" | "secondary" | "warning";

  interface Props {
    icon: ComponentType;
    title: string;
    subtitle?: string;
    iconColor?: IconColor;
    actions?: Snippet;
    class?: string;
  }

  let {
    icon: Icon,
    title,
    subtitle,
    iconColor = "accent",
    actions,
    class: className = "",
  }: Props = $props();

  const colorMap: Record<IconColor, { bg: string; border: string; text: string }> = {
    accent: { bg: "bg-accent/10", border: "border-accent/20", text: "text-accent" },
    secondary: { bg: "bg-secondary/10", border: "border-secondary/20", text: "text-secondary" },
    warning: { bg: "bg-warning/10", border: "border-warning/20", text: "text-warning" },
  };

  const colors = $derived(colorMap[iconColor]);
</script>

<div class="mb-8 {actions ? 'flex items-center justify-between' : ''} {className}">
  <div>
    <h1 class="text-2xl font-bold text-text-primary flex items-center gap-3">
      <div class="p-2 rounded-xl {colors.bg} border {colors.border}">
        <Icon class="w-6 h-6 {colors.text}" />
      </div>
      {title}
    </h1>
    {#if subtitle}
      <p class="text-text-muted mt-1">{subtitle}</p>
    {/if}
  </div>
  {#if actions}
    {@render actions()}
  {/if}
</div>
