<script lang="ts">
  import { ArrowRight, CircleAlert } from "lucide-svelte";
  import type { Report } from "$lib/types/report";
  import { stripMarkdown } from "$lib/utils/format";

  interface Props {
    report: Report;
    topic: "demand" | "market" | "competition";
    fullDetailHref?: string;
  }

  let { report, topic, fullDetailHref }: Props = $props();

  const details = $derived(report.selected_solution_details);
  const dashboard = $derived(report.executive_dashboard);
  const sourceCount = $derived.by<number | null>(() => {
    if (dashboard?.key_metrics?.social_evidence_threads !== undefined) {
      return dashboard.key_metrics.social_evidence_threads;
    }
    const metadata = report.research_metadata;
    if (
      metadata?.reddit_posts_analyzed !== undefined ||
      metadata?.twitter_threads_analyzed !== undefined ||
      metadata?.generic_posts_analyzed !== undefined
    ) {
      return (
        (metadata.reddit_posts_analyzed ?? 0) +
        (metadata.twitter_threads_analyzed ?? 0) +
        (metadata.generic_posts_analyzed ?? 0)
      );
    }
    return report.evidence_appendix?.top_reddit_threads.length ?? null;
  });
  const primaryBuyer = $derived(
    report.audience_mapping?.primary_target_segment ??
      details?.target_personas?.[0] ??
      "Not identified",
  );
  const painPoints = $derived(report.detailed_pain_points?.slice(0, 3) ?? []);
  const socialEvidenceLabel = $derived.by(() => {
    if (sourceCount === null) return "Social evidence unavailable";
    if (sourceCount === 0) return "No social evidence";
    return `${sourceCount} social evidence ${sourceCount === 1 ? "item" : "items"}`;
  });
  const painPointGroupLabel = $derived(
    sourceCount && sourceCount > 0
      ? "What the social evidence supports"
      : "Problems identified in this report",
  );
  const market = $derived(report.market_sizing);
  const pricing = $derived(report.pricing_strategy);
  const trend = $derived(report.trend_longevity);
  const traffic = $derived(report.traffic_monetization);
  const competition = $derived(report.competitive_analysis);
  const competitionMetrics = $derived(report.competitive_analytics);
  const selectedLandscape = $derived(
    competition?.solution_landscapes.find(
      (item) => item.solution_name === report.selected_solution_name,
    ) ?? competition?.solution_landscapes[0],
  );
  const competitors = $derived(
    (report.competitor_profiles ?? []).slice(0, 6),
  );
  const marketGaps = $derived(
    (selectedLandscape?.market_gaps ?? competition?.top_opportunities ?? []).slice(0, 4),
  );
  const differentiation = $derived(
    details?.differentiation_factors?.[0] ??
      selectedLandscape?.recommended_positioning ??
      competition?.strategic_recommendations ??
      report.competitive_summary,
  );
  const preferredPrice = $derived(
    pricing?.recommended_starter_price ??
      pricing?.recommended_pro_price ??
      pricing?.recommended_enterprise_price ??
      traffic?.estimated_monthly_revenue_range ??
      "Price unavailable",
  );
  const marketVerdict = $derived(market?.market_viability_verdict ?? "Not graded");
  const competitionVerdict = $derived(
    competitionMetrics?.differentiation_strength ??
      selectedLandscape?.competitive_intensity ??
      "Not graded",
  );

  function verdictTone(value: string | null | undefined): "positive" | "caution" | "negative" {
    const normalized = value?.trim().toLowerCase() ?? "";
    if (
      normalized.includes("no-go") ||
      normalized.includes("not viable") ||
      normalized.includes("weak") ||
      normalized.includes("poor")
    ) {
      return "negative";
    }
    if (
      normalized.includes("strong") ||
      normalized.includes("viable") ||
      normalized.includes("favorable")
    ) {
      return "positive";
    }
    return "caution";
  }

  const demandTone = $derived(sourceCount !== null && sourceCount > 0 ? "positive" : "caution");
  const marketTone = $derived(verdictTone(marketVerdict));
  const competitionTone = $derived(
    competitionMetrics?.differentiation_strength
      ? verdictTone(competitionMetrics.differentiation_strength)
      : "caution",
  );

  function scoreLabel(value: number | undefined): string | null {
    if (value === undefined || Number.isNaN(value)) return null;
    const normalized = value <= 1 ? value * 100 : value;
    return `${Math.round(normalized)}/100`;
  }
</script>

