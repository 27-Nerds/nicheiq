<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    PainPointHeroV2,
    PainStatStrip,
    SectionDivider,
    RepresentativeQuotesPanel,
    AudienceSegmentCard,
    RelatedPainCard,
    IdeaCardV2,
    SourceCommunityChips,
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

  // Filter the niche-wide audience grid to only the segments affected by
  // THIS pain (case-insensitive substring match so minor naming differences
  // between affected_segments and audience_segments still line up). Falls
  // back to a chip-strip of raw affected_segments when no matches.
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

  // Section visibility flags — let `{#if}` wrap each section + its divider so
  // numbered sections never orphan a header without body.
  const hasQuotes = $derived(
    Array.isArray(pp.representativeQuotes) && pp.representativeQuotes.length > 0,
  );
  const hasAudience = $derived(
    filteredSegments.length > 0 || affectedSegmentNames.length > 0 || categoriesChips.length > 0,
  );
  const hasSolutionApproach = $derived(
    typeof pp.solutionApproach === "string" && pp.solutionApproach.trim().length > 0,
  );

  // GTM-relevant audience signals on the pain page. The niche-wide
  // AudienceSignals payload already rides on the response.
  const sig = $derived(data.painPoint.audienceSignals);
  const messagingFrameworks = $derived(
    Array.isArray(sig?.messagingFrameworks) ? sig.messagingFrameworks.filter((s): s is string => typeof s === "string") : [],
  );
  const recommendedChannels = $derived(
    Array.isArray(sig?.recommendedChannels) ? sig.recommendedChannels.filter((s): s is string => typeof s === "string") : [],
  );
  const contentPreferences = $derived(
    typeof sig?.contentPreferences === "string" && sig.contentPreferences.trim() !== "" ? sig.contentPreferences : null,
  );
  const earlyAdopterTactics = $derived(
    typeof sig?.earlyAdopterTactics === "string" && sig.earlyAdopterTactics.trim() !== "" ? sig.earlyAdopterTactics : null,
  );
  const hasGtmSignals = $derived(
    messagingFrameworks.length > 0 ||
      recommendedChannels.length > 0 ||
      contentPreferences !== null ||
      earlyAdopterTactics !== null,
  );

  const hasSiblingPains = $derived(
    Array.isArray(data.painPoint.siblingPains) && data.painPoint.siblingPains.length > 0,
  );
  const hasRelatedIdeas = $derived(
    Array.isArray(data.painPoint.relatedIdeas) && data.painPoint.relatedIdeas.length > 0,
  );

  // Section numbering kept stable: increment only when a section actually
  // renders. Build the running counter via $derived so adding/removing a
  // section doesn't require manually re-numbering literals.
  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  const num1 = $derived(nextNum(0, hasQuotes));
  const num2 = $derived(nextNum(num1, hasAudience));
  // "Where it's reported" is folded into PainStatStrip — no top-level section.
  const num3 = $derived(nextNum(num2, hasSolutionApproach || hasGtmSignals));
  const num4 = $derived(nextNum(num3, hasSiblingPains));
  const num5 = $derived(nextNum(num4, hasRelatedIdeas));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<PainPointHeroV2
  title={pp.title}
  description={pp.description}
  categoryName={parent?.name ?? pp.category.name}
  subName={parent ? pp.category.name : null}
  rankInfo={data.painPoint.rankInfo}
/>

<PainStatStrip
  severity={severity100}
  severityRaw={pp.severityScore}
  willingnessToPay={wtp100}
  opportunityLevel={pp.opportunityLevel}
  mentionCount={pp.mentionCount}
  sourcePlatforms={sourcePlatformChips}
/>

