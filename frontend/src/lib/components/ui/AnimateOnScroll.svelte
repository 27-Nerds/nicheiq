<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    animation?:
      | "fade-up"
      | "fade-in"
      | "scale-in"
      | "slide-left"
      | "slide-right";
    delay?: number;
    duration?: number;
    threshold?: number;
    once?: boolean;
    class?: string;
    children: Snippet;
  }

  let {
    animation = "fade-up",
    delay = 0,
    duration = 600,
    threshold = 0.1,
    once = true,
    class: className = "",
    children,
  }: Props = $props();

  let visible = $state(false);
  let ref: HTMLDivElement;

  $effect(() => {
    if (ref) {
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            visible = true;
            if (once) observer.disconnect();
          } else if (!once) {
            visible = false;
          }
        },
        { threshold, rootMargin: "50px" },
      );
      observer.observe(ref);
      return () => observer.disconnect();
    }
  });

  const animationClass = $derived(`animate-${animation}`);
</script>

<div
  bind:this={ref}
  class="{animationClass} {className}"
  class:visible
  style="transition-delay: {delay}ms; transition-duration: {duration}ms;"
>
  {@render children()}
</div>
