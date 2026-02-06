<script lang="ts">
  interface Props {
    label: string;
    value: string | number;
    subvalue?: string;
    variant?: "default" | "accent" | "success" | "warning";
  }

  let { label, value, subvalue, variant = "default" }: Props = $props();

  const valueClasses: Record<string, string> = {
    default: "text-text-primary",
    accent: "text-accent",
    success: "text-success",
    warning: "text-warning",
  };
</script>

<div class="stat-card">
  <div class="stat-value {valueClasses[variant]}">{value}</div>
  <div class="stat-label">{label}</div>
  {#if subvalue}
    <div class="text-xs text-text-muted mt-1">{subvalue}</div>
  {/if}
</div>
