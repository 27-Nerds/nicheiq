<script lang="ts">
  import {
    DollarSign,
    CheckCircle,
    Globe,
    Users,
    Megaphone,
    TrendingUp,
    Layers,
    AlertCircle,
    Calculator,
    CircleDollarSign,
    Scale,
    BarChart3,
    FileText,
    Database,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type { PricingStrategy, TrafficMonetization } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import SubsectionHeader from "$lib/components/ui/SubsectionHeader.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import SectionLabel from "$lib/components/ui/SectionLabel.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";

  interface Props {
    pricingData: PricingStrategy;
    trafficData?: TrafficMonetization;
    cacBreakdown?: string;
  }

  let { pricingData, trafficData, cacBreakdown }: Props = $props();

  // Parse traffic source breakdown for display
  const trafficSources = $derived.by(() => {
    if (!Array.isArray(trafficData?.traffic_source_breakdown)) return [];
    return trafficData.traffic_source_breakdown.map((item) => ({
      source: item.source,
      percentage: item.percentage,
    }));
  });

  // Detect N/A values for muted styling
  const isNAValue = (value: string | undefined): boolean => {
    if (!value) return true;
    const lower = value.toLowerCase();
    return lower.includes("n/a") || lower.includes("not applicable");
  };

  // Get semantic variant based on metric type and value
  const getMetricVariant = (
    type: string,
    value: string | undefined,
  ): "default" | "success" | "warning" | "accent" | "muted" => {
    if (isNAValue(value)) return "muted";
    if (type === "ltv_cac") {
      const match = value?.match(/(\d+\.?\d*)/);
      if (match) {
        const ratio = parseFloat(match[1]);
        if (ratio >= 3) return "success";
        if (ratio >= 1.5) return "warning";
      }
    }
    return type === "competitor" ? "default" : "accent";
  };

  // Split long values into display + description
  const parseMetricValue = (
    value: string | undefined,
  ): { display: string; description?: string } => {
    if (!value) return { display: "N/A" };
    const dashIdx = value.indexOf(" - ");
    if (dashIdx > 0) {
      return {
        display: value.substring(0, dashIdx).trim(),
        description: value.substring(dashIdx + 3).trim(),
      };
    }
    if (value.length > 25) {
      const priceMatch = value.match(/\$[\d,]+(?:\.\d{2,})?/);
      if (priceMatch) return { display: priceMatch[0], description: value };
    }
    return { display: value };
  };
</script>

<Section
  id="monetization"
  class="report-section"
  icon={SECTION_MAP['monetization'].icon}
  title="Monetization Strategy"
  subtitle="Pricing model and revenue projections"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- ═══════════════════════════════════════════════════════════════════
	     SaaS PRICING SECTION
	     ═══════════════════════════════════════════════════════════════════ -->

  <SubsectionHeader
    title={pricingData.pricing_model === "Ad-Supported-Free" ||
    pricingData.pricing_model === "Affiliate-Only"
      ? "Traffic Monetization Model"
      : "SaaS Pricing Model"}
  >
    <Badge>{pricingData.pricing_model}</Badge>
    {#if pricingData.pricing_confidence}
      <span class="text-sm text-text-muted">
        {pricingData.pricing_confidence} confidence
      </span>
    {/if}
  </SubsectionHeader>

  <!-- Conditional Pricing Display based on pricing_model -->
  {#if pricingData.pricing_model === "Ad-Supported-Free" || pricingData.pricing_model === "Affiliate-Only"}
    <!-- Ad-Supported / Affiliate-Only: Single "Free" display with revenue projections -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 items-start">
      <!-- Free Tool Card -->
      <div class="pricing-tier pricing-tier-recommended">
        <div class="text-center mb-4 pt-2">
          <div class="text-sm text-text-muted mb-1">Free Tool</div>
          <div class="text-3xl font-bold text-accent">$0</div>
          <div class="text-xs text-text-muted mt-1">
            {#if pricingData.pricing_model === "Ad-Supported-Free"}
              Monetized via display ads
            {:else}
              Monetized via affiliate links
            {/if}
          </div>
        </div>
        <div class="text-sm text-text-secondary text-center">
          All features included for free
        </div>
      </div>

      <!-- Revenue Projections Card -->
      <div class="pricing-tier">
        <div class="text-center mb-4">
          <div class="text-sm text-text-muted mb-1">Revenue Projections</div>
        </div>
        <div class="space-y-3">
          {#if pricingData.estimated_monthly_ad_revenue}
            <div class="flex justify-between items-center">
              <span class="text-sm text-text-muted">Monthly Ad Revenue</span>
              <span class="text-sm font-semibold text-accent"
                >{pricingData.estimated_monthly_ad_revenue}</span
              >
            </div>
          {/if}
          {#if pricingData.estimated_monthly_affiliate_revenue}
            <div class="flex justify-between items-center">
              <span class="text-sm text-text-muted"
                >Monthly Affiliate Revenue</span
              >
              <span class="text-sm font-semibold text-success"
                >{pricingData.estimated_monthly_affiliate_revenue}</span
              >
            </div>
          {/if}
          {#if pricingData.estimated_cpm_rate}
            <div class="flex justify-between items-center">
              <span class="text-sm text-text-muted">CPM Rate</span>
              <span class="text-sm text-text-secondary"
                >{pricingData.estimated_cpm_rate}</span
              >
            </div>
          {/if}
          {#if pricingData.recommended_ad_networks && pricingData.recommended_ad_networks.length > 0}
            <div class="pt-2 border-t border-border">
              <div class="text-xs text-text-muted mb-2">
                Recommended Ad Networks
              </div>
              <div class="flex flex-wrap gap-1">
                {#each pricingData.recommended_ad_networks as network}
                  <Badge variant="default" size="sm">{network}</Badge>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {:else if pricingData.pricing_model === "Freemium-Lite"}
    <!-- Freemium-Lite: 2-tier display (Free + Pro only, no Starter/Enterprise) -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 items-start">
      <!-- Free Tier -->
      {#if pricingData.free_tier_features && pricingData.free_tier_features.length > 0}
        <div class="pricing-tier">
          <div class="text-center mb-4">
            <div class="text-sm text-text-muted mb-1">Free</div>
            <div class="text-3xl font-bold text-text-primary">$0</div>
            <div class="text-xs text-text-muted">forever</div>
          </div>
          <ul class="space-y-2">
            {#each pricingData.free_tier_features as feature}
              <li
                class="text-sm text-text-secondary leading-relaxed flex items-start gap-2"
              >
                <CheckCircle class="w-4 h-4 text-text-muted shrink-0 mt-0.5" />
                {feature}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- Pro Tier (Recommended for Freemium-Lite) -->
      <div class="pricing-tier pricing-tier-recommended">
        <div class="text-center mb-4 pt-2">
          <div class="text-sm text-text-muted mb-1">Pro</div>
          <div class="text-3xl font-bold text-accent">
            {pricingData.recommended_pro_price ||
              pricingData.recommended_starter_price}
          </div>
        </div>
        {#if pricingData.pro_tier_features && pricingData.pro_tier_features.length > 0}
          <ul class="space-y-2">
            {#each pricingData.pro_tier_features as feature}
              <li
                class="text-sm text-text-secondary leading-relaxed flex items-start gap-2"
              >
                <CheckCircle class="w-4 h-4 text-accent shrink-0 mt-0.5" />
                {feature}
              </li>
            {/each}
          </ul>
        {:else if pricingData.starter_tier_features && pricingData.starter_tier_features.length > 0}
          <ul class="space-y-2">
            {#each pricingData.starter_tier_features as feature}
              <li
                class="text-sm text-text-secondary leading-relaxed flex items-start gap-2"
              >
                <CheckCircle class="w-4 h-4 text-accent shrink-0 mt-0.5" />
                {feature}
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  {:else}
    <!-- Standard 3-tier display (Freemium, Subscription, Hybrid, etc.) -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 items-start">
      <!-- Free Tier -->
      {#if pricingData.free_tier_features && pricingData.free_tier_features.length > 0}
        <div class="pricing-tier">
          <div class="text-center mb-4">
            <div class="text-sm text-text-muted mb-1">Free</div>
            <div class="text-3xl font-bold text-text-primary">$0</div>
            <div class="text-xs text-text-muted">forever</div>
          </div>
          <ul class="space-y-2">
            {#each pricingData.free_tier_features as feature}
              <li
                class="text-sm text-text-secondary leading-relaxed flex items-start gap-2"
              >
                <CheckCircle class="w-4 h-4 text-text-muted shrink-0 mt-0.5" />
                {feature}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- Starter Tier (Recommended) -->
      {#if pricingData.recommended_starter_price}
        <div class="pricing-tier pricing-tier-recommended">
          <div class="text-center mb-4 pt-2">
            <div class="text-sm text-text-muted mb-1">Starter</div>
            <div class="text-3xl font-bold text-accent">
              {pricingData.recommended_starter_price}
            </div>
          </div>
          {#if pricingData.starter_tier_features && pricingData.starter_tier_features.length > 0}
            <ul class="space-y-2">
              {#each pricingData.starter_tier_features as feature}
                <li
                  class="text-sm text-text-secondary leading-relaxed flex items-start gap-2"
                >
                  <CheckCircle class="w-4 h-4 text-accent shrink-0 mt-0.5" />
                  {feature}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}

      <!-- Pro Tier -->
      {#if pricingData.recommended_pro_price}
        <div class="pricing-tier pricing-tier-pro">
          <div class="text-center mb-4">
            <div class="text-sm text-text-muted mb-1">Pro</div>
            <div class="text-3xl font-bold text-success">
              {pricingData.recommended_pro_price}
            </div>
          </div>
          {#if pricingData.pro_tier_features && pricingData.pro_tier_features.length > 0}
            <ul class="space-y-2">
              {#each pricingData.pro_tier_features as feature}
                <li
                  class="text-sm text-text-secondary leading-relaxed flex items-start gap-2"
                >
                  <CheckCircle class="w-4 h-4 text-success shrink-0 mt-0.5" />
                  {feature}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Enterprise -->
    {#if pricingData.recommended_enterprise_price}
      <div class="text-center mb-8">
        <span class="text-text-muted">Enterprise:</span>
        <span class="text-text-primary font-semibold ml-2"
          >{pricingData.recommended_enterprise_price}</span
        >
      </div>
    {/if}
  {/if}

  <!-- Pricing Rationale -->
  <InsightCard variant="accent" border="left" padding="lg" class="mb-6">
    {#snippet header()}
      <SectionLabel text="Pricing Rationale" variant="accent" icon={FileText} />
    {/snippet}
    <div class="markdown-content">
      {@html renderMarkdown(pricingData.pricing_rationale)}
    </div>
  </InsightCard>

  <!-- Unit Economics -->
  <ExpandableSection
    title="Unit Economics"
    icon={Calculator}
    defaultOpen={false}
    variant="muted"
  >
    <CardGrid minWidth={180} gap="md" class="mb-8">
      {#if pricingData.estimated_arpu}
        {@const parsed = parseMetricValue(pricingData.estimated_arpu)}
        <InsightCard
          variant={getMetricVariant("arpu", pricingData.estimated_arpu)}
          border="left"
          padding="md"
        >
          {#snippet meta()}
            <div class="metric-label">
              <CircleDollarSign class="w-3.5 h-3.5" />
              <span class="mono-label">Estimated ARPU</span>
              <Tooltip content={getTermTooltip("ARPU")} position="top" />
            </div>
          {/snippet}
          <div class="metric-value">{parsed.display}</div>
          {#if parsed.description}
            <p class="metric-desc">{parsed.description}</p>
          {/if}
        </InsightCard>
      {/if}
      {#if pricingData.estimated_ltv}
        {@const parsed = parseMetricValue(pricingData.estimated_ltv)}
        <InsightCard
          variant={getMetricVariant("ltv", pricingData.estimated_ltv)}
          border="left"
          padding="md"
        >
          {#snippet meta()}
            <div class="metric-label">
              <TrendingUp class="w-3.5 h-3.5" />
              <span class="mono-label">Estimated LTV</span>
              <Tooltip content={getTermTooltip("LTV")} position="top" />
            </div>
          {/snippet}
          <div class="metric-value">{parsed.display}</div>
          {#if parsed.description}
            <p class="metric-desc">{parsed.description}</p>
          {/if}
        </InsightCard>
      {/if}
      {#if pricingData.ltv_to_cac_ratio}
        {@const parsed = parseMetricValue(pricingData.ltv_to_cac_ratio)}
        <InsightCard
          variant={getMetricVariant("ltv_cac", pricingData.ltv_to_cac_ratio)}
          border="left"
          padding="md"
        >
          {#snippet meta()}
            <div class="metric-label">
              <Scale class="w-3.5 h-3.5" />
              <span class="mono-label">LTV:CAC Ratio</span>
              <Tooltip content={getTermTooltip("LTV:CAC")} position="top" />
            </div>
          {/snippet}
          <div class="metric-value">{parsed.display}</div>
          {#if parsed.description}
            <p class="metric-desc">{parsed.description}</p>
          {/if}
        </InsightCard>
      {/if}
      {#if pricingData.price_vs_competitors}
        {@const parsed = parseMetricValue(pricingData.price_vs_competitors)}
        <InsightCard
          variant={getMetricVariant(
            "competitor",
            pricingData.price_vs_competitors,
          )}
          border="left"
          padding="md"
        >
          {#snippet meta()}
            <div class="metric-label">
              <BarChart3 class="w-3.5 h-3.5" />
              <span class="mono-label">vs Competitors</span>
              <Tooltip
                content="How your pricing compares to competitor offerings in the market"
                position="top"
              />
            </div>
          {/snippet}
          <div class="metric-value">{parsed.display}</div>
          {#if parsed.description}
            <p class="metric-desc">{parsed.description}</p>
          {/if}
        </InsightCard>
      {/if}
    </CardGrid>
  </ExpandableSection>

  <!-- CAC Breakdown -->
  {#if cacBreakdown}
    <ExpandableSection
      title="CAC Breakdown"
      icon={DollarSign}
      defaultOpen={false}
      variant="muted"
    >
      <div class="markdown-content">
        {@html renderMarkdown(cacBreakdown)}
      </div>
    </ExpandableSection>
  {/if}

  <!-- WTP Validation -->
  {#if pricingData.wtp_validation}
    <ExpandableSection
      title="WTP Validation"
      defaultOpen={false}
      variant="muted"
    >
      <div class="markdown-content">
        {@html renderMarkdown(pricingData.wtp_validation)}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Value Proposition Delta -->
  {#if pricingData.value_proposition_delta}
    <ExpandableSection
      title="Value Proposition Delta"
      defaultOpen={false}
      variant="muted"
    >
      <div class="markdown-content">
        {@html renderMarkdown(pricingData.value_proposition_delta)}
      </div>
    </ExpandableSection>
  {/if}

  <!-- ═══════════════════════════════════════════════════════════════════
	     REVENUE SCALING ROADMAP (optional)
	     ═══════════════════════════════════════════════════════════════════ -->

  {#if trafficData}
    <div class="section-divider my-8"></div>

    <SubsectionHeader title="Revenue Scaling Roadmap">
      <Badge variant="accent">{trafficData.monetization_model}</Badge>
    </SubsectionHeader>

    <!-- 1. HERO ANCHOR — at-scale revenue potential -->
    {#if trafficData.revenue_milestones?.length}
      {@const lastMilestone = trafficData.revenue_milestones[trafficData.revenue_milestones.length - 1]}
      <AnimateOnScroll animation="fade-up">
        <div class="card bento-accent mb-6">
          <div class="flex items-center gap-2 mb-2">
            <TrendingUp class="w-5 h-5 text-accent" />
            <span class="text-xs uppercase tracking-wider text-text-muted">Revenue Potential at Scale</span>
          </div>
          <div class="text-3xl font-bold text-accent">{lastMilestone.total_potential}</div>
          <p class="text-sm text-text-muted mt-2">
            Starting from {trafficData.estimated_monthly_revenue_range}/mo with organic growth alone.
            These projections assume basic ad networks only — premium networks and diversified revenue add 2-4x.
          </p>
        </div>
      </AnimateOnScroll>
    {/if}

    <!-- 2. YEAR PROGRESSION -->
    {#if trafficData.year3_monthly_revenue || trafficData.full_potential_monthly_revenue}
      <HeroStrip>
        <HeroMetric
          value={trafficData.estimated_monthly_revenue_range ?? "N/A"}
          label="Year 1"
          progress={0.25}
        />
        {#if trafficData.year3_monthly_revenue}
          <HeroMetric
            value={trafficData.year3_monthly_revenue}
            label="Year 3"
            progress={0.5}
          />
        {/if}
        {#if trafficData.full_potential_monthly_revenue}
          <HeroMetric
            value={trafficData.full_potential_monthly_revenue}
            label="Full Potential"
            color="accent"
            progress={1.0}
          />
        {/if}
      </HeroStrip>
    {/if}

    <!-- 3. MILESTONE ROADMAP — vertical timeline -->
    {#if trafficData.revenue_milestones?.length}
      <AnimateOnScroll animation="fade-up">
        <div class="relative ml-4 mb-8">
          <div class="absolute left-3 top-0 bottom-0 w-0.5 bg-border"></div>
          {#each trafficData.revenue_milestones as milestone, i}
            {@const isLast = i === trafficData.revenue_milestones.length - 1}
            {@const isFirst = i === 0}
            <div class="relative pl-10 pb-6">
              <div class="absolute left-0 top-1.5 w-6 h-6 rounded-full flex items-center justify-center text-xs
                {isLast ? 'bg-accent text-white' : isFirst ? 'border-2 border-accent bg-background' : 'border-2 border-border bg-background'}">
                {#if isLast}&#9733;{/if}
              </div>
              <div class="card {isLast ? 'bento-accent' : ''}">
                <div class="flex items-baseline justify-between mb-1">
                  <span class="text-sm font-medium">{milestone.traffic}</span>
                  {#if isFirst}
                    <span class="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent">Starting Point</span>
                  {/if}
                </div>
                <div class="text-xl font-bold {isLast ? 'text-accent' : ''}">{milestone.total_potential}</div>
                <p class="text-xs text-text-muted mt-1">{milestone.unlock}</p>
              </div>
            </div>
          {/each}
        </div>
      </AnimateOnScroll>
    {/if}

    <!-- 4. GROWTH STORY -->
    {#if trafficData.revenue_growth_note}
      <ExpandableSection title="Why These Numbers Are the Floor" icon={Layers} defaultOpen={true}>
        <InsightCard variant="muted">
          <p class="text-sm text-muted-foreground whitespace-pre-line">{trafficData.revenue_growth_note}</p>
        </InsightCard>
      </ExpandableSection>
    {/if}

    <!-- 5. REVENUE STREAMS -->
    <AnimateOnScroll animation="fade-up">
      <div class="grid md:grid-cols-3 gap-6 mb-8 items-start">
        <!-- Advertising Revenue -->
        <div class="card">
          <div class="flex items-center gap-2 mb-4 pb-4 border-b border-border">
            <Globe class="w-5 h-5 text-blue-500" />
            <h4 class="font-semibold text-text-primary">Advertising</h4>
          </div>
          <div class="space-y-3">
            <div>
              <div class="text-xs text-text-muted">Monthly Ad Revenue</div>
              <div class="text-lg font-semibold text-text-primary">
                {trafficData.estimated_monthly_ad_revenue}
              </div>
            </div>
            {#if trafficData.estimated_cpm_rate}
              <div>
                <div
                  class="text-xs text-text-muted inline-flex items-center gap-1"
                >
                  CPM Rate <Tooltip
                    content={getTermTooltip("CPM")}
                    position="top"
                  />
                </div>
                <div class="text-sm text-text-secondary">
                  {trafficData.estimated_cpm_rate}
                </div>
              </div>
            {/if}
            {#if trafficData.recommended_ad_networks && trafficData.recommended_ad_networks.length > 0}
              <div>
                <div class="text-xs text-text-muted mb-2">
                  Recommended Networks
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each trafficData.recommended_ad_networks as network}
                    <Badge variant="default" size="sm">{network}</Badge>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Affiliate Revenue -->
        <div class="card">
          <div class="flex items-center gap-2 mb-4 pb-4 border-b border-border">
            <Users class="w-5 h-5 text-green-500" />
            <h4 class="font-semibold text-text-primary">Affiliate</h4>
          </div>
          <div class="space-y-3">
            <div>
              <div class="text-xs text-text-muted">
                Monthly Affiliate Revenue
              </div>
              <div class="text-lg font-semibold text-text-primary">
                {trafficData.estimated_monthly_affiliate_revenue}
              </div>
            </div>
            {#if trafficData.affiliate_commission_rate}
              <div>
                <div class="text-xs text-text-muted">Commission Rate</div>
                <div class="text-sm text-text-secondary">
                  {trafficData.affiliate_commission_rate}
                </div>
              </div>
            {/if}
            {#if trafficData.estimated_affiliate_ctr}
              <div>
                <div
                  class="text-xs text-text-muted inline-flex items-center gap-1"
                >
                  Expected CTR <Tooltip
                    content={getTermTooltip("CTR")}
                    position="top"
                  />
                </div>
                <div class="text-sm text-text-secondary">
                  {trafficData.estimated_affiliate_ctr}
                </div>
              </div>
            {/if}
            {#if trafficData.recommended_affiliate_programs && trafficData.recommended_affiliate_programs.length > 0}
              <div>
                <div class="text-xs text-text-muted mb-2">
                  Recommended Programs
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each trafficData.recommended_affiliate_programs as program}
                    <Badge variant="success" size="sm">{program}</Badge>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Sponsorship Revenue -->
        <div class="card">
          <div class="flex items-center gap-2 mb-4 pb-4 border-b border-border">
            <Megaphone class="w-5 h-5 text-secondary" />
            <h4 class="font-semibold text-text-primary">Sponsorship</h4>
          </div>
          <div class="space-y-3">
            {#if trafficData.sponsored_listing_price}
              <div>
                <div class="text-xs text-text-muted">Sponsored Listing</div>
                <div class="text-lg font-semibold text-text-primary">
                  {trafficData.sponsored_listing_price}
                </div>
              </div>
            {/if}
            {#if trafficData.premium_placement_price}
              <div>
                <div class="text-xs text-text-muted">Premium Placement</div>
                <div class="text-sm text-text-secondary">
                  {trafficData.premium_placement_price}
                </div>
              </div>
            {/if}
            {#if trafficData.lead_gen_price_per_lead}
              <div>
                <div class="text-xs text-text-muted">Lead Gen Price</div>
                <div class="text-sm text-text-secondary">
                  {trafficData.lead_gen_price_per_lead}
                </div>
              </div>
            {/if}
          </div>
        </div>
      </div>
    </AnimateOnScroll>

    <!-- 6. SUPPORTING DETAILS -->
    <!-- Traffic & Break-even -->
    <AnimateOnScroll animation="fade-in">
      <div class="grid md:grid-cols-2 gap-4 mb-8">
        <div class="card-surface">
          <div class="text-sm text-text-muted mb-1">
            Estimated Monthly Pageviews
          </div>
          <div class="text-xl font-semibold text-text-primary">
            {trafficData.estimated_monthly_pageviews}
          </div>
        </div>
        {#if trafficData.break_even_traffic_threshold}
          <div class="card-surface">
            <div class="text-sm text-text-muted mb-1">
              Break-even Traffic Threshold
            </div>
            <div class="text-xl font-semibold text-text-primary">
              {trafficData.break_even_traffic_threshold}
            </div>
          </div>
        {/if}
      </div>
    </AnimateOnScroll>

    <!-- Traffic Source Breakdown -->
    {#if trafficSources.length > 0}
      <AnimateOnScroll animation="fade-in">
        <div class="card mb-8">
          <h4 class="text-lg font-semibold text-text-primary mb-4">
            Traffic Source Breakdown
          </h4>
          <div class="space-y-3">
            {#each trafficSources as { source, percentage }}
              <div class="flex items-center gap-3">
                <div class="w-24 text-sm text-text-muted">{source}</div>
                <div
                  class="flex-1 h-2 bg-surface-secondary rounded-full overflow-hidden"
                >
                  <div
                    class="h-full bg-accent rounded-full"
                    style="width: {percentage}"
                  ></div>
                </div>
                <div class="w-16 text-right text-sm text-text-primary">
                  {percentage}
                </div>
              </div>
            {/each}
          </div>
        </div>
      </AnimateOnScroll>
    {/if}

    <!-- Strategy & Rationale -->
    <div class="grid md:grid-cols-2 gap-6 mb-6 items-start">
        <div class="card">
          <h4 class="text-lg font-semibold text-text-primary mb-3">
            Monetization Rationale
          </h4>
          <p class="text-text-secondary text-sm leading-relaxed">
            {trafficData.monetization_rationale}
          </p>
        </div>
        <div class="card">
          <h4 class="text-lg font-semibold text-text-primary mb-3">
            Scaling Strategy
          </h4>
          <p class="text-text-secondary text-sm leading-relaxed">
            {trafficData.scaling_strategy}
          </p>
        </div>
      </div>

    <!-- SaaS Alternative Recommendation -->
    <AnimateOnScroll animation="slide-right">
      <div
        class="card mb-6 {trafficData.saas_alternative_viable
          ? 'border-success/30'
          : 'border-border'}"
      >
        <div class="flex items-start gap-4">
          {#if trafficData.saas_alternative_viable}
            <div class="p-3 rounded-lg border border-border shrink-0">
              <CheckCircle class="w-6 h-6 text-success" />
            </div>
          {:else}
            <div class="p-3 rounded-lg border border-border shrink-0">
              <AlertCircle class="w-6 h-6 text-warning" />
            </div>
          {/if}
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
              <h4 class="font-semibold text-text-primary">SaaS Alternative</h4>
              <Badge
                variant={trafficData.saas_alternative_viable
                  ? "success"
                  : "warning"}
              >
                {trafficData.saas_alternative_viable
                  ? "Viable"
                  : "Not Recommended"}
              </Badge>
            </div>
            <p class="text-text-secondary text-sm leading-relaxed">
              {trafficData.saas_vs_traffic_recommendation}
            </p>
          </div>
        </div>
      </div>
    </AnimateOnScroll>

    <!-- Traffic Methodology -->
    {#if trafficData.traffic_methodology}
      <ExpandableSection
        title="Traffic Methodology"
        icon={Database}
        count={trafficData.traffic_data_sources?.length}
        variant="muted"
        defaultOpen={false}
      >
        <InsightCard variant="muted" border="left" padding="md">
          <p class="text-sm text-muted-foreground">{trafficData.traffic_methodology}</p>
          {#if trafficData.traffic_data_sources && trafficData.traffic_data_sources.length > 0}
            <div class="flex flex-wrap gap-1.5 mt-3">
              {#each trafficData.traffic_data_sources as source}
                <span class="px-2 py-0.5 bg-muted rounded-md text-xs">{source}</span>
              {/each}
            </div>
          {/if}
        </InsightCard>
      </ExpandableSection>
    {/if}
  {/if}
</Section>

<style>
  .section-divider {
    height: 0;
    background: none;
    border-top: 1px solid var(--color-border);
  }

  .pricing-tier {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-6);
    transition: border-color 0.15s ease;
  }

  .pricing-tier:hover {
    border-color: var(--color-border-hover);
  }

  .pricing-tier-recommended {
    border-color: var(--color-accent);
    background: var(--color-accent-subtle);
    position: relative;
  }

  .pricing-tier-recommended::before {
    content: "Recommended";
    position: absolute;
    top: -0.75rem;
    left: 50%;
    transform: translateX(-50%);
    background: var(--color-accent);
    color: var(--color-bg-primary);
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-full);
  }

  .pricing-tier-pro {
    border-color: var(--color-success);
    background: var(--color-accent-subtle);
  }

  /* Unit Economics metric styles */
  .metric-label {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .mono-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  .metric-value {
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    margin-top: var(--space-1);
    color: var(--color-text-primary);
  }

  .metric-desc {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    line-height: 1.4;
    margin-top: 0.375rem;
    margin-bottom: 0;
  }
</style>
