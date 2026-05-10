<script lang="ts">
  import type { FaqEntry } from "$lib/types/catalog-landing";

  interface Props {
    items: FaqEntry[];
    /** Editorial heading. Default reads as a section title; override per-page
     *  for context-specific copy (e.g. "Common questions about <niche>"). */
    heading?: string;
    /** Mono-spaced eyebrow above the heading. Empty string hides it. */
    eyebrow?: string;
  }

  let {
    items,
    heading = "Frequently asked",
    eyebrow = "FAQ — APPENDIX",
  }: Props = $props();
</script>

{#if items.length > 0}
  <section class="faq" aria-labelledby="faq-title">
    <header class="faq-header">
      {#if eyebrow}
        <span class="faq-eyebrow">{eyebrow}</span>
      {/if}
      <h2 id="faq-title" class="faq-title">{heading}</h2>
      <span class="faq-count" aria-hidden="true">
        {String(items.length).padStart(2, "0")}
        {items.length === 1 ? "entry" : "entries"}
      </span>
    </header>

    <ol class="faq-list">
      {#each items as item, i}
        <li class="faq-item">
          <details name="catalog-faq" open={i === 0}>
            <summary>
              <span class="faq-num" aria-hidden="true"></span>
              <span class="faq-question">{item.q}</span>
            </summary>
            <div class="faq-answer">
              <p>{item.a}</p>
            </div>
          </details>
        </li>
      {/each}
    </ol>
  </section>
{/if}

<style>
  /* ─── Section frame ──────────────────────────────────────────────── */

  .faq {
    margin: 4rem 0 2.5rem;
  }

  .faq-header {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    column-gap: 2rem;
    row-gap: 0.625rem;
    align-items: end;
    margin-bottom: 2.25rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--color-border);
  }

  .faq-eyebrow {
    grid-column: 1;
    grid-row: 1;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--color-accent);
  }

  .faq-title {
    grid-column: 1;
    grid-row: 2;
    font-family: var(--font-display);
    font-size: clamp(1.75rem, 2.6vw, 2.25rem);
    line-height: 1.05;
    font-weight: 600;
    letter-spacing: -0.022em;
    color: var(--color-text-primary);
    margin: 0;
    text-wrap: balance;
  }

  .faq-count {
    grid-column: 2;
    grid-row: 2;
    align-self: end;
    padding-bottom: 0.25rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
    font-feature-settings: "tnum";
    white-space: nowrap;
  }

  /* ─── List & rows ────────────────────────────────────────────────── */

  .faq-list {
    list-style: none;
    margin: 0;
    padding: 0;
    counter-reset: faq;
  }

  .faq-item {
    counter-increment: faq;
    border-bottom: 1px solid var(--color-border);
  }

  /* When ANY item is open, dim the closed siblings — focuses the eye on
     the open content without movement. Hover restores so the user can
     preview before clicking. */
  .faq-list:has(details[open]) .faq-item:not(:has(details[open])) {
    opacity: 0.5;
    transition: opacity 240ms ease;
  }
  .faq-list:has(details[open]) .faq-item:not(:has(details[open])):hover {
    opacity: 1;
  }

  /* ─── Summary ────────────────────────────────────────────────────── */

  summary {
    display: grid;
    grid-template-columns: 3rem 1fr;
    align-items: baseline;
    padding: 1.375rem 0;
    cursor: pointer;
    list-style: none;
    user-select: none;
    transition:
      padding-top 220ms ease,
      padding-bottom 220ms ease;
  }
  summary::-webkit-details-marker {
    display: none;
  }
  summary::marker {
    display: none;
  }

  details[open] > summary {
    padding-top: 1.625rem;
    padding-bottom: 1.125rem;
  }

  /* CSS counter — auto-numbers without JS, no drift on reorder. The
     decimal-leading-zero style ("01", "02"…) ties into NicheIQ's existing
     numbered SectionDivider convention. */
  .faq-num {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    font-feature-settings: "tnum";
    /* Optical lift to align with the question's cap-height. */
    transform: translateY(-1px);
    transition: color 240ms ease;
  }
  .faq-num::before {
    content: counter(faq, decimal-leading-zero);
  }

  details[open] > summary .faq-num {
    color: var(--color-accent);
  }

  .faq-question {
    font-family: var(--font-display);
    font-size: 1.0625rem;
    line-height: 1.4;
    font-weight: 500;
    color: var(--color-text-primary);
    text-wrap: balance;
    transition:
      color 240ms ease,
      font-size 240ms ease,
      font-weight 240ms ease,
      letter-spacing 240ms ease;
  }

  /* Open: subtly larger + heavier. */
  details[open] > summary .faq-question {
    font-size: 1.1875rem;
    font-weight: 600;
    letter-spacing: -0.005em;
  }

  /* Hover (closed only): nudge color, no movement. */
  summary:hover .faq-num,
  summary:hover .faq-question {
    color: var(--color-accent);
  }
  details[open] > summary:hover .faq-question {
    color: var(--color-text-primary);
  }

  summary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 2px;
  }

  /* ─── Answer ─────────────────────────────────────────────────────── */

  .faq-answer {
    /* Left padding aligns the answer text with the question column. */
    padding: 0 0 2.25rem 3rem;
  }

  .faq-answer p {
    margin: 0;
    max-width: 64ch;
    font-family: var(--font-body);
    font-size: 0.9375rem;
    line-height: 1.75;
    font-weight: 400;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }

  /* Editorial drop-cap rule — small accent line precedes each answer. */
  .faq-answer p::before {
    content: "";
    display: block;
    width: 1.5rem;
    height: 1px;
    margin-bottom: 0.875rem;
    background: var(--color-accent);
    opacity: 0.7;
  }

  /* ─── Smooth open/close (Chrome 129+) ────────────────────────────── */

  @supports (interpolate-size: allow-keywords) {
    :root {
      interpolate-size: allow-keywords;
    }
    details::details-content {
      block-size: 0;
      overflow: clip;
      opacity: 0;
      transition:
        block-size 280ms cubic-bezier(0.22, 1, 0.36, 1),
        opacity 220ms ease 40ms,
        content-visibility 280ms allow-discrete;
    }
    details[open]::details-content {
      block-size: auto;
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .faq-item,
    summary,
    .faq-question,
    .faq-num {
      transition: none;
    }
    details::details-content {
      transition: none !important;
    }
    .faq-list:has(details[open]) .faq-item:not(:has(details[open])) {
      transition: none;
    }
  }

  /* ─── Narrow viewports ───────────────────────────────────────────── */

  @media (max-width: 32rem) {
    .faq-header {
      grid-template-columns: 1fr;
    }
    .faq-count {
      grid-column: 1;
      grid-row: 3;
      align-self: start;
      padding-bottom: 0;
    }
    summary {
      grid-template-columns: 2.5rem 1fr;
      padding: 1.125rem 0;
    }
    details[open] > summary {
      padding-top: 1.375rem;
      padding-bottom: 0.875rem;
    }
    .faq-answer {
      padding-left: 2.5rem;
      padding-bottom: 1.75rem;
    }
    .faq-question {
      font-size: 1rem;
    }
    details[open] > summary .faq-question {
      font-size: 1.0625rem;
    }
  }
</style>
