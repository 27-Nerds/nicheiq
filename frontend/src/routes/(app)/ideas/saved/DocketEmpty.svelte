<script lang="ts">
  // Editorial empty-state for /ideas/saved. NO frame — no box, no hairlines,
  // no border, no kicker. Left-aligned typography does the framing: folio
  // `00` top-right + display headline + body + CTA. The kicker that earlier
  // revisions placed above the headline was dropped because in section mode
  // it duplicated the SectionDivider above ("01 · IDEAS · 0 saved" vs
  // "SUBJECT · IDEAS · NONE SAVED"), and in page mode it duplicated the
  // headline ("DOCKET · EMPTY" vs "An empty docket."). The surrounding
  // chrome (hero border-bottom in page mode; SectionDivider line in section
  // mode) already provides the upper containment. Co-located here (not in
  // $lib) because it's saved-page-specific.
  //
  // Three reachable scopes (discriminated by the union below):
  // - scope='page'                    → globally empty docket. Replaces both
  //                                     section blocks. CTA → /ideas.
  // - scope='section' + mode='filter' → user has saves of this type but
  //                                     the "Has notes" filter excluded
  //                                     all of them. CTA clears the filter.
  // - scope='section' + mode='discover' → user has saves of the OTHER type
  //                                       only; this type's section shows
  //                                       a supply/demand-framed prompt
  //                                       inviting them to balance the
  //                                       docket. CTA → /ideas.
  //
  // The discriminated union locks `subject`/`onClearFilter`/etc. to the
  // arms that actually need them — TypeScript prevents miswiring at the
  // call site.
  type Props =
    | { scope: "page" }
    | {
        scope: "section";
        subject: "IDEAS" | "PAIN POINTS";
        mode: "filter";
        onClearFilter: () => void;
      }
    | {
        scope: "section";
        subject: "IDEAS" | "PAIN POINTS";
        mode: "discover";
      };

  let props: Props = $props();

  // All copy strings live in this component (no i18n; the rest of the
  // saved page is English-only). Five reachable combinations across
  // scope × subject × mode.
  const copy = $derived.by(() => {
    if (props.scope === "page") {
      return {
        headline: "An empty docket.",
        body:
          "Bookmark ideas and pain points from the catalog. Each save lives here until you remove it. Add notes to track your thinking as you validate.",
        cta: "Browse the catalog →",
      };
    }
    const subjectNoun = props.subject === "IDEAS" ? "ideas" : "pain points";
    if (props.mode === "filter") {
      return {
        headline: "This filter returned no entries.",
        body: `No saved ${subjectNoun} match the "Has notes" filter. Clear it to see all your saves.`,
        cta: "Show all saves →",
      };
    }
    // mode === 'discover' — body is written per-subject so the supply/demand
    // framing reads as deliberate prose, not template fill.
    const body =
      props.subject === "IDEAS"
        ? "Ideas capture the supply side — what could be built. Bookmark a few to pair with your saved pain points and validate against real evidence."
        : "Pain points capture the demand side — what users are complaining about. Bookmark a few to pair with your saved ideas and validate against real evidence.";
    return {
      headline: `No ${subjectNoun} in this docket yet.`,
      body,
      cta: "Browse the catalog →",
    };
  });
</script>

<aside class="docket-empty">
  <span class="de-folio" aria-hidden="true">00</span>
  <h3 class="de-headline">{copy.headline}</h3>
  <p class="de-body-text">{copy.body}</p>
  {#if props.scope === "section" && props.mode === "filter"}
    <button type="button" class="de-cta" onclick={props.onClearFilter}>
      {copy.cta}
    </button>
  {:else}
    <a class="de-cta" href="/ideas">{copy.cta}</a>
  {/if}
</aside>

<style>
  .docket-empty {
    width: 100%;
    /* Acts as the positioning context for the absolute folio `00`. No box,
       no rules — the surrounding SectionDivider lines (section mode) or
       hero border-bottom (page mode) already separate this from the rest
       of the page. Margin keeps the same vertical rhythm as populated
       sections so layout doesn't shift between empty and populated states. */
    position: relative;
    padding: 2rem 0 2.5rem;
    margin: 0 0 1rem;
    text-align: left;
  }

  /* Folio mark — visually rhymes with the bottom-left .folio on
     SavedIdeaCard. Lives top-right of the empty block, baseline-aligned
     with the headline's top edge so it reads as a small label next to a
     chapter title rather than a floating accent. */
  .de-folio {
    position: absolute;
    top: 2rem;
    right: 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    font-feature-settings: "tnum";
  }

  .de-headline {
    margin: 0 0 0.625rem;
    font-family: var(--font-display);
    font-size: 1.375rem;
    font-weight: 600;
    line-height: 1.25;
    letter-spacing: -0.015em;
    color: var(--color-text-primary);
    max-width: 32ch;
  }

  .de-body-text {
    margin: 0 0 1.25rem;
    font-size: 0.9375rem;
    line-height: 1.65;
    color: var(--color-text-secondary);
    max-width: 56ch;
  }

  /* CTA visual treatment is verbatim from the old .docket-empty-cta on
     +page.svelte. The padding/margin trick (8/9px padding + matching
     negative margin) expands the click target to ~28px tall without
     shifting layout — the underline baseline stays in the same pixel row. */
  .de-cta {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-accent);
    letter-spacing: 0.04em;
    text-decoration: none;
    border: 0;
    border-bottom: 1px solid currentColor;
    background: transparent;
    cursor: pointer;
    display: inline-block;
    padding: 8px 0 9px;
    margin: -8px 0 -9px;
  }
  .de-cta:hover {
    color: var(--color-accent-hover, var(--color-accent));
  }
  .de-cta:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 2px;
  }
</style>
