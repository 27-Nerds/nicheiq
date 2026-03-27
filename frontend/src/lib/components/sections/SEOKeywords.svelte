<script lang="ts">
  import {
    Search,
    Zap,
    FileText,
    Layers,
    Target,
    Clock,
    AlertTriangle,
    Code,
    ChevronRight,
    Hash,
    Table,
    Lightbulb,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type { SEOStrategy, SEOAnalytics } from "$lib/types/report";
  import {
    formatNumber,
    formatScorePercent,
    parseCompetition,
    getTierLabel,
    renderMarkdown,
    renderTechnicalContent,
  } from "$lib/utils/format";
  import {
    getDifficultyColor,
    getKeywordTierVariant,
    getSeoDifficultyColor,
    getSeoDifficultyLabel,
  } from "$lib/utils/variantHelpers";
  import Badge from "$lib/components/ui/Badge.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";
  import KeywordTierChart from "$lib/components/charts/KeywordTierChart.svelte";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";

  interface Props {
    strategy: SEOStrategy;
    analytics: SEOAnalytics;
  }

  let { strategy, analytics }: Props = $props();

  // Keyword tab state
  let activeTab = $state<
    "tier0" | "tier1" | "tier2" | "tier3" | "tier4" | "all"
  >("all");

  // Keyword search and display state
  let searchQuery = $state("");
  let showAllKeywords = $state(false);
  const INITIAL_KEYWORD_LIMIT = 15;
  const EXPANDED_KEYWORD_LIMIT = 50;

  // Extract keywords from tier 3 geographic groups
  // Structure: GeographicKeywordGroup -> GeographicKeywordEntry { keyword, search_volume, city, notes }
  function extractTier3Keywords() {
    const groups = strategy.tier_3_geographic_groups || [];
    const keywords: any[] = [];
    for (const group of groups) {
      const groupKeywords = group.keywords || [];
      for (const kw of groupKeywords) {
        keywords.push({
          keyword: kw.keyword,
          search_volume: kw.search_volume || 0,
          competition: group.competition_level || null,
          tier: 3,
          geographic_region: group.region_name,
          city: kw.city,
          notes: kw.notes,
        });
      }
    }
    return keywords;
  }

  // Extract keywords from tier 4 category groups
  // Structure: CategoryKeywordGroup -> CategoryKeyword { keyword_name, search_volume, competition, cpc }
  function extractTier4Keywords() {
    const groups = strategy.tier_4_category_groups || [];
    const keywords: any[] = [];
    for (const group of groups) {
      const groupKeywords = group.keywords || [];
      for (const kw of groupKeywords) {
        keywords.push({
          keyword: kw.keyword_name,
          search_volume: kw.search_volume || 0,
          competition: kw.competition,
          tier: 4,
          category: group.category_name,
          cpc: kw.cpc,
        });
      }
    }
    return keywords;
  }

  // Combine all keywords with tier info (including grouped tiers 3 & 4)
  const allKeywords = $derived(
    [
      ...(strategy.tier_0_keywords || []).map((k) => ({ ...k, tier: 0 })),
      ...(strategy.tier_1_keywords || []).map((k) => ({ ...k, tier: 1 })),
      ...(strategy.tier_2_keywords || []).map((k) => ({ ...k, tier: 2 })),
      ...extractTier3Keywords(),
      ...extractTier4Keywords(),
    ].sort((a, b) => b.search_volume - a.search_volume),
  );

  // Top keywords for preview (always visible)
  const previewKeywords = $derived({
    tier0: allKeywords.filter((k) => k.tier === 0).slice(0, 3),
    tier1: allKeywords.filter((k) => k.tier === 1).slice(0, 3),
    tier2: allKeywords.filter((k) => k.tier === 2).slice(0, 3),
    tier3: allKeywords.filter((k) => k.tier === 3).slice(0, 3),
    tier4: allKeywords.filter((k) => k.tier === 4).slice(0, 3),
  });

  // Count keywords per tier (for tier 3 and 4 which are extracted from groups)
  const tier3Count = $derived(extractTier3Keywords().length);
  const tier4Count = $derived(extractTier4Keywords().length);

  function getFilteredKeywords() {
    let keywords = allKeywords;

    // Filter by tab
    if (activeTab !== "all") {
      const tierNum = parseInt(activeTab.replace("tier", ""));
      keywords = keywords.filter((k) => k.tier === tierNum);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      keywords = keywords.filter((k) =>
        k.keyword.toLowerCase().includes(query),
      );
    }

    return keywords;
  }

  const displayLimit = $derived(
    showAllKeywords ? EXPANDED_KEYWORD_LIMIT : INITIAL_KEYWORD_LIMIT,
  );

  // Calculate opportunity score
  const opportunityScore = $derived(
    Math.round(
      (analytics.high_volume_keywords / Math.max(analytics.total_keywords, 1)) *
        100,
    ),
  );

  // Check if high-priority keywords are missing
  const hasLimitedKeywords = $derived(
    (strategy.tier_0_keywords?.length || 0) === 0 ||
      (strategy.tier_1_keywords?.length || 0) === 0,
  );

  // View mode for keywords section
  let viewMode = $state<"table" | "insights">("table");

  // Helper to get intent badge variant
  function getIntentVariant(
    intent: string | undefined,
  ): "success" | "accent" | "muted" | "info" {
    if (!intent) return "muted";
    const lower = intent.toLowerCase();
    if (lower.includes("conversion") || lower.includes("transactional"))
      return "success";
    if (lower.includes("commercial")) return "accent";
    if (lower.includes("informational")) return "info";
    return "muted";
  }
</script>

<Section
  id="seo"
  class="report-section"
  icon={SECTION_MAP['seo'].icon}
  title="SEO Strategy & Keywords"
  subtitle="Keyword opportunities and content roadmap"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Hero Strip -->
  <HeroStrip>
    {#snippet primary()}
      <HeroPrimary
        value={opportunityScore / 100}
        label="Opportunity"
        sublabel="{analytics.high_volume_keywords} high volume"
        size={56}
        strokeWidth={6}
        color="success"
      />
    {/snippet}
    <HeroMetric value={analytics.total_keywords} label="Keywords" />
    <HeroMetric
      value={formatNumber(analytics.total_search_volume)}
      label="Monthly Vol"
      color="accent"
    />
    <HeroMetric
      value={analytics.avg_competition.toFixed(0)}
      label="Avg Competition"
      color={analytics.avg_competition < 40
        ? "success"
        : analytics.avg_competition < 70
          ? "warning"
          : "error"}
      progress={analytics.avg_competition / 100}
    />
  </HeroStrip>

  <!-- Warning for limited keyword data -->
  {#if hasLimitedKeywords}
    <div class="limited-keywords-warning">
      <EmptyState
        icon={AlertTriangle}
        title="Limited Keyword Data"
        description="Not enough high-opportunity keywords were found for this niche. SEO results may be limited and require additional investigation."
        variant="warning"
        size="sm"
      />
    </div>
  {/if}

  <!-- Key Findings (Always Visible) -->
  {#if strategy.key_findings}
    <div class="insight-card insight-card--accent findings-card">
      <div class="findings-header">
        <Zap class="findings-icon" />
        <span class="findings-title">Key Findings</span>
      </div>
      <p class="findings-text">{strategy.key_findings}</p>
    </div>
  {/if}

  <!-- Keyword Tier Chart (Always Visible) -->
  <div class="chart-card">
    <KeywordTierChart
      tier0Count={analytics.tier0_count}
      tier1Count={analytics.tier1_count}
      tier2Count={analytics.tier2_count}
      tier3Count={analytics.tier3_count}
      tier4Count={analytics.tier4_count}
    />
  </div>

  <!-- Keyword Preview (Always Visible) -->
  <div class="keyword-preview-card">
    <div class="preview-header">
      <span class="preview-title">Top Keywords by Tier</span>
      <a href="#seo-keywords-details" class="preview-expand-btn">
        View All {allKeywords.length}
        <ChevronRight class="w-4 h-4" />
      </a>
    </div>
    <div class="preview-tiers">
      {#if previewKeywords.tier0.length > 0}
        <div class="preview-tier">
          <span class="tier-label success">Premium</span>
          <div class="tier-pills">
            {#each previewKeywords.tier0 as kw}
              <span class="keyword-pill success">{kw.keyword}</span>
            {/each}
            {#if (strategy.tier_0_keywords?.length || 0) > 3}
              <span class="pill-more"
                >+{(strategy.tier_0_keywords?.length || 0) - 3}</span
              >
            {/if}
          </div>
        </div>
        {#if strategy.tier_0_strategy}
          <p class="tier-strategy">{strategy.tier_0_strategy}</p>
        {/if}
      {/if}
      {#if previewKeywords.tier1.length > 0}
        <div class="preview-tier">
          <span class="tier-label accent">Quick Win</span>
          <div class="tier-pills">
            {#each previewKeywords.tier1 as kw}
              <span class="keyword-pill accent">{kw.keyword}</span>
            {/each}
            {#if (strategy.tier_1_keywords?.length || 0) > 3}
              <span class="pill-more"
                >+{(strategy.tier_1_keywords?.length || 0) - 3}</span
              >
            {/if}
          </div>
        </div>
        {#if strategy.tier_1_quick_win_strategy}
          <p class="tier-strategy">{strategy.tier_1_quick_win_strategy}</p>
        {/if}
      {/if}
      {#if previewKeywords.tier2.length > 0}
        <div class="preview-tier">
          <span class="tier-label muted">High Value</span>
          <div class="tier-pills">
            {#each previewKeywords.tier2 as kw}
              <span class="keyword-pill muted">{kw.keyword}</span>
            {/each}
            {#if (strategy.tier_2_keywords?.length || 0) > 3}
              <span class="pill-more"
                >+{(strategy.tier_2_keywords?.length || 0) - 3}</span
              >
            {/if}
          </div>
        </div>
        {#if strategy.tier_2_strategy}
          <p class="tier-strategy">{strategy.tier_2_strategy}</p>
        {/if}
      {/if}
      {#if previewKeywords.tier3.length > 0}
        <div class="preview-tier">
          <span class="tier-label info">Geographic</span>
          <div class="tier-pills">
            {#each previewKeywords.tier3 as kw}
              <span class="keyword-pill info">{kw.keyword}</span>
            {/each}
            {#if tier3Count > 3}
              <span class="pill-more">+{tier3Count - 3}</span>
            {/if}
          </div>
        </div>
      {/if}
      {#if previewKeywords.tier4.length > 0}
        <div class="preview-tier">
          <span class="tier-label warning">Category</span>
          <div class="tier-pills">
            {#each previewKeywords.tier4 as kw}
              <span class="keyword-pill warning">{kw.keyword}</span>
            {/each}
            {#if tier4Count > 3}
              <span class="pill-more">+{tier4Count - 3}</span>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- Expandable: Keywords Table -->
  <div id="seo-keywords-details">
    <ExpandableSection
      title="Keyword Details"
      icon={Hash}
      count={allKeywords.length}
      countSuffix="keywords"
    >
      <!-- View Toggle -->
      <div class="view-toggle">
        <button
          class="view-toggle-btn"
          class:active={viewMode === "table"}
          onclick={() => (viewMode = "table")}
        >
          <Table class="toggle-icon" />
          Table
        </button>
        <button
          class="view-toggle-btn"
          class:active={viewMode === "insights"}
          onclick={() => (viewMode = "insights")}
        >
          <Lightbulb class="toggle-icon" />
          Insights
        </button>
      </div>

      <!-- Search and Tabs Row -->
      <div class="keyword-controls">
        <div class="search-input-wrapper">
          <Search class="search-icon" />
          <input
            type="text"
            class="search-input"
            placeholder="Search keywords..."
            bind:value={searchQuery}
          />
          {#if searchQuery}
            <button class="search-clear" onclick={() => (searchQuery = "")}>
              &times;
            </button>
          {/if}
        </div>

        <!-- Tab Navigation -->
        <div class="tabs-container">
          <button
            class="tab-button"
            class:active={activeTab === "all"}
            onclick={() => (activeTab = "all")}
            type="button"
          >
            <span class="tab-label">All</span>
            <span class="tab-count">{allKeywords.length}</span>
          </button>
          <button
            class="tab-button"
            class:active={activeTab === "tier0"}
            onclick={() => (activeTab = "tier0")}
            type="button"
          >
            <span class="tab-label">Premium</span>
            <span class="tab-count success"
              >{strategy.tier_0_keywords?.length || 0}</span
            >
          </button>
          <button
            class="tab-button"
            class:active={activeTab === "tier1"}
            onclick={() => (activeTab = "tier1")}
            type="button"
          >
            <span class="tab-label">Quick Win</span>
            <span class="tab-count accent"
              >{strategy.tier_1_keywords?.length || 0}</span
            >
          </button>
          <button
            class="tab-button"
            class:active={activeTab === "tier2"}
            onclick={() => (activeTab = "tier2")}
            type="button"
          >
            <span class="tab-label">High Value</span>
            <span class="tab-count"
              >{strategy.tier_2_keywords?.length || 0}</span
            >
          </button>
          <button
            class="tab-button"
            class:active={activeTab === "tier3"}
            onclick={() => (activeTab = "tier3")}
            type="button"
          >
            <span class="tab-label">Geographic</span>
            <span class="tab-count info">{tier3Count}</span>
          </button>
          <button
            class="tab-button"
            class:active={activeTab === "tier4"}
            onclick={() => (activeTab = "tier4")}
            type="button"
          >
            <span class="tab-label">Category</span>
            <span class="tab-count">{tier4Count}</span>
          </button>
        </div>
      </div>

      <!-- Search results count -->
      {#if searchQuery}
        <p class="search-results-count">
          Found {getFilteredKeywords().length} keywords matching "{searchQuery}"
        </p>
      {/if}

      {#if viewMode === "table"}
        <!-- Keywords Table -->
        <div class="table-container">
          <table class="keywords-table">
            <thead>
              <tr>
                <th class="th-keyword">Keyword</th>
                <th class="th-volume">Volume</th>
                <th class="th-difficulty">Difficulty</th>
                <th class="th-competition">Competition</th>
                <th class="th-tier">Tier</th>
              </tr>
            </thead>
            <tbody>
              {#each getFilteredKeywords().slice(0, displayLimit) as kw}
                {@const competition = parseCompetition(kw.competition)}
                <tr>
                  <td class="td-keyword">
                    <div class="td-keyword-inner">
                      <Hash class="keyword-icon" />
                      <span>{kw.keyword}</span>
                    </div>
                  </td>
                  <td class="td-volume">
                    <span class="volume-value"
                      >{formatNumber(kw.search_volume)}</span
                    >
                    <span class="volume-unit">/mo</span>
                  </td>
                  <td class="td-difficulty">
                    <div class="td-difficulty-inner">
                      {#if kw.keyword_difficulty != null}
                        <span
                          class="difficulty-badge"
                          style="background: {getSeoDifficultyColor(
                            kw.keyword_difficulty,
                          )}20; color: {getSeoDifficultyColor(
                            kw.keyword_difficulty,
                          )}"
                        >
                          {Math.round(kw.keyword_difficulty)}
                        </span>
                        <span
                          class="difficulty-label"
                          style="color: {getSeoDifficultyColor(
                            kw.keyword_difficulty,
                          )}"
                        >
                          {getSeoDifficultyLabel(kw.keyword_difficulty)}
                        </span>
                      {:else}
                        <span class="difficulty-na">—</span>
                      {/if}
                    </div>
                  </td>
                  <td class="td-competition">
                    <div class="td-competition-inner">
                      <div class="competition-bar">
                        <div
                          class="competition-fill"
                          style="width: {competition *
                            100}%; background: {getDifficultyColor(
                            competition,
                          )}"
                        ></div>
                      </div>
                      <span
                        class="competition-value"
                        style="color: {getDifficultyColor(competition)}"
                        >{formatScorePercent(competition)}</span
                      >
                    </div>
                  </td>
                  <td class="td-tier">
                    <Badge variant={getKeywordTierVariant(kw.tier)} size="sm"
                      >{getTierLabel(kw.tier)}</Badge
                    >
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <!-- Insights cards view -->
        <div class="insights-grid">
          {#each getFilteredKeywords().slice(0, displayLimit) as kw}
            {@const competition = parseCompetition(kw.competition)}
            <div class="insight-card">
              <div class="insight-header">
                <span class="insight-keyword">{kw.keyword}</span>
                <Badge variant={getKeywordTierVariant(kw.tier)} size="sm"
                  >{getTierLabel(kw.tier)}</Badge
                >
              </div>
              <div class="insight-metrics">
                <div class="metric">
                  <span class="metric-value"
                    >{formatNumber(kw.search_volume)}</span
                  >
                  <span class="metric-label">Volume/mo</span>
                </div>
                {#if kw.keyword_difficulty != null}
                  <div class="metric">
                    <span
                      class="metric-value"
                      style="color: {getSeoDifficultyColor(
                        kw.keyword_difficulty,
                      )}">{Math.round(kw.keyword_difficulty)}</span
                    >
                    <span class="metric-label">
                      Difficulty
                      <span class="difficulty-hint"
                        >({getSeoDifficultyLabel(kw.keyword_difficulty)})</span
                      >
                    </span>
                  </div>
                {/if}
                <div class="metric">
                  <span
                    class="metric-value"
                    style="color: {getDifficultyColor(competition)}"
                    >{formatScorePercent(competition)}</span
                  >
                  <span class="metric-label">Competition</span>
                </div>
              </div>
              {#if kw.intent}
                <div class="insight-intent">
                  <Badge variant={getIntentVariant(kw.intent)} size="sm"
                    >{kw.intent}</Badge
                  >
                  <span class="insight-label">Intent</span>
                </div>
              {/if}
              {#if kw.strategy}
                <div class="insight-strategy">
                  <span class="insight-label">Strategy</span>
                  <p class="insight-text">{kw.strategy}</p>
                </div>
              {/if}
              {#if kw.tier_rationale}
                <div class="insight-rationale">
                  <span class="insight-label">Why this tier?</span>
                  <p class="insight-text muted">{kw.tier_rationale}</p>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}

      <!-- Show More / Show Less -->
      {#if getFilteredKeywords().length > INITIAL_KEYWORD_LIMIT}
        {@const filteredCount = getFilteredKeywords().length}
        <div class="table-footer-actions">
          <p class="table-footer">
            Showing {Math.min(displayLimit, filteredCount)} of {filteredCount}
            keywords
          </p>
          {#if !showAllKeywords}
            <button
              class="show-more-btn"
              onclick={() => (showAllKeywords = true)}
            >
              Show More Keywords
            </button>
          {:else}
            <button
              class="show-more-btn"
              onclick={() => (showAllKeywords = false)}
            >
              Show Less
            </button>
          {/if}
        </div>
      {/if}
    </ExpandableSection>
  </div>

  <!-- Expandable: Topic Clusters -->
  {#if strategy.topic_clusters && strategy.topic_clusters.length > 0}
    <ExpandableSection
      title="Topic Clusters"
      icon={Layers}
      count={strategy.topic_clusters.length}
      countSuffix="clusters"
    >
      <CardGrid minWidth={240} gap="md">
        {#each strategy.topic_clusters.slice(0, 6) as cluster}
          {@const clusterKeywords = cluster.supporting_keywords || []}
          <div class="cluster-card">
            <div class="cluster-header">
              <h4 class="cluster-name">{cluster.cluster_name}</h4>
              {#if cluster.primary_keyword}
                <Badge variant="accent" size="sm"
                  >{cluster.primary_keyword}</Badge
                >
              {/if}
            </div>
            <div class="cluster-keywords">
              {#each clusterKeywords.slice(0, 5) as keyword}
                <span class="cluster-keyword">{keyword}</span>
              {/each}
              {#if clusterKeywords.length > 5}
                <span class="cluster-more">+{clusterKeywords.length - 5}</span>
              {/if}
            </div>
          </div>
        {/each}
      </CardGrid>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Implementation Roadmap -->
  {#if strategy.implementation_roadmap}
    <ExpandableSection title="Implementation Roadmap" icon={Clock}>
      <div class="roadmap-content markdown-content">
        {@html renderTechnicalContent(String(strategy.implementation_roadmap))}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Content Strategy & Budget -->
  {#if strategy.content_strategy || strategy.budget_allocation}
    <ExpandableSection title="Content Strategy & Budget" icon={FileText}>
      <CardGrid minWidth={260} gap="md">
        {#if strategy.content_strategy}
          <div class="strategy-card">
            <h4 class="card-label">Content Strategy</h4>
            <div class="strategy-content markdown-content">
              {@html renderMarkdown(String(strategy.content_strategy))}
            </div>
          </div>
        {/if}

        {#if strategy.budget_allocation}
          <div class="strategy-card">
            <h4 class="card-label">Budget Allocation</h4>
            <div class="budget-content markdown-content">
              {@html renderMarkdown(String(strategy.budget_allocation))}
            </div>
          </div>
        {/if}
      </CardGrid>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Technical SEO -->
  {#if strategy.technical_seo_recommendations}
    <ExpandableSection title="Technical SEO Recommendations" icon={Code}>
      <div class="markdown-content technical-content timeline-styled">
        {@html renderTechnicalContent(strategy.technical_seo_recommendations)}
      </div>
    </ExpandableSection>
  {/if}

  <!-- key_metrics_to_track removed - generic boilerplate -->
  <!-- risk_mitigation removed - generic boilerplate -->
  <!-- schema_markup_strategy removed - Task 5/6 deleted -->
  <!-- page_type_implementations removed - Task 5/6 deleted -->

  <!-- Expandable: Competitive Positioning -->
  {#if strategy.competitive_positioning}
    <ExpandableSection title="Competitive Positioning" icon={Target}>
      <div class="positioning-card">
        <div class="positioning-content">
          {@html renderMarkdown(strategy.competitive_positioning)}
        </div>
      </div>
    </ExpandableSection>
  {/if}
  <!-- competitive_advantages removed - redundant with competitive_positioning -->
  <!-- conclusion_bottom_line + next_steps_checklist removed - generic boilerplate -->
</Section>

<style>
  /* Limited Keywords Warning */
  .limited-keywords-warning {
    margin-bottom: var(--space-4);
  }

  /* Findings Card */
  .findings-card {
    margin-bottom: var(--space-4);
  }

  .findings-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .findings-header :global(.findings-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent);
  }

  .findings-title {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-accent);
  }

  .findings-text {
    font-size: 0.9375rem;
    color: var(--color-text-primary);
    line-height: 1.6;
    margin: 0;
  }

  /* Chart Card */
  .chart-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-4);
  }

  /* Tabs */
  .tabs-container {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  .tab-button {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0.375rem 0.75rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
  }

  .tab-button:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-hover);
  }

  .tab-button.active {
    background: var(--color-accent-subtle);
    border-color: var(--color-border-accent);
    color: var(--color-accent);
  }

  .tab-label {
    font-weight: 500;
  }

  .tab-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-elevated);
    border-radius: var(--radius-sm);
  }

  .tab-count.success {
    background: var(--color-success-subtle);
    color: var(--color-success);
  }

  .tab-count.accent {
    background: var(--color-accent-glow);
    color: var(--color-accent);
  }

  .tab-count.info {
    background: var(--color-info-subtle);
    color: var(--color-info);
  }

  /* Keywords Table */
  .table-container {
    overflow-x: auto;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .keywords-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
  }

  .keywords-table th {
    padding: 0.625rem 0.875rem;
    text-align: left;
    font-family: var(--font-mono);
    font-weight: 500;
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .th-volume,
  .th-difficulty,
  .th-competition,
  .th-tier {
    text-align: right;
  }

  .keywords-table td {
    padding: 0.625rem 0.875rem;
    border-bottom: 1px solid var(--color-border);
  }

  .keywords-table tbody tr:last-child td {
    border-bottom: none;
  }

  .keywords-table tbody tr:hover {
    background: var(--color-bg-surface);
  }

  .td-keyword {
    font-family: var(--font-mono);
    color: var(--color-text-primary);
  }

  .td-keyword-inner {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  :global(.keyword-icon) {
    width: 0.75rem;
    height: 0.75rem;
    color: var(--color-text-muted);
  }

  .td-volume {
    text-align: right;
  }

  .volume-value {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .volume-unit {
    color: var(--color-text-muted);
    font-size: 0.6875rem;
  }

  .td-difficulty {
    text-align: right;
  }

  .td-difficulty-inner {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.375rem;
  }

  .difficulty-badge {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    padding: 0.125rem 0.375rem;
    border-radius: var(--radius-sm);
    min-width: 1.5rem;
    text-align: center;
  }

  .difficulty-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .difficulty-na {
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  .difficulty-hint {
    font-weight: 400;
    color: inherit;
    opacity: 0.8;
  }

  .td-competition {
    text-align: right;
  }

  .td-competition-inner {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2);
  }

  .competition-bar {
    width: 2.5rem;
    height: 0.25rem;
    background: var(--color-bg-surface);
    border-radius: 0.125rem;
    overflow: hidden;
  }

  .competition-fill {
    height: 100%;
    border-radius: 0.125rem;
  }

  .competition-value {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    min-width: 1.25rem;
  }

  .td-tier {
    text-align: right;
  }

  /* View Toggle */
  .view-toggle {
    display: flex;
    gap: var(--space-1);
    padding: var(--space-1);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    width: fit-content;
    margin-bottom: var(--space-4);
  }

  .view-toggle-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    background: transparent;
    border: none;
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: color 0.15s ease, background-color 0.15s ease;
  }

  .view-toggle-btn:hover {
    color: var(--color-text-primary);
  }

  .view-toggle-btn.active {
    background: var(--color-bg-elevated);
    color: var(--color-accent);
  }

  .view-toggle-btn :global(.toggle-icon) {
    width: 1rem;
    height: 1rem;
  }

  /* Insights Grid */
  .insights-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-3);
  }

  .insight-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .insight-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .insight-keyword {
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .insight-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
  }

  .insight-metrics .metric {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .insight-metrics .metric-value {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: var(--text-md);
    color: var(--color-text-primary);
  }

  .insight-metrics .metric-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .insight-intent {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .insight-strategy,
  .insight-rationale {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .insight-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .insight-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  .insight-text.muted {
    color: var(--color-text-muted);
    font-style: italic;
  }

  .table-footer {
    text-align: center;
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    margin-top: var(--space-3);
  }

  /* Cluster Card */
  .cluster-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
  }

  .cluster-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .cluster-name {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .cluster-keywords {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .cluster-keyword {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-elevated);
    border-radius: var(--radius-sm);
    color: var(--color-text-muted);
  }

  .cluster-more {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    padding: 0.125rem 0.25rem;
  }

  /* Strategy Cards */
  .strategy-card,
  .positioning-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
  }

  .card-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin: 0 0 0.75rem;
  }

  .strategy-content,
  .positioning-content {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .strategy-content :global(p),
  .positioning-content :global(p) {
    margin: 0 0 0.5rem;
  }

  .strategy-content :global(ul),
  .positioning-content :global(ul) {
    margin: 0 0 0.5rem;
    padding-left: var(--space-4);
  }

  /* Technical Content */
  .technical-content {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  /* Metrics list, risk content, next steps styles removed - generic boilerplate sections deleted */
  /* Schema markup styles removed - Task 5/6 deleted */

  /* Keyword Preview Card */
  .keyword-preview-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-4) var(--space-5);
    margin-bottom: var(--space-4);
  }

  .preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-3);
  }

  .preview-title {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .preview-expand-btn {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0.25rem 0.625rem;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-accent);
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .preview-expand-btn:hover {
    background: var(--color-accent-subtle);
    border-color: var(--color-border-accent);
  }

  .preview-tiers {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }

  .preview-tier {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .tier-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    min-width: 5rem;
  }

  .tier-label.success {
    color: var(--color-success);
  }

  .tier-label.accent {
    color: var(--color-accent);
  }

  .tier-label.muted {
    color: var(--color-text-muted);
  }

  .tier-label.info {
    color: var(--color-info);
  }

  .tier-label.warning {
    color: var(--color-warning);
  }

  .tier-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .keyword-pill {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    border: 1px solid var(--color-border);
  }

  .keyword-pill.success {
    background: var(--color-success-subtle);
    border-color: var(--color-border-success);
    color: var(--color-success-dark);
  }

  .keyword-pill.accent {
    background: var(--color-accent-subtle);
    border-color: var(--color-border-accent);
    color: var(--color-accent);
  }

  .keyword-pill.muted {
    background: var(--color-bg-surface);
  }

  .keyword-pill.info {
    background: var(--color-info-subtle);
    border-color: var(--color-border-info);
    color: var(--color-info);
  }

  .keyword-pill.warning {
    background: var(--color-warning-subtle);
    border-color: var(--color-border-warning);
    color: var(--color-warning);
  }

  .pill-more {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: 0.25rem 0.375rem;
    color: var(--color-text-muted);
  }

  .tier-strategy {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0.5rem 0 0;
    padding-left: 5.75rem; /* Align with pills (5rem label + 0.75rem gap) */
  }

  /* Keyword Controls */
  .keyword-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }

  .search-input-wrapper {
    position: relative;
    flex: 1;
    min-width: 180px;
    max-width: 280px;
  }

  .search-input-wrapper :global(.search-icon) {
    position: absolute;
    left: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-text-muted);
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    padding: 0.5rem 2rem 0.5rem 2.25rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-text-primary);
    transition: border-color 0.15s ease;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .search-input::placeholder {
    color: var(--color-text-muted);
  }

  .search-clear {
    position: absolute;
    right: 0.5rem;
    top: 50%;
    transform: translateY(-50%);
    width: 1.25rem;
    height: 1.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg-elevated);
    border: none;
    border-radius: 50%;
    font-size: var(--text-base);
    color: var(--color-text-muted);
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
  }

  .search-clear:hover {
    background: var(--color-bg-hover);
    color: var(--color-text-primary);
  }

  .search-results-count {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    margin: 0 0 0.75rem;
  }

  /* Table Footer Actions */
  .table-footer-actions {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }

  .show-more-btn {
    padding: var(--space-2) var(--space-4);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-accent);
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .show-more-btn:hover {
    background: var(--color-accent-subtle);
    border-color: var(--color-border-accent);
  }

  /* Responsive */
  @media (max-width: 768px) {
    .keyword-controls {
      flex-direction: column;
      align-items: stretch;
    }

    .insights-grid {
      grid-template-columns: 1fr;
    }

    .search-input-wrapper {
      max-width: none;
    }

    .preview-tier {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.375rem;
    }

    .tier-pills {
      padding-left: 0;
    }

    .tier-strategy {
      padding-left: 0;
      margin-top: 0.375rem;
    }
  }

  @media (max-width: 480px) {
    .tabs-container {
      flex-direction: column;
    }

    .tab-button {
      width: 100%;
      justify-content: space-between;
    }

    .view-toggle {
      width: 100%;
    }

    .view-toggle-btn {
      flex: 1;
      justify-content: center;
    }
  }

  /* Markdown content in expandable sections */
  .markdown-content {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .markdown-content :global(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
    margin: 0.75rem 0;
  }

  .markdown-content :global(th),
  .markdown-content :global(td) {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    text-align: left;
    vertical-align: top;
  }

  .markdown-content :global(th) {
    background: var(--color-bg-surface);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .markdown-content :global(tr:hover) {
    background: var(--color-bg-surface);
  }

  .markdown-content :global(ul),
  .markdown-content :global(ol) {
    margin: 0.5rem 0;
    padding-left: var(--space-5);
  }

  .markdown-content :global(li) {
    margin-bottom: var(--space-1);
  }

  .roadmap-content,
  .budget-content {
    max-height: 500px;
    overflow-y: auto;
  }

  /* Page type implementation styles removed - Task 5/6 deleted */
</style>
