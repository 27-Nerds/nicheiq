<script lang="ts">
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import StatPill from "$lib/components/ui/StatPill.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import MetricCard from "$lib/components/ui/MetricCard.svelte";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import {
    MessageCircle,
    MessageSquare,
    Globe,
    Search,
    DollarSign,
    TrendingUp,
    ThumbsUp,
    BarChart3,
    Target,
  } from "lucide-svelte";
  import { formatCount, formatVolume, tierVariant } from "$lib/utils/format-numbers";
  import { normalizePainPoint } from "$lib/utils/pain-point";

  interface Props {
    phase: "discovery" | "analysis";
    artifacts: Record<number, Record<string, any>>;
  }

  let { phase, artifacts }: Props = $props();

  const completedCount = $derived(
    Object.keys(artifacts).length,
  );

  const totalStages = $derived(phase === "discovery" ? 4 : 4);

  // Discovery helpers
  const nicheArtifact = $derived(artifacts[1]);
  const searchArtifact = $derived(artifacts[2]);
  const painArtifact = $derived(artifacts[3]);
  const audienceArtifact = $derived(artifacts[4]);

  // Analysis helpers
  const seoArtifact = $derived(artifacts[6]);
  const pricingArtifact = $derived(artifacts[7]);
  const marketArtifact = $derived(artifacts[9]);
  const trendArtifact = $derived(artifacts[11]);
</script>

