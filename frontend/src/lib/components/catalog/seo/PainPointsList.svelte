<script lang="ts">
  import PainPointCardV2 from "./PainPointCardV2.svelte";

  // Renders a list of pain cards. Used on idea-detail page after the user
  // has chosen the catalog rebuild's "separate lists, no row pairing" model.
  // Pain points come from researchContext.detailedPainPoints (pipeline) so
  // shape isn't the same as CatalogPainPoint — adapt here.

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
  }

  let { pains }: Props = $props();

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
  const list = $derived(normalize(pains) as never as import("$lib/types/catalog-landing.js").PainPointPreview[]);
</script>

{#if list.length > 0}
  <div class="pains-list">
    {#each list as p}
      <PainPointCardV2 pain={p} />
    {/each}
  </div>
{/if}

<style>
  .pains-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
</style>
