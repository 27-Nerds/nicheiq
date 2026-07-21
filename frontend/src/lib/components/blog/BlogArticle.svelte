<script lang="ts">
  import { renderMarkdown } from '$lib/utils/format';
  import type { BlogPost } from '$lib/blog/registry';

  let { post, content }: { post: BlogPost; content: string } = $props();

  // Author-controlled content: links + images enabled. DOMPurify strips
  // onerror/javascript: srcs; only src/alt/width/height survive.
  const rawHtml = $derived(renderMarkdown(content, { allowLinks: true, allowImages: true }));

  // Wrap standalone markdown images in <figure> with a <figcaption> sourced
  // from the alt text. The alt is author-written (trusted), so this mirrors
  // the week-highlight post-sanitize pattern in renderTechnicalContent.
  const html = $derived(
    rawHtml.replace(
      /<p><img\s+src="([^"]+)"\s+alt="([^"]*)"(?:\s+width="([^"]*)")?(?:\s+height="([^"]*)")?\s*\/?><\/p>/g,
      (_m, src, alt, w, h) => {
        const dims = `${w ? ` width="${w}"` : ''}${h ? ` height="${h}"` : ''}`;
        const cap = alt
          ? `<figcaption class="blog-figcap">${alt}</figcaption>`
          : '';
        return `<figure class="blog-fig"><img src="${src}" alt="${alt}"${dims} loading="lazy" />${cap}</figure>`;
      },
    ),
  );
</script>

<article class="blog-article">
  <a href="/blog" class="blog-back">
    &larr; All posts
  </a>

  <div class="blog-hero">
    <img src={post.coverImage} alt={post.title} />
  </div>

  <header class="blog-header">
    <div class="blog-tags">
      {#each post.tags as tag (tag)}
        <span class="blog-tag">{tag}</span>
      {/each}
    </div>
    <h1 class="blog-title">{post.title}</h1>
    <p class="blog-dek">{post.description}</p>
    <div class="blog-byline">
      <span class="blog-byline-meta">{post.dateLabel}</span>
      <span class="blog-byline-dot" aria-hidden="true">·</span>
      <span class="blog-byline-meta">{post.readingMins} min read</span>
      <span class="blog-byline-dot" aria-hidden="true">·</span>
      <span class="blog-byline-meta">{post.author}</span>
    </div>
  </header>

  <div class="blog-prose">
    {@html html}
  </div>

  <a href="/blog" class="blog-back blog-back-end">
    &larr; Back to all posts
  </a>
</article>

<style>
  .blog-article {
    max-width: 46rem;
    margin: 0 auto;
    padding: 2rem 1.25rem 5rem;
  }
  @media (min-width: 640px) {
    .blog-article {
      padding: 3rem 1.5rem 6rem;
    }
  }

  .blog-back {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color var(--duration-normal) var(--ease-default);
  }
  .blog-back:hover {
    color: var(--color-accent);
  }
  .blog-back-end {
    margin-top: 3rem;
    display: inline-flex;
  }

  .blog-hero {
    margin-top: 1.5rem;
    border-radius: 0.75rem;
    overflow: hidden;
    border: 1px solid var(--color-border);
    background: var(--color-bg-surface);
    aspect-ratio: 1200 / 420;
  }
  .blog-hero img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }

  .blog-header {
    margin-top: 2rem;
  }
  .blog-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .blog-tag {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
    border-radius: 999px;
    padding: 0.25rem 0.625rem;
  }
  .blog-title {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: clamp(1.75rem, 4vw, 2.4rem);
    line-height: 1.15;
    color: var(--color-text-primary);
    margin: 0 0 0.75rem;
  }
  .blog-dek {
    font-size: 1.05rem;
    color: var(--color-text-secondary);
    margin: 0 0 1.25rem;
    line-height: 1.5;
  }
  .blog-byline {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
  }
  .blog-byline-dot {
    color: var(--color-border-emphasis);
  }

  /* ---- prose ---- */
  .blog-prose {
    margin-top: 2.5rem;
    color: var(--color-text-secondary);
    font-size: 1.0625rem;
    line-height: 1.75;
  }
  .blog-prose :global(p) {
    margin: 0 0 1.15rem;
  }
  .blog-prose :global(h2) {
    font-family: var(--font-display);
    font-weight: 700;
    color: var(--color-text-primary);
    font-size: 1.5rem;
    line-height: 1.3;
    margin: 2.75rem 0 1rem;
  }
  .blog-prose :global(h2:first-child) {
    margin-top: 0;
  }
  .blog-prose :global(h3) {
    font-family: var(--font-display);
    font-weight: 600;
    color: var(--color-text-primary);
    font-size: 1.2rem;
    margin: 2rem 0 0.75rem;
  }
  .blog-prose :global(strong) {
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .blog-prose :global(em) {
    font-style: italic;
  }
  .blog-prose :global(ul),
  .blog-prose :global(ol) {
    list-style: disc;
    padding-left: 1.5rem;
    margin: 0 0 1.15rem;
  }
  .blog-prose :global(ol) {
    list-style: decimal;
  }
  .blog-prose :global(li) {
    margin-bottom: 0.4rem;
  }
  .blog-prose :global(blockquote) {
    border-left: 3px solid var(--color-border-emphasis);
    padding: 0.25rem 0 0.25rem 1rem;
    margin: 0 0 1.15rem;
    color: var(--color-text-secondary);
    font-style: italic;
  }
  .blog-prose :global(a) {
    color: var(--color-text-primary);
    text-decoration: underline;
    text-underline-offset: 2px;
    text-decoration-color: var(--color-text-muted);
  }
  .blog-prose :global(a:hover) {
    text-decoration-color: var(--color-text-primary);
  }
  .blog-prose :global(code) {
    font-family: var(--font-mono);
    font-size: 0.9em;
    background: var(--color-bg-surface);
    padding: 0.15rem 0.35rem;
    border-radius: 4px;
  }

  /* ---- figures (generated from markdown images) ---- */
  .blog-prose :global(.blog-fig) {
    margin: 2.25rem -0.5rem;
    text-align: center;
  }
  @media (min-width: 640px) {
    .blog-prose :global(.blog-fig) {
      /* break out slightly into the gutter for a wider editorial feel */
      margin-left: -1.5rem;
      margin-right: -1.5rem;
    }
  }
  .blog-prose :global(.blog-fig img) {
    width: 100%;
    height: auto;
    display: block;
    border-radius: 0.625rem;
    border: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }
  .blog-prose :global(.blog-figcap) {
    font-size: 0.85rem;
    color: var(--color-text-muted);
    margin-top: 0.625rem;
    line-height: 1.45;
    max-width: 42rem;
    margin-left: auto;
    margin-right: auto;
  }
</style>
