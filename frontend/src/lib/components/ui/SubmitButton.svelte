<script lang="ts">
  import type { ComponentType } from "svelte";
  import { Loader2 } from "lucide-svelte";

  interface Props {
    onclick?: () => void;
    disabled?: boolean;
    loading?: boolean;
    loadingText: string;
    icon?: ComponentType;
    iconPosition?: "start" | "end";
    keepIconOnLoad?: boolean;
    label: string;
    type?: "button" | "submit";
    title?: string;
    class?: string;
  }

  let {
    onclick,
    disabled = false,
    loading = false,
    loadingText,
    icon: Icon,
    iconPosition = "start",
    keepIconOnLoad = false,
    label,
    type = "submit",
    title,
    class: className = "btn-primary w-full",
  }: Props = $props();
</script>

<button
  {type}
  {onclick}
  disabled={disabled || loading}
  class={className}
  {title}
>
  {#if loading}
    {#if keepIconOnLoad && Icon}
      <Icon class="w-4 h-4 animate-spin" />
    {:else}
      <Loader2 class="w-4 h-4 animate-spin" />
    {/if}
    {#if loadingText}{loadingText}{/if}
  {:else}
    {#if Icon && iconPosition === "start"}<Icon class="w-4 h-4" />{/if}
    {label}
    {#if Icon && iconPosition === "end"}<Icon class="w-4 h-4" />{/if}
  {/if}
</button>
