<script lang="ts">
	import { DollarSign, CheckCircle, Globe, Users, Megaphone, TrendingUp, Zap, AlertCircle } from 'lucide-svelte';
	import type { PricingStrategy, TrafficMonetization } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		pricingData: PricingStrategy;
		trafficData?: TrafficMonetization;
	}

	let { pricingData, trafficData }: Props = $props();

	// Parse traffic source breakdown for display
	const trafficSources = $derived(() => {
		if (!trafficData?.traffic_source_breakdown) return [];
		return Object.entries(trafficData.traffic_source_breakdown).map(([source, percentage]) => ({
			source,
			percentage
		}));
	});
</script>

<section id="monetization" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<DollarSign class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Monetization Strategy</h2>
	</div>

	<!-- ═══════════════════════════════════════════════════════════════════
	     SaaS PRICING SECTION
	     ═══════════════════════════════════════════════════════════════════ -->

	<div class="subsection-header mb-6">
		<h3 class="text-lg font-semibold text-text-primary">SaaS Pricing Model</h3>
		<div class="flex items-center gap-4">
			<Badge>{pricingData.pricing_model}</Badge>
			{#if pricingData.pricing_confidence}
				<span class="text-sm text-text-muted">
					{pricingData.pricing_confidence} confidence
				</span>
			{/if}
		</div>
	</div>

	<!-- Pricing Tiers -->
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
						<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
							<CheckCircle class="w-4 h-4 text-text-muted shrink-0 mt-0.5" />
							{feature}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Starter Tier (Recommended) -->
		<div class="pricing-tier pricing-tier-recommended">
			<div class="text-center mb-4 pt-2">
				<div class="text-sm text-text-muted mb-1">Starter</div>
				<div class="text-3xl font-bold text-accent">{pricingData.recommended_starter_price}</div>
			</div>
			{#if pricingData.starter_tier_features && pricingData.starter_tier_features.length > 0}
				<ul class="space-y-2">
					{#each pricingData.starter_tier_features as feature}
						<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
							<CheckCircle class="w-4 h-4 text-accent shrink-0 mt-0.5" />
							{feature}
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Pro Tier -->
		<div class="pricing-tier pricing-tier-pro">
			<div class="text-center mb-4">
				<div class="text-sm text-text-muted mb-1">Pro</div>
				<div class="text-3xl font-bold text-success">{pricingData.recommended_pro_price}</div>
			</div>
			{#if pricingData.pro_tier_features && pricingData.pro_tier_features.length > 0}
				<ul class="space-y-2">
					{#each pricingData.pro_tier_features as feature}
						<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
							<CheckCircle class="w-4 h-4 text-success shrink-0 mt-0.5" />
							{feature}
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>

	<!-- Enterprise -->
	{#if pricingData.recommended_enterprise_price}
		<div class="text-center mb-8">
			<span class="text-text-muted">Enterprise:</span>
			<span class="text-text-primary font-semibold ml-2">{pricingData.recommended_enterprise_price}</span>
		</div>
	{/if}

	<!-- Pricing Rationale -->
	<div class="card mb-8">
		<h4 class="text-lg font-semibold text-text-primary mb-4">Pricing Rationale</h4>
		<div class="markdown-content narrative">
			{@html renderMarkdown(pricingData.pricing_rationale)}
		</div>
	</div>

	<!-- Unit Economics -->
	<div class="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
		{#if pricingData.estimated_arpu}
			<div class="card-surface card-sm text-center">
				<div class="text-sm text-text-muted mb-1">Estimated ARPU</div>
				<div class="text-xl font-semibold text-text-primary">{pricingData.estimated_arpu}</div>
			</div>
		{/if}
		{#if pricingData.estimated_ltv}
			<div class="card-surface card-sm text-center">
				<div class="text-sm text-text-muted mb-1">Estimated LTV</div>
				<div class="text-xl font-semibold text-accent">{pricingData.estimated_ltv}</div>
			</div>
		{/if}
		{#if pricingData.ltv_to_cac_ratio}
			<div class="card-surface card-sm text-center">
				<div class="text-sm text-text-muted mb-1">LTV:CAC Ratio</div>
				<div class="text-xl font-semibold text-success">{pricingData.ltv_to_cac_ratio}</div>
			</div>
		{/if}
		{#if pricingData.price_vs_competitors}
			<div class="card-surface card-sm text-center">
				<div class="text-sm text-text-muted mb-1">vs Competitors</div>
				<div class="text-xl font-semibold text-text-primary">{pricingData.price_vs_competitors}</div>
			</div>
		{/if}
	</div>

	<!-- WTP Validation -->
	{#if pricingData.wtp_validation}
		<div class="highlight-box mb-8">
			<h4 class="font-semibold text-text-primary mb-2">WTP Validation</h4>
			<div class="markdown-content narrative">
				{@html renderMarkdown(pricingData.wtp_validation)}
			</div>
		</div>
	{/if}

	<!-- Value Proposition Delta -->
	{#if pricingData.value_proposition_delta}
		<div class="card mb-8">
			<h4 class="font-semibold text-text-primary mb-2">Value Proposition Delta</h4>
			<div class="markdown-content narrative">
				{@html renderMarkdown(pricingData.value_proposition_delta)}
			</div>
		</div>
	{/if}

	<!-- ═══════════════════════════════════════════════════════════════════
	     TRAFFIC-BASED REVENUE SECTION (optional)
	     ═══════════════════════════════════════════════════════════════════ -->

	{#if trafficData}
		<div class="section-divider my-8"></div>

		<div class="subsection-header mb-6">
			<h3 class="text-lg font-semibold text-text-primary">Traffic-Based Revenue</h3>
			<Badge variant="accent">{trafficData.monetization_model}</Badge>
		</div>

		<!-- Revenue Overview Cards -->
		<AnimateOnScroll animation="fade-up">
			<div class="grid md:grid-cols-3 gap-4 mb-8">
				<!-- Monthly Revenue Range -->
				<div class="card bento-accent">
					<div class="flex items-center gap-2 mb-2">
						<TrendingUp class="w-4 h-4 text-accent" />
						<span class="text-xs text-text-muted uppercase tracking-wider">Monthly Revenue</span>
					</div>
					<div class="text-2xl font-bold text-accent">{trafficData.estimated_monthly_revenue_range}</div>
				</div>

				<!-- Annual Revenue Range -->
				<div class="card">
					<div class="flex items-center gap-2 mb-2">
						<DollarSign class="w-4 h-4 text-success" />
						<span class="text-xs text-text-muted uppercase tracking-wider">Annual Revenue</span>
					</div>
					<div class="text-2xl font-bold text-success">{trafficData.estimated_annual_revenue_range}</div>
				</div>

				<!-- Model -->
				<div class="card">
					<div class="flex items-center gap-2 mb-2">
						<Zap class="w-4 h-4 text-text-muted" />
						<span class="text-xs text-text-muted uppercase tracking-wider">Model</span>
					</div>
					<Badge variant="accent">{trafficData.monetization_model}</Badge>
				</div>
			</div>
		</AnimateOnScroll>

		<!-- Three Revenue Streams -->
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
							<div class="text-lg font-semibold text-text-primary">{trafficData.estimated_monthly_ad_revenue}</div>
						</div>
						{#if trafficData.estimated_cpm_rate}
							<div>
								<div class="text-xs text-text-muted">CPM Rate</div>
								<div class="text-sm text-text-secondary">{trafficData.estimated_cpm_rate}</div>
							</div>
						{/if}
						{#if trafficData.recommended_ad_networks && trafficData.recommended_ad_networks.length > 0}
							<div>
								<div class="text-xs text-text-muted mb-2">Recommended Networks</div>
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
							<div class="text-xs text-text-muted">Monthly Affiliate Revenue</div>
							<div class="text-lg font-semibold text-text-primary">{trafficData.estimated_monthly_affiliate_revenue}</div>
						</div>
						{#if trafficData.affiliate_commission_rate}
							<div>
								<div class="text-xs text-text-muted">Commission Rate</div>
								<div class="text-sm text-text-secondary">{trafficData.affiliate_commission_rate}</div>
							</div>
						{/if}
						{#if trafficData.estimated_affiliate_ctr}
							<div>
								<div class="text-xs text-text-muted">Expected CTR</div>
								<div class="text-sm text-text-secondary">{trafficData.estimated_affiliate_ctr}</div>
							</div>
						{/if}
						{#if trafficData.recommended_affiliate_programs && trafficData.recommended_affiliate_programs.length > 0}
							<div>
								<div class="text-xs text-text-muted mb-2">Recommended Programs</div>
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
						<Megaphone class="w-5 h-5 text-purple-500" />
						<h4 class="font-semibold text-text-primary">Sponsorship</h4>
					</div>
					<div class="space-y-3">
						{#if trafficData.sponsored_listing_price}
							<div>
								<div class="text-xs text-text-muted">Sponsored Listing</div>
								<div class="text-lg font-semibold text-text-primary">{trafficData.sponsored_listing_price}</div>
							</div>
						{/if}
						{#if trafficData.premium_placement_price}
							<div>
								<div class="text-xs text-text-muted">Premium Placement</div>
								<div class="text-sm text-text-secondary">{trafficData.premium_placement_price}</div>
							</div>
						{/if}
						{#if trafficData.lead_gen_price_per_lead}
							<div>
								<div class="text-xs text-text-muted">Lead Gen Price</div>
								<div class="text-sm text-text-secondary">{trafficData.lead_gen_price_per_lead}</div>
							</div>
						{/if}
					</div>
				</div>
			</div>
		</AnimateOnScroll>

		<!-- Traffic & Break-even -->
		<AnimateOnScroll animation="fade-up">
			<div class="grid md:grid-cols-2 gap-4 mb-8">
				<div class="card-surface">
					<div class="text-sm text-text-muted mb-1">Estimated Monthly Pageviews</div>
					<div class="text-xl font-semibold text-text-primary">{trafficData.estimated_monthly_pageviews}</div>
				</div>
				{#if trafficData.break_even_traffic_threshold}
					<div class="card-surface">
						<div class="text-sm text-text-muted mb-1">Break-even Traffic Threshold</div>
						<div class="text-xl font-semibold text-text-primary">{trafficData.break_even_traffic_threshold}</div>
					</div>
				{/if}
			</div>
		</AnimateOnScroll>

		<!-- Traffic Source Breakdown -->
		{#if trafficSources().length > 0}
			<AnimateOnScroll animation="fade-up">
				<div class="card mb-8">
					<h4 class="text-lg font-semibold text-text-primary mb-4">Traffic Source Breakdown</h4>
					<div class="space-y-3">
						{#each trafficSources() as { source, percentage }}
							<div class="flex items-center gap-3">
								<div class="w-24 text-sm text-text-muted">{source}</div>
								<div class="flex-1 h-2 bg-surface-secondary rounded-full overflow-hidden">
									<div
										class="h-full bg-accent rounded-full"
										style="width: {percentage}"
									></div>
								</div>
								<div class="w-16 text-right text-sm text-text-primary">{percentage}</div>
							</div>
						{/each}
					</div>
				</div>
			</AnimateOnScroll>
		{/if}

		<!-- Strategy & Rationale -->
		<AnimateOnScroll animation="fade-up">
			<div class="grid md:grid-cols-2 gap-6 mb-8 items-start">
				<div class="card">
					<h4 class="text-lg font-semibold text-text-primary mb-3">Monetization Rationale</h4>
					<p class="text-text-secondary text-sm leading-relaxed">{trafficData.monetization_rationale}</p>
				</div>
				<div class="card">
					<h4 class="text-lg font-semibold text-text-primary mb-3">Scaling Strategy</h4>
					<p class="text-text-secondary text-sm leading-relaxed">{trafficData.scaling_strategy}</p>
				</div>
			</div>
		</AnimateOnScroll>

		<!-- SaaS Alternative Recommendation -->
		<AnimateOnScroll animation="fade-up">
			<div class="card {trafficData.saas_alternative_viable ? 'border-success/30' : 'border-border'}">
				<div class="flex items-start gap-4">
					{#if trafficData.saas_alternative_viable}
						<div class="p-3 rounded-lg bg-success/10">
							<CheckCircle class="w-6 h-6 text-success" />
						</div>
					{:else}
						<div class="p-3 rounded-lg bg-warning/10">
							<AlertCircle class="w-6 h-6 text-warning" />
						</div>
					{/if}
					<div class="flex-1">
						<div class="flex items-center gap-2 mb-2">
							<h4 class="font-semibold text-text-primary">SaaS Alternative</h4>
							<Badge variant={trafficData.saas_alternative_viable ? 'success' : 'warning'}>
								{trafficData.saas_alternative_viable ? 'Viable' : 'Not Recommended'}
							</Badge>
						</div>
						<p class="text-text-secondary text-sm leading-relaxed">{trafficData.saas_vs_traffic_recommendation}</p>
					</div>
				</div>
			</div>
		</AnimateOnScroll>

		<!-- Confidence -->
		{#if trafficData.monetization_confidence}
			<div class="mt-6 pt-4 border-t border-border text-xs text-text-muted">
				<span>Confidence: {trafficData.monetization_confidence}</span>
			</div>
		{/if}
	{/if}
</section>

<style>
	.subsection-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.section-divider {
		height: 1px;
		background: linear-gradient(90deg, transparent, var(--color-border), transparent);
	}

	.pricing-tier {
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1.5rem;
		transition: all 0.3s ease;
	}

	.pricing-tier:hover {
		border-color: var(--color-border-hover);
		transform: translateY(-2px);
	}

	.pricing-tier-recommended {
		border-color: var(--color-accent);
		background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, transparent 60%);
		position: relative;
	}

	.pricing-tier-recommended::before {
		content: 'Recommended';
		position: absolute;
		top: -0.75rem;
		left: 50%;
		transform: translateX(-50%);
		background: var(--color-accent);
		color: var(--color-bg-primary);
		font-size: 0.625rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		padding: 0.25rem 0.75rem;
		border-radius: 9999px;
	}

	.pricing-tier-pro {
		border-color: var(--color-success);
		background: linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, transparent 60%);
	}
</style>
