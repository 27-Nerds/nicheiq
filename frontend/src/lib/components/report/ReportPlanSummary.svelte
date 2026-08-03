<script module lang="ts">
  /** Lowercase a leading plain-capitalised word so it reads mid-sentence, while leaving
   *  acronyms and camel-cased product names ("SOC2", "QuickBooks") untouched. */
  function decapitalize(text: string): string {
    const [firstWord] = text.split(/\s/, 1);
    return /^[A-Z][a-z]*$/.test(firstWord)
      ? text.charAt(0).toLowerCase() + text.slice(1)
      : text;
  }

  /** The backend's ICP copy normally already opens with its own trigger clause
   *  ("Triggered when a settlement dispute arises…"), so a "Their buying trigger is"
   *  lead-in produced "…is Triggered when…". Only add the lead-in when the value needs it. */
  export function formatBuyingTrigger(rawTrigger: string | null | undefined): string {
    const trigger = (rawTrigger ?? "").trim();
    if (!trigger) return "";
    const opensAsTriggerClause =
      /^(triggered|triggers|trigger|when|whenever|once|after|during|occurs|happens)\b/i.test(
        trigger,
      );
    const sentence = opensAsTriggerClause
      ? trigger.charAt(0).toUpperCase() + trigger.slice(1)
      : `Their buying trigger is ${decapitalize(trigger)}`;
    return /[.!?]$/.test(sentence) ? sentence : `${sentence}.`;
  }

  /** The plan view is often the reader's first encounter with the persona, so a bare
   *  name ("Multi-Room Operator Maya") has no referent. Introduce it with the ICP descriptor. */
  export function formatPersonaIntro(
    personaName: string | null | undefined,
    demographics?: string | null,
  ): string {
    const name = (personaName ?? "").trim();
    const descriptor = (demographics ?? "").trim();
    if (!name) return "";
    const sentence = descriptor
      ? `Start with ${name} — ${decapitalize(descriptor)}`
      : `Start with ${name}`;
    return /[.!?]$/.test(sentence) ? sentence : `${sentence}.`;
  }
</script>

