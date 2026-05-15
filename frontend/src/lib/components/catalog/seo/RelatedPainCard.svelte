<script lang="ts">
  import type { SiblingPainSummary } from "$lib/types/catalog-landing.js";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";

  interface Props {
    pain: SiblingPainSummary;
  }

  let { pain }: Props = $props();

  const sev100 = $derived(scaleSeverity(pain.severityScore, "pain"));
  const tier = $derived.by(() => {
    if (sev100 == null) return "lo";
    if (sev100 >= 75) return "high";
    if (sev100 >= 60) return "med";
    return "lo";
  });
</script>

<a class="card tier-{tier}" href={`/pain-point/${pain.slug}`}>
  <div class="severity">
    <span class="num">{sev100 ?? "—"}</span>
    <span class="label">Severity</span>
  </div>
  <div class="body">
    <h4>{pain.title}</h4>
    {#if pain.description}
      <p class="desc">{pain.description}</p>
    {/if}
  </div>
  <div class="meta">
    {#if pain.mentionCount > 0}
      <span class="mono">{pain.mentionCount.toLocaleString()} mentions</span>
    {/if}
  </div>
</a>

<style>
  .card {
    display: grid;
    grid-template-columns: 72px 1fr auto;
    gap: 16px;
    align-items: center;
    padding: 14px 16px;
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-error, #dc2626);
    border-radius: 6px;
    background: var(--color-surface, #fff);
    color: inherit;
    text-decoration: none;
    transition: background-color 140ms ease, box-shadow 160ms ease,
      border-color 140ms ease;
  }
  .tier-med {
    border-left-color: var(--color-accent);
  }
  .tier-lo {
    border-left-color: var(--color-info);
  }
  /* Two-layer neutral shadow on hover only — flat at rest preserves the
     refined-minimal voice; subtle elevation on hover telegraphs clickability
     without the generic "card lift" translateY tell. */
  .card:hover {
    background: var(--color-surface-elevated, #fafafa);
    box-shadow:
      0 1px 2px rgba(24, 24, 27, 0.04),
      0 4px 12px rgba(24, 24, 27, 0.06);
  }
  .severity {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    padding: 6px 8px;
    background: var(--color-surface-elevated, #fafafa);
    border: 1px solid var(--color-border);
    border-radius: 5px;
  }
  .severity .num {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 700;
    color: var(--color-error, #dc2626);
    line-height: 1;
  }
  .tier-med .severity .num {
    color: var(--color-accent);
  }
  .tier-lo .severity .num {
    color: var(--color-info);
  }
  .severity .label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .body {
    min-width: 0;
  }
  h4 {
    margin: 0 0 4px;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.35;
    letter-spacing: -0.005em;
    color: var(--color-text-primary);
  }
  .desc {
    margin: 0;
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-secondary, var(--color-text-primary));
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .meta {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  @media (max-width: 600px) {
    .card {
      grid-template-columns: 56px 1fr;
    }
    .meta {
      grid-column: 1 / -1;
      text-align: right;
    }
  }
</style>
