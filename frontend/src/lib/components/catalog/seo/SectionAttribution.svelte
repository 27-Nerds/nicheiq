<script lang="ts">
  // Mono-uppercase attribution link surfaced under section dividers on the
  // parent niche route. Tells the user that a section's content was drawn
  // from a specific sub-niche's research (e.g., themes / audience on
  // category landings, where the data is single-source-derived rather than
  // aggregated across the subtree).
  //
  // Sub-niche pages don't render this — they own their data.

  interface Props {
    source: { slug: string; name: string };
    /** Pre-built href to the source sub-niche. Caller computes via
     *  `categoryPath({ slug, parentSlug })` so the URL helper stays the
     *  single source of truth. */
    href: string;
  }

  let { source, href }: Props = $props();
</script>

<a class="section-attribution" {href}>
  <span class="arrow" aria-hidden="true">↗</span>
  <span class="prefix">From</span>
  <span class="name">{source.name}</span>
  <span class="suffix">research</span>
</a>

<style>
  .section-attribution {
    display: inline-flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 6px;
    margin: 4px 0 18px;
    padding: 6px 0;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.12s;
    overflow-wrap: anywhere;
  }
  .section-attribution:hover {
    color: var(--color-accent);
  }
  .section-attribution:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
    border-radius: 2px;
  }
  .arrow {
    color: var(--color-text-muted);
  }
  .name {
    color: var(--color-text-secondary);
    font-weight: 700;
  }
  .section-attribution:hover .name {
    color: var(--color-accent);
  }

  @media (max-width: 640px) {
    .section-attribution {
      margin-bottom: 14px;
    }
  }
</style>
