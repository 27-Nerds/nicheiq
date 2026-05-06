<script lang="ts">
  import type { Theme } from "$lib/types/publicCatalog.js";
  import { categoryPath } from "$lib/utils/urls";

  // Two render paths gated on `emphasis`:
  //   - Lead (`emphasis = true`)  → editorial prose, no chrome (.theme-lead)
  //   - Row  (`emphasis = false`) → compact grid row in a parent table (.theme-row)
  //
  // Hierarchy comes from typography scale, position, and structural difference —
  // no accent border, no tint, no badge. Per the "no AI-slop hover effects"
  // memory, decorated-card emphasis is explicitly avoided.
  //
  // Both render paths preserve `id="theme-{theme.id}"` so chips in the
  // ranked-pain table can deep-link via #theme-{id} and trigger the inset
  // accent ring on `:target`.

  interface Props {
    theme: Theme;
    /** 0-based index — used for `.catalog-fade-in` stagger AND display number.
     *  Caller (PainPointsByTheme) must preserve original sorted indexes when
     *  splitting [lead, ...rest] so that lead = 0 and rolls = 1, 2, 3, ... */
    index: number;
    /** 1-based number rendered in the kicker. Defaults to `index + 1`. */
    displayNumber?: number;
    /** When true, render the lead variant (no chrome, large typography).
     *  When false, render the compact row variant inside a parent table. */
    emphasis?: boolean;
    /** Wave 3 — when true AND `theme.sourceSubNiche` is non-null, render a
     *  per-row source attribution footer at the bottom of the card body.
     *  Parent route's PainPointsByTheme passes this as `themeMultiSource` so
     *  the footer only shows when at least 2 sub-niches contributed themes
     *  (otherwise the section-level <SectionAttribution> handles attribution).
     *  Sub-niche route always leaves it false. */
    showSource?: boolean;
  }

  let {
    theme,
    index,
    displayNumber,
    emphasis = false,
    showSource = false,
  }: Props = $props();

  const formattedNumber = $derived(
    String(displayNumber ?? index + 1).padStart(2, "0"),
  );

  // Frequency normalization. Backend passes the value verbatim; the type
  // allows arbitrary string. Anything outside high/medium/low renders no
  // pill and no styled inline label — fail closed rather than render
  // unstyled junk.
  const frequencyKey = $derived.by<"high" | "medium" | "low" | null>(() => {
    const v = theme.frequency?.trim().toLowerCase();
    if (v === "high" || v === "medium" || v === "low") return v;
    return null;
  });
  const frequencyLabel = $derived(
    frequencyKey === "medium" ? "MED" : frequencyKey?.toUpperCase() ?? null,
  );

  const anchorId = $derived(
    theme.id ? `theme-${theme.id}` : `theme-orphan-${index}`,
  );
  const animationDelay = $derived(`${Math.min(index, 5) * 0.06}s`);

  // Lead-only: render up to 3 primary user segments as inline metadata so
  // the lead carries informational depth that the rolls don't (justifies
  // its larger typographic treatment with actual additional context).
  const leadSegments = $derived.by<string[]>(() => {
    if (!emphasis) return [];
    const segs = theme.primaryUserSegments ?? [];
    return segs.filter((s): s is string => !!s && s.trim().length > 0).slice(0, 3);
  });

  // Wave 3 — per-row source footer: rendered only when both showSource AND
  // the theme has sourceSubNiche metadata. `categoryPath` is the canonical
  // URL helper; do not interpolate URLs by hand.
  const showSourceFooter = $derived(!!showSource && !!theme.sourceSubNiche);
  const sourceHref = $derived(
    theme.sourceSubNiche
      ? categoryPath({
          slug: theme.sourceSubNiche.slug,
          parentSlug: theme.sourceSubNiche.parentSlug,
        })
      : "",
  );
</script>

