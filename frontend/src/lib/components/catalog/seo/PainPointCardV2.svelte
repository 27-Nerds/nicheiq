<script lang="ts">
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";

  // Single pain card. Severity-tile + title + description + quote + meta.
  // Used inside PainPointsList (idea/pain-point detail) and link-mode on
  // category landing top-pain table when clicked.

  interface Props {
    pain: PainPointPreview;
    /** When true, render as <a href="/pain-point/[slug]">. Default false. */
    asLink?: boolean;
  }

  let { pain, asLink = false }: Props = $props();

  const sev100 = $derived(scaleSeverity(pain.severityScore, "pain"));
  const tier = $derived.by(() => {
    if (sev100 == null) return "lo";
    if (sev100 >= 75) return "high";
    if (sev100 >= 60) return "med";
    return "lo";
  });

  const quote = $derived(
    Array.isArray(pain.representativeQuotes) && pain.representativeQuotes.length > 0
      ? pain.representativeQuotes[0]
      : null,
  );
  const segments = $derived(
    Array.isArray(pain.affectedSegments) ? pain.affectedSegments.slice(0, 3) : [],
  );
</script>

{#if asLink}
  <a class="pain-card tier-{tier}" href={`/pain-point/${pain.slug}`}>
    <div class="head">
      <div class="severity">
        <div class="v">{sev100 == null ? "—" : sev100}</div>
        <div class="l">Severity</div>
      </div>
      <h4>{pain.title}</h4>
    </div>
    <p class="desc">{pain.description}</p>
    {#if quote}
      <div class="quote">
        "{quote}"
        {#if pain.mentionCount}
          <span class="src-line">{pain.mentionCount} similar mentions</span>
        {/if}
      </div>
    {/if}
    {#if segments.length > 0}
      <div class="meta">
        <span>{segments.join(" / ")}</span>
      </div>
    {/if}
  </a>
{:else}
  <article class="pain-card tier-{tier}">
    <div class="head">
      <div class="severity">
        <div class="v">{sev100 == null ? "—" : sev100}</div>
        <div class="l">Severity</div>
      </div>
      <h4>{pain.title}</h4>
    </div>
    <p class="desc">{pain.description}</p>
    {#if quote}
      <div class="quote">
        "{quote}"
        {#if pain.mentionCount}
          <span class="src-line">{pain.mentionCount} similar mentions</span>
        {/if}
      </div>
    {/if}
    {#if segments.length > 0}
      <div class="meta">
        <span>{segments.join(" / ")}</span>
      </div>
    {/if}
  </article>
{/if}

<style>
  .pain-card {
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-error, #dc2626);
    border-radius: 6px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    color: inherit;
    text-decoration: none;
  }
  .tier-med {
    border-left-color: var(--color-accent);
  }
  .tier-lo {
    border-left-color: var(--color-info);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .severity {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    padding: 5px 9px;
    background: var(--color-surface-elevated, #fafafa);
    border: 1px solid var(--color-border);
    border-radius: 5px;
    min-width: 60px;
  }
  .severity .v {
    font-size: 15px;
    font-weight: 600;
    color: var(--color-error, #dc2626);
    line-height: 1;
  }
  .tier-med .severity .v {
    color: var(--color-accent);
  }
  .tier-lo .severity .v {
    color: var(--color-info);
  }
  .severity .l {
    font-size: 9px;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
  }
  h4 {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.35;
    flex: 1;
    color: var(--color-text-primary);
    margin: 0;
  }
  .desc {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.55;
    margin: 0;
  }
  .quote {
    border-left: 2px solid var(--color-border-emphasis);
    padding: 10px 12px;
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    background: var(--color-surface-elevated, #fafafa);
    border-radius: 0 4px 4px 0;
  }
  .src-line {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    margin-top: 6px;
    font-weight: 500;
  }
  .meta {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 11px;
    color: var(--color-text-muted);
    align-items: center;
    font-family: var(--font-mono);
  }
</style>
