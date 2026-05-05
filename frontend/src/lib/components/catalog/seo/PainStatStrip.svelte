<script lang="ts">
  import { severityTier, type SeverityTier } from "$lib/types/publicCatalog.js";

  interface Props {
    /** Pre-scaled to 0-100 by the route via scaleSeverity(value, 'pain'). */
    severity: number | null;
    /** Raw 0-1 severity score for tier derivation. */
    severityRaw?: number | null;
    /** Pre-scaled to 0-100 by the route. WTP shares the 0-1 Pydantic convention. */
    willingnessToPay: number | null;
    opportunityLevel: string | null;
    mentionCount?: number | null;
    /** Source platforms (e.g. ["reddit", "hackernews"]). When non-empty,
     *  rendered as a "Reported on" mono chip row inside the strip. */
    sourcePlatforms?: string[] | null;
  }

  let {
    severity,
    severityRaw = null,
    willingnessToPay,
    opportunityLevel,
    mentionCount = null,
    sourcePlatforms = null,
  }: Props = $props();

  const platformChips = $derived(
    Array.isArray(sourcePlatforms)
      ? sourcePlatforms.filter((s): s is string => typeof s === "string" && s.trim() !== "")
      : [],
  );

  const tier: SeverityTier | null = $derived(severityTier(severityRaw));

  const opportunityNorm = $derived.by<'high' | 'medium' | 'low' | null>(() => {
    if (typeof opportunityLevel !== 'string') return null;
    const u = opportunityLevel.trim().toLowerCase();
    if (u === 'high') return 'high';
    if (u === 'medium' || u === 'med') return 'medium';
    if (u === 'low') return 'low';
    return null;
  });
</script>

<section class="strip-wrap">
  <div class="strip">
    <div class="tile">
      <span class="label">Severity</span>
      <div class="value-row">
        <span class="num severity">{severity ?? '—'}</span>
        {#if tier}
          <span class="tier-chip severity-tier-{tier}">{tier}</span>
        {/if}
      </div>
      <span class="unit">/ 100</span>
    </div>
    <div class="tile">
      <span class="label">Willingness to pay</span>
      <span class="num wtp">{willingnessToPay ?? '—'}</span>
      <span class="unit">/ 100</span>
    </div>
    <div class="tile">
      <span class="label">Opportunity</span>
      {#if opportunityNorm}
        <span class="opp-pill opportunity-tier-{opportunityNorm}">{opportunityNorm}</span>
      {:else}
        <span class="num">—</span>
      {/if}
    </div>
  </div>
  {#if mentionCount != null && mentionCount > 0}
    <p class="mentions">
      <span class="m-num">{mentionCount.toLocaleString()}</span>
      <span class="m-label">discussions</span>
    </p>
  {/if}
  {#if platformChips.length > 0}
    <div class="reported-on" class:has-mentions={mentionCount != null && mentionCount > 0}>
      <span class="reported-label">Reported on</span>
      <ul class="reported-chips">
        {#each platformChips as p}
          <li class="reported-chip">{p}</li>
        {/each}
      </ul>
    </div>
  {/if}
</section>

<style>
  .strip-wrap {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    padding: 18px 22px;
    margin: 0 0 36px;
  }
  .strip {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    align-items: end;
  }
  @media (max-width: 700px) {
    .strip {
      grid-template-columns: 1fr 1fr;
    }
    .strip .tile:nth-child(3) {
      grid-column: 1 / -1;
    }
  }
  .tile {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .value-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
  }
  .tier-chip {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 2px 6px;
    border-radius: 3px;
    border: 1px solid var(--color-border);
  }
  /* `severity-tier-*` namespace prevents collision with the
     `opportunity-tier-*` classes defined further down. Do NOT rename back
     to `.tier-*` — both selectors used to share those names and the second
     definition silently overrode the first. */
  .severity-tier-critical {
    color: var(--color-error, #dc2626);
    border-color: var(--color-error, #dc2626);
  }
  .severity-tier-high {
    color: var(--color-accent);
    border-color: var(--color-accent);
  }
  .severity-tier-medium {
    color: var(--color-text-muted);
  }
  .num {
    font-family: var(--font-mono);
    font-size: 32px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    color: var(--color-text-primary);
  }
  .num.severity {
    color: var(--color-error, #dc2626);
  }
  .num.wtp {
    color: var(--color-accent);
  }
  .unit {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
  }
  .opp-pill {
    display: inline-flex;
    align-items: center;
    align-self: flex-start;
    padding: 4px 10px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border: 1px solid var(--color-border);
    background: var(--color-surface-elevated, #fafafa);
  }
  /* Opportunity pill tiers — separate namespace from severity-tier-* above. */
  .opportunity-tier-high {
    color: var(--color-accent, #b45309);
    border-color: var(--color-accent, #b45309);
  }
  .opportunity-tier-medium {
    color: var(--color-text-primary);
  }
  .opportunity-tier-low {
    color: var(--color-text-muted);
  }
  .mentions {
    margin: 14px 0 0;
    padding-top: 12px;
    border-top: 1px solid var(--color-border);
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }
  .m-num {
    font-size: 18px;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .m-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  /* Reported-on platform chips. When the mentions row is present, share its
     hairline divider; otherwise the chip block adds its own top border. */
  .reported-on {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .reported-on.has-mentions {
    margin-top: 8px;
    padding-top: 0;
    border-top: 0;
  }
  .reported-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }
  .reported-chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .reported-chip {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 3px 8px;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
  }
</style>
