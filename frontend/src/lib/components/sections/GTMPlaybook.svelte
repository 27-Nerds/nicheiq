<script lang="ts">
  import {
    User,
    MessageSquare,
    Calendar,
    Target,
    Zap,
    ListChecks,
    CheckCircle,
    ArrowRight,
    DollarSign,
    Users,
    Megaphone,
    FileText,
    ChevronRight,
    Clock,
    TrendingUp,
    Play,
    BarChart3,
    PieChart,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type { GoToMarketBlueprint, BudgetEstimate } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";

  interface Props {
    gtmData: GoToMarketBlueprint;
    nextSteps?: string | string[];
  }

  let { gtmData, nextSteps }: Props = $props();

  // Type guard for BudgetEstimate object
  const isBudgetObject = (
    budget: string | BudgetEstimate | null,
  ): budget is BudgetEstimate => {
    return (
      budget !== null &&
      typeof budget === "object" &&
      "monthly_budget_min" in budget
    );
  };

  // Get budget display string
  const budgetDisplayString = $derived.by(() => {
    if (!gtmData.budget_estimate) return null;
    if (isBudgetObject(gtmData.budget_estimate)) {
      return `$${gtmData.budget_estimate.monthly_budget_min.toLocaleString()}-${gtmData.budget_estimate.monthly_budget_max.toLocaleString()}/month`;
    }
    return gtmData.budget_estimate;
  });

  // Get budget object for detailed display
  const budgetDetails = $derived.by(() => {
    if (gtmData.budget_estimate && isBudgetObject(gtmData.budget_estimate)) {
      return gtmData.budget_estimate;
    }
    return null;
  });

  const icp = $derived(gtmData.ideal_customer_profile);
  const playbook = $derived(gtmData.first_30_days_playbook);

  // Parse next steps - could be string or array
  const steps = $derived.by(() => {
    if (!nextSteps) return [];
    if (Array.isArray(nextSteps)) {
      return nextSteps;
    }
    if (typeof nextSteps === "string") {
      // Check if it's a numbered list (1. item, 2. item, etc.)
      const numberedListPattern = /^\d+\.\s/m;
      if (numberedListPattern.test(nextSteps)) {
        return nextSteps
          .split(/\n/)
          .filter((line) => line.trim() && /^\d+\./.test(line.trim()))
          .map((line) => line.replace(/^\d+\.\s*/, "").trim());
      }
      // Check if it's a bullet list
      const bulletListPattern = /^[-•*]\s/m;
      if (bulletListPattern.test(nextSteps)) {
        return nextSteps
          .split(/\n/)
          .filter((line) => line.trim() && /^[-•*]/.test(line.trim()))
          .map((line) => line.replace(/^[-•*]\s*/, "").trim());
      }
      // Just return as single item if no list format detected
      return [nextSteps];
    }
    return [];
  });

  // Channel priority color
  const getChannelColor = (priority: string) => {
    if (priority === "High") return "var(--color-success)";
    if (priority === "Medium") return "var(--color-warning)";
    return "var(--color-text-muted)";
  };

  // Calculate hero metrics
  const channelCount = $derived(gtmData.recommended_channels?.length || 0);
  const highPriorityChannels = $derived(
    gtmData.recommended_channels?.filter((c) => c.priority === "High").length ||
      0,
  );
  const contentAnglesCount = $derived(
    gtmData.example_content_angles?.length || 0,
  );
  const totalActions = $derived.by(() => {
    if (!playbook) return 0;
    return (
      (playbook.week_1_actions?.length || 0) +
      (playbook.week_2_actions?.length || 0) +
      (playbook.week_3_actions?.length || 0) +
      (playbook.week_4_actions?.length || 0)
    );
  });
</script>

<Section
  id="gtm-playbook"
  class="report-section"
  icon={SECTION_MAP['gtm-playbook'].icon}
  title="Go-to-Market Playbook"
  subtitle="Launch strategy and customer acquisition"
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
        value={Math.min(totalActions / 20, 1)}
        label="30-Day Plan"
        sublabel="{totalActions} Actions"
        color="accent"
      />
    {/snippet}
    <HeroMetric
      value={channelCount}
      label="Channels"
      icon={Megaphone}
      color={highPriorityChannels > 0 ? "success" : "neutral"}
    />
    <HeroMetric
      value={contentAnglesCount}
      label="Content Angles"
      icon={FileText}
    />
    <HeroMetric
      value="4"
      label="Weeks"
      suffix="planned"
      icon={Calendar}
      color="accent"
    />
  </HeroStrip>

  <!-- Core Message Hero - Always Visible -->
  <div class="insight-card insight-card--accent message-hero">
    <div class="message-header">
      <Megaphone class="message-icon" />
      <span class="message-label">Core Marketing Message</span>
    </div>
    <p class="message-text">{gtmData.core_marketing_message}</p>
    {#if gtmData.message_framework}
      <div class="message-framework">
        {@html renderMarkdown(gtmData.message_framework)}
      </div>
    {/if}
    {#if budgetDisplayString}
      <div class="budget-badge">
        <DollarSign class="budget-icon" />
        <span class="budget-label">Estimated Budget:</span>
        <span class="budget-value">{budgetDisplayString}</span>
      </div>
    {/if}
  </div>

  <!-- ICP Quick Summary - Always Visible -->
  <div class="icp-summary">
    <div class="icp-summary-header">
      <User class="icp-summary-icon" />
      <div class="icp-summary-content">
        <span class="icp-summary-label">Ideal Customer</span>
        <span class="icp-summary-persona">{icp.persona_name}</span>
      </div>
    </div>
    <div class="icp-summary-grid">
      <div class="icp-summary-item">
        <span class="icp-summary-item-label">Demographics</span>
        <span class="icp-summary-item-value">{icp.demographics}</span>
      </div>
      <div class="icp-summary-item">
        <span class="icp-summary-item-label">Key Trigger</span>
        <span class="icp-summary-item-value">{icp.buying_triggers}</span>
      </div>
    </div>
  </div>

  <!-- 30-Day Playbook - Always Visible (Core Value) -->
  <div class="playbook-section">
    <div class="playbook-header">
      <Calendar class="playbook-icon" />
      <h3 class="playbook-title">First 30 Days Playbook</h3>
    </div>

    <div class="playbook-timeline">
      <div class="week-card week-1">
        <div class="week-indicator"></div>
        <div class="week-content">
          <div class="week-header">
            <span class="week-badge">Week 1</span>
            <Badge variant="success" size="sm">Foundation</Badge>
          </div>
          <ul class="week-actions">
            {#each playbook.week_1_actions as action}
              <li class="action-item">
                <CheckCircle class="action-icon" />
                {action}
              </li>
            {/each}
          </ul>
        </div>
      </div>

      <div class="week-card week-2">
        <div class="week-indicator"></div>
        <div class="week-content">
          <div class="week-header">
            <span class="week-badge">Week 2</span>
            <Badge variant="accent" size="sm">Launch</Badge>
          </div>
          <ul class="week-actions">
            {#each playbook.week_2_actions as action}
              <li class="action-item">
                <CheckCircle class="action-icon" />
                {action}
              </li>
            {/each}
          </ul>
        </div>
      </div>

      <div class="week-card week-3">
        <div class="week-indicator"></div>
        <div class="week-content">
          <div class="week-header">
            <span class="week-badge">Week 3</span>
            <Badge variant="muted" size="sm">Growth</Badge>
          </div>
          <ul class="week-actions">
            {#each playbook.week_3_actions as action}
              <li class="action-item">
                <CheckCircle class="action-icon" />
                {action}
              </li>
            {/each}
          </ul>
        </div>
      </div>

      <div class="week-card week-4">
        <div class="week-indicator"></div>
        <div class="week-content">
          <div class="week-header">
            <span class="week-badge">Week 4</span>
            <Badge variant="warning" size="sm">Optimize</Badge>
          </div>
          <ul class="week-actions">
            {#each playbook.week_4_actions as action}
              <li class="action-item">
                <CheckCircle class="action-icon" />
                {action}
              </li>
            {/each}
          </ul>
        </div>
      </div>
    </div>
  </div>

  <!-- Expandable Sections Container -->
  <div class="expandable-sections">
    <!-- Ideal Customer Profile Details -->
    <ExpandableSection
      title="Customer Profile Details"
      icon={User}
      count={(icp.pain_points?.length || 0) + (icp.goals?.length || 0)}
      countSuffix="insights"
    >
      <div class="icp-details-grid">
        <div class="icp-detail-card">
          <h5 class="icp-detail-label">Psychographics</h5>
          <p class="icp-detail-text">{icp.psychographics}</p>
        </div>
        <div class="icp-detail-card">
          <h5 class="icp-detail-label">Decision Criteria</h5>
          <p class="icp-detail-text">{icp.decision_criteria}</p>
        </div>
      </div>

      {#if icp.pain_points && icp.pain_points.length > 0}
        <div class="icp-list-section">
          <h5 class="icp-list-label">
            <Target class="list-label-icon error" />
            Pain Points
          </h5>
          <ul class="icp-list">
            {#each icp.pain_points as point}
              <li class="icp-list-item">
                <span class="list-bullet error"></span>
                <span>{point}</span>
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if icp.goals && icp.goals.length > 0}
        <div class="icp-list-section">
          <h5 class="icp-list-label">
            <Zap class="list-label-icon success" />
            Goals & Aspirations
          </h5>
          <ul class="icp-list">
            {#each icp.goals.slice(0, 5) as goal}
              <li class="icp-list-item">
                <span class="list-bullet success"></span>
                <span>{goal}</span>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    </ExpandableSection>

    <!-- Recommended Channels -->
    {#if gtmData.recommended_channels && gtmData.recommended_channels.length > 0}
      <ExpandableSection
        title="Marketing Channels"
        icon={Users}
        count={channelCount}
        countSuffix="channels"
        variant="success"
      >
        <div class="channels-grid">
          {#each gtmData.recommended_channels as channel}
            <div
              class="insight-card insight-card--dynamic channel-card"
              style="--card-accent-color: {getChannelColor(channel.priority)}"
            >
              <div class="channel-header">
                <div class="channel-info">
                  <h4 class="channel-name">{channel.channel_name}</h4>
                  <Badge variant="muted" size="sm">{channel.channel_type}</Badge
                  >
                </div>
                <Badge
                  variant={channel.priority === "High"
                    ? "success"
                    : channel.priority === "Medium"
                      ? "warning"
                      : "muted"}
                  size="sm"
                >
                  {channel.priority}
                </Badge>
              </div>
              <p class="channel-audience">{channel.target_audience_size}</p>
              <p class="channel-rationale">{channel.rationale}</p>
              <div class="channel-strategy">
                <span class="strategy-label">Strategy</span>
                <p class="strategy-text">{channel.strategy}</p>
              </div>
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Content Angles -->
    {#if gtmData.example_content_angles && gtmData.example_content_angles.length > 0}
      <ExpandableSection
        title="Content Angles"
        icon={FileText}
        count={contentAnglesCount}
        countSuffix="ideas"
      >
        <div class="angles-list">
          {#each gtmData.example_content_angles as angle}
            <div class="angle-card">
              <div class="angle-header">
                <Badge size="sm">{angle.content_type}</Badge>
                <span class="angle-channel">{angle.target_channel}</span>
              </div>
              <h4 class="angle-title">{angle.title}</h4>
              <p class="angle-hook">{angle.hook}</p>
              {#if angle.key_points && angle.key_points.length > 0}
                <ul class="angle-points">
                  {#each angle.key_points as point}
                    <li class="angle-point">
                      <ChevronRight class="point-icon" />
                      {point}
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Success Metrics -->
    {#if playbook.success_metrics && playbook.success_metrics.length > 0}
      <ExpandableSection
        title="Success Metrics"
        icon={BarChart3}
        count={playbook.success_metrics.length}
        countSuffix="KPIs"
        variant="success"
      >
        <div class="metrics-grid">
          {#each playbook.success_metrics as metric, i}
            <div class="metric-item">
              <span class="metric-number">{i + 1}</span>
              <span class="metric-text">{metric}</span>
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Budget Breakdown -->
    {#if budgetDetails}
      <ExpandableSection
        title="Budget Breakdown"
        icon={PieChart}
        count={4}
        countSuffix="categories"
        variant="accent"
      >
        <div class="budget-breakdown">
          <!-- Allocation Bars -->
          <div class="allocation-section">
            <h5 class="allocation-header">Monthly Allocation</h5>
            <div class="allocation-grid">
              <div class="allocation-item">
                <div class="allocation-label-row">
                  <span class="allocation-label">Content Creation</span>
                  <span class="allocation-percent"
                    >{budgetDetails.allocation.content_creation}%</span
                  >
                </div>
                <div class="allocation-bar">
                  <div
                    class="allocation-fill content"
                    style="width: {budgetDetails.allocation.content_creation}%"
                  ></div>
                </div>
                <span class="allocation-amount">
                  ${Math.round(
                    (budgetDetails.monthly_budget_min *
                      budgetDetails.allocation.content_creation) /
                      100,
                  ).toLocaleString()}-${Math.round(
                    (budgetDetails.monthly_budget_max *
                      budgetDetails.allocation.content_creation) /
                      100,
                  ).toLocaleString()}
                </span>
              </div>

              <div class="allocation-item">
                <div class="allocation-label-row">
                  <span class="allocation-label">Paid Advertising</span>
                  <span class="allocation-percent"
                    >{budgetDetails.allocation.paid_advertising}%</span
                  >
                </div>
                <div class="allocation-bar">
                  <div
                    class="allocation-fill paid"
                    style="width: {budgetDetails.allocation.paid_advertising}%"
                  ></div>
                </div>
                <span class="allocation-amount">
                  ${Math.round(
                    (budgetDetails.monthly_budget_min *
                      budgetDetails.allocation.paid_advertising) /
                      100,
                  ).toLocaleString()}-${Math.round(
                    (budgetDetails.monthly_budget_max *
                      budgetDetails.allocation.paid_advertising) /
                      100,
                  ).toLocaleString()}
                </span>
              </div>

              <div class="allocation-item">
                <div class="allocation-label-row">
                  <span class="allocation-label">Tools & Software</span>
                  <span class="allocation-percent"
                    >{budgetDetails.allocation.tools_and_software}%</span
                  >
                </div>
                <div class="allocation-bar">
                  <div
                    class="allocation-fill tools"
                    style="width: {budgetDetails.allocation
                      .tools_and_software}%"
                  ></div>
                </div>
                <span class="allocation-amount">
                  ${Math.round(
                    (budgetDetails.monthly_budget_min *
                      budgetDetails.allocation.tools_and_software) /
                      100,
                  ).toLocaleString()}-${Math.round(
                    (budgetDetails.monthly_budget_max *
                      budgetDetails.allocation.tools_and_software) /
                      100,
                  ).toLocaleString()}
                </span>
              </div>

              <div class="allocation-item">
                <div class="allocation-label-row">
                  <span class="allocation-label">Community & Outreach</span>
                  <span class="allocation-percent"
                    >{budgetDetails.allocation.community_and_outreach}%</span
                  >
                </div>
                <div class="allocation-bar">
                  <div
                    class="allocation-fill community"
                    style="width: {budgetDetails.allocation
                      .community_and_outreach}%"
                  ></div>
                </div>
                <span class="allocation-amount">
                  ${Math.round(
                    (budgetDetails.monthly_budget_min *
                      budgetDetails.allocation.community_and_outreach) /
                      100,
                  ).toLocaleString()}-${Math.round(
                    (budgetDetails.monthly_budget_max *
                      budgetDetails.allocation.community_and_outreach) /
                      100,
                  ).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          <!-- Rationale -->
          <div class="budget-rationale">
            <h5 class="rationale-header">Why This Budget?</h5>
            <p class="rationale-text">{budgetDetails.rationale}</p>
          </div>

          <!-- Scaling Guidance -->
          <div class="scaling-guidance">
            <TrendingUp class="scaling-icon" />
            <div class="scaling-content">
              <span class="scaling-label">Scaling Guidance</span>
              <p class="scaling-text">{budgetDetails.scaling_guidance}</p>
            </div>
          </div>
        </div>
      </ExpandableSection>
    {/if}

    <!-- Implementation Checklist -->
    {#if nextSteps && (steps.length > 0 || typeof nextSteps === "string")}
      <ExpandableSection
        title="Implementation Checklist"
        icon={ListChecks}
        count={steps.length}
        countSuffix="steps"
        variant="accent"
      >
        {#if steps.length > 1}
          <div class="checklist-items">
            {#each steps as step, i}
              <div class="checklist-item">
                <span class="item-number">{i + 1}</span>
                <span class="item-text">{step}</span>
                <ArrowRight class="item-arrow" />
              </div>
            {/each}
          </div>
        {:else if steps.length === 1}
          <div class="checklist-content">
            {@html renderMarkdown(steps[0])}
          </div>
        {:else if typeof nextSteps === "string"}
          <div class="checklist-content">
            {@html renderMarkdown(nextSteps)}
          </div>
        {/if}
      </ExpandableSection>
    {/if}
  </div>
</Section>

<style>
  /* Message Hero */
  .message-hero {
    margin-bottom: var(--space-6);
  }

  .message-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  :global(.message-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent-dark);
  }

  .message-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-accent-dark);
  }

  .message-text {
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.4;
    margin: 0 0 var(--space-4);
  }

  .message-framework {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border-emphasis);
  }

  .budget-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-4);
    padding: var(--space-2) var(--space-4);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  :global(.budget-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent-dark);
  }

  .budget-label {
    font-size: var(--text-base);
    color: var(--color-text-muted);
  }

  .budget-value {
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: 700;
    color: var(--color-accent-dark);
  }

  /* ICP Summary (Always Visible) */
  .icp-summary {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 1.25rem;
    margin-bottom: var(--space-6);
  }

  .icp-summary-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    padding-bottom: var(--space-4);
    border-bottom: 1px solid var(--color-border);
  }

  :global(.icp-summary-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent-dark);
  }

  .icp-summary-content {
    display: flex;
    flex-direction: column;
  }

  .icp-summary-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .icp-summary-persona {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--color-accent-dark);
  }

  .icp-summary-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
  }

  .icp-summary-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .icp-summary-item-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .icp-summary-item-value {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* Playbook Section (Always Visible) */
  .playbook-section {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
  }

  .playbook-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: 1.25rem;
  }

  :global(.playbook-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent-dark);
  }

  .playbook-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  /* Playbook Timeline */
  .playbook-timeline {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
  }

  .week-card {
    display: flex;
    gap: var(--space-4);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: 1.25rem;
  }

  .week-indicator {
    width: 4px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  .week-1 .week-indicator {
    background: var(--color-success);
  }

  .week-2 .week-indicator {
    background: var(--color-accent);
  }

  .week-3 .week-indicator {
    background: var(--viz-cat-4);
  }

  .week-4 .week-indicator {
    background: var(--color-warning);
  }

  .week-content {
    flex: 1;
  }

  .week-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .week-badge {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .week-actions {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: var(--space-2);
  }

  .action-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  :global(.action-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent-dark);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  /* Expandable Sections Container */
  .expandable-sections {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  /* ICP Details */
  .icp-details-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .icp-detail-card {
    background: var(--color-bg-surface);
    border-radius: var(--radius-md);
    padding: var(--space-4);
  }

  .icp-detail-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin: 0 0 var(--space-2);
  }

  .icp-detail-text {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  .icp-list-section {
    margin-bottom: var(--space-4);
  }

  .icp-list-section:last-child {
    margin-bottom: 0;
  }

  .icp-list-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
    margin: 0 0 var(--space-3);
  }

  :global(.list-label-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }

  :global(.list-label-icon.error) {
    color: var(--color-error);
  }

  :global(.list-label-icon.success) {
    color: var(--color-success);
  }

  .icp-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: var(--space-2);
  }

  .icp-list-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    font-size: var(--text-base);
    color: var(--color-text-secondary);
  }

  .list-bullet {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 0.4rem;
  }

  .list-bullet.error {
    background: var(--color-error);
  }

  .list-bullet.success {
    background: var(--color-success);
  }

  /* Channels Grid */
  .channels-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--space-4);
  }

  .channel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .channel-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .channel-name {
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .channel-audience {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    margin: 0 0 var(--space-3);
  }

  .channel-rationale {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0 0 var(--space-4);
  }

  .channel-strategy {
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .strategy-label {
    display: block;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
    margin-bottom: 0.375rem;
  }

  .strategy-text {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  /* Content Angles */
  .angles-list {
    display: grid;
    gap: var(--space-4);
  }

  .angle-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: 1.25rem;
  }

  .angle-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .angle-channel {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  .angle-title {
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 var(--space-2);
  }

  .angle-hook {
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--color-accent-dark);
    margin: 0 0 var(--space-3);
    font-style: italic;
  }

  .angle-points {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.375rem;
  }

  .angle-point {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    font-size: var(--text-base);
    color: var(--color-text-secondary);
  }

  :global(.point-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  /* Metrics Grid */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--space-3);
  }

  .metric-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    background: var(--color-bg-surface);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
  }

  .metric-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    background: var(--color-success-subtle);
    border-radius: 50%;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-success);
    flex-shrink: 0;
  }

  .metric-text {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  /* Implementation Checklist */
  .checklist-items {
    display: grid;
    gap: var(--space-3);
  }

  .checklist-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-4);
    padding: var(--space-4);
    background: var(--color-bg-surface);
    border-radius: var(--radius-md);
    transition: background 0.15s ease;
  }

  .checklist-item:hover {
    background: var(--color-bg-hover);
  }

  .item-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    background: var(--color-accent-glow);
    border-radius: 50%;
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-accent-dark);
    flex-shrink: 0;
  }

  .item-text {
    flex: 1;
    font-size: 0.9375rem;
    color: var(--color-text-primary);
    line-height: 1.5;
  }

  :global(.item-arrow) {
    width: 1rem;
    height: 1rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
    margin-top: var(--space-1);
  }

  .checklist-content {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  /* Budget Breakdown Styles */
  .budget-breakdown {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .allocation-section {
    background: var(--color-bg-surface);
    border-radius: var(--radius-md);
    padding: 1.25rem;
  }

  .allocation-header {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin: 0 0 var(--space-4);
  }

  .allocation-grid {
    display: grid;
    gap: var(--space-4);
  }

  .allocation-item {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .allocation-label-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .allocation-label {
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .allocation-percent {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .allocation-bar {
    height: 8px;
    background: var(--color-bg-elevated);
    border-radius: 4px;
    overflow: hidden;
  }

  .allocation-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
  }

  .allocation-fill.content {
    background: var(--viz-cat-4);
  }

  .allocation-fill.paid {
    background: var(--color-error);
  }

  .allocation-fill.tools {
    background: var(--color-info);
  }

  .allocation-fill.community {
    background: var(--color-success);
  }

  .allocation-amount {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
  }

  .budget-rationale {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: 1rem 1.25rem;
  }

  .rationale-header {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-accent-dark);
    margin: 0 0 var(--space-2);
  }

  .rationale-text {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin: 0;
  }

  .scaling-guidance {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    background: var(--color-success-subtle);
    border: 1px solid var(--color-border-success);
    border-radius: var(--radius-md);
    padding: var(--space-4);
  }

  :global(.scaling-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-success);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .scaling-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .scaling-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-success);
  }

  .scaling-text {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .icp-summary-grid,
    .icp-details-grid {
      grid-template-columns: 1fr;
    }

    .channels-grid {
      grid-template-columns: 1fr;
    }

    .playbook-timeline {
      grid-template-columns: 1fr;
    }

    .metrics-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 480px) {
    .message-text {
      font-size: 1.125rem;
    }

    .week-card {
      padding: var(--space-4);
    }
  }
</style>