{#if emphasis}
  <!-- LEAD VARIANT — hero row inside the parent `.theme-table` container.
       Same 4-col grid skeleton as the compact rolls (kicker | body | mentions
       | freq) so the table's vertical right-rail rhythm is uninterrupted.
       Differentiated by larger padding, accent kicker, bigger title, and a
       featured 32px mention count. Editorial pattern: scale carries
       hierarchy, structure carries unity. -->
  <article
    id={anchorId}
    class="theme-lead catalog-fade-in"
    style:animation-delay={animationDelay}
  >
    <span class="tl-num">THEME {formattedNumber}</span>
    <div class="tl-body">
      <h3 class="tl-title">{theme.title}</h3>
      {#if theme.description}
        <p class="tl-desc">{theme.description}</p>
      {/if}
      {#if leadSegments.length > 0}
        <div class="tl-personas">
          <span class="tl-personas-kicker">Primary users</span>
          {#each leadSegments as segment, i (segment)}
            {#if i > 0}
              <span class="tl-personas-sep" aria-hidden="true">·</span>
            {/if}
            <span class="tl-personas-text">{segment}</span>
          {/each}
        </div>
      {/if}
      {#if showSourceFooter && theme.sourceSubNiche}
        <a class="tl-source" href={sourceHref}>
          <span class="arrow" aria-hidden="true">↗</span>
          <span>From {theme.sourceSubNiche.name}</span>
        </a>
      {/if}
    </div>
    {#if theme.mentionCount != null}
      <div class="tl-mentions">
        <span class="tl-mentions-n">{theme.mentionCount.toLocaleString()}</span>
        <span class="tl-mentions-l">Mentions</span>
      </div>
    {:else}
      <span></span>
    {/if}
    {#if frequencyKey}
      <span class="tl-freq" data-frequency={frequencyKey}>{frequencyLabel}</span>
    {:else}
      <span></span>
    {/if}
  </article>
{:else}
  <!-- ROW VARIANT — compact grid row. Caller wraps these in a bordered
       `.theme-table` container; the row contributes a hairline `border-bottom`
       and the container suppresses the bottom border on `:last-child`. -->
  <article
    id={anchorId}
    class="theme-row catalog-fade-in"
    style:animation-delay={animationDelay}
  >
    <span class="tr-num">THEME {formattedNumber}</span>
    <div class="tr-body">
      <h3 class="tr-title">{theme.title}</h3>
      {#if theme.description}
        <p class="tr-desc">{theme.description}</p>
      {/if}
      {#if showSourceFooter && theme.sourceSubNiche}
        <a class="tr-source" href={sourceHref}>
          <span class="arrow" aria-hidden="true">↗</span>
          <span>From {theme.sourceSubNiche.name}</span>
        </a>
      {/if}
    </div>
    {#if theme.mentionCount != null}
      <div class="tr-mentions">
        <span class="tr-mentions-n">{theme.mentionCount.toLocaleString()}</span>
        <span class="tr-mentions-l">Mentions</span>
      </div>
    {:else}
      <span></span>
    {/if}
    {#if frequencyKey}
      <span class="tr-freq" data-frequency={frequencyKey}>{frequencyLabel}</span>
    {:else}
      <span></span>
    {/if}
  </article>
{/if}

<style>
  /* ─── Lead variant — hero row inside the parent `.theme-table` container.
        Same 4-col grid skeleton as `.theme-row` (kicker | body | mentions |
        freq) so the right-rail mention column reads as a continuous scan-
        track top-down across all rows. Differentiated by larger padding,
        accent kicker, bigger title (24px), and a featured 32px mention
        number. `align-items: start` keeps the right-rail stats anchored
        to the kicker baseline rather than centering them ~50px below. */
  .theme-lead {
    position: relative;
    display: grid;
    grid-template-columns: 60px 1fr auto auto;
    gap: 18px;
    align-items: start;
    padding: 26px 28px;
    border-bottom: 1px solid var(--color-border);
  }
  .tl-num {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-accent);
    white-space: nowrap;
    padding-top: 6px;
  }
  .tl-body {
    min-width: 0;
  }
  .tl-title {
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.015em;
    line-height: 1.2;
    color: var(--color-text-primary);
    text-wrap: balance;
    max-width: 720px;
    margin: 0 0 10px;
  }
  .tl-desc {
    font-size: 14.5px;
    line-height: 1.7;
    color: var(--color-text-secondary, var(--color-text-primary));
    max-width: 680px;
    margin: 0;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }
  /* Lead-only "Primary users" metadata line — informational depth the rolls
     don't carry; pairs the bigger typographic weight of the lead with
     actual extra context. Mono kicker matches the catalog's editorial
     voice; segments inline with hairline `·` separators. */
  .tl-personas {
    margin-top: 14px;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.02em;
    color: var(--color-text-secondary);
    max-width: 720px;
  }
  .tl-personas-kicker {
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    margin-right: 6px;
  }
  .tl-personas-sep {
    color: var(--color-text-muted);
    opacity: 0.55;
    margin: 0 2px;
  }
  /* Wave 3 — per-row source attribution footer. Mono uppercase byline that
     visually echoes <SectionAttribution> + AudienceSegmentCard's footer
     pattern. Hairline divider above separates it from the body content
     (title / desc / primary users). 32px min-height for tappable a11y. */
  .tl-source,
  .tr-source {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.12s;
    min-height: 32px;
    flex-wrap: wrap;
    overflow-wrap: anywhere;
  }
  .tr-source {
    margin-top: 8px;
    padding-top: 8px;
  }
  .tl-source:hover,
  .tr-source:hover {
    color: var(--color-accent);
  }
  .tl-source:focus-visible,
  .tr-source:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
    border-radius: 2px;
  }
  .tl-source .arrow,
  .tr-source .arrow {
    color: var(--color-text-muted);
  }
  .tl-source:hover .arrow,
  .tr-source:hover .arrow {
    color: var(--color-accent);
  }
  .tl-mentions {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    white-space: nowrap;
    padding-top: 2px;
  }
  .tl-mentions-n {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 32px;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1;
    color: var(--color-text-primary);
  }
  .tl-mentions-l {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .tl-freq {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    padding: 2px 8px;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    color: var(--color-text-muted);
    white-space: nowrap;
    line-height: 1.4;
    margin-top: 6px;
  }
  .tl-freq[data-frequency="high"] {
    color: var(--color-accent);
    border-color: var(--color-border-accent, rgba(234, 88, 12, 0.3));
  }
  .tl-freq[data-frequency="medium"] {
    color: var(--color-text-primary);
  }
  .tl-freq[data-frequency="low"] {
    opacity: 0.7;
  }

  /* ─── Row variant — compact grid row inside parent `.theme-table` ──── */
  .theme-row {
    position: relative;
    display: grid;
    grid-template-columns: 60px 1fr auto auto;
    gap: 18px;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border);
  }
  .tr-num {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-text-muted);
    white-space: nowrap;
    align-self: start;
    padding-top: 2px;
  }
  .tr-body {
    min-width: 0;
  }
  .tr-title {
    font-size: 14.5px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.35;
    color: var(--color-text-primary);
    margin: 0 0 4px;
  }
  .tr-desc {
    font-size: 13px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
    max-width: 680px;
    margin: 0;
    overflow-wrap: anywhere;
  }
  .tr-mentions {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
    white-space: nowrap;
  }
  .tr-mentions-n {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 17px;
    font-weight: 600;
    letter-spacing: -0.01em;
    line-height: 1;
    color: var(--color-text-primary);
  }
  .tr-mentions-l {
    font-family: var(--font-mono);
    font-size: 9px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .tr-freq {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    padding: 2px 8px;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    color: var(--color-text-muted);
    white-space: nowrap;
    line-height: 1.4;
  }
  .tr-freq[data-frequency="high"] {
    color: var(--color-accent);
    border-color: var(--color-border-accent, rgba(234, 88, 12, 0.3));
  }
  .tr-freq[data-frequency="medium"] {
    color: var(--color-text-primary);
  }
  .tr-freq[data-frequency="low"] {
    opacity: 0.7;
  }

  /* ─── :target highlight — preserved across both render paths.
        Both classes now sit inside the parent `.theme-table` container, so
        the inset rectangle aligns flush with the row's bounding box. */
  .theme-lead:target::after,
  .theme-row:target::after {
    content: "";
    position: absolute;
    pointer-events: none;
    inset: 0;
    border: 2px solid var(--color-accent);
    border-radius: 0;
    animation: tc-flash 1.2s ease-out forwards;
  }
  @keyframes tc-flash {
    0%, 40% { opacity: 1; }
    100% { opacity: 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    .theme-lead:target::after,
    .theme-row:target::after {
      animation: none;
      opacity: 1;
    }
  }

  /* ─── Mobile ───────────────────────────────────────────────────────── */
  @media (max-width: 640px) {
    .theme-lead {
      grid-template-columns: 1fr auto;
      grid-template-areas:
        "num   freq"
        "body  body"
        "ments ments";
      gap: 8px 12px;
      padding: 18px 18px;
    }
    .tl-num    { grid-area: num; padding-top: 0; }
    .tl-freq   { grid-area: freq; margin-top: 0; justify-self: end; }
    .tl-body   { grid-area: body; }
    .tl-mentions {
      grid-area: ments;
      flex-direction: row;
      align-items: baseline;
      gap: 6px;
      padding-top: 0;
      align-self: flex-start;
    }
    .tl-mentions-n {
      font-size: 24px;
    }
    .tl-title {
      font-size: 19px;
    }
    .tl-desc {
      font-size: 14px;
    }
    .theme-row {
      grid-template-columns: 1fr auto;
      grid-template-areas:
        "num   freq"
        "body  body"
        "ments ments";
      gap: 6px 12px;
      align-items: baseline;
      padding: 14px 16px;
    }
    .tr-num    { grid-area: num; padding-top: 0; }
    .tr-freq   { grid-area: freq; justify-self: end; }
    .tr-body   { grid-area: body; }
    .tr-mentions {
      grid-area: ments;
      flex-direction: row;
      align-items: baseline;
      gap: 6px;
      align-self: flex-start;
    }
  }
</style>
