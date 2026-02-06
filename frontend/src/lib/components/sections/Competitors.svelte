<script lang="ts">
  import {
    Users,
    CheckCircle,
    XCircle,
    ExternalLink,
    Sparkles,
    Layers,
    AlertTriangle,
    TrendingUp,
    Target,
    ChevronDown,
    BarChart3,
  } from "lucide-svelte";
  import type {
    CompetitorProfile,
    CompetitiveAnalysis,
    CompetitiveAnalytics,
    CompetitiveLandscapeMatrix,
  } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import {
    getThreatVariant,
    parseIntensity,
    getDifferentiationConfig,
    getCompetitorTypeVariant,
  } from "$lib/utils/variantHelpers";
  import Badge from "$lib/components/ui/Badge.svelte";
  import SectionHeader from "$lib/components/ui/SectionHeader.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";

  interface Props {
    profiles: CompetitorProfile[];
    analysis: CompetitiveAnalysis;
    analytics: CompetitiveAnalytics;
    landscapeMatrix?: CompetitiveLandscapeMatrix;
    summary?: string;
    selectedSolutionName?: string;
  }

  let {
    profiles,
    analysis,
    analytics,
    landscapeMatrix,
    summary,
    selectedSolutionName,
  }: Props = $props();

  // Expandable sections state
  let showProfiles = $state(false);
  let expandedCompetitor: number | null = $state(null);

  function toggleCompetitor(index: number) {
    expandedCompetitor = expandedCompetitor === index ? null : index;
  }

  // Build feature matrix from competitor profiles
  const featureList = $derived.by(() => {
    const allFeatures = new Set<string>();
    profiles.forEach((p) => p.key_features?.forEach((f) => allFeatures.add(f)));
    return Array.from(allFeatures).slice(0, 8);
  });

  // Calculate saturation percentage for display
  const saturationPercent = $derived(
    Math.round(analytics.market_saturation_score * 100),
  );
  const opportunityPercent = $derived(100 - saturationPercent);
  const diffConfig = $derived(
    getDifferentiationConfig(analytics.differentiation_strength),
  );

  // Get competitive intensity for the selected solution
  const selectedIntensity = $derived.by(() => {
    if (
      !landscapeMatrix?.competitive_intensity_by_solution ||
      !selectedSolutionName
    )
      return null;
    return landscapeMatrix.competitive_intensity_by_solution.find(
      (item) => item.solution_name === selectedSolutionName,
    );
  });
  const selectedIntensityParsed = $derived(
    selectedIntensity ? parseIntensity(selectedIntensity.intensity) : null,
  );
  const selectedIntensityDescription = $derived(
    selectedIntensity
      ? parseIntensityDescription(selectedIntensity.intensity)
      : "",
  );

  // Parse intensity text to extract description (after the dash)
  function parseIntensityDescription(intensity: string): string {
    const dashIndex = intensity.indexOf("—");
    if (dashIndex !== -1) {
      return intensity.substring(dashIndex + 1).trim();
    }
    // Also try regular hyphen
    const hyphenIndex = intensity.indexOf(" - ");
    if (hyphenIndex !== -1) {
      return intensity.substring(hyphenIndex + 3).trim();
    }
    return "";
  }

  // Get the selected solution's landscape for market gaps
  const selectedLandscape = $derived.by(() => {
    if (!analysis?.solution_landscapes || !selectedSolutionName) return null;
    return analysis.solution_landscapes.find(
      (l) => l.solution_name === selectedSolutionName,
    );
  });
</script>

