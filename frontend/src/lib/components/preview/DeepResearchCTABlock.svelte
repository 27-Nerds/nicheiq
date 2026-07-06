<script lang="ts">
  import { ArrowRight } from "lucide-svelte";

  interface Props {
    creditCost: number;
    onUnlock: () => void;
  }

  let { creditCost, onUnlock }: Props = $props();
</script>

<section class="cta-block">
  <div class="cta-copy">
    <span class="cta-eyebrow">Locked preview</span>
    <h2 class="cta-title">Deep Research unlocks the validation layer.</h2>
    <p class="cta-desc">
      Market sizing, competitors, SEO, pricing, trends, and technical blueprint are generated after you choose the ideas to pressure-test.
    </p>
  </div>
  <div class="cta-actions">
    <button class="cta-primary" onclick={onUnlock}>
      Select opportunities
      <ArrowRight class="cta-arrow" aria-hidden="true" />
    </button>
    <p class="cta-price">{creditCost} credits · one-time per niche</p>
  </div>
</section>

<style>
  .cta-block {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    margin: 1rem 0;
    padding: 1rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
  }

  .cta-copy {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    min-width: 0;
  }

  .cta-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .cta-title {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 700;
    line-height: 1.25;
    color: var(--color-text-primary);
    margin: 0;
  }

  .cta-desc {
    font-size: 0.875rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    max-width: 36rem;
    margin: 0;
  }

  .cta-actions {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .cta-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.875rem 1.5rem;
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-family: var(--font-body);
    font-size: 0.9375rem;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 150ms ease;
    white-space: nowrap;
  }

  .cta-primary:hover {
    background: var(--color-accent-dark);
  }

  .cta-primary:active {
    transform: scale(0.98);
  }

  :global(.cta-arrow) {
    width: 1rem;
    height: 1rem;
  }

  .cta-price {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    letter-spacing: 0.03em;
    margin: 0;
  }

  @media (max-width: 640px) {
    .cta-block {
      flex-direction: column;
      align-items: flex-start;
    }
    .cta-actions {
      align-items: flex-start;
    }
  }
</style>
