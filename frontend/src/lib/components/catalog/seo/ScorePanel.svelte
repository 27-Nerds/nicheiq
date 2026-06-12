<script lang="ts">
  import type { Snippet } from "svelte";
  import DataList from "./DataList.svelte";
  import DataRow from "./DataRow.svelte";

  // Canonical right-rail score panel shared by IdeaHeroAside (niche score) and
  // PainPointHeroAside (pain score). Three-tier chassis:
  //   1. Header — uppercase kicker + composite /100 anchor + tier line, plus an
  //      optional verdict pill and/or header-extra slot (e.g. quality badge).
  //   2. Rows — dashed-ledger metric list: score bars, a categorical pill, or a
  //      group subhead. All rendered here so the styling is single-sourced.
  //   3. Footer — optional numeric stat cells and/or a chip group.
  // Theme via the `accent` prop (sets --score-accent → composite number + any
  // bar that omits its own tone). Bars keep per-metric tones via row.tone.

  export type ScoreRow =
    | { kind: "bar"; label: string; value: number | null; tone?: string }
    | { kind: "pill"; label: string; text: string; tier?: "high" | "medium" | "low" | null }
    | { kind: "subhead"; label: string };

  interface Props {
    /** Uppercase kicker, e.g. "Niche score" / "Pain score". */
    label: string;
    /** Composite 0-100. Header collapses to just the label when null. */
    composite: number | null;
    /** Tier line under the composite (e.g. "Top quartile · build now"). */
    tier?: string | null;
    /** One-line provenance note under the composite (e.g. "avg of severity +
     *  willingness-to-pay"). Only pass copy that matches the ACTUAL
     *  computation feeding `composite` — trace it before writing. */
    formulaNote?: string | null;
    /** CSS color for the composite number; themes the panel. Default accent. */
    accent?: string;
    /** Optional verdict pill rendered under the tier line. */
    verdict?: "GO" | "CONDITIONAL" | "NO-GO" | null;
    /** Optional header extra (e.g. a quality-tier badge) under the tier. */
    headerExtra?: Snippet;
    /** Metric rows: score bars, a categorical pill, or a group subhead. */
    rows: ScoreRow[];
    /** Footer numeric cells (e.g. mention count). */
    footerStats?: Array<{ value: string | number; label: string }>;
    /** Footer chip group (e.g. source platforms). */
    footerChips?: { label: string; items: string[] } | null;
  }

  let {
    label,
    composite,
    tier = null,
    formulaNote = null,
    accent = "var(--color-accent)",
    verdict = null,
    headerExtra,
    rows,
    footerStats = [],
    footerChips = null,
  }: Props = $props();

  const compositeRounded = $derived(
    composite == null || !Number.isFinite(composite) ? null : Math.round(composite),
  );

  const hasFooter = $derived(
    footerStats.length > 0 || (footerChips?.items?.length ?? 0) > 0,
  );

  // Stat cells size to content; the chip group flexes. Mirrors the legacy
  // pain-panel footer (`auto 1fr`) and generalizes to N stat cells.
  const footerCols = $derived(
    footerChips && footerChips.items.length > 0
      ? `repeat(${footerStats.length}, auto) minmax(0, 1fr)`
      : `repeat(${Math.max(footerStats.length, 1)}, 1fr)`,
  );

  function pct(v: number | null): number {
    if (v == null || !Number.isFinite(v)) return 0;
    return Math.max(0, Math.min(100, v));
  }
</script>

<aside class="score-panel" style:--score-accent={accent}>
  <header class="sp-top">
    <span class="sp-label">{label}</span>
    {#if compositeRounded != null}
      <div class="sp-overall">
        <span class="num">{compositeRounded}</span><span class="suffix">/100</span>
      </div>
      {#if tier}
        <div class="sp-tier">{tier}</div>
      {/if}
      {#if formulaNote}
        <div class="sp-formula">{formulaNote}</div>
      {/if}
      {#if verdict}
        <div class="sp-verdict" data-verdict={verdict.toLowerCase()}>{verdict}</div>
      {/if}
    {/if}
    {#if headerExtra}
      <div class="sp-extra">{@render headerExtra()}</div>
    {/if}
  </header>

  <div class="sp-rows">
    <DataList>
      {#each rows as row}
        {#if row.kind === "subhead"}
          <div class="sp-subhead" aria-hidden="true"><span>{row.label}</span></div>
        {:else if row.kind === "bar"}
          <DataRow label={row.label} align="center">
            <div class="sp-value">
              <div class="bar">
                <span
                  class="fill"
                  style:width={`${pct(row.value)}%`}
                  style:background={row.tone ?? "var(--score-accent)"}
                ></span>
              </div>
              <span class="val">{row.value == null ? "—" : Math.round(row.value)}</span>
            </div>
          </DataRow>
        {:else}
          <DataRow label={row.label} align="center">
            <div class="sp-cat-value">
              <span class="opp-pill" data-tier={row.tier ?? undefined}>{row.text}</span>
            </div>
          </DataRow>
        {/if}
      {/each}
    </DataList>
  </div>

  {#if hasFooter}
    <footer class="sp-foot" style:grid-template-columns={footerCols}>
      {#each footerStats as s}
        <div class="fi">
          <div class="n">{s.value}</div>
          <div class="l">{s.label}</div>
        </div>
      {/each}
      {#if footerChips && footerChips.items.length > 0}
        <div class="fi platforms">
          <div class="l">{footerChips.label}</div>
          <ul class="chips">
            {#each footerChips.items as item}
              <li class="chip">{item}</li>
            {/each}
          </ul>
        </div>
      {/if}
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

  /* Header — composite anchor centered over a soft tonal gradient so the number
     floats rather than sitting on flat white. */
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
    color: var(--score-accent);
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
  /* Composite provenance note — quiet mono line so the big number can't be
     misread against its strongest component (e.g. 70 next to severity 85). */
  .sp-formula {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    margin-top: 4px;
  }
  /* Verdict pill under the tier line. */
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
  /* Generic header-extra slot (e.g. quality-tier badge). */
  .sp-extra {
    margin-top: 10px;
    display: flex;
    justify-content: center;
  }

  /* Rows — dashed-ledger metric list. */
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
  .sp-value .val {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-primary);
    text-align: right;
  }

  /* Group subhead (e.g. "Founder fit") — no rule of its own; the preceding
     row's dashed separator + this label carry the break. */
  .sp-subhead {
    margin: 10px 0 2px;
    text-align: left;
  }
  .sp-subhead span {
    font-family: var(--font-mono);
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
    color: var(--color-text-muted);
  }

  /* Categorical row — pill right-aligned in the value cell. */
  .sp-cat-value {
    display: flex;
    justify-content: flex-end;
  }
  .opp-pill {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border: 1px solid var(--color-border);
    background: var(--color-surface-elevated, #fafafa);
    color: var(--color-text-muted);
  }
  .opp-pill[data-tier="high"] {
    color: var(--color-accent);
    border-color: var(--color-accent);
  }
  .opp-pill[data-tier="medium"] {
    color: var(--color-text-primary);
  }

  /* Footer — stat cells + optional chip group, single hairline above. */
  .sp-foot {
    display: grid;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-base, #fafafa);
  }
  .sp-foot .fi {
    padding: 14px 20px;
    border-right: 1px solid var(--color-border);
    min-width: 0;
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
  .sp-foot .platforms .l {
    margin-top: 0;
    margin-bottom: 6px;
  }
  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .chip {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 2px 6px;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
  }
</style>
