<script lang="ts">
  import type {
    Theme,
    AudienceSegment,
    AudienceSignals,
    QualitySignals,
    SubredditSource,
  } from "$lib/types/publicCatalog.js";
  import { scaleSeverity, severityRailTier } from "$lib/types/publicCatalog.js";
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import { editionLabel, isFallbackEdition } from "$lib/seo/edition";
  import SeverityBar from "./SeverityBar.svelte";
  import CatalogTable from "./CatalogTable.svelte";

  interface Props {
    name: string;
    /** "sub-niche" gates subreddit-names, tools, and segments prose. */
    kind: "niche" | "sub-niche";
    subredditSources?: SubredditSource[] | null;
    sourceCommunities?: number | null;
    contentItemsMined?: number | null;
    topPainPoints?: PainPointPreview[] | null;
    totalPainPoints?: number | null;
    themes?: Theme[] | null;
    audienceSignals?: AudienceSignals | null;
    audienceSegments?: AudienceSegment[] | null;
    qualitySignals?: QualitySignals | null;
    latestModifiedAt?: string | null;
  }

  let {
    name,
    kind,
    subredditSources = null,
    sourceCommunities = null,
    contentItemsMined = null,
    topPainPoints = null,
    totalPainPoints = null,
    themes = null,
    audienceSignals = null,
    audienceSegments = null,
    qualitySignals = null,
    latestModifiedAt = null,
  }: Props = $props();

  const isSub = $derived(kind === "sub-niche");

  const topPains = $derived((topPainPoints ?? []).slice(0, 3));

  const themeTitleById = $derived.by(() => {
    const map = new Map<string, string>();
    for (const t of themes ?? []) {
      if (t.id) map.set(t.id, t.title);
    }
    return map;
  });

  const topSubreddits = $derived(
    isSub ? (subredditSources ?? []).slice(0, 3).map((s) => s.name) : [],
  );
  const tools = $derived(
    isSub ? (audienceSignals?.currentTools ?? []).slice(0, 4) : [],
  );
  const segments = $derived(
    isSub ? (audienceSegments ?? []).slice(0, 3).map((s) => s.name) : [],
  );

  function joinList(parts: string[]): string {
    if (parts.length === 0) return "";
    if (parts.length === 1) return parts[0];
    if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
    return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`;
  }

  const subredditPhrase = $derived(joinList(topSubreddits));
  const toolPhrase = $derived(joinList(tools));

  const themeCount = $derived(themes?.length ?? 0);
  const previewPainCount = $derived(topPains.length);
  const totalPains = $derived(totalPainPoints ?? topPainPoints?.length ?? 0);
  const communities = $derived(sourceCommunities ?? 0);
  const discussions = $derived(contentItemsMined ?? 0);

  const edition = $derived(editionLabel(latestModifiedAt));
  const isStale = $derived(isFallbackEdition(edition));
  const editionUpper = $derived(edition.toUpperCase());

  // Percent form — matches the QualityTierBadge's "GOLD · 91%" voice; a raw
  // 0-1 decimal ("0.89") reads as an internal value in user-facing prose.
  const confidencePct = $derived(
    qualitySignals?.confidenceScore != null
      ? Math.round(qualitySignals.confidenceScore * 100)
      : null,
  );

  const nicheWord = $derived(isSub ? "sub-niche" : "niche");

  const hasContent = $derived(previewPainCount > 0 && communities > 0);

</script>

{#if hasContent}
  <section class="nss" aria-label="Niche data summary">
    <!-- Almanac kicker — mirrors CatalogIndexHero's "EDITION · MAY 2026" voice
         so this footer reads as backmatter from the same publication. -->
    <header class="nss-kicker" aria-hidden="true">
      <span class="k-mark">◆</span>
      <span class="k-edition">{isStale ? "LATEST EDITION" : `EDITION · ${editionUpper}`}</span>
      <span class="k-line"></span>
      <span class="k-label">DATA INDEX · {isSub ? "SUB-NICHE" : "NICHE"} BACKMATTER</span>
    </header>

    <!-- Editorial lede. First sentence stands alone (drop-style); the
         research-coverage sentence follows on its own block so the
         numerals line up visually. -->
    <p class="nss-lede">
      The <strong class="nss-name">{name}</strong> market is tracked across
      <span class="nss-fig">{communities.toLocaleString()}</span>
      active {communities === 1 ? "community" : "communities"}{#if isSub && subredditPhrase}{" "}including <em>{subredditPhrase}</em>{/if}.
    </p>
    <p class="nss-prose">
      {#if isStale}Recent research{:else}The <em>{edition}</em> research{/if}{" "}{#if discussions > 0}covers <span class="nss-fig">{discussions.toLocaleString()}</span> discussions,{" "}{/if}{#if discussions > 0}revealing{:else}reveals{/if}{" "}<span class="nss-fig">{previewPainCount}</span> top-ranked pain {previewPainCount === 1 ? "point" : "points"}{#if totalPains > previewPainCount}{" "}(of <span class="nss-fig">{totalPains.toLocaleString()}</span> tracked){/if}{#if themeCount > 0}{" "}across <span class="nss-fig">{themeCount}</span> {themeCount === 1 ? "theme" : "themes"}{/if}.
    </p>

    <!-- Pain ledger — wraps CatalogTable so the chrome (mono uppercase header
         bar, hairline rows, tier rail) matches the canonical
         PainPointRankTable used in the body of the page. Theme attribution
         renders as a mono sub-line under the title (saved-table idiom) —
         a dedicated 160px column truncated every real theme name and showed
         em-dashes on legacy rows with null themeIds. -->
    <div class="nss-ledger" aria-label="Top ranked pain points">
      <CatalogTable>
        <div class="ct-head nss-row">
          <span class="cell-rank">#</span>
          <span>Pain point</span>
          <span class="ar head-mentions">Mentions</span>
          <span class="ar">Severity</span>
        </div>
        {#each topPains as pp, i (pp.id)}
          {@const sev = scaleSeverity(pp.severityScore, "pain")}
          {@const tier = severityRailTier(sev)}
          {@const themeTitle = pp.themeId
            ? themeTitleById.get(pp.themeId)
            : null}
          <div class="ct-row nss-row" data-tier={tier}>
            <span class="cell-rank">{String(i + 1).padStart(2, "0")}</span>
            <span class="cell-title">
              {pp.title}
              {#if themeTitle}
                <span class="cell-theme-sub">{themeTitle}</span>
              {/if}
            </span>
            <span class="cell-mentions">{pp.mentionCount.toLocaleString()}</span>
            <span class="cell-severity"><SeverityBar value={sev} showTier={false} /></span>
          </div>
        {/each}
      </CatalogTable>
    </div>

    <!-- Tools / segments — sentence prose per spec. Sub-niche only because
         these fields flatten from a single research context and don't
         describe parent niches truthfully. -->
    {#if isSub && (toolPhrase || segments.length > 0)}
      <p class="nss-prose">
        {#if toolPhrase}The most common tools used in this {nicheWord} include <em>{toolPhrase}</em>.{/if}{#if segments.length > 0}{" "}{#if segments.length > 1}Primary audience segments range from <em>{segments[0]}</em> to <em>{segments[1]}</em>{#if segments.length > 2}{" "}and <em>{segments[2]}</em>{/if}.{:else}Primary audience segment: <em>{segments[0]}</em>.{/if}{/if}
      </p>
    {/if}

    <!-- Research-metadata footer sentence. Quiet mono baseline so it reads
         as a colophon under the editorial body without competing. -->
    <p class="nss-meta">
      {#if confidencePct != null}Research confidence: <span class="nss-fig">{confidencePct}%</span>.{" "}{/if}{#if discussions > 0}Based on <span class="nss-fig">{discussions.toLocaleString()}</span> items analyzed across <span class="nss-fig">{communities.toLocaleString()}</span> {communities === 1 ? "community" : "communities"}.{" "}{/if}Updated <em>{isStale ? "recently" : edition}</em>.
    </p>
  </section>
{/if}

<style>
  /* ───────────────────────────────────────────────────────────────
     Almanac backmatter. Mirrors CatalogIndexHero kicker + Section-
     Divider chapter chrome to bookend the page with the same voice.
     Bordered "card" shell so it reads as a distinct artefact rather
     than just trailing prose.
     ─────────────────────────────────────────────────────────────── */
  .nss {
    margin: 56px 0 32px;
    padding: 28px 32px 24px;
    background: var(--color-bg-base, #fafafa);
    border: 1px solid var(--color-border);
    border-radius: 10px;
    position: relative;
  }
  /* No top accent stripe — the partial-width orange rail read as a stray
     loading bar above the card, and accent stripes on wrapper zones are
     against the catalog conventions. The ◆ EDITION kicker carries the
     orange signature. */

  /* ── Kicker (top dateline) ───────────────────────────────────── */
  .nss-kicker {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-bottom: 22px;
  }
  .k-mark {
    color: var(--color-accent);
    font-size: 9px;
    line-height: 1;
  }
  .k-edition {
    color: var(--color-accent);
    font-weight: 700;
  }
  .k-line {
    flex: 1;
    height: 1px;
    background: var(--color-border);
  }
  .k-label {
    color: var(--color-text-muted);
  }

  /* ── Lede / prose ────────────────────────────────────────────── */
  .nss-lede {
    margin: 0 0 10px;
    font-size: 16px;
    line-height: 1.55;
    color: var(--color-text-primary);
    max-width: 760px;
    letter-spacing: -0.005em;
  }
  .nss-prose {
    margin: 0 0 24px;
    font-size: 14px;
    line-height: 1.65;
    color: var(--color-text-secondary, var(--color-text-primary));
    max-width: 760px;
  }
  /* Plain semibold — the orange mono figures carry the sentence's accent
     rhythm; a highlighter smear behind the name competed with them and was
     a one-off device (everything else here uses dotted-underline em). */
  .nss-name {
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .nss-fig {
    font-family: var(--font-mono);
    font-feature-settings: "tnum" 1, "calt" 1;
    color: var(--color-accent-dark);
    font-weight: 700;
    font-size: 0.95em;
    padding: 0 1px;
  }
  .nss-lede em,
  .nss-prose em {
    font-style: normal;
    color: var(--color-text-primary);
    font-weight: 500;
    border-bottom: 1px dotted var(--color-border-emphasis);
    padding-bottom: 1px;
  }

  /* ── Pain ledger ─────────────────────────────────────────────── */
  .nss-ledger {
    margin: 0 0 24px;
  }
  /* Grid template shared by header + body rows. Compact-but-honest
     proportions; pain title (with optional theme sub-line) takes the bulk,
     mentions / severity tight on the right. */
  .nss-row {
    grid-template-columns: 28px 1fr 72px 130px;
    gap: 14px;
  }
  .ar {
    text-align: right;
  }
  .cell-rank {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 700;
    font-feature-settings: "tnum" 1;
  }
  .cell-title {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 13.5px;
    color: var(--color-text-primary);
    font-weight: 500;
    line-height: 1.4;
    min-width: 0;
  }
  /* Theme attribution sub-line — same idiom as the saved table's
     category sub-label. Full row width means real theme names fit. */
  .cell-theme-sub {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    font-weight: 500;
  }
  .cell-mentions {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
    text-align: right;
    font-feature-settings: "tnum" 1;
  }
  .cell-severity {
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }

  /* ── Meta sentence (footer) ──────────────────────────────────── */
  .nss-meta {
    margin: 20px 0 0;
    padding-top: 18px;
    border-top: 1px solid var(--color-border);
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--color-text-muted);
    max-width: 760px;
    font-feature-settings: "tnum" 1, "calt" 1;
  }

  /* ── Responsive ──────────────────────────────────────────────── */
  @media (max-width: 720px) {
    .nss {
      padding: 22px 18px 18px;
      margin: 40px 0 24px;
    }
    .nss-lede {
      font-size: 15px;
    }
    .nss-prose {
      font-size: 13.5px;
    }
    .nss-row {
      grid-template-columns: 24px 1fr 80px;
    }
    .cell-mentions,
    .head-mentions {
      display: none;
    }
    .k-label {
      display: none;
    }
  }
  @media (max-width: 480px) {
    .nss-kicker {
      gap: 8px;
      font-size: 10px;
    }
  }
</style>
