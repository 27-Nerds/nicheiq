<script lang="ts">
  import "../app.css";
  import Analytics from "$lib/components/Analytics.svelte";
  import JsonLd from "$lib/components/seo/JsonLd.svelte";
  import { organization, website } from "$lib/seo/jsonld";

  let { children } = $props();

  // Site-global brand entities. Defined once here so every route inherits the
  // same Organization + WebSite signal. Per-route schemas (BreadcrumbList,
  // CollectionPage, Article, FAQPage) reference these via `@id` to build the
  // E-E-A-T entity chain that AI Overviews and Knowledge Graph consumers
  // trace.
  const siteSchema = [organization(), website()];
</script>

<JsonLd data={siteSchema} />
<Analytics />
{@render children()}
