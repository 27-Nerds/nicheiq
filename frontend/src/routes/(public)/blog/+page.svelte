<script lang="ts">
  import { BLOG_POSTS_SORTED } from '$lib/blog/registry';
  import { SeoHead } from '$lib/components/seo';
  import { canonicalUrl, siteOrigin } from '$lib/seo/canonical';

  const title = 'NicheIQ Blog — Engineering notes on AI market research';
  const description =
    'How we build and tune the research pipeline: idea generation, evaluation, benchmarks, and the hard parts of making an AI system tell the truth.';
</script>

<SeoHead
  {title}
  {description}
  canonical={canonicalUrl('/blog', '')}
  image={`${siteOrigin()}/blog/cover-og.svg`}
/>

<div class="blog-index">
  <div class="blog-index-inner">
    <a href="/" class="blog-back">
      &larr; Home
    </a>

    <header class="blog-index-header">
      <span class="blog-eyebrow">NICHEIQ · BLOG</span>
      <h1>Engineering notes</h1>
      <p class="blog-index-lead">
        How we build and tune the research pipeline — the structural changes,
        the failed hypotheses, and the hard parts of making an AI system
        tell the truth instead of what you want to hear.
      </p>
    </header>

    <ul class="post-list">
      {#each BLOG_POSTS_SORTED as post (post.slug)}
        <li>
          <a href={`/blog/${post.slug}`} class="post-card">
            <div class="post-card-cover">
              <img src={post.coverImage} alt={post.title} loading="lazy" />
            </div>
            <div class="post-card-body">
              <div class="post-card-meta">
                <span>{post.dateLabel}</span>
                <span class="dot" aria-hidden="true">·</span>
                <span>{post.readingMins} min read</span>
              </div>
              <h2 class="post-card-title">{post.title}</h2>
              <p class="post-card-dek">{post.description}</p>
              <div class="post-card-tags">
                {#each post.tags as tag (tag)}
                  <span class="post-card-tag">{tag}</span>
                {/each}
              </div>
            </div>
          </a>
        </li>
      {/each}
    </ul>
  </div>
</div>

<style>
  .blog-index {
    min-height: 100vh;
    background: var(--color-bg-base);
  }
  .blog-index-inner {
    max-width: 46rem;
    margin: 0 auto;
    padding: 2.5rem 1.25rem 5rem;
  }
  @media (min-width: 640px) {
    .blog-index-inner {
      padding: 4rem 1.5rem 6rem;
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

  .blog-index-header {
    margin-top: 2rem;
    margin-bottom: 3rem;
  }
  .blog-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    letter-spacing: 0.12em;
    color: var(--color-text-muted);
  }
  .blog-index-header h1 {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: clamp(2rem, 5vw, 2.75rem);
    line-height: 1.1;
    color: var(--color-text-primary);
    margin: 0.75rem 0 1rem;
  }
  .blog-index-lead {
    font-size: 1.1rem;
    color: var(--color-text-secondary);
    line-height: 1.55;
    max-width: 40rem;
    margin: 0;
  }

  .post-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 1.75rem;
  }
  .post-card {
    display: block;
    text-decoration: none;
    border: 1px solid var(--color-border);
    border-radius: 0.875rem;
    overflow: hidden;
    background: #fff;
    transition: border-color var(--duration-normal) var(--ease-default),
      box-shadow var(--duration-normal) var(--ease-default);
  }
  .post-card:hover {
    border-color: var(--color-border-emphasis);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  }
  .post-card:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .post-card-cover {
    aspect-ratio: 1200 / 420;
    background: var(--color-bg-surface);
    border-bottom: 1px solid var(--color-border);
  }
  .post-card-cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .post-card-body {
    padding: 1.25rem 1.25rem 1.5rem;
  }
  @media (min-width: 640px) {
    .post-card-body {
      padding: 1.5rem 1.5rem 1.75rem;
    }
  }
  .post-card-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    margin-bottom: 0.5rem;
  }
  .post-card-meta .dot {
    color: var(--color-border-emphasis);
  }
  .post-card-title {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.35rem;
    line-height: 1.25;
    color: var(--color-text-primary);
    margin: 0 0 0.5rem;
  }
  .post-card-dek {
    font-size: 0.975rem;
    color: var(--color-text-secondary);
    line-height: 1.55;
    margin: 0 0 0.85rem;
  }
  .post-card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .post-card-tag {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
    border-radius: 999px;
    padding: 0.2rem 0.55rem;
  }
</style>
