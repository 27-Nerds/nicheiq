<script lang="ts">
  import type { Snippet } from "svelte";

  // Full-bleed background stripe used to visually separate sections on
  // catalog pages (audience, source signal). Scoped to catalog so it doesn't
  // collide with any global `.band` rules elsewhere in the app.

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<section class="catalog-band">
  <div class="inner">{@render children()}</div>
</section>

<style>
  /* Tonal stripe — wraps section CONTENT only, not the SectionDivider header
     (the divider should sit above the band). Body is #FAFAFA; a slightly
     darker --color-bg-surface (#F5F5F5) gives perceptible contrast without
     looking like a heavy card. Borders kept faint so the stripe reads as a
     soft tonal shift, not a boxed frame.
     Inner padding is symmetric on both axes — content gets breathing room
     from the band edges in BOTH directions, which the previous version
     missed. */
  .catalog-band {
    background: var(--color-bg-surface, #f5f5f5);
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
    margin: 8px 0 24px;
    border-radius: 6px;
  }
  .inner {
    padding: 20px 24px;
  }
</style>
