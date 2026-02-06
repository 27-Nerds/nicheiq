<script lang="ts">
  interface Props {
    variant?: "text" | "circular" | "rectangular";
    width?: string;
    height?: string;
    class?: string;
  }

  let {
    variant = "text",
    width,
    height,
    class: className = "",
  }: Props = $props();

  const variantClass = $derived(`skeleton-${variant}`);
</script>

<div
  class="skeleton {variantClass} {className}"
  style:width
  style:height
  role="presentation"
  aria-hidden="true"
></div>

<style>
  .skeleton {
    background: linear-gradient(
      90deg,
      var(--color-bg-surface) 0%,
      var(--color-bg-hover) 50%,
      var(--color-bg-surface) 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 4px;
  }

  .skeleton-text {
    height: 1em;
    width: 100%;
  }

  .skeleton-circular {
    border-radius: 50%;
  }

  .skeleton-rectangular {
    border-radius: 8px;
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .skeleton {
      animation: none;
    }
  }
</style>
