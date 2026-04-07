<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    sectionNumber: string;
    title: string;
    teaser: string;
    children: Snippet;
  }

  let { sectionNumber, title, teaser, children }: Props = $props();
</script>

<section class="locked-section">
  <div class="locked-content" aria-hidden="true">
    {@render children()}
  </div>
  <div class="locked-fade"></div>
  <div class="locked-label">
    <span class="locked-counter">{sectionNumber}</span>
    <span class="locked-title">{title}</span>
    <span class="locked-teaser">{teaser}</span>
  </div>
</section>

<style>
  .locked-section {
    position: relative;
    overflow: hidden;
    max-height: 320px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .locked-content {
    filter: blur(5px);
    user-select: none;
    pointer-events: none;
    opacity: 0.5;
  }

  .locked-fade {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 160px;
    background: linear-gradient(to bottom, transparent, var(--color-bg-base));
    pointer-events: none;
  }

  .locked-label {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    pointer-events: none;
  }

  .locked-label::before {
    content: '';
    position: absolute;
    inset: 25% 30%;
    background: color-mix(in srgb, var(--color-bg-base) 55%, transparent);
    backdrop-filter: blur(8px);
    border-radius: var(--radius-md);
  }

  .locked-counter {
    position: relative;
    font-family: var(--font-display);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .locked-title {
    position: relative;
    font-family: var(--font-display);
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  .locked-teaser {
    position: relative;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    letter-spacing: 0.05em;
    max-width: 320px;
    text-align: center;
  }
</style>
