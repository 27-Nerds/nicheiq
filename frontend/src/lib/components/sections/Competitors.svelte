<script lang="ts">
  import {
    Users,
    CheckCircle,
    XCircle,
    ExternalLink,
    Crosshair,
    Layers,
    TrendingUp,
    Target,
    ChevronDown,
    BarChart3,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type {
    CompetitorProfile,
    CompetitiveAnalysis,
    CompetitiveAnalytics,
    CompetitiveLandscapeMatrix,
  } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import {
    parseIntensity,
    getDifferentiationConfig,
    getCompetitorTypeVariant,
  } from "$lib/utils/variantHelpers";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Section from "$lib/components/ui/Section.svelte";
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
    previewMode?: boolean;
  }

  let {
    profiles,
    analysis,
    analytics,
    landscapeMatrix,
    summary,
    selectedSolutionName,
    previewMode = false,
  }: Props = $props();

  // Merged competitor type
  interface MergedCompetitor {
    name: string;
    type?: string;
    solutions: string[];
    profile: CompetitorProfile | null;
    isSelected: boolean;
  }

  const mergedCompetitors = $derived.by(() => {
    if (!landscapeMatrix?.competitor_overlap) {
      // Fallback: no overlap data (older reports) — show profiles only
      return {
        selected: profiles.map((p) => ({
          name: p.name,
          type: p.competitor_type,
          solutions: [],
          profile: p,
          isSelected: true,
        })) as MergedCompetitor[],
        alternative: [] as MergedCompetitor[],
      };
    }

    const selectedSet = new Set(
      (landscapeMatrix.selected_solution_competitors || []).map((n) =>
        n.trim().toLowerCase(),
      ),
    );

    const selected: MergedCompetitor[] = [];
    const alternative: MergedCompetitor[] = [];

    for (const overlap of landscapeMatrix.competitor_overlap) {
      const normalized = overlap.competitor_name.trim().toLowerCase();
      const profile =
        profiles.find((p) => p.name.trim().toLowerCase() === normalized) ??
        null;
      const isSelected = selectedSet.has(normalized);

      const merged: MergedCompetitor = {
        name: overlap.competitor_name,
        type: profile?.competitor_type ?? overlap.competitor_type,
        solutions: overlap.solutions_competed,
        profile,
        isSelected,
      };

      if (isSelected) selected.push(merged);
      else alternative.push(merged);
    }

    return { selected, alternative };
  });

  let expandedName: string | null = $state(null);

  function toggleExpand(name: string, hasProfile: boolean) {
    if (!hasProfile) return;
    expandedName = expandedName === name ? null : name;
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

  // Total merged competitor count
  const totalCompetitors = $derived(
    mergedCompetitors.selected.length + mergedCompetitors.alternative.length,
  );
</script>

<Section
  id="competitors"
  class="report-section"
  icon={SECTION_MAP['competitors'].icon}
  title="Competitive Analysis"
  subtitle="Market landscape and positioning"
  headerSize="lg"
  elevated={false}
  border="none"
  padding={previewMode ? "none" : "container"}
  marginBottom="none"
>
  <div class:preview-locked={previewMode}>
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
      <div class="strip-badges" class:preview-blur={previewMode}>
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
        <p class="strip-description" class:preview-blur={previewMode}>{selectedIntensityDescription}</p>
      {/if}
    </div>
  {/if}

  <!-- Competitive Summary (if available) -->
  {#if summary}
    <div class="summary-card">
      <p class="summary-text" class:preview-blur={previewMode}>{@html renderMarkdown(summary)}</p>
    </div>
  {/if}

  <!-- Expandable: Market Gaps & Opportunities (from selected solution) -->
  {#if selectedLandscape?.market_gaps && selectedLandscape.market_gaps.length > 0}
    <ExpandableSection
      title="Market Gaps & Opportunities"
      icon={Crosshair}
      count={selectedLandscape.market_gaps.length}
      variant="success"
      defaultOpen={previewMode}
    >
      <div class="opportunities-list" class:preview-blur={previewMode}>
        {#each selectedLandscape.market_gaps as gap, i}
          <div class="opportunity-item">
            <span class="opportunity-number">{i + 1}</span>
            <span class="opportunity-text">{gap}</span>
          </div>
        {/each}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Competitive Landscape (Merged) -->
  {#if totalCompetitors > 0}
    <ExpandableSection
      title="Competitive Landscape"
      icon={Layers}
      count={totalCompetitors}
      defaultOpen={previewMode}
    >
      <div class="competitors-list" class:preview-blur={previewMode}>
        <!-- Selected Solution Competitors -->
        {#each mergedCompetitors.selected as comp (comp.name)}
          {@const isExpanded = expandedName === comp.name}
          <div
            class="competitor-card"
            class:expanded={isExpanded}
          >
            <button
              class="competitor-header"
              onclick={() => toggleExpand(comp.name, !!comp.profile)}
              type="button"
            >
              <div class="competitor-info">
                <div class="competitor-name-row">
                  <span class="competitor-name">{comp.name}</span>
                  <div class="competitor-badges">
                    {#if comp.type}
                      <Badge
                        variant={getCompetitorTypeVariant(comp.type)}
                        size="sm"
                      >
                        {comp.type}
                      </Badge>
                    {/if}
                  </div>
                </div>
                {#if comp.profile?.description}
                  <p class="competitor-description">{comp.profile.description}</p>
                {/if}
              </div>
              <div class="competitor-actions">
                {#if comp.profile?.url}
                  <a
                    href={comp.profile.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="competitor-link"
                    onclick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink class="link-icon" />
                  </a>
                {/if}
                {#if comp.profile}
                  <ChevronDown
                    class="competitor-chevron {isExpanded ? 'expanded' : ''}"
                  />
                {/if}
              </div>
            </button>

            {#if comp.solutions.length > 0}
              <div class="competitor-solutions">
                <span class="solutions-label">Competes with:</span>
                <div class="solutions-list">
                  {#each comp.solutions as solution}
                    <Badge variant="muted" size="sm">{solution}</Badge>
                  {/each}
                </div>
              </div>
            {/if}

            {#if isExpanded && comp.profile}
              <div class="competitor-details">
                <div class="details-grid">
                  {#if comp.profile.key_features && comp.profile.key_features.length > 0}
                    <div class="detail-section">
                      <h5 class="detail-label">Key Features</h5>
                      <ul class="feature-list">
                        {#each comp.profile.key_features as feature}
                          <li class="feature-item">
                            <CheckCircle class="feature-icon" />
                            {feature}
                          </li>
                        {/each}
                      </ul>
                    </div>
                  {/if}

                  {#if comp.profile.pricing_model}
                    <div class="detail-section">
                      <h5 class="detail-label">Pricing Model</h5>
                      <p class="pricing-text">{comp.profile.pricing_model}</p>
                    </div>
                  {/if}

                  {#if comp.profile.strengths && comp.profile.strengths.length > 0}
                    <div class="detail-section">
                      <h5 class="detail-label success">Strengths</h5>
                      <ul class="swot-list">
                        {#each comp.profile.strengths as strength}
                          <li class="swot-item success">+ {strength}</li>
                        {/each}
                      </ul>
                    </div>
                  {/if}

                  {#if comp.profile.weaknesses && comp.profile.weaknesses.length > 0}
                    <div class="detail-section">
                      <h5 class="detail-label error">Weaknesses</h5>
                      <ul class="swot-list">
                        {#each comp.profile.weaknesses as weakness}
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

        <!-- Group Separator -->
        {#if mergedCompetitors.alternative.length > 0}
          <div class="group-separator">
            <span>FROM ALTERNATIVE SOLUTIONS</span>
          </div>
        {/if}

        <!-- Alternative Solution Competitors -->
        {#each mergedCompetitors.alternative as comp (comp.name)}
          <div class="competitor-card competitor-card--simple">
            <div class="competitor-header competitor-header--static">
              <div class="competitor-info">
                <div class="competitor-name-row">
                  <span class="competitor-name">{comp.name}</span>
                  <div class="competitor-badges">
                    {#if comp.type}
                      <Badge
                        variant={getCompetitorTypeVariant(comp.type)}
                        size="sm"
                      >
                        {comp.type}
                      </Badge>
                    {/if}
                  </div>
                </div>
              </div>
            </div>

            {#if comp.solutions.length > 0}
              <div class="competitor-solutions">
                <span class="solutions-label">Competes with:</span>
                <div class="solutions-list">
                  {#each comp.solutions as solution}
                    <Badge variant="muted" size="sm">{solution}</Badge>
                  {/each}
                </div>
              </div>
            {/if}
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
      <div class="table-container" class:preview-blur={previewMode}>
        <table class="feature-table">
          <thead>
            <tr>
              <th class="feature-header">Feature Category</th>
              {#each profiles.slice(0, 4) as competitor}
                <th class="competitor-col-header">{competitor.name.slice(0, 12)}</th
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
      <div class="table-container" class:preview-blur={previewMode}>
        <table class="feature-table">
          <thead>
            <tr>
              <th class="feature-header">Feature</th>
              {#each profiles.slice(0, 4) as competitor}
                <th class="competitor-col-header">{competitor.name.slice(0, 12)}</th
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

  <!-- Expandable: Strategic Recommendations -->
  {#if analysis?.strategic_recommendations}
    <ExpandableSection title="Strategic Recommendations" icon={TrendingUp}>
      <div class="recommendations-content" class:preview-blur={previewMode}>
        {@html renderMarkdown(analysis.strategic_recommendations)}
      </div>
    </ExpandableSection>
  {/if}
  </div>
</Section>

<style>
  /* Key Competitors Strip */
  .key-competitors-strip {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    flex-wrap: wrap;
  }

  .key-competitors-strip :global(.strip-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent-dark);
  }

  .strip-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-accent-dark);
  }

  .strip-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .strip-description {
    width: 100%;
    margin: var(--space-2) 0 0 0;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* Summary Card */
  .summary-card {
    padding: var(--space-4) var(--space-5);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    margin-bottom: var(--space-4);
  }

  .summary-text {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
    margin: 0;
    max-width: 70ch;
  }

  .summary-text :global(p) {
    margin: 0 0 var(--space-3);
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
    gap: var(--space-3);
  }

  .opportunity-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.375rem;
    height: 1.375rem;
    background: var(--color-success-subtle);
    border-radius: 50%;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-success);
    flex-shrink: 0;
  }

  .opportunity-text {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* Competitors List (Merged) */
  .competitors-list {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }

  .competitor-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    overflow: hidden;
    transition: border-color 0.15s ease;
  }

  .competitor-card:hover {
    border-color: var(--color-border-hover);
  }

  .competitor-card.expanded {
    border-color: var(--color-accent);
  }

  .competitor-card--simple {
    opacity: 0.85;
  }

  .competitor-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    width: 100%;
    padding: var(--space-4);
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
  }

  .competitor-header--static {
    cursor: default;
  }

  .competitor-info {
    flex: 1;
    min-width: 0;
  }

  .competitor-name-row {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    margin-bottom: var(--space-1);
    flex-wrap: wrap;
  }

  .competitor-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .competitor-badges {
    display: flex;
    gap: 0.375rem;
  }

  :global(.badge-icon) {
    width: 0.75rem;
    height: 0.75rem;
    margin-right: 0.125rem;
  }

  .competitor-description {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: 0;
  }

  .competitor-actions {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    flex-shrink: 0;
  }

  .competitor-link {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    color: var(--color-text-muted);
    border-radius: var(--radius-sm);
    transition:
      color 0.15s ease,
      background 0.15s ease;
  }

  .competitor-link:hover {
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
  }

  :global(.link-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }

  :global(.competitor-chevron) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--color-text-muted);
    transition: transform 0.2s ease;
  }

  :global(.competitor-chevron.expanded) {
    transform: rotate(180deg);
  }

  .competitor-solutions {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding: 0 var(--space-4) var(--space-3);
  }

  .solutions-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
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

  /* Group Separator */
  .group-separator {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) 0;
  }

  .group-separator::before,
  .group-separator::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--color-border);
  }

  .group-separator span {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  /* Competitor Details (Expandable) */
  .competitor-details {
    padding: 0 var(--space-4) var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .details-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-5);
    padding-top: var(--space-4);
  }

  .detail-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .detail-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
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
    gap: var(--space-2);
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  :global(.feature-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent-dark);
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
    gap: var(--space-1);
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

  /* Feature Table */
  .table-container {
    overflow-x: auto;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .feature-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-base);
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

  .competitor-col-header {
    text-align: center;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
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

  /* Recommendations Content */
  .recommendations-content {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
    max-width: 70ch;
  }

  .recommendations-content :global(p) {
    margin: 0 0 var(--space-3);
  }

  .recommendations-content :global(p:last-child) {
    margin-bottom: 0;
  }

  .recommendations-content :global(ul) {
    margin: 0 0 var(--space-3);
    padding-left: var(--space-5);
  }

  .recommendations-content :global(li) {
    margin-bottom: 0.375rem;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .details-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 480px) {
    .competitor-header {
      flex-direction: column;
      gap: 0.5rem;
    }

    .competitor-actions {
      align-self: flex-end;
    }

    .key-competitors-strip {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
  }

  /* ── Preview mode ── */
  .preview-locked {
    user-select: none;
    pointer-events: none;
  }

  .preview-blur {
    filter: blur(5px);
    opacity: 0.5;
  }

  /* Blur HeroStrip data values, keep labels clear */
  .preview-locked :global(.hero-metric__value),
  .preview-locked :global(.hero-metric__bar-fill),
  .preview-locked :global(.hero-metric__footer),
  .preview-locked :global(.hero-primary__sublabel),
  .preview-locked :global(.hero-primary__value),
  .preview-locked :global(.hero-primary__ring) {
    filter: blur(5px);
    opacity: 0.5;
  }
</style>
