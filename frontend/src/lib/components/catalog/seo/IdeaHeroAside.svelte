<script lang="ts">
  import DataList from "./DataList.svelte";
  import DataRow from "./DataRow.svelte";

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
      /** Optional 4th axis: how differentiated the idea is (BaseSolutionIdea.novelty_score). */
      novelty?: number | null;
      /** Optional 5th axis: can a solo dev ship it (BaseSolutionIdea.solo_dev_feasibility). */
      soloDev?: number | null;
    };
    /** Optional composite 0-100. When omitted, computed as mean of the 3 PRIMARY
     *  bars (demand/feasibility/opportunity). Novelty + solo-dev are
     *  personal-fit context, deliberately excluded from the niche-score composite. */
    composite?: number | null;
    /** Optional verdict label (e.g. "GO" / "CONDITIONAL" / "NO-GO"). When set,
     *  renders as a mono pill under the tier line. */
    verdict?: 'GO' | 'CONDITIONAL' | 'NO-GO' | null;
    /** Footer renders the first 2 visible stats (mock spec). Extras truncated. */
    stats?: Stat[];
  }

  let { scores, composite = null, verdict = null, stats = [] }: Props = $props();

  const computedComposite = $derived.by<number | null>(() => {
    if (composite != null && Number.isFinite(composite)) return composite;
    const vals = [scores.demand, scores.feasibility, scores.opportunity].filter(
      (v): v is number => v != null && Number.isFinite(v),
    );
    if (vals.length === 0) return null;
    return vals.reduce((s, v) => s + v, 0) / vals.length;
  });

  const hasFitRow = $derived(
    (scores.novelty != null && Number.isFinite(scores.novelty)) ||
      (scores.soloDev != null && Number.isFinite(scores.soloDev)),
  );

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
      {#if verdict}
        <div class="sp-verdict" data-verdict={verdict.toLowerCase()}>{verdict}</div>
      {/if}
    {/if}
  </header>

  <div class="sp-rows">
    <DataList>
      <DataRow label="Demand" align="center">
        <div class="sp-value" data-type="demand">
          <div class="bar"><span class="fill" style:width={`${pct(scores.demand)}%`}></span></div>
          <span class="val">{scores.demand == null ? "—" : Math.round(scores.demand)}</span>
        </div>
      </DataRow>
      <DataRow label="Feasibility" align="center">
        <div class="sp-value" data-type="feasibility">
          <div class="bar"><span class="fill" style:width={`${pct(scores.feasibility)}%`}></span></div>
          <span class="val">{scores.feasibility == null ? "—" : Math.round(scores.feasibility)}</span>
        </div>
      </DataRow>
      <DataRow label="Opportunity" align="center">
        <div class="sp-value" data-type="opportunity">
          <div class="bar"><span class="fill" style:width={`${pct(scores.opportunity)}%`}></span></div>
          <span class="val">{scores.opportunity == null ? "—" : Math.round(scores.opportunity)}</span>
        </div>
      </DataRow>
      {#if hasFitRow}
        <div class="sp-fit-divider" aria-hidden="true">
          <span>Founder fit</span>
        </div>
        {#if scores.novelty != null && Number.isFinite(scores.novelty)}
          <DataRow label="Novelty" align="center">
            <div class="sp-value" data-type="novelty">
              <div class="bar"><span class="fill" style:width={`${pct(scores.novelty)}%`}></span></div>
              <span class="val">{Math.round(scores.novelty)}</span>
            </div>
          </DataRow>
        {/if}
        {#if scores.soloDev != null && Number.isFinite(scores.soloDev)}
          <DataRow label="Solo-dev" align="center">
            <div class="sp-value" data-type="solo-dev">
              <div class="bar"><span class="fill" style:width={`${pct(scores.soloDev)}%`}></span></div>
              <span class="val">{Math.round(scores.soloDev)}</span>
            </div>
          </DataRow>
        {/if}
      {/if}
    </DataList>
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

  /* Middle — 3 horizontal score bars rendered as <DataList> + <DataRow>.
     `.sp-rows` provides horizontal padding around the dashed-row list;
     `.sp-value` is the per-row [bar : numeric] layout inside each DataRow's
     value cell. The data-type attribute carries the bar-fill color. */
  .sp-rows {
    padding: 14px 20px;
  }
  .sp-value {
    display: grid;
    grid-template-columns: 1fr 28px;
    gap: 8px;
    align-items: center;
  }
  .sp-value .bar {
    height: 6px;
    background: var(--color-border);
    border-radius: 3px;
    overflow: hidden;
    position: relative;
  }
  .sp-value .bar .fill {
    display: block;
    height: 100%;
    border-radius: 3px;
    transition: width 0.8s ease;
  }
  .sp-value[data-type="demand"] .bar .fill {
    background: var(--color-accent);
  }
  .sp-value[data-type="feasibility"] .bar .fill {
    background: var(--color-info);
  }
  .sp-value[data-type="opportunity"] .bar .fill {
    background: var(--color-success);
  }
  /* Founder-fit axes — muted slate fill so they read as secondary signals
     beneath the niche-score primary axes. */
  .sp-value[data-type="novelty"] .bar .fill,
  .sp-value[data-type="solo-dev"] .bar .fill {
    background: var(--color-text-muted);
  }
  /* Mini-divider separating the 3 niche-score axes from the 2 founder-fit axes.
     Keeps composite/tier semantically tied to the primary 3 above the divider. */
  .sp-fit-divider {
    margin: 4px 0 2px;
    padding-top: 8px;
    border-top: 1px solid var(--color-border);
    text-align: left;
  }
  .sp-fit-divider span {
    font-family: var(--font-mono);
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  /* Verdict pill under the tier label inside the score panel header. */
  .sp-verdict {
    display: inline-block;
    margin-top: 10px;
    padding: 4px 10px;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: var(--color-bg-elevated, #fff);
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: var(--color-text-muted);
  }
  .sp-verdict[data-verdict="go"] {
    color: var(--color-success-dark, #16a34a);
    border-color: var(--color-success, #16a34a);
  }
  .sp-verdict[data-verdict="conditional"] {
    color: var(--color-accent);
    border-color: var(--color-accent-muted, var(--color-accent));
  }
  .sp-verdict[data-verdict="no-go"] {
    color: var(--color-text-muted);
    border-color: var(--color-border);
  }
  .sp-value .val {
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
