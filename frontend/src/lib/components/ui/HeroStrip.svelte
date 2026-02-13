<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    children: Snippet;
    primary?: Snippet;
    variant?: "default" | "compact";
    class?: string;
  }

  let {
    children,
    primary,
    variant = "default",
    class: className = "",
  }: Props = $props();
</script>

<div class="hero-strip hero-strip--{variant} {className}">
  {#if primary}
    <div class="hero-strip__primary">
      {@render primary()}
    </div>
  {/if}
  <div class="hero-strip__rail" class:hero-strip__rail--full={!primary}>
    {@render children()}
  </div>
</div>

<style>
  .hero-strip {
    display: flex;
    align-items: stretch;
    gap: 1rem;
    padding: 1rem 1.25rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    margin-bottom: 1.25rem;
    position: relative;
    overflow: hidden;
  }

  /* Subtle dot grid pattern background */
  .hero-strip::before {
    content: "";
    position: absolute;
    inset: 0;
    background-image: radial-gradient(
      circle,
      var(--color-border) 1px,
      transparent 1px
    );
    background-size: 16px 16px;
    opacity: 0.3;
    pointer-events: none;
  }

  .hero-strip--compact {
    padding: 0.875rem 1rem;
    gap: 0.875rem;
  }

  /* Primary metric card (elevated) */
  .hero-strip__primary {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    padding: 0.875rem 1.25rem;
    background: linear-gradient(
      135deg,
      var(--color-bg-surface) 0%,
      var(--color-bg-elevated) 100%
    );
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    position: relative;
    z-index: 1;
  }

  /* Secondary metrics rail */
  .hero-strip__rail {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0;
    position: relative;
    z-index: 1;
  }

  .hero-strip__rail--full {
    justify-content: flex-start;
  }

  /* Add dividers between metrics via CSS */
  .hero-strip__rail > :global(*) {
    position: relative;
    padding: 0 1.25rem;
  }

  .hero-strip__rail > :global(*:not(:last-child))::after {
    content: "";
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 1px;
    height: 60%;
    background: var(--color-border);
  }

  .hero-strip__rail > :global(*:first-child) {
    padding-left: 0;
  }

  .hero-strip__rail > :global(*:last-child) {
    padding-right: 0;
  }

  /* Entrance animation */
  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .hero-strip__rail > :global(*) {
    animation: slideUp 0.4s ease-out backwards;
  }

  .hero-strip__rail > :global(*:nth-child(1)) {
    animation-delay: 0.05s;
  }
  .hero-strip__rail > :global(*:nth-child(2)) {
    animation-delay: 0.1s;
  }
  .hero-strip__rail > :global(*:nth-child(3)) {
    animation-delay: 0.15s;
  }
  .hero-strip__rail > :global(*:nth-child(4)) {
    animation-delay: 0.2s;
  }
  .hero-strip__rail > :global(*:nth-child(5)) {
    animation-delay: 0.25s;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .hero-strip {
      flex-direction: column;
      align-items: stretch;
      gap: 1rem;
    }

    .hero-strip__primary {
      justify-content: center;
    }

    .hero-strip__rail {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.75rem;
    }

    .hero-strip__rail > :global(*) {
      padding: 0;
    }

    .hero-strip__rail > :global(*:not(:last-child))::after {
      display: none;
    }
  }

  @media (max-width: 480px) {
    .hero-strip__rail {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>
