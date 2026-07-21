<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    PainPointHeroV2,
    SectionDivider,
    RepresentativeQuotesPanel,
    TopRedditThreads,
    AudienceSection,
    RelatedPainCard,
    IdeaCardV2,
    SourceCommunityChips,
    BuildCTA,
    CategoryFAQ,
    CatalogLockedSection,
    LockedListSkeleton,
    TriLegend,
  } from "$lib/components/catalog/seo";
  import ResearchCtaButton from "$lib/components/catalog/ResearchCtaButton.svelte";
  import { categoryPath } from "$lib/utils/urls";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";

  let { data } = $props();

  const pp = $derived(data.painPoint);
  const parent = $derived(pp.category.parent ?? null);

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
  const intent100 = $derived(scaleSeverity(pp.commercialIntentScore, "pain"));

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

  // Gated-item counts (non-entitled users). > 0 → render a teaser even with no
  // visible rows.
  const siblingPainsLocked = $derived(data.painPoint.siblingPainsLockedCount ?? 0);
  const relatedIdeasLocked = $derived(data.painPoint.relatedIdeasLockedCount ?? 0);
  const showSiblingPains = $derived(hasSiblingPains || siblingPainsLocked > 0);
  const showRelatedIdeas = $derived(hasRelatedIdeas || relatedIdeasLocked > 0);

  // Parent theme: match pp.themeId against data.painPoint.themes[].id. The
  // matched Theme carries `description` (mapped from Pydantic `definition`),
  // `title`, and `id` — we use all three (link target, hero hint, section 04
  // deck prose). Resolves on ~47% of pains in dev catalog; the rest see no
  // theme content (purely additive).
  const parentTheme = $derived.by(() => {
    const themeId = pp.themeId;
    if (typeof themeId !== "string" || !themeId) return null;
    const themes = data.painPoint.themes;
    if (!Array.isArray(themes)) return null;
    return themes.find((t) => t.id === themeId) ?? null;
  });

  // Pre-build the cross-page anchor href. Uses categoryPath which handles
  // both sub-niche (parent slug present) and top-level (parent null) cases —
  // both render PainPointsByTheme with #theme-{id} anchors.
  const themeAnchorHref = $derived.by<string | null>(() => {
    if (!parentTheme || !parentTheme.id) return null;
    return `${categoryPath({ slug: pp.category.slug, parentSlug: parent?.slug ?? null })}#theme-${parentTheme.id}`;
  });

  // Section 04 deck gates on theme + non-empty description. Trim-check
  // mirrors the pattern in PainPointsByTheme.svelte:45-47 so whitespace-only
  // descriptions don't render an empty deck.
  const hasThemeDeck = $derived(
    !!parentTheme && typeof parentTheme.description === "string" && parentTheme.description.trim().length > 0,
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
  const num4 = $derived(nextNum(num3, showSiblingPains));
  const num5 = $derived(nextNum(num4, showRelatedIdeas));
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
  {parentTheme}
  {themeAnchorHref}
  severity={severity100}
  commercialIntent={intent100}
  opportunity={opportunityNorm}
  qualitySignals={data.painPoint.qualitySignals}
  mentionCount={pp.mentionCount}
  sourcePlatforms={sourcePlatformChips}
  updatedAt={pp.updatedAt ?? pp.createdAt}
/>

{#if hasEvidence}
  <SectionDivider num={num1} label="Voices of the audience" />
  {#if hasSubredditSources}
    <div class="source-strip">
      <span class="source-strip-label">Sourced from</span>
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
  <AudienceSection
    segments={filteredSegments}
    signals={audienceSignals}
    categories={categoriesChips}
  />
{/if}

{#if hasSolutionApproach}
  <SectionDivider num={num3} label="Solution approach" />
  <div class="approach-card">
    <span class="approach-label">How to solve</span>
    <p>{pp.solutionApproach}</p>
  </div>
{/if}

{#if showSiblingPains}
  {@const siblings = data.painPoint.siblingPains}
  {#snippet sibCount()}
    <span>{siblings.length + siblingPainsLocked} related</span>
  {/snippet}
  <SectionDivider num={num4} label="Related pains in this theme" right={sibCount} />
  {#if hasThemeDeck && parentTheme}
    <aside class="theme-deck">
      <span class="theme-deck-kicker">Theme</span>
      {#if themeAnchorHref}
        <a class="theme-deck-name" href={themeAnchorHref}>{parentTheme.title}</a>
      {:else}
        <span class="theme-deck-name static">{parentTheme.title}</span>
      {/if}
      <p class="theme-deck-prose">{parentTheme.description}</p>
    </aside>
  {/if}
  {#if siblings.length > 0}
    <div class="sibling-list">
      {#each siblings as sp}
        <RelatedPainCard pain={sp} />
      {/each}
    </div>
  {/if}
  {#if siblingPainsLocked > 0}
    <CatalogLockedSection
      title="More pain points in this theme"
      summary={`Subscribe to unlock ${siblingPainsLocked} more validated pain point${siblingPainsLocked === 1 ? '' : 's'} in this theme.`}
      ctaHref="/unlock-catalog"
      ctaLabel={`Unlock ${siblingPainsLocked} more pain point${siblingPainsLocked === 1 ? '' : 's'}`}
    />
  {/if}
{/if}

{#if showRelatedIdeas}
  {@const related = data.painPoint.relatedIdeas}
  {#snippet relCount()}
    <span class="rel-right">
      <span class="rel-legend"><TriLegend /></span>
      <span>{related.length + relatedIdeasLocked} idea{related.length + relatedIdeasLocked === 1 ? "" : "s"}</span>
    </span>
  {/snippet}
  <SectionDivider num={num5} label="Ideas built for this pain" right={relCount} />
  <div class="idea-grid">
    {#each related as i}
      <IdeaCardV2 idea={i} />
    {/each}
    {#if relatedIdeasLocked > 0}
      <LockedListSkeleton variant="idea" count={relatedIdeasLocked} />
    {/if}
  </div>
  {#if relatedIdeasLocked > 0}
    <CatalogLockedSection
      title="More ideas built for this pain"
      summary={`Subscribe to unlock ${relatedIdeasLocked} more idea${relatedIdeasLocked === 1 ? '' : 's'} that address this pain point.`}
      ctaHref="/unlock-catalog"
      ctaLabel={`Unlock ${relatedIdeasLocked} more idea${relatedIdeasLocked === 1 ? '' : 's'}`}
    />
  {/if}
{/if}

<!-- FAQ — supplementary block before the CTA, paired with FAQPage JSON-LD
     (gated on painPoint.faqJson.length >= 2). Anchored on the pain title
     in the LLM prompt — that's a real search phrase. -->
{#if (data.painPoint.faqJson?.length ?? 0) >= 2}
  <CategoryFAQ items={data.painPoint.faqJson ?? []} />
{/if}

<BuildCTA
  headline="Build a solution for this pain?"
  body="Generate and validate solution ideas for this exact pain point. You'll review the candidates and pick which to take into deep research — sourced from real Reddit and Hacker News conversations."
  secondaryLabel={`More in ${pp.category?.name ?? 'catalog'}`}
  secondaryHref={categoryPath({
    slug: pp.category.slug,
    parentSlug: parent?.slug ?? null,
  })}
>
  {#snippet primary()}
    <ResearchCtaButton kind="pain" slug={pp.slug} label="Explore solutions for this pain" subject={pp.title} />
  {/snippet}
</BuildCTA>

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
  /* Exception to the "all kickers colored" rule: this kicker sits directly
     next to SourceChip data that uses platform-identity accent colors
     (orange for Reddit/HN, blue for Twitter/Discord). A colored kicker
     would compete with the chips for the eye instead of introducing them.
     Stays muted so the chips own the color hierarchy. */
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
    color: var(--color-accent-muted);
    margin-bottom: 10px;
  }

  /* Solution approach card — bordered prose block. */
  .approach-card {
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-surface-elevated);
    border-radius: 6px;
    padding: 18px 22px;
    margin: 0 0 36px;
  }
  .approach-label {
    display: block;
    font-family: var(--font-mono);
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

  /* Editorial sub-heading inside section 04. Mono kicker → linked heading
     → italic muted prose — frames the related-pains list with the theme
     name + description. NOT a deck-note pill (that idiom is for overview
     prose); this is a journalistic sub-section header. */
  .theme-deck {
    display: block;
    max-width: 780px;
    margin: 0 0 20px;
  }
  .theme-deck-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-accent-muted);
    margin-bottom: 4px;
  }
  .theme-deck-name {
    display: inline-block;
    font-size: 15px;
    font-weight: 600;
    line-height: 1.3;
    color: var(--color-text-primary);
    text-decoration: none;
    margin-bottom: 6px;
    transition: color 120ms ease;
  }
  a.theme-deck-name:hover,
  a.theme-deck-name:focus-visible {
    color: var(--color-accent);
    outline: none;
  }
  a.theme-deck-name:focus-visible {
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .theme-deck-name.static {
    cursor: default;
  }
  .theme-deck-prose {
    margin: 0;
    font-size: 13.5px;
    line-height: 1.65;
    color: var(--color-text-muted);
    font-style: italic;
    text-wrap: pretty;
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
  /* Ring-color legend + count in the section divider's right slot. Legend
     hides on narrow widths where the slot can't fit three labels. */
  .rel-right {
    display: inline-flex;
    align-items: center;
    gap: 14px;
  }
  @media (max-width: 768px) {
    .idea-grid {
      grid-template-columns: 1fr;
    }
    .rel-legend {
      display: none;
    }
  }
</style>
