<script lang="ts">
  import {
    Code,
    Database,
    Clock,
    Server,
    CheckCircle,
    Layers,
    Globe,
    User,
    Cpu,
    Zap,
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
  import { getTermTooltip } from "$lib/stores/glossary";

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
  let expandedSections: Set<string> = $state(new Set());

  function toggleSection(sectionName: string) {
    if (expandedSections.has(sectionName)) {
      expandedSections.delete(sectionName);
    } else {
      expandedSections.add(sectionName);
    }
    expandedSections = new Set(expandedSections);
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
</script>

<Section
  id="technical"
  class="report-section"
  icon={Code}
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
    <AnimateOnScroll animation="fade-up">
      <div class="tech-approach-card">
        <div class="tech-approach-header">
          <Server class="w-5 h-5 text-accent" />
          <h3>Technical Architecture</h3>
        </div>
        <p class="tech-approach-text">{solution.technical_approach}</p>
      </div>
    </AnimateOnScroll>
  {/if}

  <!-- Bento Grid: Key Metrics with Progress Rings -->
  <AnimateOnScroll animation="fade-up" delay={100}>
    <div class="bento-grid mb-8">
      <!-- Featured: Dev Time (large card) -->
      {#if solution.estimated_development_time}
        <div class="bento-card bento-featured bento-accent">
          <div class="bento-icon-large bg-accent/10 border border-accent/30">
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
    <AnimateOnScroll animation="fade-up" delay={200}>
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
    </AnimateOnScroll>
  {/if}

  <!-- Implementation Overview with Timeline styling -->
  {#if implementationOverview}
    <AnimateOnScroll animation="fade-up" delay={300}>
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
    <AnimateOnScroll animation="fade-up" delay={450}>
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
    </AnimateOnScroll>
  {/if}

  <!-- User Flows (LLM-generated) -->
  {#if userFlows && userFlows.flows.length > 0}
    <AnimateOnScroll animation="fade-up" delay={500}>
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
    <AnimateOnScroll animation="fade-up" delay={500}>
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
    </AnimateOnScroll>
  {/if}

  <!-- Feature Priorities from Keywords -->
  {#if solution.keyword_feature_priorities && solution.keyword_feature_priorities.length > 0}
    <AnimateOnScroll animation="fade-up" delay={600}>
      <div class="priorities-section">
        <SubsectionHeader title="Feature Development Priorities" icon={Zap} />
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
    <AnimateOnScroll animation="fade-up" delay={700}>
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
    </AnimateOnScroll>
  {/if}
</Section>

<style>
  .dev-time-value {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.4;
  }

  .tech-approach-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 2rem;
  }

  .tech-approach-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
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
    margin-bottom: 2rem;
  }

  .data-sources-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .implementation-section,
  .mvp-section,
  .journey-section {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .implementation-content,
  .mvp-content,
  .journey-content {
    font-size: 0.9375rem;
  }

  /* Timeline-styled markdown lists */
  .timeline-styled :global(ul) {
    position: relative;
    padding-left: 2rem;
    list-style: none;
  }

  .timeline-styled :global(ul)::before {
    content: "";
    position: absolute;
    left: 0.5rem;
    top: 0.5rem;
    bottom: 0.5rem;
    width: 2px;
    background: linear-gradient(
      180deg,
      var(--color-accent) 0%,
      var(--color-border) 100%
    );
  }

  .timeline-styled :global(li) {
    position: relative;
    padding-bottom: 1rem;
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
    margin-bottom: 2rem;
  }

  .priority-content {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 1rem 1.25rem;
  }

  .priority-rank {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-accent);
    background: rgba(229, 90, 40, 0.1);
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
  }

  .priority-text {
    color: var(--color-text-secondary);
    font-size: 0.9375rem;
  }

  .geo-section {
    margin-bottom: 1rem;
  }

  .geo-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  /* =============================================================================
	   Site Structure Styles
	   ============================================================================= */

  .site-structure-section {
    margin-bottom: 2rem;
  }

  .site-overview-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 1rem;
  }

  .site-overview-text {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
    margin-bottom: 1.25rem;
  }

  .site-stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .site-stat {
    text-align: center;
    padding: 0.75rem;
    background: var(--color-bg-base);
    border-radius: 0.5rem;
    border: 1px solid var(--color-border);
  }

  .site-stat-value {
    display: block;
    font-family: var(--font-mono);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-accent);
  }

  .site-stat-label {
    display: block;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.25rem;
  }

  .tech-stack-callout {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: rgba(229, 90, 40, 0.05);
    border: 1px solid rgba(229, 90, 40, 0.2);
    border-radius: 0.5rem;
  }

  .tech-stack-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
  }

  .site-sections {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .site-section-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    overflow: hidden;
  }

  .site-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 1rem 1.25rem;
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
    gap: 0.75rem;
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
    margin: 0.25rem 0 0 0;
  }

  .site-section-header-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .site-pages-list {
    border-top: 1px solid var(--color-border);
    padding: 0.75rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .site-page-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 0.75rem;
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
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.375rem;
  }

  .site-page-name {
    font-weight: 600;
    font-size: 0.875rem;
    color: var(--color-text-primary);
  }

  .site-page-url {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-accent);
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
    padding-left: 1rem;
  }

  .site-page-count .count-value {
    font-family: var(--font-mono);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-accent);
  }

  .site-page-count .count-label {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
  }

  /* =============================================================================
	   User Flows Styles
	   ============================================================================= */

  .user-flows-section {
    margin-bottom: 2rem;
  }

  .user-flows-insight {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    background: rgba(229, 90, 40, 0.05);
    border: 1px solid rgba(229, 90, 40, 0.2);
    border-radius: 0.5rem;
    margin-bottom: 1.25rem;
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
    gap: 1.25rem;
  }

  .user-flow-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
  }

  .user-flow-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .user-flow-name {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .user-flow-meta {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--color-border);
  }

  .user-flow-meta-item {
    display: flex;
    gap: 0.5rem;
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
    gap: 0.75rem;
    margin-bottom: 1rem;
    flex: 1;
  }

  .user-flow-step {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
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
    font-size: 0.75rem;
    font-weight: 700;
    border-radius: 50%;
  }

  .step-content {
    flex: 1;
    min-width: 0;
  }

  .step-action {
    font-size: 0.875rem;
    color: var(--color-text-primary);
    font-weight: 500;
    margin-bottom: 0.25rem;
  }

  .step-page {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-accent);
    margin-bottom: 0.25rem;
  }

  .step-response {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-style: italic;
  }

  .step-connector {
    display: flex;
    justify-content: center;
    padding: 0.25rem 0;
    margin-left: 0.625rem;
  }

  .user-flow-footer {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
  }

  .user-flow-conversion,
  .user-flow-metric {
    display: flex;
    gap: 0.5rem;
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
