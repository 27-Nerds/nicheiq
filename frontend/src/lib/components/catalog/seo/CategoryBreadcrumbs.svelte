<script lang="ts">
  import Breadcrumb from "$lib/components/ui/Breadcrumb.svelte";

  export interface BreadcrumbStop {
    label: string;
    href?: string;
  }

  interface Props {
    /**
     * Trail from root to current page. The last entry is rendered as the
     * non-link "current" segment; all earlier entries must have an href.
     *
     * Example for `/ideas/saas/b2b-tools`:
     *   [
     *     { label: 'Home', href: '/' },
     *     { label: 'Ideas', href: '/ideas' },
     *     { label: 'SaaS', href: '/ideas/saas' },
     *     { label: 'B2B Tools' },                       // current
     *   ]
     */
    trail: BreadcrumbStop[];
  }

  let { trail }: Props = $props();

  // Translate the simpler `trail` API into the existing Breadcrumb API
  // ({ items, current }). Existing Breadcrumb expects every item to have
  // href, so we strip the last entry (which becomes `current`) and require
  // the rest to carry hrefs.
  const items = $derived(
    trail.slice(0, -1).map((s) => ({ label: s.label, href: s.href ?? "/" })),
  );
  const current = $derived(trail.at(-1)?.label ?? "");
</script>

{#if trail.length > 0}
  <Breadcrumb {items} {current} />
{/if}
