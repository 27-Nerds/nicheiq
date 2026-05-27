<script lang="ts">
  import type { ComponentType } from "svelte";

  interface Props {
    icon: ComponentType;
    tone?: "accent" | "success" | "error";
  }

  let { icon: Icon, tone = "accent" }: Props = $props();

  // Full literal class strings per tone so Tailwind's scanner picks them up.
  const toneClasses: Record<string, string> = {
    accent: "bg-accent/10 border-accent/20 text-accent",
    success: "bg-success/10 border-success/20 text-success",
    error: "bg-error/10 border-error/20 text-error",
  };
</script>

<div
  class="badge mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full border {toneClasses[
    tone
  ]}"
>
  <Icon class="h-7 w-7" />
</div>

<style>
  .badge {
    animation: badge-pop 260ms var(--ease-default, cubic-bezier(0.16, 1, 0.3, 1)) both;
  }

  @keyframes badge-pop {
    from {
      opacity: 0;
      transform: scale(0.85);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .badge {
      animation: none;
    }
  }
</style>
