<script lang="ts">
  import {
    MessageSquare,
    Users,
    BarChart3,
    Quote,
    Star,
    Shield,
    Hash,
  } from "lucide-svelte";
  import type { ContentCategorization } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import QuoteBlock from "$lib/components/ui/QuoteBlock.svelte";

  interface Props {
    contentCategorization?: ContentCategorization;
    overallCompetitiveInsights?: string;
  }

  let { contentCategorization, overallCompetitiveInsights }: Props = $props();

  // Get frequency badge variant
  const getFrequencyVariant = (frequency: string) => {
    const f = frequency?.toLowerCase() || "";
    if (f.includes("high")) return "success";
    if (f.includes("medium")) return "warning";
    return "muted";
  };

  // Get quality badge variant
  const getQualityVariant = (quality: string) => {
    const q = quality?.toLowerCase() || "";
    if (q.includes("high") || q.includes("excellent")) return "success";
    if (q.includes("medium") || q.includes("good")) return "warning";
    return "muted";
  };

  // Get quality score for display
  const getQualityScore = (quality: string | undefined) => {
    const q = quality?.toLowerCase() || "";
    if (q.includes("excellent") || q.includes("high")) return 85;
    if (q.includes("good") || q.includes("medium")) return 65;
    if (q.includes("fair") || q.includes("low")) return 45;
    return 30;
  };

  // Count themes and segments
  const themesCount = $derived(
    contentCategorization?.theme_categories?.length ?? 0,
  );
  const segmentsCount = $derived(
    contentCategorization?.user_segments?.length ?? 0,
  );
</script>

