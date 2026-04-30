<script lang="ts">
  import type { FaqEntry } from "$lib/types/catalog-landing";

  interface Props {
    items: FaqEntry[];
  }

  let { items }: Props = $props();
</script>

{#if items.length > 0}
  <div class="faq-list">
    {#each items as item, i}
      <details class="faq-item" name="catalog-faq" open={i === 0}>
        <summary class="faq-summary">
          <span class="faq-marker" aria-hidden="true">※</span>
          <span class="faq-question">{item.q}</span>
        </summary>
        <div class="faq-answer">
          {item.a}
        </div>
      </details>
    {/each}
  </div>
{/if}

<style>
  .faq-list {
    display: flex;
    flex-direction: column;
  }

  .faq-item {
    border-bottom: 1px solid var(--color-border);
    transition: background 140ms ease;
  }

  .faq-item:first-child {
    border-top: 1px solid var(--color-border);
  }

  .faq-summary {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    padding: 1rem 0;
    cursor: pointer;
    list-style: none;
    user-select: none;
    transition: color 140ms ease;
  }

  .faq-summary::-webkit-details-marker {
    display: none;
  }

  .faq-summary:hover {
    color: var(--color-text-primary);
  }

  .faq-summary:active {
    transform: scale(0.998);
  }

  .faq-marker {
    color: var(--color-accent);
    font-size: 1rem;
    line-height: 1;
    flex-shrink: 0;
  }

  .faq-question {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.5;
    text-wrap: balance;
  }

  .faq-answer {
    padding: 0 0 1rem 1.75rem;
    color: var(--color-text-secondary);
    line-height: 1.65;
    text-wrap: pretty;
  }

  /* Smooth open/close on supporting browsers (Chrome 129+). Safe fallback to
     instant on older browsers. */
  @supports (interpolate-size: allow-keywords) {
    :root {
      interpolate-size: allow-keywords;
    }
    .faq-item::details-content {
      block-size: 0;
      overflow: clip;
      transition: block-size 200ms ease, content-visibility 200ms allow-discrete;
    }
    .faq-item[open]::details-content {
      block-size: auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .faq-item,
    .faq-summary {
      transition: none;
    }
  }
</style>
