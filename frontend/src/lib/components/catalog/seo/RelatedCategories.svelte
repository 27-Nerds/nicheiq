<script lang="ts">
  import { categoryPath } from "$lib/utils/urls";

  interface Item {
    name: string;
    slug: string;
    parentSlug?: string | null;
  }

  interface Props {
    items: Item[];
    label?: string;
  }

  let { items, label = "Related niches" }: Props = $props();
</script>

{#if items.length > 0}
  <nav class="related-categories" aria-label={label}>
    {#each items as item, i}
      <a
        class="related-link"
        href={categoryPath({ slug: item.slug, parentSlug: item.parentSlug })}
        data-sveltekit-preload-data="hover"
      >
        {item.name}
      </a>
      {#if i < items.length - 1}
        <span class="related-sep font-mono" aria-hidden="true">·</span>
      {/if}
    {/each}
  </nav>
{/if}

<style>
  .related-categories {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.5rem 0.75rem;
    line-height: 1.6;
  }

  .related-link {
    position: relative;
    color: var(--color-text-primary);
    font-weight: 500;
    text-decoration: none;
    padding: 0.25rem 0.125rem;
    transition: color 140ms ease;
  }

  /* Hit-slop expand for small inline links (Fitts) */
  .related-link::after {
    content: "";
    position: absolute;
    inset: -0.5rem -0.25rem;
  }

  .related-link:hover {
    color: var(--color-accent);
  }

  .related-link:active {
    transform: scale(0.98);
  }

  .related-sep {
    /* Aligns with hub & detail-page provenance separators (--color-border).
       --color-border-emphasis was too prominent — read as bullet markers
       rather than separators. */
    color: var(--color-border);
  }
</style>
