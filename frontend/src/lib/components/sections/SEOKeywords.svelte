<script lang="ts">
  import {
    TrendingUp,
    Search,
    Zap,
    FileText,
    FileCode,
    Layers,
    Target,
    Clock,
    CheckCircle,
    AlertTriangle,
    Code,
    BarChart3,
    ChevronRight,
    ArrowUpRight,
    Hash,
    Table,
    Lightbulb,
  } from "lucide-svelte";
  import type {
    SEOStrategy,
    SEOAnalytics,
    SchemaMarkupStrategy,
  } from "$lib/types/report";
  import {
    formatNumber,
    parseCompetition,
    getTierLabel,
    renderMarkdown,
    renderTechnicalContent,
  } from "$lib/utils/format";
  import {
    getDifficultyColor,
    getKeywordTierVariant,
    getPriorityVariant,
  } from "$lib/utils/variantHelpers";
  import Badge from "$lib/components/ui/Badge.svelte";
  import SectionHeader from "$lib/components/ui/SectionHeader.svelte";
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
  let activeTab = $state<"tier0" | "tier1" | "tier2" | "all">("all");

  // Keyword search and display state
  let searchQuery = $state("");
  let showAllKeywords = $state(false);
  const INITIAL_KEYWORD_LIMIT = 15;
  const EXPANDED_KEYWORD_LIMIT = 50;

  // Combine all keywords with tier info
  const allKeywords = $derived(
    [
      ...(strategy.tier_0_keywords || []).map((k) => ({ ...k, tier: 0 })),
      ...(strategy.tier_1_keywords || []).map((k) => ({ ...k, tier: 1 })),
      ...(strategy.tier_2_keywords || []).map((k) => ({ ...k, tier: 2 })),
    ].sort((a, b) => b.search_volume - a.search_volume),
  );

  // Top keywords for preview (always visible)
  const previewKeywords = $derived({
    tier0: allKeywords.filter((k) => k.tier === 0).slice(0, 3),
    tier1: allKeywords.filter((k) => k.tier === 1).slice(0, 3),
    tier2: allKeywords.filter((k) => k.tier === 2).slice(0, 3),
  });

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

  // Type guard to check schema markup format
  function isStructuredSchemaMarkup(
    schema: unknown,
  ): schema is SchemaMarkupStrategy {
    return (
      typeof schema === "object" &&
      schema !== null &&
      ("why_schema_matters" in schema ||
        "schema_examples" in schema ||
        "priority_schema_types" in schema)
    );
  }

  // Helper to normalize h2_structure from old string format or new array format
  function getH2StructureItems(h2: string | string[] | undefined): string[] {
    if (!h2) return [];
    if (Array.isArray(h2)) return h2;
    // Old format: try to split by newlines or return as single item
    return h2
      .split("\n")
      .map((s) => s.replace(/^[-*]\s*/, "").trim())
      .filter(Boolean);
  }

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