<Section
  id="content-insights"
  class="report-section"
  icon={MessageSquare}
  title="Content & Competitive Insights"
  subtitle="Discussion analysis and market intelligence"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Overall Competitive Insights - Hero Card -->
  {#if overallCompetitiveInsights}
    <div class="insight-card insight-card--accent insight-hero">
      <div class="insight-icon">
        <Shield class="icon-lg" />
      </div>
      <div class="insight-content">
        <span class="insight-label">STRATEGIC INSIGHT</span>
        <div class="insight-text">
          {@html renderMarkdown(overallCompetitiveInsights)}
        </div>
      </div>
    </div>
  {/if}

  {#if contentCategorization}
    <!-- Quality Strip -->
    <div class="quality-strip">
      {#if contentCategorization.overall_quality}
        <div class="quality-main">
          <div
            class="quality-ring"
            class:success={getQualityScore(
              contentCategorization.overall_quality,
            ) >= 70}
            class:warning={getQualityScore(
              contentCategorization.overall_quality,
            ) >= 50 &&
              getQualityScore(contentCategorization.overall_quality) < 70}
            class:error={getQualityScore(
              contentCategorization.overall_quality,
            ) < 50}
          >
            <span class="quality-num"
              >{getQualityScore(contentCategorization.overall_quality)}</span
            >
          </div>
          <div class="quality-info">
            <span class="quality-label">Discussion Quality</span>
            <Badge
              variant={getQualityVariant(contentCategorization.overall_quality)}
              size="sm"
            >
              {contentCategorization.overall_quality}
            </Badge>
          </div>
        </div>
      {/if}
      <div class="quality-stats">
        <div class="quality-stat">
          <BarChart3 class="stat-icon" />
          <span class="stat-num">{themesCount}</span>
          <span class="stat-label">Themes</span>
        </div>
        <div class="quality-stat">
          <Users class="stat-icon" />
          <span class="stat-num">{segmentsCount}</span>
          <span class="stat-label">Segments</span>
        </div>
      </div>
    </div>

    <!-- Executive Summary - Always visible -->
    {#if contentCategorization.executive_summary}
      <div class="summary-card">
        <h3 class="summary-title">Content Analysis Summary</h3>
        <div class="summary-text">
          {@html renderMarkdown(contentCategorization.executive_summary)}
        </div>
      </div>
    {/if}

    <!-- Expandable: Theme Categories -->
    {#if contentCategorization.theme_categories && contentCategorization.theme_categories.length > 0}
      <ExpandableSection
        title="Discussion Themes"
        icon={BarChart3}
        count={contentCategorization.theme_categories.length}
        defaultOpen={true}
      >
        <div class="themes-list">
          {#each contentCategorization.theme_categories as category, i}
            <details class="theme-card">
              <summary class="theme-summary">
                <div class="theme-main">
                  <span class="theme-rank">{i + 1}</span>
                  <div class="theme-info">
                    <h4 class="theme-name">{category.category_name}</h4>
                    <p class="theme-def">{category.definition}</p>
                  </div>
                </div>
                <div class="theme-meta">
                  <Badge
                    variant={getFrequencyVariant(category.frequency)}
                    size="sm">{category.frequency}</Badge
                  >
                  <span class="theme-mentions">{category.mention_count}</span>
                </div>
              </summary>

              <div class="theme-details">
                {#if category.primary_user_segments && category.primary_user_segments.length > 0}
                  <div class="theme-section">
                    <span class="theme-section-label">
                      <Users class="section-icon-sm" />
                      User Segments
                    </span>
                    <div class="tag-row">
                      {#each category.primary_user_segments as segment}
                        <span class="tag">{segment}</span>
                      {/each}
                    </div>
                  </div>
                {/if}

                {#if category.representative_quotes && category.representative_quotes.length > 0}
                  <div class="theme-section">
                    <span class="theme-section-label">
                      <Quote class="section-icon-sm" />
                      Quotes
                    </span>
                    <div class="quotes-list">
                      {#each category.representative_quotes.slice(0, 3) as quote}
                        <QuoteBlock
                          text={quote}
                          variant="card"
                          class="theme-quote-block"
                        />
                      {/each}
                      {#if category.representative_quotes.length > 3}
                        <span class="quotes-more"
                          >+{category.representative_quotes.length - 3} more</span
                        >
                      {/if}
                    </div>
                  </div>
                {/if}
              </div>
            </details>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Expandable: User Segments -->
    {#if contentCategorization.user_segments && contentCategorization.user_segments.length > 0}
      <ExpandableSection
        title="User Segments"
        icon={Users}
        count={contentCategorization.user_segments.length}
      >
        <div class="segments-grid">
          {#each contentCategorization.user_segments as segment}
            <div class="segment-card">
              <div class="segment-header">
                <h4 class="segment-name">{segment.segment_name}</h4>
                <Badge
                  variant={getFrequencyVariant(segment.mention_frequency)}
                  size="sm">{segment.mention_frequency}</Badge
                >
              </div>
              {#if segment.primary_concerns && segment.primary_concerns.length > 0}
                <ul class="concerns-list">
                  {#each segment.primary_concerns as concern}
                    <li>{concern}</li>
                  {/each}
                </ul>
              {/if}
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Expandable: Quality Assessment -->
    {#if contentCategorization.overall_quality_justification}
      <ExpandableSection
        title="Quality Assessment"
        icon={Star}
        variant="warning"
      >
        <div class="assessment-grid">
          <div class="assessment-card">
            <h4 class="assessment-title">
              <Star class="assessment-icon" />
              Quality Justification
            </h4>
            <p class="assessment-text">
              {contentCategorization.overall_quality_justification}
            </p>
          </div>
        </div>
      </ExpandableSection>
    {/if}
  {/if}
</Section>

<style>
  /* =========================
	   INSIGHT HERO
	   ========================= */
  .insight-hero {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .insight-icon {
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(229, 90, 40, 0.1);
    border-radius: 0.5rem;
    flex-shrink: 0;
  }

  :global(.icon-lg) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent);
  }

  .insight-content {
    flex: 1;
  }

  .insight-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    color: var(--color-accent);
    letter-spacing: 0.1em;
    margin-bottom: 0.375rem;
    display: block;
  }

  .insight-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .insight-text :global(p) {
    margin-bottom: 0.5rem;
  }

  .insight-text :global(p:last-child) {
    margin-bottom: 0;
  }

  /* =========================
	   QUALITY STRIP
	   ========================= */
  .quality-strip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 1rem 1.25rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .quality-main {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .quality-ring {
    width: 3rem;
    height: 3rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--color-bg-base);
    border: 3px solid var(--color-border);
  }

  .quality-ring.success {
    border-color: var(--color-success);
  }

  .quality-ring.warning {
    border-color: var(--color-warning);
  }

  .quality-ring.error {
    border-color: var(--color-error);
  }

  .quality-num {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .quality-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .quality-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .quality-stats {
    display: flex;
    gap: 1.5rem;
  }

  .quality-stat {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  :global(.stat-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent);
  }

  .stat-num {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .stat-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* =========================
	   SUMMARY CARD
	   ========================= */
  .summary-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
  }

  .summary-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.625rem;
  }

  .summary-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .summary-text :global(p) {
    margin-bottom: 0.5rem;
  }

  .summary-text :global(p:last-child) {
    margin-bottom: 0;
  }

  /* Themes List */
  .themes-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .theme-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    overflow: hidden;
  }

  .theme-card[open] {
    border-color: var(--color-accent);
  }

  .theme-summary {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    cursor: pointer;
    list-style: none;
  }

  .theme-summary::-webkit-details-marker {
    display: none;
  }

  .theme-main {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    flex: 1;
  }

  .theme-rank {
    width: 1.5rem;
    height: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(229, 90, 40, 0.1);
    border-radius: 0.25rem;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .theme-info {
    flex: 1;
  }

  .theme-name {
    font-family: var(--font-display);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.125rem;
  }

  .theme-card[open] .theme-name {
    color: var(--color-accent);
  }

  .theme-def {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .theme-card[open] .theme-def {
    display: block;
  }

  .theme-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .theme-mentions {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: var(--color-text-muted);
  }

  .theme-details {
    padding: 0 1rem 1rem;
    border-top: 1px solid var(--color-border);
    padding-top: 0.75rem;
  }

  .theme-section {
    margin-bottom: 0.75rem;
  }

  .theme-section:last-child {
    margin-bottom: 0;
  }

  .theme-section-label {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.375rem;
  }

  :global(.section-icon-sm) {
    width: 0.75rem;
    height: 0.75rem;
  }

  .tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .tag {
    font-size: 0.6875rem;
    padding: 0.125rem 0.5rem;
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 9999px;
    color: var(--color-text-secondary);
  }

  .quotes-list {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  :global(.theme-quote-block) {
    padding: 0.625rem 0.75rem;
  }

  :global(.theme-quote-block .quote-text) {
    font-size: 0.75rem;
  }

  .quotes-more {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Segments Grid */
  .segments-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 0.75rem;
  }

  .segment-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 0.875rem;
  }

  .segment-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }

  .segment-name {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .concerns-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .concerns-list li {
    position: relative;
    padding-left: 0.75rem;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
    margin-bottom: 0.125rem;
  }

  .concerns-list li::before {
    content: "•";
    position: absolute;
    left: 0;
    color: var(--color-accent);
  }

  /* Assessment Grid */
  .assessment-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0.75rem;
  }

  .assessment-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 0.875rem;
  }

  .assessment-title {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.5rem;
  }

  :global(.assessment-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
  }

  .assessment-text {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  /* =========================
	   RESPONSIVE
	   ========================= */
  @media (max-width: 768px) {
    .quality-strip {
      flex-direction: column;
      align-items: stretch;
    }

    .quality-stats {
      justify-content: space-around;
    }

    .theme-summary {
      flex-direction: column;
    }

    .theme-meta {
      margin-top: 0.375rem;
    }
  }
</style>
