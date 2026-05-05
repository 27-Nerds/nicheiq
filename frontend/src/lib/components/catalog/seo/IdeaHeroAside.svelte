<script lang="ts">
  // Right rail of IdeaHeroV2 — niche-score panel.
  // Three-tier layout per ideas-v2/page-idea.jsx:71-101 + styles.css:404-440:
  //   1. Top: composite anchor with `Niche score` kicker + tier label.
  //   2. Middle: 3 horizontal score bars (Demand / Feasibility / Opportunity)
  //      with dashed separators between rows.
  //   3. Footer: 2-col grid (e.g. Pain points / Sub-ideas) with hairline above
  //      and vertical divider between cells.

  interface Stat {
    value: string | number | null;
    label: string;
  }

  interface Props {
    scores: {
      demand: number | null;
      feasibility: number | null;
      opportunity: number | null;
    };
    /** Optional composite 0-100. When omitted, computed as mean of the 3 bars. */
    composite?: number | null;
    /** Footer renders the first 2 visible stats (mock spec). Extras truncated. */
    stats?: Stat[];
  }

  let { scores, composite = null, stats = [] }: Props = $props();

  const computedComposite = $derived.by<number | null>(() => {
    if (composite != null && Number.isFinite(composite)) return composite;
    const vals = [scores.demand, scores.feasibility, scores.opportunity].filter(
      (v): v is number => v != null && Number.isFinite(v),
    );
    if (vals.length === 0) return null;
    return vals.reduce((s, v) => s + v, 0) / vals.length;
  });

  const compositeRounded = $derived(
    computedComposite == null ? null : Math.round(computedComposite),
  );

  const tierLabel = $derived.by<string | null>(() => {
    if (compositeRounded == null) return null;
    if (compositeRounded >= 80) return "Top quartile · build now";
    if (compositeRounded >= 65) return "Strong · validate then build";
    if (compositeRounded >= 50) return "Moderate · niche play";
    return "Weak signal";
  });

  const visibleStats = $derived(
    stats.filter((s) => {
      if (s.value == null) return false;
      if (typeof s.value === "string" && s.value.trim() === "") return false;
      return true;
    }),
  );

  function fmt(v: string | number | null): string {
    if (v == null) return "—";
    if (typeof v === "number") {
      if (v >= 1000) return `${(v / 1000).toFixed(1).replace(/\.0$/, "")}k`;
      return String(v);
    }
    return v;
  }

  function pct(v: number | null): number {
    if (v == null || !Number.isFinite(v)) return 0;
    return Math.max(0, Math.min(100, v));
  }
</script>

<aside class="score-panel">
  <header class="sp-top">
    <span class="sp-label">Niche score</span>
    {#if compositeRounded != null}
      <div class="sp-overall">
        <span class="num">{compositeRounded}</span><span class="suffix">/100</span>
      </div>
      {#if tierLabel}
        <div class="sp-tier">{tierLabel}</div>
      {/if}
    {/if}
  </header>

  <div class="sp-rows">
    <div class="sp-row" data-type="demand">
      <span class="nm">Demand</span>
      <div class="bar"><span class="fill" style:width={`${pct(scores.demand)}%`}></span></div>
      <span class="val">{scores.demand == null ? "—" : Math.round(scores.demand)}</span>
    </div>
    <div class="sp-row" data-type="feasibility">
      <span class="nm">Feasibility</span>
      <div class="bar"><span class="fill" style:width={`${pct(scores.feasibility)}%`}></span></div>
      <span class="val">{scores.feasibility == null ? "—" : Math.round(scores.feasibility)}</span>
    </div>
    <div class="sp-row" data-type="opportunity">
      <span class="nm">Opportunity</span>
      <div class="bar"><span class="fill" style:width={`${pct(scores.opportunity)}%`}></span></div>
      <span class="val">{scores.opportunity == null ? "—" : Math.round(scores.opportunity)}</span>
    </div>
  </div>

  {#if visibleStats.length > 0}
    <footer class="sp-foot">
      {#each visibleStats.slice(0, 2) as s}
        <div class="fi">
          <div class="n">{fmt(s.value)}</div>
          <div class="l">{s.label}</div>
        </div>
      {/each}
    </footer>
  {/if}
</aside>

<style>
  .score-panel {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-bg-elevated, #fff);
    overflow: hidden;
  }

  /* Top — composite anchor centered, subtle gradient bg from base → elevated
     so the composite floats over a soft tonal field rather than flat white. */
  .sp-top {
    padding: 22px 24px 18px;
    text-align: center;
    border-bottom: 1px solid var(--color-border);
    background: linear-gradient(
      180deg,
      var(--color-bg-base, #fafafa) 0%,
      var(--color-bg-elevated, #fff) 100%
    );
  }
  .sp-label {
    display: block;
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 10px;
  }
  .sp-overall {
    display: inline-flex;
    align-items: baseline;
    gap: 2px;
    font-family: var(--font-display);
  }
  .sp-overall .num {
    font-size: 64px;
    font-weight: 700;
    letter-spacing: -0.04em;
    line-height: 0.9;
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
  }
  .sp-overall .suffix {
    font-size: 18px;
    color: var(--color-text-muted);
    font-weight: 500;
    letter-spacing: 0;
    margin-left: 4px;
  }
  .sp-tier {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    margin-top: 6px;
    font-weight: 500;
  }

  /* Middle — 3 horizontal score bars; dashed line between rows. */
  .sp-rows {
    padding: 14px 20px;
  }
  .sp-row {
    display: grid;
    grid-template-columns: 1fr 70px 28px;
    gap: 10px;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px dashed var(--color-border);
  }
  .sp-row:last-child {
    border-bottom: none;
  }
  .sp-row .nm {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    font-weight: 500;
  }
  .sp-row .bar {
    height: 6px;
    background: var(--color-border);
    border-radius: 3px;
    overflow: hidden;
    position: relative;
  }
  .sp-row .bar .fill {
    display: block;
    height: 100%;
    border-radius: 3px;
    transition: width 0.8s ease;
  }
  .sp-row[data-type="demand"] .bar .fill {
    background: var(--color-accent);
  }
  .sp-row[data-type="feasibility"] .bar .fill {
    background: var(--color-info);
  }
  .sp-row[data-type="opportunity"] .bar .fill {
    background: var(--color-success);
  }
  .sp-row .val {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-primary);
    text-align: right;
  }

  /* Footer — 2-col grid with hairline above + vertical divider between cells. */
  .sp-foot {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-base, #fafafa);
  }
  .sp-foot .fi {
    padding: 14px 20px;
    border-right: 1px solid var(--color-border);
  }
  .sp-foot .fi:last-child {
    border-right: none;
  }
  .sp-foot .fi .n {
    font-size: 22px;
    font-weight: 600;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    letter-spacing: -0.01em;
    line-height: 1;
  }
  .sp-foot .fi .l {
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    margin-top: 4px;
  }
</style>
