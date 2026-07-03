<script lang="ts">
  import BlogArticle from '$lib/components/blog/BlogArticle.svelte';
  import { SeoHead, JsonLd } from '$lib/components/seo';

  let { data } = $props();
</script>

<SeoHead
  title={`${data.post.title} | NicheIQ Blog`}
  description={data.post.description}
  canonical={data.canonical}
  image={data.imageUrl}
  type="article"
/>
<JsonLd data={data.jsonLd} />

<BlogArticle post={data.post} content={data.content} />