<section id="seo" class="report-section">
  <SectionHeader
    icon={TrendingUp}
    title="SEO Strategy & Keywords"
    subtitle="Keyword opportunities and content roadmap"
  />

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
                  <th class="th-competition">Competition</th>
                  <th class="th-tier">Tier</th>
                </tr>
              </thead>
              <tbody>
                {#each getFilteredKeywords().slice(0, displayLimit) as kw}
                  {@const difficulty = parseCompetition(kw.competition)}
                  <tr>
                    <td class="td-keyword">
                      <Hash class="keyword-icon" />
                      <span>{kw.keyword}</span>
                    </td>
                    <td class="td-volume">
                      <span class="volume-value"
                        >{formatNumber(kw.search_volume)}</span
                      >
                      <span class="volume-unit">/mo</span>
                    </td>
                    <td class="td-competition">
                      <div class="competition-bar">
                        <div
                          class="competition-fill"
                          style="width: {difficulty *
                            100}%; background: {getDifficultyColor(difficulty)}"
                        ></div>
                      </div>
                      <span
                        class="competition-value"
                        style="color: {getDifficultyColor(difficulty)}"
                        >{(difficulty * 100).toFixed(0)}</span
                      >
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
              {@const difficulty = parseCompetition(kw.competition)}
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
                  <div class="metric">
                    <span
                      class="metric-value"
                      style="color: {getDifficultyColor(difficulty)}"
                      >{(difficulty * 100).toFixed(0)}</span
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
                <span class="cluster-more"
                  >+{clusterKeywords.length - 5}</span
                >
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
        {@html renderTechnicalContent(
          strategy.technical_seo_recommendations,
        )}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Key Metrics to Track -->
  {#if strategy.key_metrics_to_track && strategy.key_metrics_to_track.length > 0}
    <ExpandableSection
      title="Key Metrics to Track"
      icon={BarChart3}
      count={strategy.key_metrics_to_track.length}
    >
      <div class="metrics-list">
        {#each strategy.key_metrics_to_track as metric, i}
          <div class="metric-item">
            <span class="metric-number">{i + 1}</span>
            <span class="metric-text">{metric}</span>
          </div>
        {/each}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Risk Mitigation -->
  {#if strategy.risk_mitigation}
    <ExpandableSection
      title="Risk Mitigation"
      icon={AlertTriangle}
      variant="warning"
    >
      <div class="markdown-content risk-content timeline-styled">
        {@html renderMarkdown(strategy.risk_mitigation)}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Schema Markup -->
  {#if strategy.schema_markup_strategy}
    <ExpandableSection title="Schema Markup Strategy" icon={Code}>
      {#if isStructuredSchemaMarkup(strategy.schema_markup_strategy)}
            {#if strategy.schema_markup_strategy.why_schema_matters}
              <div class="schema-intro">
                <p>{strategy.schema_markup_strategy.why_schema_matters}</p>
              </div>
            {/if}

            {#if strategy.schema_markup_strategy.priority_schema_types?.length}
              <div class="schema-types">
                <span class="schema-types-label">Priority Schema Types</span>
                <div class="schema-type-tags">
                  {#each strategy.schema_markup_strategy.priority_schema_types as schemaType}
                    <code class="schema-type-tag">{schemaType}</code>
                  {/each}
                </div>
              </div>
            {/if}

            {#if strategy.schema_markup_strategy.schema_examples?.length}
              <div class="schema-examples">
                <span class="schema-examples-label"
                  >Implementation Examples</span
                >
                <div class="schema-examples-grid">
                  {#each strategy.schema_markup_strategy.schema_examples as example}
                    <div class="schema-example-card">
                      <span class="schema-example-type"
                        >{example.schema_type}</span
                      >
                      <pre class="schema-code"><code
                          >{example.json_ld_code}</code
                        ></pre>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            {#if strategy.schema_markup_strategy.implementation_method}
              <div class="schema-method markdown-content">
                {@html renderMarkdown(
                  strategy.schema_markup_strategy.implementation_method,
                )}
              </div>
            {/if}

            {#if strategy.schema_markup_strategy.testing_validation}
              <div class="schema-testing">
                <span class="schema-testing-label">Testing & Validation</span>
                <p>{strategy.schema_markup_strategy.testing_validation}</p>
              </div>
            {/if}
      {:else}
        <!-- String/markdown format fallback -->
        <div class="schema-content markdown-content">
          {@html renderMarkdown(String(strategy.schema_markup_strategy))}
        </div>
      {/if}
    </ExpandableSection>
  {/if}

  <!-- Expandable: Page Type Implementations -->
  {#if strategy.page_type_implementations && strategy.page_type_implementations.length > 0}
    <ExpandableSection
      title="Page Type Implementations"
      icon={FileCode}
      count={strategy.page_type_implementations.length}
      countSuffix="types"
    >
      <div class="page-types-grid">
            {#each strategy.page_type_implementations as pageType}
              <div class="page-type-card">
                <div class="page-type-header">
                  <h4 class="page-type-name">{pageType.page_type}</h4>
                  {#if pageType.priority}
                    <Badge
                      variant={getPriorityVariant(pageType.priority)}
                      size="sm">{pageType.priority}</Badge
                    >
                  {/if}
                </div>

                {#if pageType.url_pattern}
                  <div class="page-type-section">
                    <span class="page-type-label">URL Pattern</span>
                    <code class="page-type-url">{pageType.url_pattern}</code>
                  </div>
                {/if}

                {#if pageType.target_keywords && pageType.target_keywords.length > 0}
                  <div class="page-type-section">
                    <span class="page-type-label">Target Keywords</span>
                    <div class="page-type-keywords">
                      {#each pageType.target_keywords.slice(0, 5) as keyword}
                        <span class="cluster-keyword">{keyword}</span>
                      {/each}
                      {#if pageType.target_keywords.length > 5}
                        <span class="cluster-more"
                          >+{pageType.target_keywords.length - 5}</span
                        >
                      {/if}
                    </div>
                  </div>
                {/if}

                {#if pageType.title_tag_example}
                  <div class="page-type-section">
                    <span class="page-type-label">Title Example</span>
                    <code class="page-type-example"
                      >{pageType.title_tag_example}</code
                    >
                  </div>
                {/if}

                {#if pageType.meta_description_example}
                  <div class="page-type-section">
                    <span class="page-type-label">Meta Description</span>
                    <code class="page-type-example"
                      >{pageType.meta_description_example}</code
                    >
                  </div>
                {/if}

                {#if pageType.h1_structure}
                  <div class="page-type-section">
                    <span class="page-type-label">H1 Structure</span>
                    <code class="page-type-example"
                      >{pageType.h1_structure}</code
                    >
                  </div>
                {/if}

                {#if pageType.h2_structure}
                  {@const h2Items = getH2StructureItems(pageType.h2_structure)}
                  {#if h2Items.length > 0}
                    <div class="page-type-section">
                      <span class="page-type-label">H2 Sections</span>
                      <ul class="h2-list">
                        {#each h2Items as h2}
                          <li>{h2}</li>
                        {/each}
                      </ul>
                    </div>
                  {/if}
                {/if}

                {#if pageType.schema_types && pageType.schema_types.length > 0}
                  <div class="page-type-section">
                    <span class="page-type-label">Schema Types</span>
                    <div class="schema-type-tags">
                      {#each pageType.schema_types as schemaType}
                        <code class="schema-type-tag">{schemaType}</code>
                      {/each}
                    </div>
                  </div>
                {/if}

                {#if pageType.internal_linking_strategy}
                  <div class="page-type-section">
                    <span class="page-type-label">Internal Linking</span>
                    <div class="page-type-text markdown-content">
                      {@html renderMarkdown(pageType.internal_linking_strategy)}
                    </div>
                  </div>
                {/if}

                {#if pageType.content_guidelines}
                  <div class="page-type-section">
                    <span class="page-type-label">Content Guidelines</span>
                    <div class="page-type-text markdown-content">
                      {@html renderMarkdown(pageType.content_guidelines)}
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Competitive Positioning -->
  {#if strategy.competitive_positioning || (strategy.competitive_advantages && strategy.competitive_advantages.length > 0)}
    <ExpandableSection title="Competitive Positioning" icon={Target}>
      <CardGrid minWidth={260} gap="md">
        {#if strategy.competitive_positioning}
          <div class="positioning-card">
            <h4 class="card-label">Market Position</h4>
            <div class="positioning-content">
              {@html renderMarkdown(strategy.competitive_positioning)}
            </div>
          </div>
        {/if}
        {#if strategy.competitive_advantages && strategy.competitive_advantages.length > 0}
          <div class="advantages-card">
            <h4 class="card-label success">Competitive Advantages</h4>
            <ul class="advantages-list">
              {#each strategy.competitive_advantages as advantage}
                <li class="advantage-item">
                  <ArrowUpRight class="advantage-icon" />
                  {advantage}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </CardGrid>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Conclusion & Next Steps -->
  {#if strategy.conclusion_bottom_line || (strategy.next_steps_checklist && strategy.next_steps_checklist.length > 0) || (strategy.critical_success_factors && strategy.critical_success_factors.length > 0)}
    <ExpandableSection
      title="Conclusion & Next Steps"
      icon={CheckCircle}
      variant="success"
    >
      {#if strategy.critical_success_factors && strategy.critical_success_factors.length > 0}
        <div class="success-factors">
          <h4 class="card-label">Critical Success Factors</h4>
          <div class="factors-grid">
            {#each strategy.critical_success_factors as factor}
              <div class="factor-item">
                <CheckCircle class="factor-icon" />
                <span>{factor}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <CardGrid minWidth={260} gap="md">
        {#if strategy.conclusion_bottom_line}
          <div class="bottomline-card">
            <h4 class="card-label accent">Bottom Line</h4>
            <div class="bottomline-content">
              {@html renderMarkdown(strategy.conclusion_bottom_line)}
            </div>
          </div>
        {/if}
        {#if strategy.next_steps_checklist && strategy.next_steps_checklist.length > 0}
          <div class="nextsteps-card">
            <h4 class="card-label success">Next Steps</h4>
            <ol class="nextsteps-list">
              {#each strategy.next_steps_checklist as step, i}
                <li class="nextstep-item">
                  <span class="step-number">{i + 1}</span>
                  <span class="step-text">{step}</span>
                </li>
              {/each}
            </ol>
          </div>
        {/if}
      </CardGrid>
    </ExpandableSection>
  {/if}
</section>

<style>
  /* Findings Card */
  .findings-card {
    margin-bottom: 1rem;
  }

  .findings-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
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
    border-radius: 0.75rem;
    padding: 1.25rem;
    margin-bottom: 1rem;
  }

  /* Tabs */
  .tabs-container {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .tab-button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .tab-button:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-hover);
  }

  .tab-button.active {
    background: rgba(229, 90, 40, 0.1);
    border-color: rgba(229, 90, 40, 0.5);
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
    border-radius: 0.25rem;
  }

  .tab-count.success {
    background: rgba(34, 197, 94, 0.15);
    color: var(--color-success);
  }

  .tab-count.accent {
    background: rgba(229, 90, 40, 0.15);
    color: var(--color-accent);
  }

  /* Keywords Table */
  .table-container {
    overflow-x: auto;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
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
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-mono);
    color: var(--color-text-primary);
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

  .td-competition {
    text-align: right;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.5rem;
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
    gap: 0.25rem;
    padding: 0.25rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    width: fit-content;
    margin-bottom: 1rem;
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
    transition: all 0.15s ease;
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
    gap: 0.75rem;
  }

  .insight-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .insight-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .insight-keyword {
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .insight-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .insight-metrics .metric {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .insight-metrics .metric-value {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 1rem;
    color: var(--color-text-primary);
  }

  .insight-metrics .metric-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .insight-intent {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .insight-strategy,
  .insight-rationale {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .insight-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
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
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin-top: 0.75rem;
  }

  /* Cluster Card */
  .cluster-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 1rem;
  }

  .cluster-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .cluster-name {
    font-family: var(--font-display);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .cluster-keywords {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .cluster-keyword {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-elevated);
    border-radius: 0.25rem;
    color: var(--color-text-muted);
  }

  .cluster-more {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    padding: 0.125rem 0.25rem;
  }

  /* Strategy Cards */
  .strategy-card,
  .positioning-card,
  .advantages-card,
  .bottomline-card,
  .nextsteps-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 1rem;
  }

  .card-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin: 0 0 0.75rem;
  }

  .card-label.success {
    color: var(--color-success);
  }

  .card-label.accent {
    color: var(--color-accent);
  }

  .strategy-content,
  .positioning-content,
  .bottomline-content {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .strategy-content :global(p),
  .positioning-content :global(p),
  .bottomline-content :global(p) {
    margin: 0 0 0.5rem;
  }

  .strategy-content :global(ul),
  .positioning-content :global(ul) {
    margin: 0 0 0.5rem;
    padding-left: 1rem;
  }

  /* Technical Content */
  .technical-content {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  /* Metrics List */
  .metrics-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.5rem;
  }

  .metric-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.625rem 0.875rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
  }

  .metric-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    background: rgba(229, 90, 40, 0.15);
    border-radius: 50%;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .metric-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  /* Risk Content */
  .risk-content {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  /* Rich Schema Format Styles */
  .schema-intro {
    margin-bottom: 1rem;
  }

  .schema-intro p {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin: 0;
  }

  .schema-types {
    margin-bottom: 1rem;
  }

  .schema-types-label,
  .schema-examples-label,
  .schema-testing-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.5rem;
  }

  .schema-type-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .schema-type-tag {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    background: rgba(229, 90, 40, 0.1);
    border: 1px solid rgba(229, 90, 40, 0.2);
    border-radius: 0.25rem;
    color: var(--color-accent);
  }

  .schema-examples {
    margin-bottom: 1rem;
  }

  .schema-examples-grid {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .schema-example-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    overflow: hidden;
  }

  .schema-example-type {
    display: block;
    padding: 0.5rem 0.75rem;
    background: var(--color-bg-elevated);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-accent);
    border-bottom: 1px solid var(--color-border);
  }

  .schema-code {
    margin: 0;
    padding: 0.75rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    line-height: 1.5;
    overflow-x: auto;
    max-height: 200px;
    background: var(--color-bg-base);
  }

  .schema-code code {
    white-space: pre-wrap;
    word-break: break-word;
  }

  .schema-method {
    margin-bottom: 1rem;
  }

  .schema-testing {
    padding: 0.75rem;
    background: rgba(34, 197, 94, 0.05);
    border: 1px solid rgba(34, 197, 94, 0.2);
    border-radius: 0.5rem;
  }

  .schema-testing p {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  /* Advantages List */
  .advantages-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .advantage-item {
    display: flex;
    align-items: flex-start;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .advantage-item :global(.advantage-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-success);
    flex-shrink: 0;
    margin-top: 0.0625rem;
  }

  /* Success Factors */
  .success-factors {
    margin-bottom: 1rem;
  }

  .factors-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.5rem;
  }

  .factor-item {
    display: flex;
    align-items: flex-start;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .factor-item :global(.factor-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
    flex-shrink: 0;
    margin-top: 0.0625rem;
  }

  /* Next Steps */
  .nextsteps-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .nextstep-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .step-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    background: rgba(34, 197, 94, 0.15);
    border-radius: 50%;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-success);
    flex-shrink: 0;
  }

  .step-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  /* Keyword Preview Card */
  .keyword-preview-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
  }

  .preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
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
    gap: 0.25rem;
    padding: 0.25rem 0.625rem;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: 1rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-accent);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .preview-expand-btn:hover {
    background: rgba(229, 90, 40, 0.1);
    border-color: rgba(229, 90, 40, 0.3);
  }

  .preview-tiers {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }

  .preview-tier {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .tier-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
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

  .tier-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .keyword-pill {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    border: 1px solid var(--color-border);
  }

  .keyword-pill.success {
    background: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.2);
    color: var(--color-success-dark);
  }

  .keyword-pill.accent {
    background: rgba(229, 90, 40, 0.1);
    border-color: rgba(229, 90, 40, 0.2);
    color: var(--color-accent);
  }

  .keyword-pill.muted {
    background: var(--color-bg-surface);
  }

  .pill-more {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: 0.25rem 0.375rem;
    color: var(--color-text-muted);
  }

  /* Keyword Controls */
  .keyword-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
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
    font-size: 0.875rem;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .search-clear:hover {
    background: var(--color-bg-hover);
    color: var(--color-text-primary);
  }

  .search-results-count {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin: 0 0 0.75rem;
  }

  /* Table Footer Actions */
  .table-footer-actions {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }

  .show-more-btn {
    padding: 0.5rem 1rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-accent);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .show-more-btn:hover {
    background: rgba(229, 90, 40, 0.1);
    border-color: rgba(229, 90, 40, 0.3);
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
    font-size: 0.75rem;
    margin: 0.75rem 0;
  }

  .markdown-content :global(th),
  .markdown-content :global(td) {
    padding: 0.5rem 0.75rem;
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
    padding-left: 1.25rem;
  }

  .markdown-content :global(li) {
    margin-bottom: 0.25rem;
  }

  .roadmap-content,
  .budget-content,
  .schema-content {
    max-height: 500px;
    overflow-y: auto;
  }

  /* Page Type Implementations */
  .page-types-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 0.75rem;
  }

  .page-type-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .page-type-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .page-type-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .page-type-section {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .page-type-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .page-type-url {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    padding: 0.375rem 0.5rem;
    background: var(--color-bg-elevated);
    border-radius: 0.25rem;
    color: var(--color-accent);
    word-break: break-all;
  }

  .page-type-keywords {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .page-type-example {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    padding: 0.5rem;
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 0.25rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .page-type-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .page-type-text :global(p) {
    margin: 0 0 0.375rem;
  }

  .page-type-text :global(ul) {
    margin: 0 0 0.375rem;
    padding-left: 1rem;
  }

  .h2-list {
    list-style: disc;
    margin: 0;
    padding-left: 1.25rem;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .h2-list li {
    margin-bottom: 0.125rem;
    line-height: 1.4;
  }

  @media (max-width: 768px) {
    .page-types-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