<script lang="ts">
  import { ArrowRight, CircleAlert } from "lucide-svelte";
  import type { Report } from "$lib/types/report";
  import { normalizeSeoScalabilityNarrative, renderMarkdown } from "$lib/utils/format";
  import { humanizeTag } from "$lib/utils/ideaTagLabels";

  interface Props {
    report: Report;
    topic: "first-30-days" | "product" | "launch";
    fullDetailHref?: string;
    /** Named when the appendix link lands on a different topic tab than this one. */
    fullDetailDestination?: string;
    /** The identity deck already on screen above this view — never repeated here. */
    deckText?: string;
  }

  let { report, topic, fullDetailHref, fullDetailDestination, deckText }: Props = $props();

  const details = $derived(report.selected_solution_details);
  const snapshot = $derived(report.executive_dashboard?.recommended_solution_snapshot);
  // The heading here used to restate the page H1 and the paragraph the identity
  // deck, so the same promise printed three times across the report. Keep the deck
  // and show only a candidate that says something the reader has not already read.
  const productPromise = $derived(
    [
      snapshot?.core_value_prop,
      details?.value_proposition,
      details?.short_description,
      details?.description,
      report.executive_summary,
    ].find((candidate) => {
      const text = candidate?.trim();
      return !!text && text !== deckText?.trim();
    }) ?? null,
  );
  const gtm = $derived(report.go_to_market_blueprint);
  const pricing = $derived(report.pricing_strategy);
  const seo = $derived(report.seo_strategy_report);
  const seoMetrics = $derived(report.seo_analytics);
  const hasDatedPlaybook = $derived(Boolean(gtm?.first_30_days_playbook));
  const STEP_LIMIT = 6;
  // The playbook prefixes each action with its week theme ("Week 1 Foundation: ...").
  // That context is carried by the section header here, so strip it — otherwise every
  // visible row repeats the same prefix. GTMPlaybook keeps it (weeks render separately).
  const stripWeekPrefix = (action: string) =>
    action.replace(/^\s*week\s+\d+\b[^:]{0,40}:\s*/i, "");
  const firstMonthSteps = $derived.by(() => {
    const playbook = gtm?.first_30_days_playbook;
    if (playbook) {
      const weeks = [
        playbook.week_1_actions,
        playbook.week_2_actions,
        playbook.week_3_actions,
        playbook.week_4_actions,
      ].map((week) => week ?? []);
      // Round-robin across weeks so the summary shows the whole 30-day arc. A flat
      // concat + slice(0, 6) never got past week 1, which can hold up to 8 actions.
      const picked: string[][] = weeks.map(() => []);
      let taken = 0;
      for (let depth = 0; taken < STEP_LIMIT; depth += 1) {
        let progressed = false;
        for (let w = 0; w < weeks.length && taken < STEP_LIMIT; w += 1) {
          const action = weeks[w][depth];
          if (action === undefined) continue;
          picked[w].push(action);
          taken += 1;
          progressed = true;
        }
        if (!progressed) break;
      }
      // Flatten back in week order so the sequence still reads chronologically.
      return picked.flat().map(stripWeekPrefix);
    }
    return report.next_steps?.slice(0, STEP_LIMIT) ?? [];
  });
  const firstMonthStepCount = $derived.by(() => {
    const playbook = gtm?.first_30_days_playbook;
    if (!playbook) return report.next_steps?.length ?? 0;
    return (
      (playbook.week_1_actions?.length ?? 0) +
      (playbook.week_2_actions?.length ?? 0) +
      (playbook.week_3_actions?.length ?? 0) +
      (playbook.week_4_actions?.length ?? 0)
    );
  });
  const remainingFirstMonthSteps = $derived(
    Math.max(0, firstMonthStepCount - firstMonthSteps.length),
  );
  const budget = $derived.by(() => {
    if (!gtm?.budget_estimate) return "Budget unavailable";
    if (typeof gtm.budget_estimate === "string") return gtm.budget_estimate;
    return `$${gtm.budget_estimate.monthly_budget_min.toLocaleString()}–$${gtm.budget_estimate.monthly_budget_max.toLocaleString()} / month`;
  });
  const channels = $derived(gtm?.recommended_channels?.slice(0, 3) ?? []);
  const ideaGrowthChannels = $derived(
    (details?.tags?.growth_channels ?? []).slice(0, 3).map(humanizeTag).filter(Boolean),
  );
  const acquisitionSummary = $derived(
    normalizeSeoScalabilityNarrative(
      report.acquisition_strategy_summary ?? "",
      details?.seo_scalability_score,
    ),
  );
  const topKeywords = $derived(
    [...(seo?.tier_0_keywords ?? []), ...(seo?.tier_1_keywords ?? [])].slice(0, 6),
  );
  // The aggregate keyword volume is category reach, not validated idea demand — lead with
  // the idea-intent subset when the backend produced one (null on legacy reports).
  const ideaIntentVolume = $derived(seo?.idea_intent_monthly_volume ?? null);
  const categoryReachVolume = $derived(
    seoMetrics?.total_search_volume || seo?.total_monthly_volume || null,
  );
  const icp = $derived(gtm?.ideal_customer_profile);
  // `solution_implementation_overview` is generated as markdown ("## Implementation
  // Overview **Phase 1: …**"). The full-detail appendix runs it through renderMarkdown;
  // this summary printed it as a text node, so the syntax reached the reader verbatim.
  const buildApproach = $derived(
    details?.technical_approach ?? report.solution_implementation_overview ?? null,
  );
  const productFeatures = $derived(details?.core_features?.slice(0, 6) ?? []);
  const dataSources = $derived(
    details?.data_sources?.slice(0, 6) ??
      report.data_source_research_full?.primary_data_sources
        ?.slice(0, 6)
        .map((source) => source.provider) ??
      [],
  );
</script>

