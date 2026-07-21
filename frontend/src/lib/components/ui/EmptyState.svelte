<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";

  interface Props {
    title: string;
    description?: string;
    /** One muted line for empty list sections inside a populated surface. */
    inline?: boolean;
    /** @deprecated Ignored: the v3 empty state has no icon. */
    icon?: ComponentType;
    /** @deprecated Ignored: the v3 empty state has no tinted box or variant chrome. */
    variant?: "default" | "warning" | "info" | "muted";
    /** @deprecated Ignored: the v3 empty state has one size. */
    size?: "sm" | "md" | "lg";
    children?: Snippet;
  }

  let {
    title,
    description = "",
    inline = false,
    icon,
    variant,
    size: _size,
    children,
  }: Props = $props();

  $effect(() => {
    if (icon || (variant && variant !== "default")) {
      console.warn(
        "EmptyState: `icon` and `variant` are deprecated and ignored (v3 empty state renders title + directive sentence + actions only).",
      );
    }
  });
</script>

{#if inline}
  <p class="empty-inline">{description || title}</p>
{:else}
  <div class="empty-state">
    <h4>{title}</h4>
    {#if description}
      <p>{description}</p>
    {/if}
    {#if children}
      <div class="actions">
        {@render children()}
      </div>
    {/if}
  </div>
{/if}

<style>
  .empty-state {
    display: grid;
    gap: 0.4rem;
    justify-items: center;
    padding: 3rem 1.5rem;
    text-align: center;
  }

  .empty-state h4 {
    margin: 0;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .empty-state p {
    margin: 0;
    max-width: 38ch;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.5;
  }

  .empty-state .actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.6rem;
    flex-wrap: wrap;
    justify-content: center;
  }

  .empty-inline {
    margin: 0;
    padding: 0.75rem 0.15rem;
    color: var(--color-text-muted);
    font-size: var(--text-13);
  }
</style>