{#if hasQuotes}
  <SectionDivider num={num1} label="Voices of the audience" />
  <RepresentativeQuotesPanel
    quotes={pp.representativeQuotes ?? []}
    sourcePlatforms={pp.sourcePlatforms ?? null}
    mentionCount={pp.mentionCount}
  />
{/if}

{#if hasAudience}
  <SectionDivider num={num2} label="Who feels this pain" />
  {#if categoriesChips.length > 0}
    <div class="chip-strip">
      {#each categoriesChips as c}
        <Chip label={c} />
      {/each}
    </div>
  {/if}
  {#if filteredSegments.length > 0}
    <div class="seg-grid">
      {#each filteredSegments as s}
        <AudienceSegmentCard segment={s} />
      {/each}
    </div>
  {:else if affectedSegmentNames.length > 0}
    {@const rawSegs = pp.affectedSegments ?? []}
    <div class="chip-strip muted">
      {#each rawSegs as s}
        <Chip label={s} />
      {/each}
    </div>
  {/if}
{/if}

{#if hasSolutionApproach || hasGtmSignals}
  <SectionDivider num={num3} label="Solution approach" />
  {#if hasSolutionApproach}
    <div class="approach-card">
      <span class="approach-label">How to solve</span>
      <p>{pp.solutionApproach}</p>
    </div>
  {/if}
  {#if hasGtmSignals}
    <div class="gtm-grid">
      {#if messagingFrameworks.length > 0}
        <div class="gtm-row">
          <span class="gtm-label">How to message</span>
          <div class="chip-strip inline">
            {#each messagingFrameworks as m}
              <Chip label={m} />
            {/each}
          </div>
        </div>
      {/if}
      {#if recommendedChannels.length > 0}
        <div class="gtm-row">
          <span class="gtm-label">Where to reach them</span>
          <div class="chip-strip inline">
            {#each recommendedChannels as c}
              <Chip label={c} />
            {/each}
          </div>
        </div>
      {/if}
      {#if contentPreferences}
        <div class="gtm-row">
          <span class="gtm-label">Content they consume</span>
          <p class="gtm-prose">{contentPreferences}</p>
        </div>
      {/if}
      {#if earlyAdopterTactics}
        <div class="gtm-row">
          <span class="gtm-label">Early-adopter tactics</span>
          <p class="gtm-prose">{earlyAdopterTactics}</p>
        </div>
      {/if}
    </div>
  {/if}
{/if}

{#if hasSiblingPains}
  {@const siblings = data.painPoint.siblingPains}
  {#snippet sibCount()}
    <span>{siblings.length} sibling{siblings.length === 1 ? "" : "s"}</span>
  {/snippet}
  <SectionDivider num={num4} label="Sibling pain points" right={sibCount} />
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

{#if data.painPoint.subredditSources && data.painPoint.subredditSources.length > 0}
  <div class="niche-source">
    <span class="niche-label">Niche source signal</span>
    <SourceCommunityChips sources={data.painPoint.subredditSources} />
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
  .chip-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 0 0 24px;
  }
  .chip-strip.muted {
    margin-top: 12px;
  }
  .seg-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }
  /* Responsive sizing when filtered count is 1 or 2.
     `:has()` is supported in Chrome 105+, Safari 15.4+, Firefox 121+. */
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
  /* GTM signals grid below the solution approach card. */
  .gtm-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
    margin-bottom: 36px;
  }
  .gtm-row {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 14px;
    align-items: baseline;
    padding: 10px 0;
    border-top: 1px solid var(--color-border);
  }
  .gtm-row:first-child {
    border-top: none;
    padding-top: 0;
  }
  .gtm-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .gtm-prose {
    margin: 0;
    font-size: 13px;
    line-height: 1.55;
    color: var(--color-text-primary);
  }
  .chip-strip.inline {
    margin: 0;
  }
  @media (max-width: 700px) {
    .gtm-row {
      grid-template-columns: 1fr;
      gap: 6px;
    }
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
  .niche-source {
    margin-top: 32px;
    padding-top: 18px;
    border-top: 1px solid var(--color-border);
    opacity: 0.78;
  }
  .niche-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
</style>
