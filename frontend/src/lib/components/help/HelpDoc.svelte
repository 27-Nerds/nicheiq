<script lang="ts">
  import { renderMarkdown } from "$lib/utils/format";

  let { title, subtitle, content }: { title: string; subtitle?: string; content: string } = $props();

  const html = $derived(renderMarkdown(content, { allowLinks: true }));
</script>

<div class="min-h-screen bg-bg-base">
  <div class="max-w-3xl mx-auto px-6 lg:px-8 py-16 sm:py-24">
    <a
      href="/help"
      class="inline-flex items-center gap-2 text-text-muted hover:text-accent transition-colors mb-8 text-sm"
    >
      &larr; All help topics
    </a>

    <h1 class="text-3xl sm:text-4xl font-display font-bold text-text-primary mb-4">
      {title}
    </h1>
    {#if subtitle}
      <p class="text-text-muted text-sm mb-12">{subtitle}</p>
    {/if}

    <div class="methodology-prose text-text-secondary leading-relaxed">
      {@html html}
    </div>
  </div>
</div>

<style>
  .methodology-prose :global(h2) {
    font-weight: 600;
    color: var(--color-text-primary);
    font-size: 1.5rem;
    margin-top: 2.5rem;
    margin-bottom: 1rem;
  }
  .methodology-prose :global(h2:first-child) {
    margin-top: 0;
  }
  .methodology-prose :global(h3) {
    font-weight: 600;
    color: var(--color-text-primary);
    font-size: 1.15rem;
    margin-top: 2rem;
    margin-bottom: 0.75rem;
  }
  .methodology-prose :global(p) {
    margin-bottom: 1rem;
  }
  .methodology-prose :global(ul),
  .methodology-prose :global(ol) {
    list-style: disc;
    padding-left: 1.5rem;
    margin-bottom: 1rem;
  }
  .methodology-prose :global(ol) {
    list-style: decimal;
  }
  .methodology-prose :global(li) {
    margin-bottom: 0.35rem;
  }
  .methodology-prose :global(strong) {
    color: var(--color-text-primary);
  }
  /* Citation links: muted + underline, never orange (orange = interactive/brand only). */
  .methodology-prose :global(a) {
    color: var(--color-text-primary);
    text-decoration: underline;
    text-underline-offset: 2px;
    text-decoration-color: var(--color-text-muted);
  }
  .methodology-prose :global(a:hover) {
    text-decoration-color: var(--color-text-primary);
  }
</style>
