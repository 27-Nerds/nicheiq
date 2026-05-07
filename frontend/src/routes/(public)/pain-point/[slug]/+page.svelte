<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    PainPointHeroV2,
    SectionDivider,
    RepresentativeQuotesPanel,
    TopRedditThreads,
    AudienceSegmentCard,
    AudienceSignalsSection,
    RelatedPainCard,
    IdeaCardV2,
    SourceCommunityChips,
    CatalogBand,
    BuildCTA,
    Chip,
  } from "$lib/components/catalog/seo";
  import { categoryPath } from "$lib/utils/urls";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";

  let { data } = $props();

  const pp = $derived(data.painPoint);
  const parent = $derived(pp.category.parent ?? null);

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  const trail = $derived.by<Array<{ label: string; href?: string }>>(() => {
    const stops: Array<{ label: string; href?: string }> = [
      { label: "Home", href: "/" },
      { label: "Ideas", href: "/ideas" },
    ];
    if (parent) {
      stops.push({ label: parent.name, href: `/ideas/${parent.slug}` });
    }
    stops.push({
      label: pp.category.name,
      href: categoryPath({
        slug: pp.category.slug,
        parentSlug: parent?.slug ?? null,
      }),
    });
    stops.push({ label: pp.title });
    return stops;
  });

  // Pydantic severity + WTP are 0-1 (verified at
  // src/nicheiq/models/pain_point.py:202,205); reuse scaleSeverity(value,
  // 'pain') for both since the math is identical.
  const severity100 = $derived(scaleSeverity(pp.severityScore, "pain"));
  const wtp100 = $derived(scaleSeverity(pp.willingnessToPayScore, "pain"));

  // Opportunity normalization moved from PainStatStrip → route level so the
  // hero aside doesn't re-implement the high/med/low coercion.
  const opportunityNorm = $derived.by<'high' | 'medium' | 'low' | null>(() => {
    const raw = pp.opportunityLevel;
    if (typeof raw !== 'string') return null;
    const u = raw.trim().toLowerCase();
    if (u === 'high') return 'high';
    if (u === 'medium' || u === 'med') return 'medium';
    if (u === 'low') return 'low';
    return null;
  });

  // Filter the niche-wide audience grid to only the segments affected by
  // THIS pain (case-insensitive substring match so minor naming differences
  // between affected_segments and audience_segments still line up).
  const affectedSegmentNames = $derived(
    Array.isArray(pp.affectedSegments)
      ? pp.affectedSegments
          .filter((s): s is string => typeof s === "string" && s.trim() !== "")
          .map((s) => s.trim().toLowerCase())
      : [],
  );
  const filteredSegments = $derived.by(() => {
    const all = Array.isArray(data.painPoint.audienceSegments)
      ? data.painPoint.audienceSegments
      : [];
    if (affectedSegmentNames.length === 0) return [];
    return all.filter((seg) => {
      const name = seg.name?.toLowerCase() ?? "";
      return affectedSegmentNames.some(
        (a) => name.includes(a) || a.includes(name),
      );
    });
  });

  const categoriesChips = $derived(
    Array.isArray(pp.categories)
      ? pp.categories.filter((c): c is string => typeof c === "string")
      : [],
  );

  const sourcePlatformChips = $derived(
    Array.isArray(pp.sourcePlatforms)
      ? pp.sourcePlatforms.filter((s): s is string => typeof s === "string")
      : [],
  );

  // Audience signals: pass the whole object to the shared component instead
  // of cherry-picking 4 of 8 fields inline. AudienceSignalsSection compact
  // renders all 8 (vocabulary, frustrations, currentTools, communityHubs,
  // recommendedChannels, messagingFrameworks, contentPreferences,
  // earlyAdopterTactics) with consistent chrome.
  const audienceSignals = $derived(data.painPoint.audienceSignals);
  const hasAudienceSignals = $derived.by(() => {
    const sig = audienceSignals;
    if (!sig) return false;
    return (
      (sig.vocabulary?.length ?? 0) > 0 ||
      (sig.frustrations?.length ?? 0) > 0 ||
      (sig.currentTools?.length ?? 0) > 0 ||
      (sig.communityHubs?.length ?? 0) > 0 ||
      (sig.recommendedChannels?.length ?? 0) > 0 ||
      (sig.messagingFrameworks?.length ?? 0) > 0 ||
      !!sig.contentPreferences ||
      !!sig.earlyAdopterTactics
    );
  });

  // Section 01 evidence: now broader than the legacy hasQuotes gate.
  // Section can carry value when ANY of representativeQuotes ∪ quoteSources
  // ∪ topRedditThreads is populated.
  const hasQuoteSources = $derived(
    Array.isArray(data.painPoint.quoteSources) && data.painPoint.quoteSources.length > 0,
  );
  const hasRepresentativeQuotes = $derived(
    Array.isArray(pp.representativeQuotes) && pp.representativeQuotes.length > 0,
  );
  const hasTopThreads = $derived(
    Array.isArray(data.painPoint.topRedditThreads) && data.painPoint.topRedditThreads.length > 0,
  );
  const hasEvidence = $derived(hasQuoteSources || hasRepresentativeQuotes || hasTopThreads);

  // Subreddit sources surface as a community-level attribution strip directly
  // under the section 01 divider. Distinct from sourcePlatformChips (which is
  // platform-level: ["reddit", "hackernews"] etc.) — this is per-subreddit
  // with post counts (r/3Dmodeling · 10).
  const hasSubredditSources = $derived(
    Array.isArray(data.painPoint.subredditSources) && data.painPoint.subredditSources.length > 0,
  );

  // Section 02 audience: rebuilt gate. Categories (taxonomic broad) +
  // segments (audience personas) + signals (behavioral details) — at least
  // one must be populated. The legacy raw-affectedSegments fallback render
  // is dropped; its information is carried by segments + signals.
  const hasCategories = $derived(categoriesChips.length > 0);
  const hasSegments = $derived(filteredSegments.length > 0);
  const hasAudience = $derived(hasCategories || hasSegments || hasAudienceSignals);

  const hasSolutionApproach = $derived(
    typeof pp.solutionApproach === "string" && pp.solutionApproach.trim().length > 0,
  );

  const hasSiblingPains = $derived(
    Array.isArray(data.painPoint.siblingPains) && data.painPoint.siblingPains.length > 0,
  );
  const hasRelatedIdeas = $derived(
    Array.isArray(data.painPoint.relatedIdeas) && data.painPoint.relatedIdeas.length > 0,
  );

  // Section numbering kept stable: increment only when a section actually
  // renders. Hero score panel renders all pain stats; subreddit attribution
  // is a strip under section 01, not a numbered section.
  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  const num1 = $derived(nextNum(0, hasEvidence));
  const num2 = $derived(nextNum(num1, hasAudience));
  const num3 = $derived(nextNum(num2, hasSolutionApproach));
  const num4 = $derived(nextNum(num3, hasSiblingPains));
  const num5 = $derived(nextNum(num4, hasRelatedIdeas));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<PainPointHeroV2
  painPointId={pp.id}
  title={pp.title}
  description={pp.description}
  categoryName={parent?.name ?? pp.category.name}
  subName={parent ? pp.category.name : null}
  rankInfo={data.painPoint.rankInfo}
  severity={severity100}
  willingnessToPay={wtp100}
  opportunity={opportunityNorm}
  qualitySignals={data.painPoint.qualitySignals}
  mentionCount={pp.mentionCount}
  sourcePlatforms={sourcePlatformChips}