{#if topic === "first-30-days"}
  <section class="plan-section" aria-labelledby="first-month-title">
    <header class="plan-heading">
      <div>
        <p>Recommended sequence</p>
        <h3 id="first-month-title">What to do first</h3>
      </div>
      <span class:caution={!hasDatedPlaybook}>
        {hasDatedPlaybook ? "First 30 days" : "Sequence only"}
      </span>
    </header>

    {#if firstMonthSteps.length}
      <ol class="step-list">
        {#each firstMonthSteps as step, index}
          <li>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <p>{step}</p>
          </li>
        {/each}
      </ol>
    {:else}
      <div class="empty-note">
        <CircleAlert aria-hidden="true" />
        <p>A recommended action sequence was not generated for this report.</p>
      </div>
    {/if}

    {#if gtm?.first_30_days_playbook?.success_metrics?.length}
      <div class="outcome-strip">
        <strong>Know whether it worked</strong>
        <ul>
          {#each gtm.first_30_days_playbook.success_metrics.slice(0, 4) as metric}
            <li>{metric}</li>
          {/each}
        </ul>
      </div>
    {/if}
  </section>
{:else if topic === "product"}
  <section class="plan-section" aria-labelledby="product-plan-title">
    <header class="plan-heading">
      <div>
        <p>Product decision</p>
        <h3 id="product-plan-title">What the first useful version needs to prove</h3>
      </div>
      <span class:caution={!details?.estimated_development_time}>
        {details?.estimated_development_time ?? "Timing unavailable"}
      </span>
    </header>

    {#if productPromise}
      <div class="product-promise">
        <span>Product promise</span>
        <p>{productPromise}</p>
      </div>
    {/if}

    <div class="plan-grid">
      <article>
        <span>First-release scope</span>
        {#if productFeatures.length}
          <ol>
            {#each productFeatures as feature}
              <li>{feature}</li>
            {/each}
          </ol>
        {:else}
          <p>No structured feature scope was retained.</p>
        {/if}
      </article>
      <article>
        <span>Build approach</span>
        {#if buildApproach}
          <div class="build-approach">{@html renderMarkdown(buildApproach)}</div>
        {:else}
          <p>A technical approach was not retained.</p>
        {/if}
      </article>
    </div>

    {#if dataSources.length}
      <div class="dependency-strip">
        <strong>Data or integration dependencies</strong>
        <ul>
          {#each dataSources as source}
            <li>{source}</li>
          {/each}
        </ul>
      </div>
    {/if}
  </section>
{:else}
  <section class="plan-section" aria-labelledby="launch-plan-title">
    <header class="plan-heading">
      <div>
        <p>Launch decision</p>
        <h3 id="launch-plan-title">How to reach the first credible customers</h3>
      </div>
      <span class:caution={!gtm?.budget_estimate}>Marketing budget · {budget}</span>
    </header>

    <div class="positioning">
      <span>Message to lead with</span>
      <h4>{gtm?.core_marketing_message ?? snapshot?.tagline ?? report.selected_solution_name}</h4>
      {#if icp}
        <p>{formatPersonaIntro(icp.persona_name, icp.demographics)}</p>
        {#if icp.buying_triggers?.trim()}
          <p>{formatBuyingTrigger(icp.buying_triggers)}</p>
        {/if}
      {/if}
    </div>

    <div class="plan-grid">
      <article>
        <span>Priority channels</span>
        {#if channels.length}
          <ol class="channel-list">
            {#each channels as channel}
              <li>
                <strong>{channel.channel_name}</strong>
                <small>{channel.priority} priority</small>
                <p>{channel.rationale}</p>
              </li>
            {/each}
          </ol>
        {:else}
          {#if ideaGrowthChannels.length}
            <ul class="keyword-list" aria-label="Idea-stage channel hypotheses">
              {#each ideaGrowthChannels as channel}
                <li>{channel}</li>
              {/each}
            </ul>
            <p class="hypothesis-note">
              These are idea-stage channel hypotheses. Deep Research did not generate a channel
              plan, so test them before committing budget.
            </p>
          {:else}
            <p>No channel plan was retained.</p>
          {/if}
        {/if}
      </article>
      <article>
        <span>Organic acquisition</span>
        {#if topKeywords.length}
          <p class="metric-copy">
            {seoMetrics?.total_keywords ?? seo?.total_keywords_analyzed ?? topKeywords.length}
            keywords examined
            {#if ideaIntentVolume != null}
              · {ideaIntentVolume.toLocaleString()} monthly idea-intent searches
              {#if categoryReachVolume != null}
                <span class="reach-qualifier">
                  ({categoryReachVolume.toLocaleString()} category reach across all keywords)
                </span>
              {/if}
            {:else if categoryReachVolume != null}
              · {categoryReachVolume.toLocaleString()} monthly searches
              <span class="reach-qualifier">
                (category reach, not validated idea demand)
              </span>
            {/if}
          </p>
          <ul class="keyword-list">
            {#each topKeywords as keyword}
              <li>{keyword.keyword}</li>
            {/each}
          </ul>
        {:else}
          <p>
            {acquisitionSummary ||
              "A structured organic-acquisition plan was not retained."}
          </p>
        {/if}
      </article>
    </div>

    {#if pricing}
      <div class="dependency-strip">
        <strong>Offer to test</strong>
        <p>
          {pricing.pricing_model}
          {#if pricing.recommended_starter_price}
            · {pricing.recommended_starter_price} starter
          {:else if pricing.recommended_pro_price}
            · {pricing.recommended_pro_price}
          {/if}
        </p>
      </div>
    {/if}
  </section>
{/if}

{#if fullDetailHref}
  <div class="detail-entry">
    <div>
      {#if topic === "first-30-days"}
        <strong>Need the complete 30-day plan?</strong>
        <p>
          {remainingFirstMonthSteps
            ? `${remainingFirstMonthSteps} additional ${remainingFirstMonthSteps === 1 ? "action is" : "actions are"} grouped by week in the full playbook.`
            : "See the actions grouped by week with their success metrics."}
          {#if fullDetailDestination}
            It is filed under {fullDetailDestination}, so this link changes tab.
          {/if}
        </p>
      {:else}
        <strong>Need the implementation appendix?</strong>
        <p>Open the detailed generated plan for this topic when you are ready to execute it.</p>
      {/if}
    </div>
    <a href={fullDetailHref}>
      {topic === "first-30-days" ? "Open full 30-day playbook" : "Open implementation appendix"}
      {#if fullDetailDestination}
        <span class="detail-destination">in {fullDetailDestination}</span>
      {/if}
      <ArrowRight aria-hidden="true" />
    </a>
  </div>
{/if}

<style>
  .plan-section {
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    background: var(--color-bg-elevated);
  }

  .plan-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-6);
    padding: var(--space-6);
    border-bottom: 1px solid var(--color-border);
  }

  .plan-heading p,
  .plan-heading h3 {
    margin: 0;
  }

  .plan-heading p {
    margin-bottom: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-secondary);
  }

  .plan-heading h3 {
    max-width: 32ch;
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-text-primary);
    text-wrap: balance;
  }

  .plan-heading > span {
    flex: 0 0 auto;
    max-width: 22rem;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-full);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
  }

  .plan-heading > span.caution {
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
  }

  .step-list {
    display: grid;
    margin: 0;
    padding: 0 var(--space-6);
    list-style: none;
  }

  .step-list li {
    display: grid;
    grid-template-columns: var(--space-8) minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-5) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .step-list li:last-child {
    border-bottom: 0;
  }

  .step-list span {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    color: var(--color-text-muted);
  }

  .step-list p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .outcome-strip,
  .dependency-strip {
    margin: 0 var(--space-6) var(--space-6);
    padding: var(--space-5);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }

  .outcome-strip strong,
  .dependency-strip strong {
    display: block;
    margin-bottom: var(--space-3);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
  }

  .outcome-strip ul,
  .dependency-strip ul,
  .keyword-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .outcome-strip li,
  .dependency-strip li,
  .keyword-list li {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
  }

  .dependency-strip p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
  }

  .product-promise,
  .positioning {
    padding: var(--space-6);
    background: var(--color-bg-surface);
  }

  .product-promise > span,
  .positioning > span,
  .plan-grid article > span {
    display: block;
    margin-bottom: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-secondary);
  }

  .positioning h4 {
    max-width: 42ch;
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    line-height: 1.3;
    color: var(--color-text-primary);
  }

  /* The promise paragraph now follows its label directly — the duplicate heading
     that used to sit between them is gone. */
  .product-promise > span + p {
    margin-top: 0;
  }

  .product-promise p,
  .positioning p {
    max-width: 72ch;
    margin: var(--space-3) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.65;
  }

  .plan-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: var(--space-6);
  }

  .plan-grid article {
    min-width: 0;
    padding-right: var(--space-6);
  }

  .plan-grid article + article {
    padding-right: 0;
    padding-left: var(--space-6);
    border-left: 1px solid var(--color-border);
  }

  .plan-grid ol {
    display: grid;
    gap: var(--space-3);
    margin: var(--space-4) 0 0;
    padding: 0;
    list-style: none;
  }

  .plan-grid li,
  .plan-grid article > p {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.6;
  }

  .plan-grid li {
    position: relative;
    padding-left: var(--space-5);
  }

  .plan-grid li::before {
    content: "";
    position: absolute;
    top: 0.7em;
    left: 0;
    width: var(--space-1);
    height: var(--space-1);
    border-radius: var(--radius-full);
    background: var(--color-text-muted);
  }

  .plan-grid article > p {
    margin: var(--space-4) 0 0;
  }

  .build-approach {
    margin-top: var(--space-4);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.6;
  }

  .build-approach :global(h1),
  .build-approach :global(h2),
  .build-approach :global(h3),
  .build-approach :global(h4) {
    margin: var(--space-4) 0 var(--space-2);
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .build-approach :global(p),
  .build-approach :global(ul),
  .build-approach :global(ol) {
    margin: 0 0 var(--space-3);
  }

  .build-approach :global(ul),
  .build-approach :global(ol) {
    padding-left: var(--space-5);
  }

  .build-approach :global(strong) {
    color: var(--color-text-primary);
  }

  .build-approach :global(> :first-child) {
    margin-top: 0;
  }

  .build-approach :global(> :last-child) {
    margin-bottom: 0;
  }

  .channel-list li {
    padding-left: 0;
  }

  .channel-list li::before {
    display: none;
  }

  .channel-list strong,
  .channel-list small {
    display: block;
  }

  .channel-list strong {
    color: var(--color-text-primary);
    font-size: var(--text-base);
  }

  .channel-list small {
    margin-top: var(--space-1);
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    text-transform: capitalize;
  }

  .channel-list p {
    margin: var(--space-2) 0 0;
  }

  .metric-copy {
    color: var(--color-text-primary) !important;
    font-weight: 600;
  }

  .reach-qualifier {
    color: var(--color-text-muted);
    font-weight: 400;
  }

  .keyword-list {
    margin-top: var(--space-4);
  }

  .plan-grid .hypothesis-note {
    margin-top: var(--space-3);
    color: var(--color-text-muted);
    font-size: var(--text-xs);
  }

  .keyword-list li {
    padding-left: var(--space-3);
  }

  .keyword-list li::before {
    display: none;
  }

  .empty-note {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    margin: var(--space-6);
    padding: var(--space-5);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
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

  /* Names the tab this link lands on, so the underline moving is expected. */
  .detail-destination {
    font-weight: 500;
    color: var(--color-text-muted);
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
    .plan-heading,
    .detail-entry {
      align-items: stretch;
      flex-direction: column;
    }

    .plan-heading > span {
      align-self: flex-start;
    }

    .plan-grid {
      grid-template-columns: 1fr;
    }

    .plan-grid article {
      padding: var(--space-5) 0;
    }

    .plan-grid article + article {
      padding: var(--space-5) 0 0;
      border-top: 1px solid var(--color-border);
      border-left: 0;
    }

    .detail-entry a {
      width: 100%;
    }
  }
</style>
