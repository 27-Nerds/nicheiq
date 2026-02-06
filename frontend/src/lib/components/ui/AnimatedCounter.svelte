<script lang="ts">
  interface Props {
    value: number;
    duration?: number;
    format?: (n: number) => string;
    class?: string;
  }

  let {
    value,
    duration = 1000,
    format = (n: number) => n.toLocaleString(),
    class: className = "",
  }: Props = $props();

  let displayValue = $state(0);
  let visible = $state(false);
  let ref: HTMLSpanElement;

  $effect(() => {
    if (visible && ref) {
      const start = performance.now();
      const startValue = displayValue;
      const diff = value - startValue;

      const animate = (now: number) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        // Ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        displayValue = Math.round(startValue + diff * eased);

        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          displayValue = value;
        }
      };

      requestAnimationFrame(animate);
    }
  });

  $effect(() => {
    if (ref) {
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            visible = true;
          }
        },
        { threshold: 0.5 },
      );
      observer.observe(ref);
      return () => observer.disconnect();
    }
  });
</script>

<span bind:this={ref} class="animated-counter {className}">
  {format(displayValue)}
</span>

<style>
  .animated-counter {
    display: inline-block;
    font-variant-numeric: tabular-nums;
  }
</style>
