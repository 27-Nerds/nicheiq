<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import { page } from "$app/state";
  import type { CatalogResearchContext, IdeaPreview } from "$lib/types/catalog-landing";

  // Hero composition spec (binding):
  //   H1 (capitalized, Plus Jakarta 800, marker-rule under) → dek (max 60ch
  //   muted) → tag chips → single mono provenance row → ledger metric strip
  //   → right-aligned solid Subscribe CTA. NO card chrome around the hero.
  //   NO "AI-powered" copy anywhere. NO green-check status banner — quality
  //   signal lives inside the provenance row's GOLD/SILVER segment.
  interface Props {
    idea: IdeaPreview;
    researchContext: CatalogResearchContext | null;
  }

  let { idea, researchContext }: Props = $props();

  const session = $derived(page.data.session);
  const subscribeHref = $derived(
    session?.user ? "/new" : `/register?ref=catalog&slug=${encodeURIComponent(idea.slug)}`,
  );

  const updatedLabel = $derived(
    idea.updated_at
      ? new Date(idea.updated_at).toLocaleDateString("en-GB", {
          day: "numeric",
          month: "short",
          year: "numeric",
        })
      : null,
  );

  const tags = $derived.by(() => {
    const out: string[] = [];
    if (idea.format) out.push(idea.format.replace(/-/g, " "));
    if (idea.project_type) out.push(idea.project_type);
    return out.slice(0, 4);
  });

  // Ledger metrics. Pulls from researchContext when available; falls back to
  // count-based zeros otherwise. We deliberately don't render a verdict cell
  // unless we have one — empty cell beats a fake "—".
  const metrics = $derived.by(() => {
    const r = researchContext;
    return [
      { value: r?.redditPostsAnalyzed ?? null, label: "POSTS" },
      {
        value: Array.isArray(r?.detailedPainPoints)
          ? r!.detailedPainPoints.length
          : null,
        label: "PAIN POINTS",
      },
      { value: r?.redditCommentsAnalyzed ?? null, label: "MENTIONS" },
      {
        value: Array.isArray(r?.alternativeSolutions)
          ? r!.alternativeSolutions.length
          : null,
        label: "SOLUTIONS",
      },
      {
        verdict: r?.goNoGoVerdict ?? null,
        label: "TOP SIGNAL",
      },
    ];
  });

  const showsTier = $derived(
    researchContext?.dataQualityTier === "GOLD" ||
      researchContext?.dataQualityTier === "SILVER",
  );

  function fmt(value: number | null | undefined): string {
    if (value == null) return "—";
    if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}k`;
    return String(value);
  }
</script>

<header class="idea-hero">
  <h1 class="idea-hero-title marker-rule">{idea.solution_name}</h1>

  {#if idea.value_proposition}
    <p class="idea-hero-dek">{idea.value_proposition}</p>
  {/if}

  {#if tags.length > 0}
    <ul class="idea-hero-tags" aria-label="Tags">
      {#each tags as tag}
        <li class="tag-chip">{tag}</li>
      {/each}
    </ul>
  {/if}

  <p class="idea-hero-provenance">
    <span>Research file</span>
    <span class="prov-sep">·</span>
    <span>Reddit · Hacker News</span>
    {#if updatedLabel}
      <span class="prov-sep">·</span>
      <span>Updated {updatedLabel}</span>
    {/if}
    {#if showsTier}
      <span class="prov-sep">·</span>
      <span>{researchContext!.dataQualityTier} tier</span>
    {/if}
  </p>

  <div class="idea-hero-metrics" aria-label="Research metrics">
    {#each metrics as metric}
      <div class="metric-cell">
        <div class="metric-value tabular-nums">
          {#if "verdict" in metric}
            <span
              class="verdict-text"
              class:verdict-go={metric.verdict === "GO"}
              class:verdict-maybe={metric.verdict === "MAYBE"}
              class:verdict-nogo={metric.verdict === "NO_GO"}
              class:verdict-empty={metric.verdict == null}
            >
              {metric.verdict === "NO_GO" ? "NO-GO" : (metric.verdict ?? "—")}
            </span>
          {:else}
            {fmt(metric.value)}
          {/if}
        </div>
        <div class="metric-label">{metric.label}</div>
      </div>
    {/each}
  </div>

  <div class="idea-hero-cta">
    <a class="subscribe-button" href={subscribeHref} data-sveltekit-preload-data="hover">
      <span>Subscribe</span>
      <ArrowRight class="subscribe-icon" aria-hidden="true" />
    </a>
  </div>
</header>

<style>
  .idea-hero {
    margin-bottom: 3rem;
    /* No card chrome — full bleed inside the 1200px shell. */
  }

  .idea-hero-title {
    font-family: var(--font-display);
    font-size: clamp(2rem, 5vw, 3.5rem);
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.025em;
    color: var(--color-text-primary);
    margin: 0 0 0.5rem 0;
    text-wrap: balance;
  }

  .idea-hero-dek {
    font-size: 1.125rem;
    line-height: 1.6;
    color: var(--color-text-muted);
    margin: 1.25rem 0 0;
    text-wrap: pretty;
    max-width: 60ch;
  }

  .idea-hero-tags {
    list-style: none;
    padding: 0;
    margin: 1.25rem 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .tag-chip {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: transparent;
  }

  .idea-hero-provenance {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin: 1.5rem 0 0;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem 0.5rem;
    font-feature-settings: "tnum" 1, "ss01" 1;
  }

  .prov-sep {
    color: var(--color-border);
  }

  /* Newspaper-masthead metric strip. NO tile chrome — top/bottom hairlines
     span the full strip, vertical hairlines between cells. */
  .idea-hero-metrics {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    margin-top: 2rem;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
  }

  @media (max-width: 640px) {
    .idea-hero-metrics {
      grid-template-columns: repeat(2, 1fr);
    }
    .metric-cell:last-child {
      grid-column: 1 / -1;
    }
  }

  .metric-cell {
    padding: 1.125rem 1rem;
    border-left: 1px solid var(--color-border);
    text-align: center;
  }

  .metric-cell:first-child {
    border-left: none;
  }

  @media (max-width: 640px) {
    .metric-cell:nth-child(odd) {
      border-left: none;
    }
    .metric-cell:nth-child(n + 3) {
      border-top: 1px solid var(--color-border);
    }
  }

  .metric-value {
    font-family: var(--font-display);
    font-size: 1.625rem;
    font-weight: 700;
    line-height: 1.1;
    color: var(--color-text-primary);
  }

  .metric-label {
    margin-top: 0.375rem;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .verdict-text {
    font-family: var(--font-display);
    font-size: 1.625rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .verdict-go {
    color: var(--color-accent);
  }

  .verdict-maybe {
    color: var(--color-warning);
  }

  .verdict-nogo,
  .verdict-empty {
    color: var(--color-text-muted);
  }

  .idea-hero-cta {
    display: flex;
    justify-content: flex-end;
    margin-top: 2rem;
  }

  @media (max-width: 640px) {
    .idea-hero-cta {
      justify-content: stretch;
    }
  }

  .subscribe-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
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
    .subscribe-button {
      transition: none;
    }
  }
</style>
