<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";
  import { CheckCircle, AlertCircle, Info, X } from "lucide-svelte";

  type AlertVariant = "success" | "warning" | "error" | "info";

  interface Props {
    variant: AlertVariant;
    icon?: ComponentType;
    title: string;
    message?: string;
    dismissible?: boolean;
    onDismiss?: () => void;
    children?: Snippet;
    class?: string;
    id?: string;
  }

  let {
    variant,
    icon,
    title,
    message,
    dismissible = false,
    onDismiss,
    children,
    class: className = "",
    id,
  }: Props = $props();

  const variantMap: Record<AlertVariant, { bg: string; border: string; iconClass: string; defaultIcon: ComponentType }> = {
    success: {
      bg: "bg-success/10",
      border: "border-success/30",
      iconClass: "text-success",
      defaultIcon: CheckCircle,
    },
    warning: {
      bg: "bg-warning/10",
      border: "border-warning/30",
      iconClass: "text-warning",
      defaultIcon: AlertCircle,
    },
    error: {
      bg: "bg-error/10",
      border: "border-error/30",
      iconClass: "text-error",
      defaultIcon: AlertCircle,
    },
    info: {
      bg: "bg-warning/5",
      border: "border-warning/20",
      iconClass: "text-warning",
      defaultIcon: AlertCircle,
    },
  };

  const config = $derived(variantMap[variant]);
  const Icon = $derived(icon ?? config.defaultIcon);
</script>

<div {id} class="p-4 rounded-lg {config.bg} border {config.border} {className}" role={variant === 'error' ? 'alert' : 'status'}>
  <div class="flex items-center justify-between">
    <div class="flex items-start gap-3">
      <Icon class="w-5 h-5 {config.iconClass} shrink-0 mt-0.5" />
      <div>
        <p class="text-sm font-medium text-text-primary">{title}</p>
        {#if message}
          <p class="text-sm text-text-muted {title ? 'mt-1' : ''}">{message}</p>
        {/if}
        {#if children}
          {@render children()}
        {/if}
      </div>
    </div>
    {#if dismissible && onDismiss}
      <button
        onclick={onDismiss}
        class="text-text-muted hover:text-text-primary p-1"
        aria-label="Dismiss"
      >
        <X class="w-4 h-4" />
      </button>
    {/if}
  </div>
</div>
