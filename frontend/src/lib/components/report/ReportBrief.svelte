<script lang="ts">
  import { ArrowRight, CheckCircle2, CircleAlert, Database, Users } from "lucide-svelte";
  import type { Report } from "$lib/types/report";
  import { stripMarkdown } from "$lib/utils/format";
  import type { Snippet } from "svelte";

  interface Props {
    report: Report;
    evidenceHref: string;
    planHref: string;
    decisionSlot?: Snippet;
  }

  let { report, evidenceHref, planHref, decisionSlot }: Props = $props();

  const dashboard = $derived(report.executive_dashboard);
  const solution = $derived(dashboard?.recommended_solution_snapshot);
  const details = $derived(report.selected_solution_details);
  const verdict = $derived(dashboard?.go_no_go_verdict);
  const pain = $derived(
    dashboard?.core_pain_point?.title ??
      details?.pain_points_addressed?.[0] ??
      "The primary customer problem was not available.",
  );
  const buyer = $derived(
    report.audience_mapping?.primary_target_segment ??
      details?.target_personas?.[0] ??
      "The primary buyer was not identified.",
  );
  const productPromise = $derived(
    details?.short_description ??
      solution?.core_value_prop ??
      details?.value_proposition ??
      details?.description ??
      report.executive_summary,
  );
  const strategicEdge = $derived(
    details?.differentiation_factors?.[0] ??
      report.market_sizing?.recommended_entry_strategy ??
      report.competitive_analysis?.top_opportunities?.[0] ??
      "No defensible edge was identified.",
  );
  // Safe to read as risks: key_challenges is frictions-only as of the key_strengths split.
  // Reports generated before it carry a mixed list and will show a strength here — that is
  // fixed by regenerating, not by pattern-matching the strings back out.
  const primaryConcern = $derived(
    verdict?.primary_concern ??
      report.niche_difficulty_verdict?.key_challenges?.[0] ??
      "No primary concern was recorded.",
  );
  const additionalRisks = $derived(
    (report.niche_difficulty_verdict?.key_challenges ?? [])
      .filter((item) => item !== primaryConcern)
      .slice(0, 2),
  );
  const supportingSignals = $derived(
    (report.refinement_highlights?.top_strategic_insights ?? [])
      .filter((item) => item !== strategicEdge)
      .slice(0, 2),
  );
  const nextMove = $derived(
    report.next_steps?.[0] ??
      report.recommended_focus ??
      "Review the evidence behind the recommendation before deciding what to build.",
  );
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
    return report.evidence_appendix
      ? report.evidence_appendix.top_reddit_threads.length
      : null;
  });
  const evidenceLimited = $derived(
    sourceCount === 0 ||
      report.data_quality_summary?.overall_data_quality?.toUpperCase() === "LOW" ||
      !!report.niche_difficulty_verdict?.low_confidence,
  );
  function asSentence(value: string): string {
    const text = stripMarkdown(value).trim();
    return /[.!?]$/.test(text) ? text : `${text}.`;
  }
  const conclusion = $derived.by(() => {
    const edge = stripMarkdown(strategicEdge);
    const concern = stripMarkdown(primaryConcern);
    const hasEdge = edge && edge !== "No defensible edge was identified.";
    const hasConcern = concern && concern !== "No primary concern was recorded.";

    if (verdict?.verdict === "Go") {
      if (evidenceLimited) {
        const strongestCase = hasEdge ? ` Strongest supported case: ${asSentence(edge)}` : "";
        const nextCheck = hasConcern ? ` Before committing, verify: ${asSentence(concern)}` : "";
        return `This direction is promising, but the evidence is too limited for an unqualified recommendation.${strongestCase}${nextCheck}`;
      }
      if (hasEdge && hasConcern) {
        return `The research supports advancing this direction. Strongest case: ${asSentence(edge)} Before committing, verify: ${asSentence(concern)}`;
      }
      if (hasEdge) {
        return `The research supports advancing this direction. Strongest case: ${asSentence(edge)}`;
      }
      return "The research supports advancing this direction.";
    }
    if (verdict?.verdict === "Conditional") {
      return hasConcern
        ? `The opportunity is promising, but this condition remains unresolved: ${asSentence(concern)}`
        : "The opportunity is promising, but a decision-changing risk still needs validation.";
    }
    if (verdict?.verdict === "No-Go") {
      return hasConcern
        ? `The current evidence does not support moving forward. Main blocker: ${asSentence(concern)}`
        : "The current evidence does not support moving forward with this direction.";
    }
    return "The report did not produce a clear decision. Review the evidence and unresolved risks before acting.";
  });
  const painCount = $derived(
    report.pain_point_analytics?.total_pain_points ??
      report.detailed_pain_points?.length ??
      null,
  );
  const competitorCount = $derived(
    report.competitive_analytics?.competitor_count ??
      report.competitor_profiles?.length ??
      null,
  );
  const quality = $derived(
    report.data_quality_summary?.overall_data_quality
      ? `${report.data_quality_summary.overall_data_quality.toLowerCase()} coverage`
      : dashboard?.research_depth_label ?? "Coverage not graded",
  );
  const verdictClass = $derived(
    verdict?.verdict === "Go"
      ? evidenceLimited
        ? "caution"
        : "positive"
      : verdict?.verdict === "No-Go"
        ? "negative"
        : verdict?.verdict === "Conditional"
          ? "caution"
          : "unknown",
  );
  const verdictLabel = $derived(
    verdict?.verdict === "Go" && evidenceLimited
      ? "Go · evidence-limited"
      : (verdict?.verdict ?? "Not available"),
  );
  const qualityCaveatCount = $derived(
    report.data_quality_summary?.quality_caveats?.length ?? 0,
  );
  const recommendationChanged = $derived(
    !!report.original_selection_reasoning &&
      stripMarkdown(report.original_selection_reasoning) !== stripMarkdown(report.selection_rationale),
  );
  const reviewEvidenceFirst = $derived(
    verdict?.verdict !== "Go" || evidenceLimited,
  );
