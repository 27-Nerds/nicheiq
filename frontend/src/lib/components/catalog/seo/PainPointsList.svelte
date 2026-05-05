<script lang="ts">
  import type { Snippet } from "svelte";
  import PainPointCardV2 from "./PainPointCardV2.svelte";
  import type { AddressedPainLookup, PainPointPreview } from "$lib/types/catalog-landing.js";

  // Renders a list of pain cards. Used on idea-detail page after the user
  // has chosen the catalog rebuild's "separate lists, no row pairing" model.
  // Pain points come from researchContext.detailedPainPoints (pipeline) so
  // shape isn't the same as CatalogPainPoint — adapt here.
  //
  // When `solutionAside` snippet is provided, the component renders the pain
  // list and aside in a 2-column grid (1.15fr / 1fr) with a sticky right rail
  // — delivering the catalog v2 mock's pain→solution narrative without
  // forcing per-pain artificial mapping.

  interface DetailedPainShape {
    title?: string;
    description?: string;
    severity_score?: number;
    severityScore?: number;
    mention_count?: number;
    mentionCount?: number;
    representative_quotes?: unknown;
    representativeQuotes?: unknown;
    affected_segments?: unknown;
    affectedSegments?: unknown;
    [k: string]: unknown;
  }

  interface Props {
    /** Raw entries from researchContext.detailedPainPoints (loose shape). */
    pains: unknown;
    /** Title→slug map from `getIdeaBySlug`. When present, each card whose
     *  title resolves becomes a link to `/pain-point/{slug}` via
     *  PainPointCardV2's `asLink` prop. Unmatched titles render link-less. */
    addressedPains?: AddressedPainLookup | null;
    /** Cap visible cards. Extras collapse behind a `<details>` toggle so
     *  hidden entries stay DOM-resident for SEO indexing. */
    defaultLimit?: number;
    /** Right-rail solution direction snippet. When present, layout switches
     *  to 2-col with sticky aside. Mobile (≤800px) stacks the aside below
     *  the pain list so the narrative leads. */
    solutionAside?: Snippet;
  }

  let { pains, addressedPains = null, defaultLimit = 5, solutionAside }: Props = $props();

  function normalize(raw: unknown): Array<{
    title: string;
    description: string;
    severityScore: number;
    mentionCount: number;
    representativeQuotes: string[];
    affectedSegments: string[];
    slug: string | null;
    isFeatured: boolean;
    isActive: boolean;
  }> {
    if (!Array.isArray(raw)) return [];
    const out = [];
    for (const p of raw as DetailedPainShape[]) {
      if (!p || typeof p !== "object") continue;
      const title = (p.title as string) ?? "";
      if (!title) continue;
      const sev = (p.severity_score ?? p.severityScore ?? 0) as number;
      const mentions = (p.mention_count ?? p.mentionCount ?? 0) as number;
      const quotes = Array.isArray(p.representative_quotes ?? p.representativeQuotes)
        ? ((p.representative_quotes ?? p.representativeQuotes) as unknown[]).filter(
            (q): q is string => typeof q === "string",
          )
        : [];
      const segments = Array.isArray(p.affected_segments ?? p.affectedSegments)
        ? ((p.affected_segments ?? p.affectedSegments) as unknown[]).filter(
            (s): s is string => typeof s === "string",
          )
        : [];
      out.push({
        title,
        description: (p.description as string) ?? "",
        severityScore: sev,
        mentionCount: mentions,
        representativeQuotes: quotes,
        affectedSegments: segments,
        slug: null,
        isFeatured: false,
        isActive: true,
      });
    }
    return out;
  }

  // Cast the normalized entries into the PainPointPreview shape that
  // PainPointCardV2 expects. The unused PainPointPreview fields are ignored
  // by the card.
  const list = $derived(normalize(pains) as never as PainPointPreview[]);

  function resolveCard(p: PainPointPreview) {
    const resolved = addressedPains?.[p.title];
    const linkedPain = resolved
      ? {
          ...p,
          slug: resolved.slug,
          severityScore: resolved.severityScore,
          mentionCount: resolved.mentionCount,
        }
      : p;
    return { linkedPain, asLink: !!resolved?.slug };
  }

  const head = $derived(list.slice(0, defaultLimit));
  const tail = $derived(list.slice(defaultLimit));
</script>

{#if list.length > 0}
  {#if solutionAside}
    <div class="pains-with-aside">
      <div class="pain-col">
        <div class="pains-list">
          {#each head as p}
            {@const r = resolveCard(p)}
            <PainPointCardV2 pain={r.linkedPain} asLink={r.asLink} />
          {/each}
        </div>
        {#if tail.length > 0}
          <details class="show-all">
            <summary>Show all {list.length} pain points</summary>
            <div class="pains-list pains-list-extra">
              {#each tail as p}
                {@const r = resolveCard(p)}
                <PainPointCardV2 pain={r.linkedPain} asLink={r.asLink} />
              {/each}
            </div>
          </details>
        {/if}
      </div>
      <aside class="solution-col">
        {@render solutionAside()}
      </aside>
    </div>
  {:else}
    <div class="pains-list">
      {#each head as p}
        {@const r = resolveCard(p)}
        <PainPointCardV2 pain={r.linkedPain} asLink={r.asLink} />
      {/each}
    </div>
    {#if tail.length > 0}
      <details class="show-all">
        <summary>Show all {list.length} pain points</summary>
        <div class="pains-list pains-list-extra">
          {#each tail as p}
            {@const r = resolveCard(p)}
            <PainPointCardV2 pain={r.linkedPain} asLink={r.asLink} />
          {/each}
        </div>
      </details>
    {/if}
  {/if}
{/if}

<style>
  .pains-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .show-all {
    margin-top: 14px;
  }
  .show-all > summary {
    list-style: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-surface-elevated, #fafafa);
    font-family: var(--font-mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-secondary, var(--color-text-primary));
    user-select: none;
    transition: border-color 140ms ease, color 140ms ease;
  }
  .show-all > summary::-webkit-details-marker {
    display: none;
  }
  .show-all > summary::after {
    content: "↓";
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }
  .show-all[open] > summary::after {
    content: "↑";
  }
  .show-all > summary:hover {
    border-color: var(--color-text-secondary, var(--color-text-primary));
    color: var(--color-text-primary);
  }
  .pains-list-extra {
    margin-top: 14px;
  }
  /* Two-column pain ↔ solution layout. Aside is sticky on desktop and
     stacks BELOW the pain list on mobile so the narrative leads. */
  .pains-with-aside {
    display: grid;
    grid-template-columns: 1.15fr 1fr;
    gap: 24px;
    align-items: flex-start;
  }
  .pain-col {
    min-width: 0;
  }
  .solution-col {
    position: sticky;
    top: 80px;
    min-width: 0;
  }
  @media (max-width: 800px) {
    .pains-with-aside {
      grid-template-columns: 1fr;
      gap: 16px;
    }
    .solution-col {
      position: static;
    }
  }
</style>
