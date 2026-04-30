<script lang="ts">
  // The signature treatment for under-curated catalog surfaces. Two horizontal
  // hairlines (top + bottom) frame a left-aligned ledger entry with a `◐`
  // status glyph offset to the upper-right corner. NO dashed border, NO
  // surrounding box, NO loading spinner — those are the SaaS-empty-state
  // clichés this design rejects.
  interface Props {
    headline?: string;
    sub?: string;
  }

  let {
    headline = "Awaiting first findings.",
    sub = "Re-checked weekly.",
  }: Props = $props();
</script>

<div class="empty-research-state">
  <div class="state-rule"></div>
  <div class="state-body">
    <span class="state-glyph" aria-hidden="true">◐</span>
    <h3 class="state-headline">{headline}</h3>
    <p class="state-sub">{sub}</p>
  </div>
  <div class="state-rule"></div>
</div>

<style>
  .empty-research-state {
    width: 100%;
  }

  .state-rule {
    height: 1px;
    background: var(--color-border);
    width: 100%;
  }

  .state-body {
    position: relative;
    padding: 3rem 0;
    /* Left-aligned, like a ledger entry. */
    text-align: left;
  }

  .state-glyph {
    position: absolute;
    top: 1rem;
    right: 0;
    font-size: 1.5rem;
    color: var(--color-text-muted);
    line-height: 1;
  }

  .state-headline {
    margin: 0 0 0.5rem 0;
    font-family: "Plus Jakarta Sans", system-ui, sans-serif;
    font-weight: 700;
    font-size: 1.375rem;
    color: var(--color-text-primary);
    letter-spacing: -0.01em;
  }

  .state-sub {
    margin: 0;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
  }
</style>
