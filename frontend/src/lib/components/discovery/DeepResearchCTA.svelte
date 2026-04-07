<script lang="ts">
  import { scrollVisible } from "$lib/actions/scrollVisible";
</script>

<section class="deep-cta">
  <div class="deep-cta-progress">
    <span class="deep-cta-step deep-cta-step--done">Discovery &#10003;</span>
    <span class="deep-cta-arrow">&rarr;</span>
    <span class="deep-cta-step deep-cta-step--pending">Deep Research &#9675;</span>
  </div>

  <div class="tier-bar" use:scrollVisible>
    <span class="tier-bar-label">Progress</span>
    <div class="tier-bar-track">
      <div class="tier-bar-fill tier-bar-success" style="--fill-pct: 0.36"></div>
    </div>
    <span class="tier-bar-count">36%</span>
  </div>

  <p class="deep-cta-value">Deep research adds SEO keyword sizing, pricing validation, market sizing, and a go/no-go verdict</p>

  <ul class="deep-cta-list">
    <li>SEO keyword sizing with traffic volumes</li>
    <li>Pricing model validation with ARPU estimates</li>
    <li>Market sizing (TAM / SAM / SOM)</li>
    <li>Go/no-go verdict with risk assessment</li>
  </ul>

  <p class="deep-cta-meta">15 credits &middot; Typically completes in 8&ndash;12 minutes</p>
</section>

<style>
  .deep-cta {
    background: var(--color-bg-surface);
    border-top: 2px solid var(--color-accent);
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
    padding: var(--space-6);
    margin: var(--space-4) 0;
    text-align: center;
  }

  .deep-cta-progress {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 500;
    margin-bottom: var(--space-3);
  }

  .deep-cta-step--done {
    color: var(--color-success);
  }

  .deep-cta-step--pending {
    color: var(--color-text-muted);
  }

  .deep-cta-arrow {
    color: var(--color-text-muted);
    opacity: 0.5;
  }

  /* Tier bar override */
  .deep-cta :global(.tier-bar-fill) {
    transform: scaleX(0);
  }
  .deep-cta :global(.tier-bar.visible .tier-bar-fill) {
    transform: scaleX(var(--fill-pct));
  }

  .deep-cta-value {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: var(--space-3) auto 0;
    max-width: 28rem;
  }

  .deep-cta-list {
    list-style: none;
    padding: 0;
    margin: var(--space-3) 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
  }

  .deep-cta-list li::before {
    content: "→ ";
    color: var(--color-accent);
    font-family: var(--font-mono);
  }

  .deep-cta-meta {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
</style>
