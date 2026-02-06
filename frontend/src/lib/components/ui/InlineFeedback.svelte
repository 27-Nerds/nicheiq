<script lang="ts">
  import { AlertCircle, CheckCircle, Info } from "lucide-svelte";

  type FeedbackVariant = "error" | "success" | "warning" | "info";

  interface Props {
    message: string;
    variant: FeedbackVariant;
    class?: string;
  }

  let { message, variant, class: className = "" }: Props = $props();

  const variantMap: Record<FeedbackVariant, { textClass: string; icon: typeof AlertCircle }> = {
    error: { textClass: "text-error", icon: AlertCircle },
    warning: { textClass: "text-warning", icon: AlertCircle },
    success: { textClass: "text-success", icon: CheckCircle },
    info: { textClass: "text-info", icon: Info },
  };

  const config = $derived(variantMap[variant]);
</script>

<div class="flex items-center gap-2 text-sm {config.textClass} {className}">
  <config.icon class="w-4 h-4 shrink-0" />
  {message}
</div>
