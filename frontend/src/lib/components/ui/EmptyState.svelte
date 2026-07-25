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
		gap: var(--space-1-5);
    justify-items: center;
		padding: var(--space-12) var(--space-6);
    text-align: center;
  }

  .empty-state h4 {
    margin: 0;
		font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .empty-state p {
    margin: 0;
    max-width: 38ch;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
  }

  .empty-state .actions {
    display: flex;
		gap: var(--space-2);
		margin-top: var(--space-2);
    flex-wrap: wrap;
    justify-content: center;
  }

  .empty-inline {
    margin: 0;
		padding: var(--space-3) var(--space-1);
    color: var(--color-text-muted);
    font-size: var(--text-13);
  }
</style>
