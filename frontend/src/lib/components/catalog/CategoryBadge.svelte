<script lang="ts">
  import { Folder } from "lucide-svelte";
  import { categoryPath } from "$lib/utils/urls";

  interface Props {
    category: { name: string; slug: string; parentSlug?: string | null };
    type: "pain-points" | "ideas";
    size?: "sm" | "md";
    light?: boolean;
    asLink?: boolean;
  }

  let { category, type, size = "sm", light = false, asLink = true }: Props = $props();

  const href = $derived(categoryPath({
    slug: category.slug,
    parentSlug: category.parentSlug ?? null,
  }));
  const sizeClass = $derived(size === "sm" ? "cat-badge-sm" : "");
</script>

<svelte:element
  this={asLink ? "a" : "span"}
  href={asLink ? href : undefined}
  class={light ? "cat-badge-light" : `cat-badge ${sizeClass}`}
  title="Filter by {category.name}"
>
  <Folder class="cat-badge-icon" />
  {category.name}
</svelte:element>

<style>
  .cat-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: var(--space-2) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    color: var(--color-text-muted);
    background-color: rgba(100, 116, 139, 0.06);
    border: 1px solid rgba(100, 116, 139, 0.15);
    border-radius: var(--radius-md);
    text-decoration: none;
    transition: color var(--duration-normal) ease, border-color var(--duration-normal) ease;
  }

  .cat-badge:hover {
    color: var(--color-accent);
    border-color: rgba(240, 96, 48, 0.25);
  }

  .cat-badge-sm {
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    border-radius: var(--radius-sm);
  }

  .cat-badge-icon {
    width: 0.75em;
    height: 0.75em;
    opacity: 0.6;
  }

  .cat-badge-light {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color var(--duration-normal) ease;
  }
  .cat-badge-light:hover {
    color: var(--color-accent);
  }
  .cat-badge-light :global(.cat-badge-icon) {
    width: 1em;
    height: 1em;
    opacity: 0.5;
  }
</style>
