<script lang="ts">
  import {
    Database,
    Clock,
    Server,
    CheckCircle,
    Layers,
    Globe,
    User,
    Cpu,
    ListChecks,
    HardDrive,
    LayoutGrid,
    Route,
    ExternalLink,
    ArrowRight,
    Target,
    ChevronDown,
    ChevronUp,
    FileText,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type {
    SolutionDetails,
    SiteStructure,
    UserFlowsSection,
    SiteSection,
    UserFlow,
    DataInfrastructureRoadmap,
  } from "$lib/types/report";
  import { formatPercent, renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import SubsectionHeader from "$lib/components/ui/SubsectionHeader.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { getTermTooltip } from "$lib/stores/glossary";
  import { normalizeDataAccess } from "$lib/utils/ideaTagLabels";

  interface Props {
    solution: SolutionDetails;
    implementationOverview?: string;
    mvpScope?: string;
    userJourney?: string;
    dataInfrastructureRoadmap?: DataInfrastructureRoadmap;
    siteStructure?: SiteStructure;
    userFlows?: UserFlowsSection;
  }

  let {
    solution,
    implementationOverview,
    mvpScope,
    userJourney,
    dataInfrastructureRoadmap,
    siteStructure,
    userFlows,
  }: Props = $props();

  // Track expanded sections
  let expandedSections = new SvelteSet<string>();

  function toggleSection(sectionName: string) {
    if (expandedSections.has(sectionName)) {
      expandedSections.delete(sectionName);
    } else {
      expandedSections.add(sectionName);
    }
  }

  // Priority badge colors
  function getPriorityVariant(
    priority: string,
  ): "success" | "warning" | "default" {
    switch (priority) {
      case "P0":
        return "success";
      case "P1":
        return "warning";
      default:
        return "default";
    }
  }

  // Page type badge colors
  function getPageTypeVariant(
    pageType: string,
  ): "accent" | "default" | "muted" {
    switch (pageType) {
      case "programmatic":
        return "accent";
      case "static":
        return "default";
      default:
        return "muted";
    }
  }

  // Parse implementation phases from markdown if available
  const hasImplementationData = $derived(
    !!implementationOverview || !!solution.technical_approach,
  );
  const hasMvpData = $derived(!!mvpScope);
  const hasDataSources = $derived(
    solution.data_sources && solution.data_sources.length > 0,
  );

  // Data-access model → human label + risk-palette variant (severity ramp, never accent).
  const ACCESS_LABELS: Record<string, string> = {
    public: "Public API",
    freemium: "Freemium API",
    paywalled: "Paid Data",
    unofficial: "Scraping / Unofficial",
    restricted: "Access Restricted",
    blocked: "Blocked data",
    unverified: "Unverified data",
  };
  // Empty label = value outside the closed vocabulary; the badge is omitted.
  function accessLabel(m: string | undefined): string {
    const k = normalizeDataAccess(m);
    return k ? ACCESS_LABELS[k] : "";
  }
  function accessVariant(m: string | undefined): "success" | "warning" | "error" | "muted" {
    const k = normalizeDataAccess(m) ?? "";
    if (k === "public" || k === "freemium") return "success";
    if (k === "paywalled" || k === "unofficial") return "warning";
    if (k === "restricted" || k === "blocked") return "error";
    return "muted";
  }
</script>

<Section
  id="technical"
  class="report-section"
  icon={SECTION_MAP['technical'].icon}
  title="Technical Blueprint"
  subtitle="Implementation approach and architecture"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Tech Stack Overview -->
  {#if solution.technical_approach}
    <div class="tech-approach-card">
      <div class="tech-approach-header">
        <Server class="w-5 h-5 text-accent" />
        <h3>Technical Architecture</h3>
      </div>
      <p class="tech-approach-text">{solution.technical_approach}</p>
    </div>
  {/if}

  <!-- Bento Grid: Key Metrics with Progress Rings -->
  <AnimateOnScroll animation="fade-up" delay={100}>
    <div class="bento-grid mb-8">
      <!-- Featured: Dev Time (large card) -->
      {#if solution.estimated_development_time}
        <div class="bento-card bento-featured bento-accent">
          <div class="bento-icon-large border border-border">
            <Clock class="w-6 h-6 text-accent" />
          </div>
          <div class="dev-time-value text-accent">
            {solution.estimated_development_time}
          </div>
          <div class="bento-label">Development Time</div>
          <div class="bento-sublabel inline-flex items-center gap-1">
            Estimated to MVP <Tooltip
              content={getTermTooltip("MVP")}
              position="top"
            />
          </div>
        </div>
      {/if}

      <!-- Solo Dev Feasibility with Progress Ring -->
      {#if solution.solo_dev_feasibility}
        <div class="bento-card stat-card-animated">
          <div class="flex flex-col items-center gap-3">
            <ProgressRing
              value={solution.solo_dev_feasibility}
              size={72}
              strokeWidth={5}
              color="auto"
              showValue={true}
              showLabel={true}
              label="Solo"
            />
            <span class="text-xs text-text-muted uppercase tracking-wider"
              >Solo Dev Feasibility</span
            >
          </div>
        </div>
      {/if}

      <!-- Technical Feasibility with Progress Ring -->
      {#if solution.technical_feasibility_score}
        <div class="bento-card stat-card-animated">
          <div class="flex flex-col items-center gap-3">
            <ProgressRing
              value={solution.technical_feasibility_score}
              size={72}
              strokeWidth={5}
              color="auto"
              showValue={true}
              showLabel={true}
              label="Tech"
            />
            <span class="text-xs text-text-muted uppercase tracking-wider"
              >Tech Feasibility</span
            >
          </div>
        </div>
      {/if}

      <!-- Data Acquisition Readiness (annotate-only; from the feasibility critic / Stage-13 reconcile) -->
      {#if solution.data_feasibility_score != null}
        <div class="bento-card stat-card-animated">
          <div class="flex flex-col items-center gap-3">
            <ProgressRing
              value={solution.data_feasibility_score}
              size={72}
              strokeWidth={5}
              color="auto"
              showValue={true}
              showLabel={true}
              label="Data"
            />
            <span class="text-xs text-text-muted uppercase tracking-wider"
              >Data Feasibility</span
            >
            {#if accessLabel(solution.data_access_model)}
              <Badge
                variant={accessVariant(solution.data_access_model)}
                size="sm"
                title={solution.data_acquisition_notes || undefined}
              >
                {accessLabel(solution.data_access_model)}
              </Badge>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Build Feasibility (independent critic's build estimate; annotate-only) -->
      {#if solution.build_feasibility_score != null}
        <div class="bento-card stat-card-animated">
          <div class="flex flex-col items-center gap-3">
            <ProgressRing
              value={solution.build_feasibility_score}
              size={72}
              strokeWidth={5}
              color="auto"
              showValue={true}
              showLabel={true}
              label="Build"
            />
            <span class="text-xs text-text-muted uppercase tracking-wider"
              >Build Feasibility</span
            >
          </div>
        </div>
      {/if}

      <!-- Data Aggregation Required -->
      {#if solution.requires_data_aggregation !== undefined}
        <div class="bento-card stat-card-animated">
          <div class="flex items-center gap-2 mb-2">
            <Database
              class="w-4 h-4 {solution.requires_data_aggregation
                ? 'text-warning'
                : 'text-success'}"
            />
            <span class="text-xs text-text-muted uppercase tracking-wider"
              >Data Pipeline</span
            >
          </div>
          <div
            class="stat-value text-2xl {solution.requires_data_aggregation
              ? 'text-warning'
              : 'text-success'}"
          >
            {solution.requires_data_aggregation ? "Required" : "Simple"}
          </div>
          <div class="text-xs text-text-muted mt-1">
            {solution.requires_data_aggregation
              ? "Aggregation needed"
              : "No complex ETL"}
          </div>
        </div>
      {/if}

      <!-- Indexable Pages -->
      {#if solution.estimated_indexable_pages}
        <div class="bento-card stat-card-animated">
          <div class="flex items-center gap-2 mb-2">
            <Globe class="w-4 h-4 text-accent" />
            <span class="text-xs text-text-muted uppercase tracking-wider"
              >SEO Pages</span
            >
          </div>
          <div class="stat-value text-2xl text-accent">
            {solution.estimated_indexable_pages}
          </div>
          <div class="text-xs text-text-muted mt-1">Indexable Year 1</div>
        </div>
      {/if}
    </div>
  </AnimateOnScroll>

  <!-- Data Sources with enhanced styling -->
  {#if hasDataSources}
    <div class="data-sources-section">
        <SubsectionHeader
          title="Data Sources & Integrations"
          icon={HardDrive}
        />
        <div class="data-sources-grid">
          {#each solution.data_sources || [] as source, i}
            <div class="tech-badge" style="animation-delay: {i * 50}ms">
              <span class="data-indicator-dot"></span>
              {source}
            </div>
          {/each}
        </div>
      </div>
  {/if}

  <!-- Implementation Overview with Timeline styling -->
  {#if implementationOverview}
    <AnimateOnScroll animation="fade-in" delay={200}>
      <div class="implementation-section">
        <SubsectionHeader title="Implementation Roadmap" icon={Layers} />
        <div class="markdown-content implementation-content timeline-styled">
          {@html renderMarkdown(implementationOverview)}
        </div>
      </div>
    </AnimateOnScroll>
  {/if}

  <!-- MVP Scope -->
  {#if mvpScope}
    <AnimateOnScroll animation="fade-up" delay={400}>
      <div class="mvp-section">
        <SubsectionHeader
          title="MVP Scope & Success Criteria"
          icon={CheckCircle}
          variant="success"
        />
        <div class="markdown-content mvp-content">
          {@html renderMarkdown(mvpScope)}
        </div>
      </div>
    </AnimateOnScroll>
  {/if}

  <!-- Site Structure (LLM-generated) -->
  {#if siteStructure}
    <div class="site-structure-section">
        <SubsectionHeader title="Site Architecture" icon={LayoutGrid} />

        <!-- Overview and Stats -->
        <div class="site-overview-card">
          <p class="site-overview-text">{siteStructure.overview}</p>

          <div class="site-stats-grid">
            <div class="site-stat">
              <span class="site-stat-value">{siteStructure.mvp_page_count}</span
              >
              <span class="site-stat-label">MVP Pages</span>
            </div>
            <div class="site-stat">
              <span class="site-stat-value"
                >{siteStructure.total_static_pages}</span
              >
              <span class="site-stat-label">Static Pages</span>
            </div>
            <div class="site-stat">
              <span class="site-stat-value"
                >{siteStructure.total_programmatic_pages}</span
              >
              <span class="site-stat-label">Programmatic</span>
            </div>
          </div>

          {#if siteStructure.tech_stack_recommendation}
            <div class="tech-stack-callout">
              <Server class="w-4 h-4 text-accent" />
              <span class="tech-stack-text"
                >{siteStructure.tech_stack_recommendation}</span
              >
            </div>
          {/if}
        </div>

        <!-- Expandable Sections -->
        <div class="site-sections">
          {#each siteStructure.sections as section, i}
            <div class="site-section-card">
              <button
                class="site-section-header"
                onclick={() => toggleSection(section.section_name)}
                aria-expanded={expandedSections.has(section.section_name)}
              >
                <div class="site-section-header-left">
                  <FileText class="w-4 h-4 text-accent" />
                  <div>
                    <h4 class="site-section-name">{section.section_name}</h4>
                    <p class="site-section-desc">{section.description}</p>
                  </div>
                </div>
                <div class="site-section-header-right">
                  <Badge variant="muted" size="sm"
                    >{section.pages.length} pages</Badge
                  >
                  {#if expandedSections.has(section.section_name)}
                    <ChevronUp class="w-4 h-4 text-text-muted" />
                  {:else}
                    <ChevronDown class="w-4 h-4 text-text-muted" />
                  {/if}
                </div>
              </button>

              {#if expandedSections.has(section.section_name)}
                <div class="site-pages-list">
                  {#each section.pages as page}
                    <div class="site-page-row">
                      <div class="site-page-info">
                        <div class="site-page-name-row">
                          <span class="site-page-name">{page.page_name}</span>
                          <Badge
                            variant={getPriorityVariant(page.priority)}
                            size="sm">{page.priority}</Badge
                          >
                          <Badge
                            variant={getPageTypeVariant(page.page_type)}
                            size="sm">{page.page_type}</Badge
                          >
                        </div>
                        <code class="site-page-url">{page.url_pattern}</code>
                        <p class="site-page-purpose">{page.purpose}</p>
                      </div>
                      {#if page.estimated_count}
                        <div class="site-page-count">
                          <span class="count-value">{page.estimated_count}</span
                          >
                          <span class="count-label">pages</span>
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
  {/if}

  <!-- User Flows (LLM-generated) -->
  {#if userFlows && userFlows.flows.length > 0}
    <AnimateOnScroll animation="scale-in" delay={300}>
      <div class="user-flows-section">
        <SubsectionHeader title="User Journey Flows" icon={Route} />

        {#if userFlows.key_insight}
          <div class="user-flows-insight">
            <Target class="w-4 h-4 text-accent" />
            <p>{userFlows.key_insight}</p>
          </div>
        {/if}

        <div class="user-flows-grid">
          {#each userFlows.flows as flow, flowIndex}
            <div class="user-flow-card">
              <div class="user-flow-header">
                <h4 class="user-flow-name">{flow.flow_name}</h4>
                <Badge variant="accent" size="sm">{flow.persona}</Badge>
              </div>

              <div class="user-flow-meta">
                <div class="user-flow-meta-item">
                  <span class="meta-label">Goal:</span>
                  <span class="meta-value">{flow.goal}</span>
                </div>
                <div class="user-flow-meta-item">
                  <span class="meta-label">Entry:</span>
                  <span class="meta-value">{flow.entry_point}</span>
                </div>
              </div>

              <div class="user-flow-steps">
                {#each flow.steps as step, stepIndex}
                  <div class="user-flow-step">
                    <div class="step-number">{step.step_number}</div>
                    <div class="step-content">
                      <div class="step-action">{step.action}</div>
                      <div class="step-page">
                        <ExternalLink class="w-3 h-3" />
                        {step.page}
                      </div>
                      {#if step.system_response}
                        <div class="step-response">{step.system_response}</div>
                      {/if}
                    </div>
                    {#if stepIndex < flow.steps.length - 1}
                      <div class="step-connector">
                        <ArrowRight class="w-3 h-3 text-text-muted" />
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>

              <div class="user-flow-footer">
                <div class="user-flow-conversion">
                  <span class="conversion-label">Conversion:</span>
                  <span class="conversion-value">{flow.conversion_point}</span>
                </div>
                <div class="user-flow-metric">
                  <span class="metric-label">Success Metric:</span>
                  <span class="metric-value">{flow.success_metric}</span>
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    </AnimateOnScroll>
  {/if}

  <!-- User Journey -->
  {#if userJourney}
    <div class="journey-section">
      <ExpandableSection
        title="User Journey Flow"
        icon={User}
        defaultOpen={false}
        variant="muted"
      >
        <div class="markdown-content journey-content">
          {@html renderMarkdown(userJourney)}
        </div>
      </ExpandableSection>
    </div>
  {/if}

  <!-- Feature Priorities from Keywords -->
  {#if solution.keyword_feature_priorities && solution.keyword_feature_priorities.length > 0}
    <AnimateOnScroll animation="fade-in" delay={400}>
      <div class="priorities-section">
        <SubsectionHeader title="Feature Development Priorities" icon={ListChecks} />
        <div class="timeline">
          {#each solution.keyword_feature_priorities as priority, i}
            <div class="timeline-item" style="animation-delay: {i * 100}ms">
              <div class="priority-content">
                <span class="priority-rank">P{i + 1}</span>
                <span class="priority-text">{priority}</span>
              </div>
            </div>
          {/each}
        </div>
      </div>
    </AnimateOnScroll>
  {/if}

  <!-- Geographic Priorities -->
  {#if solution.keyword_geographic_priorities && solution.keyword_geographic_priorities.length > 0}
    <div class="geo-section">
      <SubsectionHeader
        title="Target Markets (Priority Order)"
        icon={Globe}
      />
      <div class="geo-badges">
        {#each solution.keyword_geographic_priorities as market, i}
          <Badge
            variant={i === 0 ? "success" : i < 3 ? "default" : "muted"}
            size="sm"
          >
            {market}
          </Badge>
        {/each}
      </div>
    </div>
  {/if}
</Section>

<style>
  .dev-time-value {
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.4;
  }

  .tech-approach-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-8);
  }

  .tech-approach-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .tech-approach-header h3 {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .tech-approach-text {
    font-family: var(--font-body);
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
  }

  .data-sources-section {
    margin-bottom: var(--space-8);
  }

  .data-sources-grid {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .implementation-section,
  .mvp-section,
  .journey-section {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
  }

  .implementation-content,
  .mvp-content,
  .journey-content {
    font-size: 0.9375rem;
  }

  /* Timeline-styled markdown lists */
  .timeline-styled :global(ul) {
    position: relative;
    padding-left: var(--space-8);
    list-style: none;
  }

  .timeline-styled :global(ul)::before {
    content: "";
    position: absolute;
    left: 0.5rem;
    top: 0.5rem;
    bottom: 0.5rem;
    width: 2px;
    background: var(--color-accent);
  }

  .timeline-styled :global(li) {
    position: relative;
    padding-bottom: var(--space-4);
  }

  .timeline-styled :global(li)::before {
    content: "";
    position: absolute;
    left: -1.625rem;
    top: 0.4rem;
    width: 8px;
    height: 8px;
    background: var(--color-accent);
    border-radius: 50%;
    border: 2px solid var(--color-bg-surface);
  }

  .priorities-section {
    margin-bottom: var(--space-8);
  }

  .priority-content {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4) var(--space-5);
  }

  .priority-rank {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
  }

  .priority-text {
    color: var(--color-text-secondary);
    font-size: 0.9375rem;
  }

  .geo-section {
    margin-bottom: var(--space-4);
  }

  .geo-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  /* =============================================================================
	   Site Structure Styles
	   ============================================================================= */

  .site-structure-section {
    margin-bottom: var(--space-8);
  }

  .site-overview-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-4);
  }

  .site-overview-text {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
    margin-bottom: var(--space-5);
  }

  .site-stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }

  .site-stat {
    text-align: center;
    padding: var(--space-3);
    background: var(--color-bg-base);
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border);
  }

  .site-stat-value {
    display: block;
    font-family: var(--font-mono);
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-accent-dark);
  }

  .site-stat-label {
    display: block;
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: var(--space-1);
  }

  .tech-stack-callout {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
  }

  .tech-stack-text {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
  }

  .site-sections {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .site-section-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .site-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: var(--space-4) var(--space-5);
    background: transparent;
    border: none;
    cursor: pointer;
    transition: background-color 0.15s ease;
  }

  .site-section-header:hover {
    background: var(--color-bg-base);
  }

  .site-section-header-left {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    text-align: left;
  }

  .site-section-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .site-section-desc {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    margin: var(--space-1) 0 0 0;
  }

  .site-section-header-right {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .site-pages-list {
    border-top: 1px solid var(--color-border);
    padding: var(--space-3) var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .site-page-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: var(--space-3);
    background: var(--color-bg-base);
    border-radius: 0.375rem;
    border: 1px solid var(--color-border);
  }

  .site-page-info {
    flex: 1;
    min-width: 0;
  }

  .site-page-name-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-bottom: 0.375rem;
  }

  .site-page-name {
    font-weight: 600;
    font-size: var(--text-base);
    color: var(--color-text-primary);
  }

  .site-page-url {
    display: block;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-accent-dark);
    margin-bottom: 0.375rem;
  }

  .site-page-purpose {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    margin: 0;
    line-height: 1.5;
  }

  .site-page-count {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-left: var(--space-4);
  }

  .site-page-count .count-value {
    font-family: var(--font-mono);
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-accent-dark);
  }

  .site-page-count .count-label {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    text-transform: uppercase;
  }

  /* =============================================================================
	   User Flows Styles
	   ============================================================================= */

  .user-flows-section {
    margin-bottom: var(--space-8);
  }

  .user-flows-insight {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-4) var(--space-5);
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-5);
  }

  .user-flows-insight p {
    margin: 0;
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    font-style: italic;
  }

  .user-flows-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: var(--space-5);
  }

  .user-flow-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
  }

  .user-flow-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .user-flow-name {
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .user-flow-meta {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
    padding-bottom: var(--space-4);
    border-bottom: 1px solid var(--color-border);
  }

  .user-flow-meta-item {
    display: flex;
    gap: var(--space-2);
    font-size: 0.8125rem;
  }

  .user-flow-meta-item .meta-label {
    color: var(--color-text-muted);
    font-weight: 500;
  }

  .user-flow-meta-item .meta-value {
    color: var(--color-text-secondary);
  }

  .user-flow-steps {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    flex: 1;
  }

  .user-flow-step {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .step-number {
    flex-shrink: 0;
    width: 1.5rem;
    height: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-accent);
    color: white;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    border-radius: 50%;
  }

  .step-content {
    flex: 1;
    min-width: 0;
  }

  .step-action {
    font-size: var(--text-base);
    color: var(--color-text-primary);
    font-weight: 500;
    margin-bottom: var(--space-1);
  }

  .step-page {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-accent-dark);
    margin-bottom: var(--space-1);
  }

  .step-response {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    font-style: italic;
  }

  .step-connector {
    display: flex;
    justify-content: center;
    padding: var(--space-1) 0;
    margin-left: 0.625rem;
  }

  .user-flow-footer {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .user-flow-conversion,
  .user-flow-metric {
    display: flex;
    gap: var(--space-2);
    font-size: 0.8125rem;
  }

  .conversion-label,
  .metric-label {
    color: var(--color-text-muted);
    font-weight: 500;
  }

  .conversion-value {
    color: var(--color-success);
  }

  .metric-value {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
  }

  /* Responsive adjustments */
  @media (max-width: 640px) {
    .site-stats-grid {
      grid-template-columns: repeat(3, 1fr);
      gap: 0.5rem;
    }

    .site-stat-value {
      font-size: 1.25rem;
    }

    .user-flows-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