</script>

<div class="brief">
  <section class="conclusion" aria-labelledby="research-conclusion-title">
    <div class="conclusion-status {verdictClass}">
      {#if verdictClass === "positive"}
        <CheckCircle2 aria-hidden="true" />
      {:else}
        <CircleAlert aria-hidden="true" />
      {/if}
      <div>
        <span>Research conclusion</span>
        <strong>{verdictLabel}</strong>
      </div>
    </div>
    <div class="conclusion-copy">
      <p class="eyebrow">The recommendation</p>
      <h2 id="research-conclusion-title">
        {solution?.tagline ?? details?.headline ?? report.selected_solution_name}
      </h2>
      <p>{conclusion}</p>
      <div class="conclusion-qualifiers" aria-label="Conclusion qualifiers">
        {#if verdict?.risk_level}
          <span>{verdict.risk_level} research risk</span>
        {/if}
        <span>{quality}</span>
        {#if qualityCaveatCount}
          <span>
            {qualityCaveatCount}
            {qualityCaveatCount === 1 ? "documented caveat" : "documented caveats"}
          </span>
        {/if}
      </div>
      {#if recommendationChanged}
        <details class="decision-trace">
          <summary>How the recommendation changed</summary>
          <p>{stripMarkdown(report.original_selection_reasoning)}</p>
        </details>
      {/if}
    </div>
  </section>

  <section class="opportunity" aria-labelledby="opportunity-title">
    <div class="section-heading">
      <p class="eyebrow">The opportunity</p>
      <h2 id="opportunity-title">What this idea is built around</h2>
    </div>
    <div class="opportunity-grid">
      <article>
        <Users aria-hidden="true" />
        <span>Primary buyer</span>
        <strong>{buyer}</strong>
      </article>
      <article>
        <CircleAlert aria-hidden="true" />
        <span>Problem to solve</span>
        <strong>{pain}</strong>
      </article>
      <article class="promise">
        <Database aria-hidden="true" />
        <span>Product promise</span>
        <strong>{productPromise}</strong>
      </article>
    </div>
  </section>

  <div class="brief-columns">
    <section class="evidence-summary" aria-labelledby="support-title">
      <p class="eyebrow">Why it could work</p>
      <h2 id="support-title">The strongest case</h2>
      <p class="lead">{strategicEdge}</p>
      {#if supportingSignals.length}
        <ul class="supporting-signals" aria-label="Additional supporting signals">
          {#each supportingSignals as signal}
            <li>{signal}</li>
          {/each}
        </ul>
      {/if}
      <dl class="coverage">
        <div>
          <dt>Research quality</dt>
          <dd>{quality}</dd>
        </div>
        <div>
          <dt>Social evidence items</dt>
          <dd>{sourceCount ?? "Not available"}</dd>
        </div>
        <div>
          <dt>Problems examined</dt>
          <dd>{painCount ?? "Not available"}</dd>
        </div>
        <div>
          <dt>Competitors reviewed</dt>
          <dd>{competitorCount ?? "Not available"}</dd>
        </div>
      </dl>
      <a class="text-action" href={evidenceHref}>
        Inspect the supporting evidence
        <ArrowRight aria-hidden="true" />
      </a>
    </section>

    <section class="risk-summary" aria-labelledby="risk-title">
      <p class="eyebrow">What could break it</p>
      <h2 id="risk-title">Decision-changing risks</h2>
      <ol>
        <li>
          <span>Primary concern</span>
          <p>{primaryConcern}</p>
        </li>
        {#each additionalRisks as risk, index}
          <li>
            <span>Risk {index + 2}</span>
            <p>{risk}</p>
          </li>
        {/each}
      </ol>
      {#if report.data_quality_summary?.quality_caveats?.length}
        <p class="caveat-count">
          {report.data_quality_summary.quality_caveats.length}
          {report.data_quality_summary.quality_caveats.length === 1
            ? "coverage caveat"
            : "coverage caveats"}
          are documented with the sources.
        </p>
      {/if}
    </section>
  </div>

  <section class="next-move" aria-labelledby="next-move-title">
    <div>
      <p class="eyebrow">Recommended next move</p>
      <h2 id="next-move-title">Turn the research into a small, testable plan</h2>
      <p>{nextMove}</p>
    </div>
    <div class="next-actions">
      {#if reviewEvidenceFirst}
        <a class="primary-action" href={evidenceHref}>
          Review the biggest risk
          <ArrowRight aria-hidden="true" />
        </a>
        <a class="secondary-action" href={planHref}>Open the action plan</a>
      {:else}
        <a class="primary-action" href={planHref}>
          Open the action plan
          <ArrowRight aria-hidden="true" />
        </a>
        <a class="secondary-action" href={evidenceHref}>Inspect the evidence</a>
      {/if}
    </div>
  </section>

  {#if decisionSlot}
    <div class="decision-entry">
      {@render decisionSlot()}
    </div>
  {/if}

  <p class="method-note">
    This is an AI-assisted synthesis of the saved research. Verify consequential claims in
    Evidence before spending money or committing to a build.
  </p>
</div>

<style>
  .brief {
    display: grid;
    gap: var(--space-10);
  }

  .eyebrow {
    margin: 0 0 var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .conclusion {
    display: grid;
    grid-template-columns: minmax(10rem, 0.34fr) minmax(0, 1fr);
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    background: var(--color-bg-elevated);
  }

  .conclusion-status {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-8);
    border-right: 1px solid var(--color-border);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
  }

  .conclusion-status :global(svg) {
    width: var(--space-6);
    height: var(--space-6);
    flex: 0 0 auto;
  }

  .conclusion-status span,
  .conclusion-status strong {
    display: block;
  }

  .conclusion-status span {
    margin-bottom: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .conclusion-status strong {
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 700;
    line-height: 1.1;
  }

  .conclusion-status.positive {
    color: var(--color-success-text);
    background: var(--color-success-subtle);
  }

  .conclusion-status.caution {
    color: var(--color-warning-text);
    background: var(--color-warning-subtle);
  }

  .conclusion-status.negative {
    color: var(--color-error-text);
    background: var(--color-error-subtle);
  }

  .conclusion-copy {
    padding: var(--space-8);
  }

  .conclusion-copy h2,
  .section-heading h2,
  .brief-columns h2,
  .next-move h2 {
    margin: 0;
    font-family: var(--font-display);
    color: var(--color-text-primary);
    text-wrap: balance;
  }

  .conclusion-copy h2 {
    max-width: 28ch;
    font-size: var(--text-3xl);
    font-weight: 700;
    line-height: 1.14;
  }

  .conclusion-copy > p:not(.eyebrow) {
    max-width: 72ch;
    margin: var(--space-4) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-md);
    line-height: 1.65;
  }

  .conclusion-qualifiers {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-4);
    margin-top: var(--space-4);
  }

  .conclusion-qualifiers span {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  .conclusion-qualifiers span + span::before {
    content: "·";
    margin-right: var(--space-4);
    color: var(--color-border-emphasis);
  }

  .decision-trace {
    margin-top: var(--space-5);
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .decision-trace summary {
    min-height: var(--space-8);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }

  .decision-trace p {
    max-width: 72ch;
    margin: var(--space-3) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.6;
  }

  .opportunity {
    display: grid;
    gap: var(--space-5);
  }

  .section-heading h2,
  .brief-columns h2,
  .next-move h2 {
    font-size: var(--text-2xl);
    font-weight: 700;
    line-height: 1.2;
  }

  .opportunity-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    border-block: 1px solid var(--color-border);
  }

  .opportunity-grid article {
    display: grid;
    align-content: start;
    gap: var(--space-3);
    min-width: 0;
    padding: var(--space-6);
  }

  .opportunity-grid article + article {
    border-left: 1px solid var(--color-border);
  }

  .opportunity-grid .promise {
    grid-column: 1 / -1;
    grid-template-columns: auto minmax(0, 1fr);
    column-gap: var(--space-4);
    border-top: 1px solid var(--color-border);
    border-left: 0;
  }

  .opportunity-grid .promise :global(svg) {
    grid-row: 1 / span 2;
  }

  .opportunity-grid :global(svg) {
    width: var(--space-5);
    height: var(--space-5);
    color: var(--color-text-muted);
  }

  .opportunity-grid span {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .opportunity-grid strong {
    font-size: var(--text-base);
    font-weight: 600;
    line-height: 1.55;
    color: var(--color-text-primary);
  }

  .brief-columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-6);
  }

  .evidence-summary,
  .risk-summary {
    padding: var(--space-6);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .lead {
    margin: var(--space-4) 0 var(--space-6);
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .supporting-signals {
    display: grid;
    gap: var(--space-3);
    margin: calc(-1 * var(--space-2)) 0 var(--space-6);
    padding: 0;
    list-style: none;
  }

  .supporting-signals li {
    position: relative;
    padding-left: var(--space-5);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.55;
  }

  .supporting-signals li::before {
    content: "";
    position: absolute;
    top: 0.65em;
    left: 0;
    width: var(--space-1);
    height: var(--space-1);
    border-radius: var(--radius-full);
    background: var(--color-text-muted);
  }

  .coverage {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-4);
    margin: 0 0 var(--space-6);
  }

  .coverage div {
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .coverage dt {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  .coverage dd {
    margin: var(--space-1) 0 0;
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
    text-transform: capitalize;
  }

  .text-action,
  .primary-action,
  .secondary-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    min-height: var(--space-10);
    border-radius: var(--radius-md);
    font-size: var(--text-base);
    font-weight: 700;
    text-decoration: none;
    transition:
      color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default);
  }

  .text-action {
    justify-content: flex-start;
    min-height: var(--space-8);
    color: var(--color-accent-dark);
  }

  .text-action:hover {
    color: var(--color-text-primary);
  }

  .text-action :global(svg),
  .primary-action :global(svg) {
    width: var(--space-4);
    height: var(--space-4);
  }

  .risk-summary ol {
    display: grid;
    gap: var(--space-4);
    margin: var(--space-5) 0 0;
    padding: 0;
    list-style: none;
  }

  .risk-summary li {
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .risk-summary li span {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .risk-summary li p,
  .caveat-count {
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.55;
  }

  .caveat-count {
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .next-move {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: var(--space-8);
    padding: var(--space-8);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .next-move h2 {
    color: inherit;
  }

  .next-move p:not(.eyebrow) {
    max-width: 68ch;
    margin: var(--space-3) 0 0;
    color: inherit;
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .next-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: var(--space-3);
  }

  .primary-action {
    padding: 0 var(--space-5);
    border: 1px solid var(--color-accent-hover);
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
  }

  .primary-action:hover {
    border-color: var(--color-accent-dark);
    background: var(--color-accent-dark);
  }

  .secondary-action {
    padding: 0 var(--space-4);
    border: 1px solid var(--color-input-border);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }

  .secondary-action:hover {
    border-color: var(--color-input-border-hover);
    background: var(--color-bg-hover);
  }

  .primary-action:active,
  .secondary-action:active,
  .text-action:active {
    opacity: 0.82;
  }

  .method-note {
    max-width: 76ch;
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.55;
  }

  .decision-entry :global(.decision-launcher) {
    margin: 0;
  }

  @media (max-width: 56rem) {
    .conclusion,
    .brief-columns,
    .next-move {
      grid-template-columns: 1fr;
    }

    .conclusion-status {
      border-right: 0;
      border-bottom: 1px solid var(--color-border);
    }

    .opportunity-grid {
      grid-template-columns: 1fr;
    }

    .opportunity-grid article + article {
      border-top: 1px solid var(--color-border);
      border-left: 0;
    }

    .next-actions {
      justify-content: flex-start;
    }
  }

  @media (max-width: 34rem) {
    .conclusion-status,
    .conclusion-copy,
    .evidence-summary,
    .risk-summary,
    .next-move {
      padding: var(--space-5);
    }

    .coverage {
      grid-template-columns: 1fr;
    }

    .conclusion-qualifiers {
      display: grid;
      gap: var(--space-2);
    }

    .conclusion-qualifiers span + span::before {
      content: none;
    }

    .next-actions,
    .primary-action,
    .secondary-action {
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .text-action,
    .primary-action,
    .secondary-action {
      transition: none;
    }
  }
</style>
