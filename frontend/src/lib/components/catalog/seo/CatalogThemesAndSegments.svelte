<script lang="ts">
  // Renders ContentCategorizationReport produced by Stage 3 PainPointCrew:
  // theme_categories (5–10) and user_segments (3+). The data lives on
  // CatalogResearchContext.contentCategorization as a loosely-typed Json
  // column — cast at the boundary, render only when populated. Renders
  // nothing for legacy rows produced before the column existed.

  interface Theme {
    category_name: string;
    definition: string;
    frequency: string;
    mention_count: number;
    primary_user_segments: string[];
    anchor_keywords: string[];
  }

  interface Segment {
    segment_name: string;
    primary_concerns: string[];
    mention_frequency: string;
  }

  interface Props {
    contentCategorization: unknown | null;
  }

  let { contentCategorization }: Props = $props();

  const data = $derived.by(() => {
    const c = contentCategorization as
      | {
          theme_categories?: Theme[];
          user_segments?: Segment[];
          executive_summary?: string;
        }
      | null
      | undefined;
    return {
      themes: (c?.theme_categories ?? []).filter((t) => t?.category_name),
      segments: (c?.user_segments ?? []).filter((s) => s?.segment_name),
      summary: c?.executive_summary ?? "",
    };
  });

  const hasContent = $derived(data.themes.length > 0 || data.segments.length > 0);

  function freqClass(f: string | undefined): string {
    const v = (f ?? "").toLowerCase();
    if (v === "high") return "freq-high";
    if (v === "medium") return "freq-medium";
    if (v === "low") return "freq-low";
    return "";
  }
</script>

{#if hasContent}
  <div class="cat-block cat-themes-segments">
    <header class="cat-block-header">
      <h2 class="cat-block-title">Themes & audience segments</h2>
      <span class="cat-block-count">
        {data.themes.length} themes · {data.segments.length} segments
      </span>
    </header>

    {#if data.summary}
      <p class="themes-summary">{data.summary}</p>
    {/if}

    {#if data.themes.length > 0}
      <section class="themes-section" aria-label="Discussion themes">
        <h3 class="themes-subhead">Discussion themes</h3>
        <ul class="themes-list">
          {#each data.themes as theme}
            <li class="theme-row">
              <div class="theme-row-head">
                <span class="theme-name">{theme.category_name}</span>
                {#if theme.frequency}
                  <span class="freq-badge {freqClass(theme.frequency)}">
                    {theme.frequency}
                  </span>
                {/if}
                {#if typeof theme.mention_count === "number"}
                  <span class="mention-count tabular-nums">
                    {theme.mention_count} mentions
                  </span>
                {/if}
              </div>
              {#if theme.definition}
                <p class="theme-definition">{theme.definition}</p>
              {/if}
              {#if theme.anchor_keywords?.length}
                <ul class="anchor-list" aria-label="Anchor phrases">
                  {#each theme.anchor_keywords.slice(0, 8) as kw}
                    <li class="tag-chip">{kw}</li>
                  {/each}
                </ul>
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if data.segments.length > 0}
      <section class="segments-section" aria-label="User segments">
        <h3 class="themes-subhead">User segments</h3>
        <ul class="segment-grid">
          {#each data.segments as segment}
            <li class="segment-card">
              <div class="segment-card-head">
                <span class="segment-name">{segment.segment_name}</span>
                {#if segment.mention_frequency}
                  <span class="freq-badge {freqClass(segment.mention_frequency)}">
                    {segment.mention_frequency}
                  </span>
                {/if}
              </div>
              {#if segment.primary_concerns?.length}
                <ul class="concern-list">
                  {#each segment.primary_concerns as concern}
                    <li>{concern}</li>
                  {/each}
                </ul>
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  </div>
{/if}

<style>
  .themes-summary {
    font-size: 0.95rem;
    line-height: 1.6;
    color: var(--color-text-muted);
    margin: 0 0 1.25rem;
    max-width: 60ch;
  }

  .themes-subhead {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 1.25rem 0 0.75rem;
    font-weight: 500;
  }

  .themes-section:first-of-type .themes-subhead {
    margin-top: 0;
  }

  .themes-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .theme-row {
    border-top: 1px solid var(--color-border);
    padding-top: 1rem;
  }

  .theme-row:first-child {
    border-top: none;
    padding-top: 0;
  }

  .theme-row-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.625rem;
    margin-bottom: 0.375rem;
  }

  .theme-name {
    font-weight: 600;
    font-size: 1rem;
    color: var(--color-text);
  }

  .segment-name {
    font-weight: 600;
    font-size: 0.9375rem;
    color: var(--color-text);
  }

  .freq-badge {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.625rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0.125rem 0.5rem;
    border-radius: 999px;
    border: 1px solid var(--color-border);
  }

  .freq-high {
    color: var(--color-text);
    border-color: var(--color-text);
  }

  .freq-medium {
    color: var(--color-text-muted);
  }

  .freq-low {
    color: var(--color-text-muted);
    opacity: 0.7;
  }

  .mention-count {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .theme-definition {
    font-size: 0.9375rem;
    line-height: 1.55;
    color: var(--color-text-muted);
    margin: 0 0 0.625rem;
    max-width: 65ch;
  }

  .anchor-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .tag-chip {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: transparent;
  }

  .segment-grid {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
  }

  .segment-card {
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 0.875rem 1rem;
  }

  .segment-card-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .concern-list {
    list-style: disc;
    padding-left: 1.125rem;
    margin: 0;
    font-size: 0.875rem;
    line-height: 1.5;
    color: var(--color-text-muted);
  }

  .concern-list li + li {
    margin-top: 0.25rem;
  }
</style>
