<script lang="ts">
  import { buildMeta, type MetaInput } from "$lib/seo/meta";

  type Props = MetaInput;

  let {
    title,
    description,
    canonical,
    image,
    type = "website",
    noindex = false,
    siteName = "NicheIQ",
  }: Props = $props();

  const meta = $derived(
    buildMeta({ title, description, canonical, image, type, noindex, siteName })
  );
</script>

<svelte:head>
  <title>{meta.title}</title>
  <meta name="description" content={meta.description} />
  <meta name="robots" content={meta.robots} />
  <link rel="canonical" href={meta.canonical} />

  <meta property="og:title" content={meta.ogTitle} />
  <meta property="og:description" content={meta.ogDescription} />
  <meta property="og:type" content={meta.type} />
  <meta property="og:url" content={meta.canonical} />
  <meta property="og:site_name" content={meta.siteName} />
  {#if meta.image}
    <meta property="og:image" content={meta.image} />
  {/if}

  <meta name="twitter:card" content={meta.image ? "summary_large_image" : "summary"} />
  <meta name="twitter:title" content={meta.twitterTitle} />
  <meta name="twitter:description" content={meta.twitterDescription} />
  {#if meta.image}
    <meta name="twitter:image" content={meta.image} />
  {/if}
</svelte:head>
