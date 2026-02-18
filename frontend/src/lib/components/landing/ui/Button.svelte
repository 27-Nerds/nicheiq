<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    variant?: "primary" | "secondary" | "ghost";
    size?: "sm" | "md" | "lg";
    href?: string;
    disabled?: boolean;
    loading?: boolean;
    class?: string;
    onclick?: () => void;
    children: Snippet;
  }

  let {
    variant = "primary",
    size = "md",
    href,
    disabled = false,
    loading = false,
    class: className = "",
    onclick,
    children,
  }: Props = $props();

  const baseClasses =
    "relative inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition-all duration-200 ease-out disabled:opacity-50 disabled:cursor-not-allowed";

  const variantClasses = {
    primary:
      "bg-accent text-white hover:bg-accent-hover active:translate-y-px",
    secondary:
      "bg-transparent border border-border-emphasis text-text-primary hover:border-accent hover:text-accent",
    ghost: "bg-transparent text-text-secondary hover:text-accent",
  };

  const sizeClasses = {
    sm: "px-4 py-2 text-sm",
    md: "px-6 py-3 text-sm",
    lg: "px-8 py-4 text-base",
  };

  const classes = $derived(
    `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`,
  );
</script>

{#if href}
  <a {href} class={classes} class:pointer-events-none={disabled || loading}>
    {#if loading}
      <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="3"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
    {/if}
    {@render children()}
  </a>
{:else}
  <button class={classes} disabled={disabled || loading} {onclick}>
    {#if loading}
      <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="3"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
    {/if}
    {@render children()}
  </button>
{/if}