{#if phase === "discovery"}
  <InsightCard variant="accent" border="left" padding="md">
    {#snippet header()}
      <div class="flex items-center justify-between">
        <span class="font-display font-semibold text-sm text-text-primary">Discovery Findings</span>
        <Badge variant="accent" size="sm">{completedCount}/{totalStages} stages</Badge>
      </div>
    {/snippet}

    {#snippet meta()}
      <div class="flex flex-wrap gap-2">
        {#if searchArtifact}
          <StatPill icon={MessageCircle} label="Posts" value={searchArtifact.reddit_posts + (searchArtifact.twitter_threads || 0)} />
          <StatPill icon={Globe} label="Communities" value={searchArtifact.subreddit_count} />
          {#if searchArtifact.total_interactions && searchArtifact.total_interactions > 0}
            <StatPill icon={MessageSquare} label="Interactions" value={formatCount(searchArtifact.total_interactions)} />
          {/if}
          {#if searchArtifact.total_upvotes && searchArtifact.total_upvotes > 0}
            <StatPill icon={ThumbsUp} label="Upvotes" value={formatCount(searchArtifact.total_upvotes)} />
          {/if}
          {#if searchArtifact.quality_tier}
            <Badge variant={tierVariant(searchArtifact.quality_tier)} size="sm">{searchArtifact.quality_tier}</Badge>
          {/if}
        {/if}
      </div>
    {/snippet}

    <div class="space-y-3">
      {#if nicheArtifact}
        <p class="text-sm text-text-secondary">{nicheArtifact.niche_description}</p>
        {#if nicheArtifact.market_segments?.length}
          <div class="flex flex-wrap gap-1.5">
            {#each nicheArtifact.market_segments as segment}
              <Badge variant="muted" size="sm">{segment}</Badge>
            {/each}
          </div>
        {/if}
      {/if}

      {#if painArtifact?.top}
        <div class="space-y-1.5">
          <span class="text-xs font-medium text-text-muted uppercase tracking-wide">Top Pain Points</span>
          {#each painArtifact.top as rawPoint}
            {@const point = normalizePainPoint(rawPoint)}
            <div class="flex items-center gap-2 text-sm">
              <Badge variant={point.severity > 0.7 ? "error" : "warning"} size="sm">
                {(point.severity * 10).toFixed(0)}/10
              </Badge>
              <span class="text-text-secondary">{point.title}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    {#snippet footer()}
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
        {#if audienceArtifact?.primary_target}
          <span>Primary target: <strong class="text-text-secondary">{audienceArtifact.primary_target}</strong></span>
          <span>&middot;</span>
          <span>{audienceArtifact.segment_count} audience segments</span>
        {/if}
        {#if audienceArtifact?.community_hubs?.length}
          <span>&middot;</span>
          {#each audienceArtifact.community_hubs as hub}
            <Badge variant="muted" size="sm">{hub}</Badge>
          {/each}
        {/if}
      </div>
    {/snippet}
  </InsightCard>

{:else}
  <!-- Analysis Results Card -->
  <InsightCard variant="info" border="left" padding="md">
    {#snippet header()}
      <div class="flex items-center justify-between">
        <span class="font-display font-semibold text-sm text-text-primary">Analysis Results</span>
        <Badge variant="info" size="sm">{completedCount}/{totalStages} stages</Badge>
      </div>
    {/snippet}

    {#snippet meta()}
      <div class="flex flex-wrap gap-2">
        {#if seoArtifact?.total_volume}
          <StatPill icon={Search} label="Monthly Searches" value="{formatVolume(seoArtifact.total_volume)}/mo" />
        {/if}
        {#if pricingArtifact?.starter_price && pricingArtifact?.pro_price}
          <StatPill icon={DollarSign} label="Price Range" value="{pricingArtifact.starter_price}-{pricingArtifact.pro_price}" />
        {/if}
        {#if seoArtifact?.demand_signal}
          <Badge variant={seoArtifact.demand_signal === "strong" ? "success" : seoArtifact.demand_signal === "moderate" ? "accent" : "warning"} size="sm">
            {seoArtifact.demand_signal} demand
          </Badge>
        {/if}
        {#if trendArtifact?.timing_recommendation}
          <Badge variant={trendArtifact.timing_recommendation === "Enter Now" ? "success" : trendArtifact.timing_recommendation === "Monitor & Wait" ? "warning" : "error"} size="sm">
            {trendArtifact.timing_recommendation}
          </Badge>
        {/if}
      </div>
    {/snippet}

    <div class="space-y-4">
      {#if seoArtifact}
        <div class="space-y-2">
          <span class="text-xs font-medium text-text-muted uppercase tracking-wide">SEO Opportunity</span>
          <div class="flex flex-wrap gap-3 text-sm text-text-secondary">
            {#if seoArtifact.validated_keywords}
              <span><strong>{seoArtifact.validated_keywords}</strong> validated keywords</span>
            {/if}
            {#if seoArtifact.cluster_count}
              <span>&middot;</span>
              <span><strong>{seoArtifact.cluster_count}</strong> topic clusters</span>
            {/if}
            {#if seoArtifact.avg_difficulty != null}
              <span>&middot;</span>
              <span>Avg difficulty: <strong>{seoArtifact.avg_difficulty.toFixed(0)}</strong></span>
            {/if}
          </div>
          {#if seoArtifact.top_clusters?.length}
            <div class="flex flex-wrap gap-1.5">
              {#each seoArtifact.top_clusters as cluster}
                <Badge variant="muted" size="sm">{cluster}</Badge>
              {/each}
            </div>
          {/if}
          {#if seoArtifact.winner_name}
            <p class="text-xs text-text-muted">Primary: <strong class="text-text-secondary">{seoArtifact.winner_name}</strong></p>
          {/if}
        </div>
      {/if}

      {#if pricingArtifact}
        <div class="space-y-1">
          <span class="text-xs font-medium text-text-muted uppercase tracking-wide">Pricing</span>
          <div class="flex flex-wrap gap-3 text-sm text-text-secondary">
            {#if pricingArtifact.pricing_model}
              <span>Model: <strong>{pricingArtifact.pricing_model}</strong></span>
            {/if}
            {#if pricingArtifact.arpu}
              <span>&middot;</span>
              <span>ARPU: <strong>{pricingArtifact.arpu}</strong></span>
            {/if}
            {#if pricingArtifact.confidence}
              <span>&middot;</span>
              <Badge variant={pricingArtifact.confidence === "High" ? "success" : pricingArtifact.confidence === "Medium" ? "accent" : "warning"} size="sm">
                {pricingArtifact.confidence} confidence
              </Badge>
            {/if}
          </div>
        </div>
      {/if}

      {#if marketArtifact}
        <div class="space-y-2">
          <span class="text-xs font-medium text-text-muted uppercase tracking-wide">Market Sizing</span>
          <CardGrid minWidth={140} gap="sm">
            <MetricCard label="TAM" value={marketArtifact.tam} variant="accent" />
            <MetricCard label="SAM" value={marketArtifact.sam} />
            <MetricCard label="SOM Y1" value={marketArtifact.som_y1} variant="success" />
          </CardGrid>
          <div class="flex flex-wrap gap-3 text-sm text-text-secondary">
            {#if marketArtifact.viability}
              <Badge variant={marketArtifact.viability === "Strong" ? "success" : marketArtifact.viability === "Moderate" ? "accent" : "warning"} size="sm">
                {marketArtifact.viability} viability
              </Badge>
            {/if}
            {#if marketArtifact.growth_rate}
              <span>Growth: <strong>{marketArtifact.growth_rate}</strong></span>
            {/if}
          </div>
          {#if marketArtifact.monetization}
            <p class="text-xs text-text-muted">
              Monetization: {marketArtifact.monetization.model}
              {#if marketArtifact.monetization.monthly_revenue_range}
                &middot; Est. {marketArtifact.monetization.monthly_revenue_range}/mo
              {/if}
            </p>
          {/if}
        </div>
      {/if}

      {#if trendArtifact}
        <div class="space-y-1">
          <span class="text-xs font-medium text-text-muted uppercase tracking-wide">Trends</span>
          <div class="flex flex-wrap gap-2 text-sm text-text-secondary">
            <Badge variant={trendArtifact.trend_direction === "Growing" ? "success" : trendArtifact.trend_direction === "Stable" ? "accent" : "error"} size="sm">
              {trendArtifact.trend_direction}
            </Badge>
            {#if trendArtifact.market_maturity}
              <Badge variant="muted" size="sm">{trendArtifact.market_maturity}</Badge>
            {/if}
            {#if trendArtifact.momentum_score != null}
              <span>Momentum: <strong>{(trendArtifact.momentum_score * 100).toFixed(0)}%</strong></span>
            {/if}
            {#if trendArtifact.longevity_verdict}
              <span>&middot;</span>
              <Badge variant={trendArtifact.longevity_verdict === "Sustainable" ? "success" : trendArtifact.longevity_verdict === "Risky" ? "warning" : "error"} size="sm">
                {trendArtifact.longevity_verdict}
              </Badge>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </InsightCard>
{/if}