<section id="competitors" class="report-section">
  <SectionHeader
    icon={Users}
    title="Competitive Analysis"
    subtitle="Market landscape and positioning"
  />

  <!-- Hero Strip -->
  <HeroStrip>
    {#snippet primary()}
      <HeroPrimary
        value={opportunityPercent / 100}
        label="Market Opportunity"
        sublabel="{opportunityPercent}% Open"
        size={56}
        strokeWidth={6}
      />
    {/snippet}
    <HeroMetric
      value={analytics.competitor_count}
      label="Competitors"
      icon={Users}
    />
    <HeroMetric
      value={diffConfig.label}
      label="Differentiation"
      color={diffConfig.label.toLowerCase() === "strong"
        ? "success"
        : diffConfig.label.toLowerCase() === "moderate"
          ? "warning"
          : "error"}
      progress={diffConfig.label.toLowerCase() === "strong"
        ? 0.85
        : diffConfig.label.toLowerCase() === "moderate"
          ? 0.5
          : 0.25}
    />
    <HeroMetric
      value={analytics.market_gaps_identified}
      label="Gaps Found"
      icon={Target}
      color="success"
    />
  </HeroStrip>

  <!-- Key Competitors Strip (Always Visible) -->
  {#if landscapeMatrix?.selected_solution_competitors && landscapeMatrix.selected_solution_competitors.length > 0}
    <div class="insight-card insight-card--accent key-competitors-strip">
      <Target class="strip-icon" />
      <span class="strip-label">Key Competitors:</span>
      <div class="strip-badges">
        {#each landscapeMatrix.selected_solution_competitors as competitor}
          <Badge variant="accent">{competitor}</Badge>
        {/each}
        {#if selectedIntensityParsed}
          <Badge
            variant={selectedIntensityParsed.label === "Low"
              ? "success"
              : selectedIntensityParsed.label === "High"
                ? "error"
                : "warning"}
          >
            {selectedIntensityParsed.label} Competition
          </Badge>
        {/if}
      </div>
      {#if selectedIntensityDescription}
        <p class="strip-description">{selectedIntensityDescription}</p>
      {/if}
    </div>
  {/if}

  <!-- Competitive Summary (if available) -->
  {#if summary}
    <div class="summary-card">
      <p class="summary-text">{@html renderMarkdown(summary)}</p>
    </div>
  {/if}

  <!-- Expandable: Market Gaps & Opportunities (from selected solution) -->
  {#if selectedLandscape?.market_gaps && selectedLandscape.market_gaps.length > 0}
    <ExpandableSection
      title="Market Gaps & Opportunities"
      icon={Sparkles}
      count={selectedLandscape.market_gaps.length}
      variant="success"
    >
      <div class="opportunities-list">
        {#each selectedLandscape.market_gaps as gap, i}
          <div class="opportunity-item">
            <span class="opportunity-number">{i + 1}</span>
            <span class="opportunity-text">{gap}</span>
          </div>
        {/each}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Competitor Overlap -->
  {#if landscapeMatrix?.competitor_overlap && landscapeMatrix.competitor_overlap.length > 0}
    <ExpandableSection
      title="Competitor Overlap"
      icon={Layers}
      count={landscapeMatrix.competitor_overlap.length}
    >
      <div class="overlap-grid">
        {#each landscapeMatrix.competitor_overlap as overlap}
          <div class="overlap-card">
            <div class="overlap-header">
              <span class="overlap-name">{overlap.competitor_name}</span>
              <div class="overlap-badges">
                {#if overlap.competitor_type}
                  <Badge
                    variant={overlap.competitor_type === "direct"
                      ? "error"
                      : "warning"}
                    size="sm"
                  >
                    {overlap.competitor_type}
                  </Badge>
                {/if}
                {#if overlap.threat_level}
                  <Badge
                    variant={getThreatVariant(overlap.threat_level)}
                    size="sm"
                  >
                    <AlertTriangle class="badge-icon" />
                    {overlap.threat_level}
                  </Badge>
                {/if}
              </div>
            </div>
            <div class="overlap-solutions">
              <span class="solutions-label">Competes with:</span>
              <div class="solutions-list">
                {#each overlap.solutions_competed as solution}
                  <Badge variant="muted" size="sm">{solution}</Badge>
                {/each}
              </div>
            </div>
          </div>
        {/each}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Feature Comparison -->
  {#if analytics?.feature_comparison?.feature_groups?.length}
    <!-- Grouped Feature Comparison (LLM-powered semantic grouping) -->
    <ExpandableSection
      title="Feature Comparison"
      icon={BarChart3}
      count={analytics.feature_comparison.feature_groups.length}
    >
      <div class="table-container">
        <table class="feature-table">
          <thead>
            <tr>
              <th class="feature-header">Feature Category</th>
              {#each profiles.slice(0, 4) as competitor}
                <th class="competitor-header">{competitor.name.slice(0, 12)}</th
                >
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each analytics.feature_comparison.feature_groups.slice(0, 8) as group}
              <tr>
                <td class="feature-name" title={group.description}>
                  {group.group_name}
                </td>
                {#each profiles.slice(0, 4) as competitor}
                  <td class="feature-check">
                    {#if group.competitors_with_feature.includes(competitor.name)}
                      <CheckCircle class="check-yes" />
                    {:else}
                      <XCircle class="check-no" />
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </ExpandableSection>
  {:else if profiles.length >= 2 && featureList.length > 0}
    <!-- Fallback: Original feature list (exact string matching) -->
    <ExpandableSection
      title="Feature Comparison"
      icon={BarChart3}
      count={featureList.length}
    >
      <div class="table-container">
        <table class="feature-table">
          <thead>
            <tr>
              <th class="feature-header">Feature</th>
              {#each profiles.slice(0, 4) as competitor}
                <th class="competitor-header">{competitor.name.slice(0, 12)}</th
                >
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each featureList as feature}
              <tr>
                <td class="feature-name">{feature}</td>
                {#each profiles.slice(0, 4) as competitor}
                  <td class="feature-check">
                    {#if competitor.key_features?.includes(feature)}
                      <CheckCircle class="check-yes" />
                    {:else}
                      <XCircle class="check-no" />
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Competitor Profiles -->
  <ExpandableSection
    title="Competitor Profiles"
    icon={Users}
    count={profiles.length}
  >
    <div class="profiles-list">
      {#each profiles as competitor, index}
        <div class="profile-card" class:expanded={expandedCompetitor === index}>
          <button
            class="profile-header"
            onclick={() => toggleCompetitor(index)}
            type="button"
          >
            <div class="profile-info">
              <div class="profile-name-row">
                <span class="profile-name">{competitor.name}</span>
                <Badge
                  variant={getCompetitorTypeVariant(competitor.competitor_type)}
                  size="sm"
                >
                  {competitor.competitor_type}
                </Badge>
              </div>
              <p class="profile-description">{competitor.description}</p>
            </div>
            <div class="profile-actions">
              {#if competitor.url}
                <a
                  href={competitor.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="profile-link"
                  onclick={(e) => e.stopPropagation()}
                >
                  <ExternalLink class="link-icon" />
                </a>
              {/if}
              <ChevronDown
                class="profile-chevron {expandedCompetitor === index
                  ? 'expanded'
                  : ''}"
              />
            </div>
          </button>

          {#if expandedCompetitor === index}
            <div class="profile-details">
              <div class="details-grid">
                <!-- Key Features -->
                {#if competitor.key_features && competitor.key_features.length > 0}
                  <div class="detail-section">
                    <h5 class="detail-label">Key Features</h5>
                    <ul class="feature-list">
                      {#each competitor.key_features as feature}
                        <li class="feature-item">
                          <CheckCircle class="feature-icon" />
                          {feature}
                        </li>
                      {/each}
                    </ul>
                  </div>
                {/if}

                <!-- Pricing -->
                {#if competitor.pricing_model}
                  <div class="detail-section">
                    <h5 class="detail-label">Pricing Model</h5>
                    <p class="pricing-text">{competitor.pricing_model}</p>
                  </div>
                {/if}

                <!-- Strengths -->
                {#if competitor.strengths && competitor.strengths.length > 0}
                  <div class="detail-section">
                    <h5 class="detail-label success">Strengths</h5>
                    <ul class="swot-list">
                      {#each competitor.strengths as strength}
                        <li class="swot-item success">+ {strength}</li>
                      {/each}
                    </ul>
                  </div>
                {/if}

                <!-- Weaknesses -->
                {#if competitor.weaknesses && competitor.weaknesses.length > 0}
                  <div class="detail-section">
                    <h5 class="detail-label error">Weaknesses</h5>
                    <ul class="swot-list">
                      {#each competitor.weaknesses as weakness}
                        <li class="swot-item error">- {weakness}</li>
                      {/each}
                    </ul>
                  </div>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </ExpandableSection>

  <!-- Expandable: Strategic Recommendations -->
  {#if analysis?.strategic_recommendations}
    <ExpandableSection title="Strategic Recommendations" icon={TrendingUp}>
      <div class="recommendations-content">
        {@html renderMarkdown(analysis.strategic_recommendations)}
      </div>
    </ExpandableSection>
  {/if}
</section>

<style>
  /* Key Competitors Strip */
  .key-competitors-strip {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .key-competitors-strip :global(.strip-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent);
  }

  .strip-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-accent);
  }

  .strip-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .strip-description {
    width: 100%;
    margin: 0.5rem 0 0 0;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* Summary Card */
  .summary-card {
    padding: 1rem 1.25rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    margin-bottom: 1rem;
  }

  .summary-text {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
    margin: 0;
  }

  .summary-text :global(p) {
    margin: 0 0 0.75rem;
  }

  .summary-text :global(p:last-child) {
    margin-bottom: 0;
  }

  /* Opportunities List */
  .opportunities-list {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }

  .opportunity-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .opportunity-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.375rem;
    height: 1.375rem;
    background: rgba(34, 197, 94, 0.15);
    border-radius: 50%;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-success);
    flex-shrink: 0;
  }

  .opportunity-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* Overlap Grid */
  .overlap-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.75rem;
  }

  .overlap-card {
    padding: 1rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
  }

  .overlap-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
  }

  .overlap-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .overlap-badges {
    display: flex;
    gap: 0.375rem;
  }

  :global(.badge-icon) {
    width: 0.75rem;
    height: 0.75rem;
    margin-right: 0.125rem;
  }

  .overlap-solutions {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .solutions-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  .solutions-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  /* Feature Table */
  .table-container {
    overflow-x: auto;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
  }

  .feature-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  .feature-table th,
  .feature-table td {
    padding: 0.625rem 0.875rem;
    border-bottom: 1px solid var(--color-border);
  }

  .feature-header {
    text-align: left;
    font-family: var(--font-display);
    font-weight: 600;
    color: var(--color-text-primary);
    background: var(--color-bg-surface);
  }

  .competitor-header {
    text-align: center;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    white-space: nowrap;
  }

  .feature-name {
    color: var(--color-text-primary);
    font-size: 0.8125rem;
  }

  .feature-check {
    text-align: center;
  }

  :global(.check-yes) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--color-success);
  }

  :global(.check-no) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--color-text-muted);
    opacity: 0.25;
  }

  .feature-table tbody tr:last-child td {
    border-bottom: none;
  }

  .feature-table tbody tr:hover {
    background: var(--color-bg-surface);
  }

  /* Profiles List */
  .profiles-list {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }

  .profile-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    overflow: hidden;
    transition: border-color 0.15s ease;
  }

  .profile-card:hover {
    border-color: var(--color-border-hover);
  }

  .profile-card.expanded {
    border-color: var(--color-accent);
  }

  .profile-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    width: 100%;
    padding: 1rem;
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
  }

  .profile-info {
    flex: 1;
    min-width: 0;
  }

  .profile-name-row {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    margin-bottom: 0.25rem;
  }

  .profile-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .profile-description {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: 0;
  }

  .profile-actions {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    flex-shrink: 0;
  }

  .profile-link {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    color: var(--color-text-muted);
    border-radius: 0.25rem;
    transition:
      color 0.15s ease,
      background 0.15s ease;
  }

  .profile-link:hover {
    color: var(--color-accent);
    background: rgba(229, 90, 40, 0.1);
  }

  :global(.link-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }

  :global(.profile-chevron) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--color-text-muted);
    transition: transform 0.2s ease;
  }

  :global(.profile-chevron.expanded) {
    transform: rotate(180deg);
  }

  /* Profile Details */
  .profile-details {
    padding: 0 1rem 1rem;
    border-top: 1px solid var(--color-border);
  }

  .details-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.25rem;
    padding-top: 1rem;
  }

  .detail-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .detail-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin: 0;
  }

  .detail-label.success {
    color: var(--color-success);
  }

  .detail-label.error {
    color: var(--color-error);
  }

  .feature-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .feature-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  :global(.feature-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
    flex-shrink: 0;
    margin-top: 0.0625rem;
  }

  .pricing-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    margin: 0;
  }

  .swot-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .swot-item {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  .swot-item.success {
    color: var(--color-text-secondary);
  }

  .swot-item.success::first-letter {
    color: var(--color-success);
  }

  .swot-item.error {
    color: var(--color-text-secondary);
  }

  .swot-item.error::first-letter {
    color: var(--color-error);
  }

  /* Recommendations Content */
  .recommendations-content {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
  }

  .recommendations-content :global(p) {
    margin: 0 0 0.75rem;
  }

  .recommendations-content :global(p:last-child) {
    margin-bottom: 0;
  }

  .recommendations-content :global(ul) {
    margin: 0 0 0.75rem;
    padding-left: 1.25rem;
  }

  .recommendations-content :global(li) {
    margin-bottom: 0.375rem;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .overlap-grid {
      grid-template-columns: 1fr;
    }

    .details-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 480px) {
    .profile-header {
      flex-direction: column;
      gap: 0.5rem;
    }

    .profile-actions {
      align-self: flex-end;
    }

    .key-competitors-strip {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
  }
</style>
