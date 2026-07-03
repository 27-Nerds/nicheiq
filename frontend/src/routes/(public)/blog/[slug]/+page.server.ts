import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { getBlogPost } from '$lib/blog/registry';
import { canonicalUrl, siteOrigin } from '$lib/seo/canonical';
import { article as articleJsonLd, breadcrumbList } from '$lib/seo/jsonld';

// Eager raw imports so SSR has the markdown inlined; adding a post is just
// dropping a .md file in content/blog + a registry entry — no per-slug route.
const posts = import.meta.glob('/src/lib/content/blog/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

export const load: PageServerLoad = async ({ params, url }) => {
  const post = getBlogPost(params.slug);
  if (!post) throw error(404, 'Post not found');

  const key = `/src/lib/content/blog/${params.slug}.md`;
  const content = posts[key];
  if (!content) throw error(404, 'Post not found');

  const canonical = canonicalUrl(`/blog/${params.slug}`, url.searchParams);
  const origin = siteOrigin();
  // OG/Twitter card uses the titled social image; the in-page hero (coverImage)
  // is titleless so it isn't redundant with the <h1> rendered below it.
  const imageUrl = `${origin}${post.ogImage}`;

  const jsonLd = [
    articleJsonLd({
      headline: post.title,
      description: post.description,
      datePublished: post.date,
      dateModified: post.date,
      url: canonical,
      image: imageUrl,
      author: post.author,
    }),
    breadcrumbList([
      { name: 'Blog', url: `${origin}/blog` },
      { name: post.title, url: canonical },
    ]),
  ];

  return { post, content, canonical, imageUrl, jsonLd };
};
