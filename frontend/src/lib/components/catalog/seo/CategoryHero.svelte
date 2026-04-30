<script lang="ts">
  import { ArrowRight } from "lucide-svelte";

  interface Props {
    name: string;
    dek?: string | null;
    tags?: string[];
    sources?: string[];
    publishedAt?: string | null;
    updatedAt?: string | null;
    totalIdeas?: number | null;
    totalPainPoints?: number | null;
    /** Required: Subscribe CTA href. Page templates derive from session. */
    subscribeHref: string;
  }

  let {
    name,
    dek,
    tags = [],
    sources = [],
    publishedAt,
    updatedAt,
    totalIdeas,
    totalPainPoints,
    subscribeHref,
  }: Props = $props();

  // Phase 5.3: multi-element metadata strip aligned with reference design.
  // Each segment splits typographic register: <dt> mono uppercase (label),
  // <dd> display font 0.875rem (value). The label/value typographic split
  // IS the editorial register — labels feel like form-field names, values
  // feel like body copy.
  const sourcesLabel = $derived(
    sources.length > 0 ? sources.join(" · ") : "Reddit · Hacker News",
  );

  function fmt(date: string | null | undefined): string | null {
    if (!date) return null;
    const d = new Date(date);
    return Number.isFinite(d.getTime())
      ? d.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
      : null;
  }

  const publishedLabel = $derived(fmt(publishedAt));
  const updatedLabel = $derived(fmt(updatedAt));

  const coverageLabel = $derived.by(() => {
    const parts: string[] = [];
    if (typeof totalIdeas === "number") parts.push(`${totalIdeas} ideas`);
    if (typeof totalPainPoints === "number") parts.push(`${totalPainPoints} pain points`);
    return parts.length > 0 ? parts.join(" · ") : null;
  });
</script>

<header class="category-hero">
  <div class="category-hero-top">
    <div class="category-hero-text">
      <h1 class="category-hero-title marker-rule">{name}</h1>
      {#if dek}
        <p class="category-hero-dek">{dek}</p>
      {/if}
      {#if tags.length > 0}
        <ul class="category-hero-chips" aria-label="Tags">
          {#each tags as tag}
            <li class="category-hero-chip">{tag}</li>
          {/each}
        </ul>
      {/if}
    </div>
    <a
      class="subscribe-button"
      href={subscribeHref}
      data-sveltekit-preload-data="hover"
    >
      <span>Subscribe</span>
      <ArrowRight class="subscribe-icon" aria-hidden="true" />
    </a>
  </div>

  <dl class="category-hero-meta">
    <div class="meta-segment">
      <dt>Research file</dt>
      <dd>{sourcesLabel}</dd>
    </div>
    {#if publishedLabel}
      <div class="meta-segment">
        <dt>Published</dt>
        <dd>{publishedLabel}</dd>
      </div>
    {/if}
    {#if updatedLabel}
      <div class="meta-segment">
        <dt>Updated</dt>
        <dd>{updatedLabel}</dd>
      </div>
    {/if}
    {#if coverageLabel}
      <div class="meta-segment">
        <dt>Coverage</dt>
        <dd>{coverageLabel}</dd>
      </div>
    {/if}
  </dl>
</header>

<style>
  .category-hero {
    /* No margin-bottom — shell's flex `gap: var(--space-12)` owns the
       vertical rhythm between hero and CategoryLandingView. */
    margin-bottom: 0;
  }

  .category-hero-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.5rem;
  }

  @media (max-width: 640px) {
    .category-hero-top {
      flex-direction: column;
      align-items: stretch;
    }
  }

  .category-hero-text {
    flex: 1;
    min-width: 0;
  }

  .category-hero-title {
    font-family: var(--font-display);
    font-size: clamp(2rem, 5vw, 3rem);
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.03em;
    color: var(--color-text-primary);
    margin: 0 0 0.5rem 0;
  }

  .category-hero-dek {
    font-size: 1.125rem;
    line-height: 1.6;
    color: var(--color-text-muted);
    max-width: 60ch;
    margin: 1rem 0 0 0;
    text-wrap: balance;
  }

  .category-hero-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 1.5rem 0 0 0;
    padding: 0;
    list-style: none;
  }

  .category-hero-chip {
    display: inline-block;
    padding: 0.25rem 0.625rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    transition:
      color 140ms ease,
      border-color 140ms ease;
  }

  .category-hero-chip:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
  }

  /* ============================================================
     Subscribe CTA — solid orange-fill pill, top-right of hero.
     Matches IdeaHero/PainPointHero exactly for cross-surface
     consistency. Mobile: stacks below text, full-width.
     ============================================================ */
  .subscribe-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
    padding: 0.75rem 1.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: white;
    background: var(--color-accent);
    border-radius: 999px;
    text-decoration: none;
    transition:
      background-color 140ms ease,
      transform 60ms ease;
  }

  @media (max-width: 640px) {
    .subscribe-button {
      width: 100%;
      justify-content: center;
    }
  }

  .subscribe-button:hover {
    background: var(--color-accent-hover, var(--color-accent));
  }

  .subscribe-button:active {
    transform: scale(0.98);
  }

  :global(.subscribe-icon) {
    width: 1rem;
    height: 1rem;
  }

  @media (prefers-reduced-motion: reduce) {
    .subscribe-button,
    .category-hero-chip {
      transition: none;
    }
  }

  /* ============================================================
     Metadata <dl> — multi-element strip with label/value split.
     Anti-slop: labels in mono, values in display. Mono-everywhere
     would read as terminal chrome.
     ============================================================ */
  .category-hero-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem 2rem;
    margin: 1.75rem 0 0;
    padding: 0;
  }

  .meta-segment {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .meta-segment dt {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0;
  }

  .meta-segment dd {
    font-family: var(--font-display);
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0;
    font-feature-settings: "tnum" 1, "ss01" 1;
  }
</style>
