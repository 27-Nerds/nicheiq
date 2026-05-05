<script lang="ts">
  import type { Theme } from "$lib/types/publicCatalog.js";
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import ThemeCard from "./ThemeCard.svelte";
  import PainPointMiniRow from "./PainPointMiniRow.svelte";

  // List of theme cards. Pain points grouped under their parent theme via
  // `themeId === theme.id`. Renders <ThemeCard> per populated theme; empty
  // themes render in a muted footer aside; unclassified pain points (only
  // when showPainRows=true) render in a simple "Other pain points" bucket.

  interface Props {
    themes: Theme[];
    painPoints: PainPointPreview[];
    /** When true, render every associated pain point under each theme card.
     *  Used by category-page mode (currently unused on routes; kept for
     *  forward compat). When false, behavior is governed by topPainRowsLimit. */
    showPainRows?: boolean;
    /** Sub-niche-page preview cap. When set with `showPainRows=false`,
     *  each theme card renders the top-N pains by severity + a
     *  "View all pain points →" link to the ranked-pain section. */
    topPainRowsLimit?: number;
    /** Offset added to each theme's display number. Defaults to 0 →
     *  themes start at "THEME 01". Sub-niche page passes 1 so other-themes
     *  start at "THEME 02" after the dominant theme. */
    displayOffset?: number;
  }

  let {
    themes,
    painPoints,
    showPainRows = true,
    topPainRowsLimit,
    displayOffset = 0,
  }: Props = $props();

  // Group pain points by themeId. Build the lookup once for O(1) access.
  const grouped = $derived.by(() => {
    const byTheme = new Map<string, PainPointPreview[]>();
    const unclassified: PainPointPreview[] = [];
    const themeIds = new Set(themes.map((t) => t.id).filter((id): id is string => !!id));
    for (const pp of painPoints) {
      if (pp.themeId && themeIds.has(pp.themeId)) {
        const existing = byTheme.get(pp.themeId) ?? [];
        existing.push(pp);
        byTheme.set(pp.themeId, existing);
      } else {
        unclassified.push(pp);
      }
    }
    for (const list of byTheme.values()) {
      list.sort((a, b) => b.severityScore - a.severityScore);
    }
    unclassified.sort((a, b) => b.severityScore - a.severityScore);
    return { byTheme, unclassified };
  });

  const populatedThemes = $derived(
    themes.filter((t) => t.id && (grouped.byTheme.get(t.id)?.length ?? 0) > 0),
  );
  const emptyThemes = $derived(
    themes.filter((t) => !t.id || (grouped.byTheme.get(t.id)?.length ?? 0) === 0),
  );

  /**
   * Decide which pain points to pass to a ThemeCard based on the current
   * mode (showPainRows + topPainRowsLimit). Caller-controlled slicing keeps
   * ThemeCard simple — it just renders what it receives.
   */
  function painPointsForCard(themeId: string | null): {
    rows: PainPointPreview[];
    hasMore: boolean;
  } {
    if (!themeId) return { rows: [], hasMore: false };
    const associated = grouped.byTheme.get(themeId) ?? [];
    if (showPainRows) {
      return { rows: associated, hasMore: false };
    }
    if (topPainRowsLimit && topPainRowsLimit > 0) {
      return {
        rows: associated.slice(0, topPainRowsLimit),
        hasMore: associated.length > topPainRowsLimit,
      };
    }
    return { rows: [], hasMore: false };
  }
</script>

<div class="ppt">
  {#each populatedThemes as theme, themeIndex (theme.id)}
    {@const slice = painPointsForCard(theme.id)}
    <ThemeCard
      {theme}
      index={themeIndex}
      displayNumber={themeIndex + 1 + displayOffset}
      painPoints={slice.rows}
      viewAllHref={slice.hasMore ? "#section-ranked-pain" : undefined}
    />
  {/each}

  {#if showPainRows && grouped.unclassified.length > 0}
    <section class="unclassified-bucket">
      <header class="ub-head">
        <span class="ub-kicker">Other pain points</span>
        <p class="ub-desc">
          Pain points from earlier research runs without theme linkage.
        </p>
      </header>
      <ul class="ub-rows">
        {#each grouped.unclassified as pp (pp.id)}
          <li><PainPointMiniRow painPoint={pp} /></li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if emptyThemes.length > 0}
    <aside class="empty-themes">
      <span class="empty-label">Themes without surfaced pain points</span>
      <ul class="empty-list">
        {#each emptyThemes as theme}
          <li>
            <span class="empty-name">{theme.title}</span>
            {#if theme.frequency}
              <span class="empty-freq" data-frequency={theme.frequency.toLowerCase()}>
                {theme.frequency}
              </span>
            {/if}
          </li>
        {/each}
      </ul>
    </aside>
  {/if}
</div>

<style>
  .ppt {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* Unclassified-bucket — small inline section for pain points without a
     matching theme. Uses PainPointMiniRow internally for visual parity. */
  .unclassified-bucket {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-bg-elevated, #fff);
    padding: 18px 20px;
  }
  .ub-head {
    margin-bottom: 10px;
  }
  .ub-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    margin-bottom: 4px;
  }
  .ub-desc {
    font-size: 12.5px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    margin: 0;
  }
  .ub-rows {
    list-style: none;
    margin: 0;
    padding: 0;
    border-top: 1px dashed var(--color-border);
  }
  .ub-rows li {
    border-bottom: 1px dashed var(--color-border);
  }
  .ub-rows li:last-child {
    border-bottom: none;
  }

  /* Empty-themes aside — muted footer chip strip. Preserved from prior impl. */
  .empty-themes {
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .empty-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .empty-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .empty-list li {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: 12px;
    color: var(--color-text-muted);
  }
  .empty-name {
    color: var(--color-text-secondary);
  }
  .empty-freq {
    font-family: var(--font-mono);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.8;
  }
</style>
