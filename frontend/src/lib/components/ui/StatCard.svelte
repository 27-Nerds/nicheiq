<script lang="ts">
  import type { ComponentType } from "svelte";

  type StatColor = "accent" | "success" | "warning" | "error";

  interface Props {
    icon: ComponentType;
    value: number | string;
    label: string;
    color: StatColor;
    class?: string;
  }

  let {
    icon: Icon,
    value,
    label,
    color,
    class: className = "",
  }: Props = $props();

  const colorMap: Record<StatColor, { cardBorder: string; hoverBorder: string; iconBg: string; iconBorder: string; iconText: string }> = {
    accent: {
      cardBorder: "border-l-accent",
      hoverBorder: "hover:border-accent/30",
      iconBg: "bg-accent/10",
      iconBorder: "border-accent/20",
      iconText: "text-accent",
    },
    success: {
      cardBorder: "border-l-success",
      hoverBorder: "hover:border-success/30",
      iconBg: "bg-success/10",
      iconBorder: "border-success/20",
      iconText: "text-success",
    },
    warning: {
      cardBorder: "border-l-warning",
      hoverBorder: "hover:border-warning/30",
      iconBg: "bg-warning/10",
      iconBorder: "border-warning/20",
      iconText: "text-warning",
    },
    error: {
      cardBorder: "border-l-error",
      hoverBorder: "hover:border-error/30",
      iconBg: "bg-error/10",
      iconBorder: "border-error/20",
      iconText: "text-error",
    },
  };

  const colors = $derived(colorMap[color]);
</script>

<div
  class="card hover:shadow-md {colors.hoverBorder} transition-all duration-200 cursor-default border-l-4 {colors.cardBorder} {className}"
>
  <div class="flex items-center gap-4">
    <div class="p-2.5 rounded-xl {colors.iconBg} border {colors.iconBorder}">
      <Icon class="w-5 h-5 {colors.iconText}" />
    </div>
    <div>
      <p
        class="text-4xl font-display font-bold text-text-primary tracking-tight"
      >
        {value}
      </p>
      <p
        class="text-xs font-mono uppercase tracking-wider text-text-muted mt-1"
      >
        {label}
      </p>
    </div>
  </div>
</div>
