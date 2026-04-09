<script lang="ts">
  import { ArrowRight } from "lucide-svelte";

  interface Props {
    creditCost: number;
    onUnlock: () => void;
  }

  let { creditCost, onUnlock }: Props = $props();
</script>

<section class="cta-block">
  <div class="cta-glow"></div>
  <div class="cta-content">
    <span class="cta-eyebrow">Phase 2 · Deep Research</span>
    <h2 class="cta-title">You found the problems.<br />Now discover how to profit from them.</h2>
    <p class="cta-desc">
      Deep Research analyzes competitive gaps, maps existing solutions, and builds a revenue model specifically for this niche — so you know exactly where to start.
    </p>

    <div class="cta-features">
      <div class="cta-feat">
        <span class="feat-check">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </span>
        Competitive landscape
      </div>
      <div class="cta-feat">
        <span class="feat-check">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </span>
        Solution gap analysis
      </div>
      <div class="cta-feat">
        <span class="feat-check">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </span>
        Revenue model
      </div>
      <div class="cta-feat">
        <span class="feat-check">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </span>
        Go-to-market strategy
      </div>
    </div>

    <div class="cta-actions">
      <button class="cta-primary" onclick={onUnlock}>
        Unlock Deep Research
        <ArrowRight class="cta-arrow" />
      </button>
    </div>

    <p class="cta-price">{creditCost} credits · One-time per niche</p>
  </div>
</section>

<style>
  .cta-block {
    --cta-bg-start: #1A1A1A;
    --cta-bg-mid: #2D2520;
    --cta-bg-end: #3D2A1F;
    --cta-text: rgba(255, 255, 255, 0.92);
    --cta-text-muted: rgba(255, 255, 255, 0.55);
    --cta-text-secondary: rgba(255, 255, 255, 0.72);
    position: relative;
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: linear-gradient(135deg, var(--cta-bg-start) 0%, var(--cta-bg-mid) 50%, var(--cta-bg-end) 100%);
    border: 1px solid rgba(240, 96, 48, 0.15);
    padding: 2.5rem 1.25rem;
    color: var(--cta-text);
    margin: 1.5rem 0;
  }

  .cta-glow {
    position: absolute;
    top: -40%;
    right: -15%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(240, 96, 48, 0.12) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
  }

  .cta-content {
    position: relative;
  }

  .cta-eyebrow {
    display: inline-block;
    font-family: var(--font-display);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    margin-bottom: 0.875rem;
  }

  .cta-title {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.3;
    color: var(--cta-text);
    margin-bottom: 0.75rem;
    max-width: 28rem;
  }

  .cta-desc {
    font-size: 0.9375rem;
    color: var(--cta-text-secondary);
    line-height: 1.65;
    margin-bottom: 1.5rem;
    max-width: 30rem;
  }

  .cta-features {
    display: flex;
    gap: 1.25rem;
    flex-wrap: wrap;
    margin-bottom: 1.75rem;
  }

  .cta-feat {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--cta-text);
  }

  .feat-check {
    width: 1.25rem;
    height: 1.25rem;
    background: rgba(240, 96, 48, 0.2);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .cta-actions {
    display: flex;
    gap: 0.875rem;
    align-items: center;
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
  }

  .cta-primary:hover {
    background: var(--color-accent-dark, #D9562A);
  }

  .cta-primary:active {
    transform: scale(0.98);
  }

  :global(.cta-arrow) {
    width: 1rem;
    height: 1rem;
  }

  .cta-price {
    font-size: 0.75rem;
    color: var(--cta-text-muted);
    margin-top: 0.75rem;
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 640px) {
    .cta-block {
      padding: 2rem 1.25rem;
    }

    .cta-title {
      font-size: 1.25rem;
    }

    .cta-features {
      flex-direction: column;
      gap: 0.625rem;
    }
  }
</style>
