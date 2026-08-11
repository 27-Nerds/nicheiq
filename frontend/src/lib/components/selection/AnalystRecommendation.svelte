<script lang="ts">
  import { ChevronDown } from "lucide-svelte";
  import IdeaReferenceText from "$lib/components/IdeaReferenceText.svelte";
  import type { IdeaReference } from "$lib/utils/ideaReferences";

  interface Props {
    recommendation: string;
    supportingNotes: string[];
    references: IdeaReference[];
    onOpen: (reference: IdeaReference) => void;
  }

  let { recommendation, supportingNotes, references, onOpen }: Props = $props();
  let expanded = $state(false);
</script>

<section class="analyst-summary" aria-label="Research recommendation" data-annotation-anchor="shortlist-recommendation">
  <header class="analyst-summary-head">
    <h3>Research recommendation</h3>
  </header>

  <div class="analyst-summary-body">
    <p class="analyst-summary-text analyst-summary-text--verdict">
      <IdeaReferenceText content={recommendation} {references} {onOpen} />
    </p>

    {#if supportingNotes.length}
      <details class="analyst-summary-details" ontoggle={(event) => (expanded = event.currentTarget.open)}>
        <summary>
          <span>{expanded ? "Hide full analysis" : "Read full analysis"}</span>
          <ChevronDown aria-hidden="true" />
        </summary>
        <div class="analyst-summary-notes">
          {#each supportingNotes as note}
            <p class="analyst-summary-text">
              <IdeaReferenceText content={note} {references} {onOpen} />
            </p>
          {/each}
        </div>
      </details>
    {/if}
  </div>
</section>

<style>
  .analyst-summary {
    display: grid;
    grid-template-columns: minmax(8.5rem, 11rem) minmax(0, 1fr);
    column-gap: clamp(1.25rem, 3vw, 2.75rem);
    align-items: start;
    margin-top: 0.72rem;
    padding: 1rem 0.2rem 1.05rem;
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
  }
  .analyst-summary-head { padding-top: 0.08rem; }
  .analyst-summary-head h3 {
    margin: 0;
    color: var(--color-text-secondary);
    font-family: var(--font-display);
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: -0.01em;
    line-height: 1.35;
    text-wrap: balance;
  }
  .analyst-summary-body {
    min-width: 0;
    max-width: 72ch;
  }
  .analyst-summary-text {
    max-width: none;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.58;
    text-wrap: pretty;
  }
  .analyst-summary-text--verdict {
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 400;
  }
  .analyst-summary :global(button.idea-reference-link) {
    color: inherit;
    font-weight: 600;
    text-decoration-color: var(--color-border-emphasis);
    text-decoration-line: underline;
    text-decoration-style: dotted;
    text-decoration-thickness: 1px;
    text-underline-offset: 0.18em;
    transition: color var(--duration-fast) var(--ease-default), text-decoration-color var(--duration-fast) var(--ease-default);
  }
  .analyst-summary :global(button.idea-reference-link:hover) {
    color: var(--color-accent-dark);
    text-decoration-color: currentColor;
  }
  .analyst-summary-details {
    margin-top: 0.72rem;
    padding-top: 0.58rem;
    border-top: 1px solid var(--color-border);
  }
  .analyst-summary-details summary {
    display: inline-flex;
    align-items: center;
    gap: 0.38rem;
    padding: 0.08rem 0;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: var(--text-11);
    font-weight: 600;
    list-style: none;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .analyst-summary-details summary::-webkit-details-marker { display: none; }
  .analyst-summary-details summary:hover { color: var(--color-text-primary); }
  .analyst-summary-details summary:active { transform: scale(0.98); }
  .analyst-summary-details summary:focus-visible {
    border-radius: 0.125rem;
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .analyst-summary-details summary :global(svg) {
    flex: 0 0 auto;
    width: 0.75rem;
    height: 0.75rem;
    transition: transform var(--duration-fast) var(--ease-default);
  }
  .analyst-summary-details[open] summary :global(svg) { transform: rotate(180deg); }
  .analyst-summary-notes {
    display: grid;
    gap: 0;
    padding: 0.82rem 0 0.12rem;
  }
  .analyst-summary-notes .analyst-summary-text + .analyst-summary-text {
    margin-top: 0.88rem;
    padding-top: 0.88rem;
    border-top: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
  }
  @media (max-width: 859px) {
    .analyst-summary {
      grid-template-columns: minmax(0, 1fr);
      row-gap: 0.45rem;
      padding: 0.9rem 0 1rem;
    }
    .analyst-summary-head h3 { max-width: none; }
  }
  @media (prefers-reduced-motion: reduce) {
    .analyst-summary-details summary:active {
      transform: none;
    }
  }
</style>
