<script lang="ts">
  import { ArrowRight } from "lucide-svelte";

  interface Props {
    creditCost: number;
    onUnlock: () => void;
  }

  let { creditCost, onUnlock }: Props = $props();
</script>

<section class="cta-block">
  <div class="cta-content">
    <span class="cta-eyebrow">Phase 2 · Deep Research</span>
    <h2 class="cta-title">You found the problems.<br />Now discover how to profit from them.</h2>
    <div class="cta-row">
      <p class="cta-desc">
        Deep Research delivers competitive landscape, solution gap analysis, revenue model, and go-to-market strategy — validated for this niche so you know exactly where to start.
      </p>
      <div class="cta-actions">
        <button class="cta-primary" onclick={onUnlock}>
          Unlock Deep Research
          <ArrowRight class="cta-arrow" />
        </button>
        <p class="cta-price">{creditCost} credits · one-time per niche</p>
      </div>
    </div>
  </div>
</section>

<style>
  .cta-block {
    margin: 1.5rem 0;
    padding: 3rem 0;
    border-top: 1px solid var(--color-border-emphasis);
    border-bottom: 1px solid var(--color-border-emphasis);
    color: var(--color-text-secondary);
  }

  .cta-content {
    display: flex;
    flex-direction: column;
    gap: 0.875rem;
  }

  .cta-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
  }

  .cta-title {
    font-family: var(--font-display);
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-text-primary);
    margin: 0;
    max-width: 36rem;
  }

  .cta-row {
    display: flex;
    gap: 2rem;
    align-items: flex-end;
    justify-content: space-between;
    flex-wrap: wrap;
    margin-top: 0.5rem;
  }

  .cta-desc {
    font-size: 0.9375rem;
    line-height: 1.65;
    color: var(--color-text-secondary);
    max-width: 32rem;
    margin: 0;
    flex: 1 1 22rem;
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
      padding: 2rem 0;
    }
    .cta-title {
      font-size: 1.375rem;
    }
    .cta-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }
    .cta-actions {
      align-items: flex-start;
    }
  }
</style>
