<script lang="ts">
  interface Props {
    data: number[];
    width?: number;
    height?: number;
    color?: string;
    showDot?: boolean;
    strokeWidth?: number;
    class?: string;
  }

  let {
    data,
    width = 80,
    height = 24,
    color = "var(--color-accent)",
    showDot = true,
    strokeWidth = 1.5,
    class: className = "",
  }: Props = $props();

  const points = $derived(() => {
    if (!data || data.length === 0) return "";
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const step = width / Math.max(data.length - 1, 1);

    return data
      .map((val, i) => {
        const x = i * step;
        const y = height - ((val - min) / range) * (height - 4) - 2;
        return `${x},${y}`;
      })
      .join(" ");
  });

  const lastPoint = $derived(() => {
    if (!data || data.length === 0) return { x: 0, y: height / 2 };
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const x = width;
    const y =
      height - ((data[data.length - 1] - min) / range) * (height - 4) - 2;
    return { x, y };
  });

  const trend = $derived(() => {
    if (!data || data.length < 2) return "neutral";
    const first = data[0];
    const last = data[data.length - 1];
    if (last > first * 1.05) return "up";
    if (last < first * 0.95) return "down";
    return "neutral";
  });

  const trendColor = $derived(() => {
    if (trend() === "up") return "var(--color-success)";
    if (trend() === "down") return "var(--color-error)";
    return color;
  });
</script>

<div class="sparkline-container {className}">
  <svg {width} {height} class="sparkline" viewBox="0 0 {width} {height}">
    <!-- Gradient definition -->
    <defs>
      <linearGradient
        id="sparkline-gradient-{data?.length || 0}"
        x1="0%"
        y1="0%"
        x2="100%"
        y2="0%"
      >
        <stop offset="0%" style="stop-color: {color}; stop-opacity: 0.3" />
        <stop
          offset="100%"
          style="stop-color: {trendColor()}; stop-opacity: 1"
        />
      </linearGradient>
    </defs>

    <!-- Line -->
    {#if data && data.length > 0}
      <polyline
        points={points()}
        fill="none"
        stroke="url(#sparkline-gradient-{data.length})"
        stroke-width={strokeWidth}
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <!-- End dot -->
      {#if showDot}
        <circle
          cx={lastPoint().x}
          cy={lastPoint().y}
          r="3"
          fill={trendColor()}
          class="sparkline-dot"
        />
      {/if}
    {/if}
  </svg>
</div>

<style>
  .sparkline {
    overflow: visible;
  }

  .sparkline-dot {
    filter: drop-shadow(0 0 3px currentColor);
  }
</style>
