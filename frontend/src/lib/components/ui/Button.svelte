<script lang="ts">
  import type { ComponentType } from "svelte";

  interface Props {
    href?: string;
    onclick?: (e: MouseEvent) => void;
    icon?: ComponentType;
    iconPosition?: "start" | "end";
    label: string;
    disabled?: boolean;
    target?: string;
    rel?: string;
    title?: string;
    class?: string;
  }

  let {
    href,
    onclick,
    icon: Icon,
    iconPosition = "start",
    label,
    disabled = false,
    target,
    rel,
    title,
    class: className = "btn-primary",
  }: Props = $props();
</script>

{#if href}
  <a {href} class={className} {target} {rel} {title}>
    {#if Icon && iconPosition === "start"}<Icon class="w-4 h-4" />{/if}
    {label}
    {#if Icon && iconPosition === "end"}<Icon class="w-4 h-4" />{/if}
  </a>
{:else}
  <button {onclick} {disabled} class={className} {title}>
    {#if Icon && iconPosition === "start"}<Icon class="w-4 h-4" />{/if}
    {label}
    {#if Icon && iconPosition === "end"}<Icon class="w-4 h-4" />{/if}
  </button>
{/if}
