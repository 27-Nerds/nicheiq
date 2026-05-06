<script lang="ts">
  // Editorial deck (standfirst) — short prose intro between <SectionDivider>
  // and section content. Typographically distinct from the kicker above and
  // the body below via size + spacing + muted color. Pure typography, no
  // chrome. Print-journalism term: the "deck" or "standfirst."
  //
  // CONSTRAINT: text-only children. Renders inside <p>; passing block-level
  // content (lists, divs, headings) produces invalid HTML. Future callers
  // needing block content should introduce a separate primitive.
  interface Props {
    children?: import("svelte").Snippet;
  }
  let { children }: Props = $props();
</script>

<p class="section-deck">{@render children?.()}</p>

<style>
  /* Editorial standfirst — italic + smaller + muted + narrower than the
     section's body prose. Per convention (Stuff & Nonsense, Fiveable on
     headline/deck design): "a standfirst should stand apart and be
     separate from running text, unlike a lead which is part of the
     article itself." Four orthogonal signals (style, size, color, width)
     keep it from competing with the lead theme's description below. */
  .section-deck {
    font-style: italic;
    font-size: 14px;
    line-height: 1.65;
    max-width: 640px;
    margin: 0 0 24px;
    color: var(--color-text-muted, var(--color-text-secondary));
  }
  @media (max-width: 640px) {
    .section-deck {
      font-size: 13.5px;
      margin-bottom: 20px;
    }
  }
</style>
