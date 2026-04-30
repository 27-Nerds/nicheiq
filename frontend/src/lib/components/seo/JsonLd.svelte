<script lang="ts">
  import { serializeJsonLd, type JsonLd } from "$lib/seo/jsonld";

  interface Props {
    data: JsonLd | JsonLd[];
  }

  let { data }: Props = $props();

  const items = $derived(Array.isArray(data) ? data : [data]);
</script>

<svelte:head>
  {#each items as item}
    {@html `<script type="application/ld+json">${serializeJsonLd(item)}</script>`}
  {/each}
</svelte:head>
