<script lang="ts">
  // Right rail of PainPointHeroV2 — pain-score panel mirroring IdeaHeroAside.
  // Three-tier layout: composite anchor → metric rows → footer stats.
  // Severity + WTP render as horizontal score bars (0-100); Opportunity is a
  // categorical row (high/medium/low) styled as a chip rather than a bar.
  // Composite is the mean of the two 0-100 scores (null rule mirrors
  // IdeaHeroAside.svelte:38-45). Quality tier is rendered via the shared
  // QualityTierBadge component — consistent tone mapping with the category hero.

  import type { QualitySignals } from "$lib/types/publicCatalog.js";
  import QualityTierBadge from "./QualityTierBadge.svelte";
  import DataList from "./DataList.svelte";
  import DataRow from "./DataRow.svelte";

  interface Props {
    /** 0-100 (already scaled at the route). */
    severity: number | null;
    /** 0-100 (already scaled at the route). */
    willingnessToPay: number | null;
    /** Pre-normalized at the route — high/medium/low/null. */
    opportunity: 'high' | 'medium' | 'low' | null;
    /** Quality signals from the research context. Drives the tier badge. */
    qualitySignals?: QualitySignals | null;
    /** Optional explicit composite (0-100). When omitted, computed as mean of finite [severity, WTP]. */
    composite?: number | null;
    /** Mention count surfaced in the footer. */
    mentionCount?: number | null;
    /** Source platforms surfaced as mono chips in the footer. */
    sourcePlatforms?: string[] | null;
  }

  let {
    severity,
    willingnessToPay,
    opportunity,
    qualitySignals = null,
    composite = null,
    mentionCount = null,
    sourcePlatforms = null,
  }: Props = $props();

  const computedComposite = $derived.by<number | null>(() => {
    if (composite != null && Number.isFinite(composite)) return composite;
    const vals = [severity, willingnessToPay].filter(
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
    if (compositeRounded >= 70) return 'Critical pain · ship this';
    if (compositeRounded >= 55) return 'High-impact · validate then ship';
    if (compositeRounded >= 40) return 'Notable · niche play';
    return 'Minor signal';
  });

  const platformChips = $derived(
    Array.isArray(sourcePlatforms)
      ? sourcePlatforms.filter((s): s is string => typeof s === 'string' && s.trim() !== '')
      : [],
  );

  const hasFooter = $derived(
    (mentionCount != null && mentionCount > 0) || platformChips.length > 0,
  );

  function pct(v: number | null): number {
    if (v == null || !Number.isFinite(v)) return 0;
    return Math.max(0, Math.min(100, v));
  }
</script>

<aside class="score-panel">
  <header class="sp-top">
    <span class="sp-label">Pain score</span>
    {#if compositeRounded != null}
      <div class="sp-overall">
        <span class="num">{compositeRounded}</span><span class="suffix">/100</span>
      </div>
      {#if tierLabel}
        <div class="sp-tier">{tierLabel}</div>
      {/if}
    {/if}
    {#if qualitySignals}
      <div class="sp-quality">
        <QualityTierBadge signals={qualitySignals} />
      </div>
    {/if}
  </header>

  <div class="sp-rows">
    <DataList>
      <DataRow label="Severity" align="center">
        <div class="sp-value" data-type="severity">
          <div class="bar"><span class="fill" style:width={`${pct(severity)}%`}></span></div>
          <span class="val">{severity == null ? '—' : Math.round(severity)}</span>
        </div>
      </DataRow>
      <DataRow label="Willingness to pay" align="center">
        <div class="sp-value" data-type="wtp">
          <div class="bar"><span class="fill" style:width={`${pct(willingnessToPay)}%`}></span></div>
          <span class="val">{willingnessToPay == null ? '—' : Math.round(willingnessToPay)}</span>
        </div>
      </DataRow>
      {#if opportunity}
        <DataRow label="Opportunity" align="center">
          <div class="sp-cat-value">
            <span class="opp-pill" data-tier={opportunity}>{opportunity}</span>
          </div>
        </DataRow>
      {/if}
    </DataList>
  </div>

  {#if hasFooter}
    <footer class="sp-foot">
      {#if mentionCount != null && mentionCount > 0}
        <div class="fi">
          <div class="n">{mentionCount.toLocaleString()}</div>
          <div class="l">Discussions</div>
        </div>
      {/if}
      {#if platformChips.length > 0}
        <div class="fi platforms">
          <div class="l">Reported on</div>
          <ul class="chips">
            {#each platformChips as p}
              <li class="chip">{p}</li>
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
    color: var(--color-error, #dc2626);
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
  .sp-quality {
    margin-top: 10px;
    display: inline-flex;
    justify-content: center;
  }

  .sp-rows {
    padding: 14px 20px;
  }
  /* Per-row bar-and-numeric layout inside DataRow's value cell. */
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
  .sp-value[data-type='severity'] .bar .fill {
    background: var(--color-error, #dc2626);
  }
  .sp-value[data-type='wtp'] .bar .fill {
    background: var(--color-accent);
  }
  .sp-value .val {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-primary);
    text-align: right;
  }

  /* Categorical row (Opportunity) — pill right-aligned inside the value cell. */
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
  .opp-pill[data-tier='high'] {
    color: var(--color-accent);
    border-color: var(--color-accent);
  }
  .opp-pill[data-tier='medium'] {
    color: var(--color-text-primary);
  }

  .sp-foot {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0;
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