/>

{#if hasEvidence}
  <SectionDivider num={num1} label="Voices of the audience" />
  {#if hasSubredditSources}
    <div class="source-strip">
      <span class="source-strip-label">↗ Sourced from</span>
      <SourceCommunityChips sources={data.painPoint.subredditSources ?? []} />
    </div>
  {/if}
  {#if hasQuoteSources || hasRepresentativeQuotes}
    <RepresentativeQuotesPanel
      quotes={pp.representativeQuotes ?? []}
      quoteSources={data.painPoint.quoteSources ?? null}
      sourcePlatforms={pp.sourcePlatforms ?? null}
      mentionCount={pp.mentionCount}
    />
  {/if}
  {#if hasTopThreads}
    <div class="top-threads-wrap">
      <span class="top-threads-label">Top threads</span>
      <TopRedditThreads threads={data.painPoint.topRedditThreads ?? []} limit={3} />
    </div>
  {/if}
{/if}

{#if hasAudience}
  <SectionDivider num={num2} label="Who feels this pain" />
  {#if hasCategories}
    <div class="type-strip">
      <span class="type-label">Type</span>
      <div class="type-chips">
        {#each categoriesChips as c}
          <Chip label={c} />
        {/each}
      </div>
    </div>
  {/if}
  {#if hasSegments}
    <CatalogBand>
      <div class="seg-grid">
        {#each filteredSegments as s}
          <AudienceSegmentCard segment={s} />
        {/each}
      </div>
    </CatalogBand>
  {/if}
  {#if hasAudienceSignals && audienceSignals}
    <div class="audience-signals-wrap">
      <AudienceSignalsSection signals={audienceSignals} compact />
    </div>
  {/if}
{/if}

{#if hasSolutionApproach}
  <SectionDivider num={num3} label="Solution approach" />
  <div class="approach-card">
    <span class="approach-label">How to solve</span>
    <p>{pp.solutionApproach}</p>
  </div>
{/if}

{#if hasSiblingPains}
  {@const siblings = data.painPoint.siblingPains}
  {#snippet sibCount()}
    <span>{siblings.length} related</span>
  {/snippet}
  <SectionDivider num={num4} label="Related pains in this theme" right={sibCount} />
  <div class="sibling-list">
    {#each siblings as sp}
      <RelatedPainCard pain={sp} />
    {/each}
  </div>
{/if}

{#if hasRelatedIdeas}
  {@const related = data.painPoint.relatedIdeas}
  {#snippet relCount()}
    <span>{related.length} idea{related.length === 1 ? "" : "s"}</span>
  {/snippet}
  <SectionDivider num={num5} label="Ideas built for this pain" right={relCount} />
  <div class="idea-grid">
    {#each related as i}
      <IdeaCardV2 idea={i} />
    {/each}
  </div>
{/if}

<BuildCTA
  {ctaHref}
  headline="Build a solution for this pain?"
  body="Generate a 30-day GTM plan, landing-page copy, and outbound list — tuned to the audience that's already complaining."
  secondaryLabel={`More in ${pp.category?.name ?? 'catalog'}`}
  secondaryHref={categoryPath({
    slug: pp.category.slug,
    parentSlug: parent?.slug ?? null,
  })}
/>

<style>
  /* Source-attribution strip under section 01 — community chips appear
     before the evidence they attribute, mirroring the /idea/[slug] pattern. */
  .source-strip {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin: -8px 0 18px;
    padding-bottom: 12px;
    border-bottom: 1px dashed var(--color-border);
  }
  .source-strip-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  /* Top discussions sub-block within section 01 — small mono kicker before
     the threads list. The list itself comes from <TopRedditThreads>. */
  .top-threads-wrap {
    margin-top: 20px;
    margin-bottom: 36px;
  }
  .top-threads-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-bottom: 10px;
  }

  /* Categories chip strip at the top of section 02 — taxonomic tags,
     editorially distinct from segments (which are personas) and signals
     (which are behavioral). Reads as inline metadata. */
  .type-strip {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
    margin: 0 0 16px;
  }
  .type-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }
  .type-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  /* Segment grid inside CatalogBand — same pattern as /idea/[slug]
     audience section. Three columns at desktop, collapsing on narrower
     viewports. */
  .seg-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }
  .seg-grid:has(> :only-child) {
    grid-template-columns: 1fr;
    max-width: 600px;
  }
  .seg-grid:has(> :nth-child(2):last-child) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    max-width: 920px;
  }
  @media (max-width: 768px) {
    .seg-grid {
      grid-template-columns: 1fr;
    }
  }

  /* Audience signals card sits below the segments band with a small gap. */
  .audience-signals-wrap {
    margin-top: 24px;
    margin-bottom: 36px;
  }

  /* Solution approach card — accent-rail prose block. */
  .approach-card {
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    background: var(--color-surface-elevated, #fafafa);
    border-radius: 0 6px 6px 0;
    padding: 18px 22px;
    margin: 0 0 36px;
  }
  .approach-label {
    display: block;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-accent-muted);
    margin-bottom: 8px;
  }
  .approach-card p {
    margin: 0;
    font-size: 14px;
    line-height: 1.6;
    color: var(--color-text-primary);
  }

  .sibling-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 36px;
  }
  .idea-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-bottom: 36px;
  }
  @media (max-width: 768px) {
    .idea-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
