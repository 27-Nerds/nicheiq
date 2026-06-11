<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import Sparkles from "lucide-svelte/icons/sparkles";

  // CTA voice cheat-sheet — read before adding new copy to BuildCTA callers
  // anywhere in /ideas, /idea/[slug], or /pain-point/[slug]:
  //
  //   1. Lead with action, not deficit. "Ready to…?", "Want to…?", or direct
  //      verbs (Run, Build, Validate, Research) — never "Don't see…?" framing.
  //   2. Self-serve ownership. "your", "your own". Drop "commission", "file",
  //      "report you'll receive". The user runs research; they don't buy a
  //      pre-made deliverable.
  //   3. Ground outputs in sourcing. "real community discussions",
  //      "Reddit + HN", "go/no-go verdict" — concrete > abstract.
  //   4. Match verb to visitor state. Index/category → "Run". Idea page →
  //      "Validate" / "Start". Pain page → "Build for". Sub-niche pre-research
  //      → "Run now". Hero buttons should be honest about what /new accepts
  //      (a niche or audience description, NOT a specific idea name).
  //   5. Keep labels 2-4 words, under ~22 chars. Sentence case throughout.
  //
  // Defaults below are deliberately neutral — they stand in only if a caller
  // forgets to pass a field. Most callers should override headline+body+label.

  interface Props {
    headline?: string;
    body?: string;
    ctaLabel?: string;
    ctaHref?: string;
    secondaryLabel?: string | null;
    secondaryHref?: string | null;
    // Optional primary-action snippet. When provided it replaces the default
    // link (used to render an interactive <ResearchCtaButton> instead).
    primary?: import("svelte").Snippet;
  }

  let {
    headline = "Ready to build?",
    body = "Run research on a niche or audience you're curious about. Get pain points, solution ideas, audience segments, and a 30-day launch plan — all sourced from real community discussions.",
    ctaLabel = "Run your own research",
    ctaHref = "",
    secondaryLabel = null,
    secondaryHref = null,
    primary,
  }: Props = $props();
</script>

<section class="build-cta">
  <div class="copy">
    <h3>{headline}</h3>
    <p>{body}</p>
  </div>
  <div class="actions">
    {#if primary}
      {@render primary()}
    {:else}
      <a class="btn-accent" href={ctaHref} data-sveltekit-preload-data="hover">
        <Sparkles size={14} />
        <span>{ctaLabel}</span>
      </a>
    {/if}
    {#if secondaryLabel && secondaryHref}
      <a class="btn-ghost" href={secondaryHref}>
        <span>{secondaryLabel}</span>
        <ArrowRight size={14} />
      </a>
    {/if}
  </div>
</section>

<style>
  .build-cta {
    background: var(--color-surface-elevated, #fafafa);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 28px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    flex-wrap: wrap;
    margin: 48px 0;
  }
  .copy {
    max-width: 560px;
  }
  h3 {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.015em;
    margin: 0 0 6px;
    color: var(--color-text-primary);
  }
  p {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.55;
    margin: 0;
  }
  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .btn-accent,
  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 18px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    border: 1px solid transparent;
    transition: background-color 140ms ease, box-shadow 140ms ease,
      transform 140ms ease, color 140ms ease, border-color 140ms ease;
    white-space: nowrap;
    will-change: transform;
  }
  /* Three-layer shadow anatomy on the primary CTA. Brand-tinted ambient
     ties depth to the accent identity rather than defaulting to neutral.
     Active-state press compresses the stack and applies a 0.98 scale. */
  .btn-accent {
    background: var(--color-accent);
    color: var(--color-surface, #fff);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.18),
      0 1px 2px rgba(154, 52, 18, 0.18),
      0 6px 14px rgba(154, 52, 18, 0.10);
  }
  .btn-accent:hover {
    background: var(--color-accent-hover, var(--color-accent-dark));
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.20),
      0 2px 4px rgba(154, 52, 18, 0.22),
      0 8px 18px rgba(154, 52, 18, 0.12);
  }
  .btn-accent:active {
    transform: scale(0.98);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.12),
      0 1px 1px rgba(154, 52, 18, 0.20);
  }
  .btn-accent:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .btn-ghost {
    color: var(--color-text-secondary, var(--color-text-primary));
    border-color: var(--color-border-emphasis);
    background: var(--color-surface, #fff);
  }
  .btn-ghost:hover {
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
  }
</style>