{#if topic === "demand"}
  <section class="summary-section" aria-labelledby="demand-summary-title">
    <header class="summary-heading">
      <div>
        <p>Demand case</p>
        <h3 id="demand-summary-title">Is the problem real enough to pay to solve?</h3>
      </div>
      <span class:positive={demandTone === "positive"} class:caution={demandTone === "caution"}>
        {socialEvidenceLabel}
      </span>
    </header>

    <dl class="summary-facts">
      <div>
        <dt>Primary buyer</dt>
        <dd>{primaryBuyer}</dd>
      </div>
      <div>
        <dt>Problems examined</dt>
        <dd>
          {report.pain_point_analytics?.total_pain_points ??
            report.detailed_pain_points?.length ??
            "Not available"}
        </dd>
      </div>
      <div>
        <dt>Strongest problem</dt>
        <dd>
          {report.pain_point_analytics?.top_pain_point_title ??
            dashboard?.core_pain_point?.title ??
            painPoints[0]?.title ??
            "Not identified"}
        </dd>
      </div>
    </dl>

    {#if painPoints.length}
      <div class="finding-group">
        <h4>{painPointGroupLabel}</h4>
        {#if !sourceCount}
          <p class="provenance-note">
            This artifact has no saved social-evidence records attached to these problem
            statements.
          </p>
        {/if}
        <ol class="finding-list">
          {#each painPoints as painPoint, index}
            <li>
              <span class="finding-number">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <div class="finding-title">
                  <strong>{painPoint.title}</strong>
                  <span>
                    {#if scoreLabel(painPoint.severity_score)}
                      Severity {scoreLabel(painPoint.severity_score)}
                    {/if}
                    {#if scoreLabel(painPoint.commercial_intent)}
                      · Buying signal {scoreLabel(painPoint.commercial_intent)}
                    {/if}
                  </span>
                </div>
                <p>{painPoint.description}</p>
                {#if painPoint.representative_quotes?.[0]}
                  <blockquote>“{painPoint.representative_quotes[0]}”</blockquote>
                {/if}
              </div>
            </li>
          {/each}
        </ol>
      </div>
    {:else}
      <div class="empty-note">
        <CircleAlert aria-hidden="true" />
        <p>
          The report retained only an aggregate demand read. Individual problem records are not
          available.
        </p>
      </div>
    {/if}

    {#if report.audience_mapping?.audience_segments?.length}
      <div class="supporting-section">
        <h4>Who appears closest to the problem</h4>
        <ul class="compact-list">
          {#each report.audience_mapping.audience_segments.slice(0, 3) as segment}
            <li>
              <strong>{segment.segment_name}</strong>
              {#if segment.motivation_drivers?.[0]}
                <span>{segment.motivation_drivers[0]}</span>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  </section>
{:else if topic === "market"}
  <section class="summary-section" aria-labelledby="market-summary-title">
    <header class="summary-heading">
      <div>
        <p>Market case</p>
        <h3 id="market-summary-title">Is there a reachable market with workable economics?</h3>
      </div>
      <span
        class:positive={marketTone === "positive"}
        class:caution={marketTone === "caution"}
        class:negative={marketTone === "negative"}
      >
        {marketVerdict}
      </span>
    </header>

    <dl class="summary-facts summary-facts--four">
      <div>
        <dt>Total market</dt>
        <dd>{market?.total_addressable_market ?? "Not estimated"}</dd>
      </div>
      <div>
        <dt>Reachable market</dt>
        <dd>{market?.serviceable_available_market ?? "Not estimated"}</dd>
      </div>
      <div>
        <dt>First-year target</dt>
        <dd>{market?.serviceable_obtainable_market_y1 ?? "Not estimated"}</dd>
      </div>
      <div>
        <dt>Entry price</dt>
        <dd>{preferredPrice}</dd>
      </div>
    </dl>

    <div class="decision-grid">
      <article>
        <span>Timing</span>
        <h4>
          {trend?.trend_direction ??
            market?.market_timing_assessment ??
            trend?.longevity_verdict ??
            "Not assessed"}
        </h4>
        <p>
          {trend?.timing_recommendation ??
            trend?.longevity_rationale ??
            market?.viability_rationale ??
            "The report did not retain a timing rationale."}
        </p>
      </article>
      <article>
        <span>Business model</span>
        <h4>{pricing?.pricing_model ?? traffic?.monetization_model ?? "Not assessed"}</h4>
        <p>
          {pricing?.pricing_rationale ??
            traffic?.monetization_rationale ??
            "The report did not retain a monetization rationale."}
        </p>
      </article>
    </div>

    {#if market?.growth_drivers?.length || market?.risk_factors?.length}
      <div class="paired-lists">
        <div>
          <h4>What supports the case</h4>
          <ul>
            {#each market.growth_drivers?.slice(0, 4) ?? [] as driver}
              <li>{driver}</li>
            {/each}
          </ul>
        </div>
        <div>
          <h4>What could weaken it</h4>
          <ul>
            {#each market.risk_factors?.slice(0, 4) ?? [] as risk}
              <li>{risk}</li>
            {/each}
          </ul>
        </div>
      </div>
    {/if}

    {#if market?.primary_methodology || market?.data_sources_used?.length}
      <div class="method-strip">
        <strong>How this was estimated</strong>
        <p>
          {market.primary_methodology ?? "Method not recorded"}
          {#if market.data_sources_used?.length}
            · {market.data_sources_used.slice(0, 4).join(", ")}
          {/if}
        </p>
      </div>
    {/if}
  </section>
{:else}
  <section class="summary-section" aria-labelledby="competition-summary-title">
    <header class="summary-heading">
      <div>
        <p>Competition case</p>
        <h3 id="competition-summary-title">Can this idea earn a distinct place in the market?</h3>
      </div>
      <span
        class:positive={competitionTone === "positive"}
        class:caution={competitionTone === "caution"}
        class:negative={competitionTone === "negative"}
      >
        {competitionVerdict}
      </span>
    </header>

    <dl class="summary-facts">
      <div>
        <dt>Alternatives reviewed</dt>
        <dd>
          {competitionMetrics?.competitor_count ?? (competitors.length || "Not available")}
        </dd>
      </div>
      <div>
        <dt>Market gaps found</dt>
        <dd>
          {competitionMetrics?.market_gaps_identified ?? (marketGaps.length || "Not available")}
        </dd>
      </div>
      <div>
        <dt>Competitive intensity</dt>
        <dd>{selectedLandscape?.competitive_intensity ?? "Not assessed"}</dd>
      </div>
    </dl>

    <div class="positioning-callout">
      <span>Where the edge could live</span>
      <p>{stripMarkdown(differentiation) || "No defensible positioning was documented."}</p>
    </div>

    <div class="decision-grid">
      <article>
        <span>Closest alternatives</span>
        {#if competitors.length}
          <ul class="name-list">
            {#each competitors as competitor}
              <li>
                <strong>{competitor.name}</strong>
                <small>{competitor.competitor_type.toLowerCase()}</small>
              </li>
            {/each}
          </ul>
        {:else}
          <p>No named competitor profiles were retained.</p>
        {/if}
      </article>
      <article>
        <span>Openings worth testing</span>
        {#if marketGaps.length}
          <ul>
            {#each marketGaps as gap}
              <li>{gap}</li>
            {/each}
          </ul>
        {:else}
          <p>No specific market gaps were retained.</p>
        {/if}
      </article>
    </div>
  </section>
{/if}

{#if fullDetailHref}
  <div class="detail-entry">
    <div>
      <strong>Need the research appendix?</strong>
      <p>Open the detailed generated artifacts for this topic, including charts and methods.</p>
    </div>
    <a href={fullDetailHref}>
      Open research appendix
      <ArrowRight aria-hidden="true" />
    </a>
  </div>
{/if}

<style>
  .summary-section {
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    background: var(--color-bg-elevated);
  }

  .summary-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-6);
    padding: var(--space-6);
    border-bottom: 1px solid var(--color-border);
  }

  .summary-heading p,
  .summary-heading h3 {
    margin: 0;
  }

  .summary-heading p {
    margin-bottom: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .summary-heading h3 {
    max-width: 34ch;
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-text-primary);
    text-wrap: balance;
  }

  .summary-heading > span {
    flex: 0 0 auto;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-full);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
  }

  .summary-heading > span.positive {
    background: var(--color-success-subtle);
    color: var(--color-success-text);
  }

  .summary-heading > span.caution {
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
  }

  .summary-heading > span.negative {
    background: var(--color-error-subtle);
    color: var(--color-error-text);
  }

  .summary-facts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .summary-facts--four {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .summary-facts div {
    min-width: 0;
    padding: var(--space-5) var(--space-6);
  }

  .summary-facts div + div {
    border-left: 1px solid var(--color-border);
  }

  .summary-facts dt {
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  .summary-facts dd {
    margin: var(--space-2) 0 0;
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 700;
    line-height: 1.45;
  }

  .finding-group,
  .supporting-section,
  .paired-lists,
  .decision-grid {
    padding: var(--space-6);
  }

  .finding-group h4,
  .supporting-section h4,
  .paired-lists h4,
  .decision-grid h4 {
    margin: 0;
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 700;
  }

  .provenance-note {
    max-width: 64ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.6;
  }

  .finding-list {
    display: grid;
    margin: var(--space-4) 0 0;
    padding: 0;
    list-style: none;
  }

  .finding-list li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-5) 0;
    border-top: 1px solid var(--color-border);
  }

  .finding-number {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  .finding-title {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }

  .finding-title strong {
    color: var(--color-text-primary);
    font-size: var(--text-md);
    font-weight: 700;
  }

  .finding-title span {
    flex: 0 0 auto;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .finding-list p,
  .finding-list blockquote {
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.6;
  }

  .finding-list blockquote {
    padding-left: var(--space-4);
    border-left: 1px solid var(--color-border-emphasis);
    font-style: italic;
  }

  .supporting-section {
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }

  .compact-list,
  .paired-lists ul,
  .decision-grid ul {
    margin: var(--space-4) 0 0;
    padding: 0;
    list-style: none;
  }

  .compact-list {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-4);
  }

  .compact-list li {
    display: grid;
    gap: var(--space-2);
  }

  .compact-list strong,
  .name-list strong {
    color: var(--color-text-primary);
    font-size: var(--text-sm);
  }

  .compact-list span {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .decision-grid,
  .paired-lists {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0;
  }

  .decision-grid article,
  .paired-lists > div {
    min-width: 0;
    padding-right: var(--space-6);
  }

  .decision-grid article + article,
  .paired-lists > div + div {
    padding-right: 0;
    padding-left: var(--space-6);
    border-left: 1px solid var(--color-border);
  }

  .decision-grid article > span,
  .positioning-callout > span {
    display: block;
    margin-bottom: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .decision-grid article > p,
  .decision-grid li,
  .paired-lists li,
  .positioning-callout p,
  .method-strip p {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.6;
  }

  .decision-grid article > p {
    margin: var(--space-3) 0 0;
  }

  .decision-grid li,
  .paired-lists li {
    position: relative;
    padding-left: var(--space-4);
  }

  .decision-grid li + li,
  .paired-lists li + li {
    margin-top: var(--space-3);
  }

  .decision-grid li::before,
  .paired-lists li::before {
    content: "";
    position: absolute;
    top: 0.7em;
    left: 0;
    width: var(--space-1);
    height: var(--space-1);
    border-radius: var(--radius-full);
    background: var(--color-text-muted);
  }

  .name-list li {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    padding-left: 0;
  }

  .name-list li::before {
    display: none;
  }

  .name-list small {
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    text-transform: capitalize;
  }

  .positioning-callout,
  .method-strip,
  .empty-note {
    margin: var(--space-6);
    padding: var(--space-5);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }

  .positioning-callout p,
  .method-strip p {
    margin: 0;
  }

  .positioning-callout p {
    color: var(--color-text-primary);
    font-size: var(--text-md);
  }

  .paired-lists {
    border-top: 1px solid var(--color-border);
  }

  .method-strip {
    border: 1px solid var(--color-border);
    background: transparent;
  }

  .method-strip strong {
    display: block;
    margin-bottom: var(--space-2);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
  }

  .empty-note {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    color: var(--color-text-muted);
  }

  .empty-note :global(svg) {
    width: var(--space-5);
    height: var(--space-5);
    flex: 0 0 auto;
  }

  .empty-note p {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.55;
  }

  .detail-entry {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-6);
    padding: var(--space-5) 0 0;
    border-top: 1px solid var(--color-border);
  }

  .detail-entry strong,
  .detail-entry p {
    display: block;
    margin: 0;
  }

  .detail-entry strong {
    color: var(--color-text-primary);
    font-size: var(--text-base);
  }

  .detail-entry p {
    margin-top: var(--space-1);
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  .detail-entry a {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    min-height: var(--space-10);
    padding: 0 var(--space-4);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
    white-space: nowrap;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default);
  }

  .detail-entry a:hover {
    border-color: var(--color-text-secondary);
    background: var(--color-bg-hover);
  }

  .detail-entry a:active {
    background: var(--color-bg-active);
  }

  .detail-entry a :global(svg) {
    width: var(--space-4);
    height: var(--space-4);
  }

  @media (max-width: 52rem) {
    .summary-heading,
    .detail-entry {
      align-items: stretch;
      flex-direction: column;
    }

    .summary-heading > span {
      align-self: flex-start;
    }

    .summary-facts,
    .summary-facts--four,
    .compact-list,
    .decision-grid,
    .paired-lists {
      grid-template-columns: 1fr;
    }

    .summary-facts div + div,
    .decision-grid article + article,
    .paired-lists > div + div {
      border-left: 0;
      border-top: 1px solid var(--color-border);
    }

    .decision-grid article,
    .paired-lists > div {
      padding: var(--space-5) 0;
    }

    .decision-grid article + article,
    .paired-lists > div + div {
      padding: var(--space-5) 0 0;
    }

    .finding-title {
      display: grid;
    }

    .finding-title span {
      white-space: normal;
    }

    .detail-entry a {
      width: 100%;
    }
  }
</style>
