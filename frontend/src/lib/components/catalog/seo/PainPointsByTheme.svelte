<script lang="ts">
  import type { Theme } from "$lib/types/publicCatalog.js";
  import ThemeCard from "./ThemeCard.svelte";

  // Themes section orchestrator: "lead headline + roll" pattern.
  //
  //   lead       → most-cited id-bearing theme, rendered as open editorial
  //                prose (no chrome) via `<ThemeCard emphasis />`.
  //   ─ rule ─   → 1px hairline separating lead from the roll, only when
  //                the roll has > 0 themes.
  //   roll       → remaining id-bearing themes, rendered as compact grid
  //                rows inside a single bordered `.theme-table` container.
  //   id-less    → legacy aside for themes without IDs (preserved from
  //                prior implementation).
  //   foot       → optional section-level cross-link pair to audience and
  //                ranked-pain anchors. Replaces the broken per-row chips.
  //
  // Sorted by mentionCount desc; lead is the most-cited. Indexes are
  // preserved across the split so display numbers and `.catalog-fade-in`
  // delays read 01, 02, 03, ... in sequence.

  interface Props {
    themes: Theme[];
    /** Optional section-overview prose (research summary). When provided
     *  alongside a lead theme, the two render in an asymmetric 2-col intro:
     *  deck in a narrow left sidebar, lead in the wide main column. This
     *  prevents the section overview from competing with the lead theme's
     *  description as adjacent prose blocks (magazine-spread pattern). When
     *  omitted, the lead spans full width. */
    deck?: string | null;
    /** Cross-link to the ranked-pain section. When set, the section-level
     *  footer renders a "Ranked pain points →" link. Caller should gate
     *  this on whether the target anchor exists. */
    painsHref?: string;
    /** Cross-link to the audience section. When set, the section-level
     *  footer renders a "See audience →" link. */
    audienceHref?: string;
    /** Wave 3 — when true, each <ThemeCard> renders a per-row source
     *  attribution footer based on `theme.sourceSubNiche`. Parent route
     *  passes `themeMultiSource` so this only fires when ≥2 sub-niches
     *  contributed themes; sub-niche route always leaves it false. */
    showSource?: boolean;
  }

  let { themes, deck, painsHref, audienceHref, showSource = false }: Props = $props();
  const hasDeck = $derived(!!deck && deck.trim().length > 0);

  const sortedThemes = $derived(
    [...themes]
      .filter((t) => !!t.id)
      .sort((a, b) => (b.mentionCount ?? 0) - (a.mentionCount ?? 0)),
  );
  const lead = $derived(sortedThemes[0] ?? null);
  const rollThemes = $derived(sortedThemes.slice(1));
  const idLessThemes = $derived(themes.filter((t) => !t.id));

  const showFoot = $derived(!!painsHref || !!audienceHref);
</script>

{#if hasDeck}
  <aside class="theme-deck-note catalog-fade-in">
    <span class="theme-deck-badge">Overview</span>
    <p class="theme-deck-text">{deck}</p>
  </aside>
{/if}

{#if lead || rollThemes.length > 0}
  <div class="theme-table">
    {#if lead}
      <ThemeCard theme={lead} index={0} emphasis {showSource} />
    {/if}
    {#each rollThemes as theme, j (theme.id)}
      <ThemeCard theme={theme} index={j + 1} emphasis={false} {showSource} />
    {/each}
  </div>
{/if}

{#if idLessThemes.length > 0}
  <aside class="empty-themes">
    <span class="empty-label">Legacy themes without IDs</span>
    <ul class="empty-list">
      {#each idLessThemes as theme}
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

{#if showFoot && (lead || rollThemes.length > 0 || idLessThemes.length > 0)}
  <nav class="theme-foot" aria-label="Related sections">
    {#if audienceHref}
      <a class="theme-foot-link" href={audienceHref}>
        See audience <span aria-hidden="true">→</span>
      </a>
    {/if}
    {#if painsHref && audienceHref}
      <span class="theme-foot-sep" aria-hidden="true">·</span>
    {/if}
    {#if painsHref}
      <a class="theme-foot-link" href={painsHref}>
        Ranked pain points <span aria-hidden="true">→</span>
      </a>
    {/if}
  </nav>
{/if}

<style>
  /* Section overview rendered as a "data note" — a chip-badge labels the
     block as supporting metadata, italic muted prose carries the content.
     The badge is a real UI element (hairline border + padding) which puts
     the deck in a different visual category than the lead's typographic
     kickers. Same idiom as documentation-site minimal callouts (Quarto,
     Mintlify) without the colored-border AI-slop pattern. */
  .theme-deck-note {
    display: block;
    max-width: 720px;
    margin: 0 0 32px;
  }
  .theme-deck-badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
    border-radius: 3px;
    padding: 2px 8px;
    margin-bottom: 10px;
    background: var(--color-bg-elevated);
    white-space: nowrap;
  }
  .theme-deck-text {
    font-style: italic;
    font-size: 13.5px;
    line-height: 1.65;
    color: var(--color-text-muted);
    margin: 0;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }


  /* Bordered container wrapping the lead + compact rows. Each item
     contributes its own hairline border-bottom; we suppress it on the last
     child regardless of variant. */
  .theme-table {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-bg-elevated, #fff);
    overflow: hidden;
  }
  .theme-table > :global(.theme-lead:last-child),
  .theme-table > :global(.theme-row:last-child) {
    border-bottom: none;
  }

  /* Section-level cross-link footer. Right-aligned mono links, replaces
     the broken per-row persona chip + per-row pain link. */
  .theme-foot {
    display: flex;
    align-items: baseline;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 18px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
  }
  .theme-foot-link {
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.12s;
  }
  .theme-foot-link:hover {
    color: var(--color-accent);
  }
  .theme-foot-sep {
    color: var(--color-text-muted);
    opacity: 0.55;
  }

  /* Legacy id-less themes — preserved from prior implementation, unchanged. */
  .empty-themes {
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 14px 20px;
    margin-top: 18px;
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

  @media (max-width: 640px) {
    .theme-deck-note {
      margin-bottom: 24px;
    }
    .theme-foot {
      justify-content: flex-start;
      flex-wrap: wrap;
    }
  }
</style>
