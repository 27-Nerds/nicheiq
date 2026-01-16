<script lang="ts">
	import type { NicheContext, ResearchMetadata, PainPointAnalytics } from '$lib/types/report';
	import { formatNumber } from '$lib/utils/format';
	import { CheckCircle, XCircle, AlertTriangle, Target, Zap, Users, TrendingUp, MessageSquare, Database, Sparkles, Search, FileText, Award, Clock, BarChart3, ChevronRight } from 'lucide-svelte';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';

	interface Props {
		niche: string;
		nicheContext?: NicheContext;
		researchMetadata?: ResearchMetadata;
		painPointAnalytics?: PainPointAnalytics;
		detailedPainPointsCount?: number;
		solutionName?: string;
		solutionDescription?: string;
		severityScore?: number;
		wtpScore?: number;
		marketFitScore?: number;
		feasibilityScore?: number;
		soloDevScore?: number;
		confidenceScore?: number;
		totalKeywords?: number;
		totalSearchVolume?: number;
	}

	let {
		niche,
		nicheContext,
		researchMetadata,
		painPointAnalytics,
		detailedPainPointsCount = 0,
		solutionName,
		solutionDescription,
		severityScore,
		wtpScore,
		marketFitScore,
		feasibilityScore,
		soloDevScore,
		confidenceScore,
		totalKeywords = 0,
		totalSearchVolume = 0
	}: Props = $props();

	// Compute GO/NO-GO verdict based on scores
	const verdictData = $derived.by(() => {
		const scores = [
			marketFitScore,
			feasibilityScore,
			soloDevScore,
			severityScore,
			wtpScore
		].filter((s): s is number => s != null);

		if (scores.length === 0) {
			return { verdict: 'INSUFFICIENT DATA', isGo: false, isInsufficient: true, confidence: 0, avgScore: 0 };
		}

		const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
		const confidence = confidenceScore ?? Math.round(avgScore * 100);

		if (avgScore >= 0.65 && (marketFitScore ?? 0) >= 0.6 && (soloDevScore ?? 0) >= 0.5) {
			return { verdict: 'GO', isGo: true, isInsufficient: false, confidence, avgScore };
		} else if (avgScore >= 0.45) {
			return { verdict: 'CONDITIONAL', isGo: true, isInsufficient: false, confidence, avgScore };
		} else {
			return { verdict: 'NO-GO', isGo: false, isInsufficient: false, confidence, avgScore };
		}
	});

	// Short niche name for display
	const nicheName = $derived.by(() => {
		if (nicheContext?.niche_input) {
			return nicheContext.niche_input;
		}
		const words = niche.split(' ').slice(0, 5);
		return words.join(' ').replace(/[,.]$/, '');
	});

	// Total discussions analyzed
	const totalDiscussions = $derived.by(() => {
		// Try data_sources first (new format), fall back to direct fields (current format)
		const sources = researchMetadata?.data_sources;
		if (sources && sources.length > 0) {
			return sources.reduce((sum, s) => sum + s.items_collected, 0);
		}
		// Fallback to direct fields from backend
		const posts = researchMetadata?.reddit_posts_analyzed ?? 0;
		const comments = researchMetadata?.reddit_comments_analyzed ?? 0;
		const twitter = researchMetadata?.twitter_threads_analyzed ?? 0;
		return posts + comments + twitter;
	});

	// Pain points count
	const painPointsCount = $derived(
		painPointAnalytics?.total_pain_points ?? detailedPainPointsCount ?? 0
	);

	// Score to percentage
	const toPercent = (score: number | undefined) => score != null ? Math.round(score * 100) : null;

	// Color based on score
	const getScoreClass = (score: number | undefined) => {
		if (score == null) return 'muted';
		if (score >= 0.7) return 'success';
		if (score >= 0.5) return 'warning';
		return 'error';
	};

	// Verdict display text
	const getVerdictDisplay = (verdict: string) => {
		if (verdict === 'GO') return { text: 'GO', subtitle: 'Validated Opportunity' };
		if (verdict === 'CONDITIONAL') return { text: 'CONDITIONAL', subtitle: 'Proceed with Caution' };
		if (verdict === 'NO-GO') return { text: 'NO-GO', subtitle: 'High Risk Detected' };
		return { text: 'ANALYZING', subtitle: 'Data Collection' };
	};

	// Format date for report
	const reportDate = $derived.by(() => {
		const date = new Date();
		return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
	});
</script>

<!-- Decision Gateway Hero - The most prominent element -->
<section class="hero-gateway">
	<!-- Top Meta Bar -->
	<div class="meta-bar">
		<div class="niche-pill">
			<Database class="pill-icon" />
			<span class="pill-text">{nicheName}</span>
		</div>
		<div class="meta-info">
			<span class="meta-item">
				<Clock class="meta-icon" />
				{reportDate}
			</span>
			<span class="meta-divider">|</span>
			<span class="meta-item">
				<FileText class="meta-icon" />
				{researchMetadata?.data_sources?.length ?? 0} sources
			</span>
		</div>
	</div>

	<!-- Primary Verdict Banner - THE Decision -->
	<div
		class="verdict-banner"
		class:verdict-go={verdictData.isGo && verdictData.verdict === 'GO'}
		class:verdict-conditional={verdictData.verdict === 'CONDITIONAL'}
		class:verdict-nogo={!verdictData.isGo && !verdictData.isInsufficient}
		class:verdict-unknown={verdictData.isInsufficient}
	>
		<div class="verdict-left">
			<div class="verdict-icon-wrap">
				{#if verdictData.isGo && verdictData.verdict === 'GO'}
					<CheckCircle class="verdict-icon" />
				{:else if verdictData.verdict === 'CONDITIONAL'}
					<AlertTriangle class="verdict-icon" />
				{:else if verdictData.isInsufficient}
					<BarChart3 class="verdict-icon" />
				{:else}
					<XCircle class="verdict-icon" />
				{/if}
			</div>
			<div class="verdict-text-group">
				<span class="verdict-eyebrow">RESEARCH VERDICT</span>
				<span class="verdict-main">{getVerdictDisplay(verdictData.verdict).text}</span>
				<span class="verdict-subtitle">{getVerdictDisplay(verdictData.verdict).subtitle}</span>
			</div>
		</div>

		<div class="verdict-right">
			<div class="confidence-ring">
				<ProgressRing
					value={verdictData.confidence / 100}
					size={88}
					strokeWidth={6}
					color={verdictData.isGo ? (verdictData.verdict === 'GO' ? 'success' : 'warning') : 'error'}
					showValue={true}
				/>
			</div>
			<span class="confidence-label">CONFIDENCE</span>
		</div>
	</div>

	<!-- Solution Hero Card -->
	{#if solutionName}
		<div class="solution-card">
			<div class="solution-header">
				<div class="solution-badge">
					<Sparkles class="badge-icon" />
					<span>RECOMMENDED SOLUTION</span>
				</div>
			</div>
			<h1 class="solution-title">{solutionName}</h1>
			{#if solutionDescription}
				<p class="solution-desc">{solutionDescription}</p>
			{/if}
		</div>
	{/if}

	<!-- Validation Scores Grid -->
	<div class="scores-panel">
		<div class="scores-header">
			<Award class="scores-header-icon" />
			<span class="scores-title">Validation Metrics</span>
		</div>
		<div class="scores-grid">
			{#if toPercent(marketFitScore) != null}
				<div class="score-tile" class:score-strong={getScoreClass(marketFitScore) === 'success'}>
					<div class="score-visual">
						<ProgressRing
							value={marketFitScore ?? 0}
							size={48}
							strokeWidth={4}
							color={getScoreClass(marketFitScore)}
							showValue={true}
						/>
					</div>
					<div class="score-detail">
						<span class="score-name">Market Fit</span>
						<span class="score-hint">Product-market alignment</span>
					</div>
				</div>
			{/if}

			{#if toPercent(feasibilityScore) != null}
				<div class="score-tile" class:score-strong={getScoreClass(feasibilityScore) === 'success'}>
					<div class="score-visual">
						<ProgressRing
							value={feasibilityScore ?? 0}
							size={48}
							strokeWidth={4}
							color={getScoreClass(feasibilityScore)}
							showValue={true}
						/>
					</div>
					<div class="score-detail">
						<span class="score-name">Feasibility</span>
						<span class="score-hint">Technical viability</span>
					</div>
				</div>
			{/if}

			{#if toPercent(soloDevScore) != null}
				<div class="score-tile" class:score-strong={getScoreClass(soloDevScore) === 'success'}>
					<div class="score-visual">
						<ProgressRing
							value={soloDevScore ?? 0}
							size={48}
							strokeWidth={4}
							color={getScoreClass(soloDevScore)}
							showValue={true}
						/>
					</div>
					<div class="score-detail">
						<span class="score-name">Solo Dev</span>
						<span class="score-hint">Indie-friendly scope</span>
					</div>
				</div>
			{/if}

			{#if toPercent(severityScore) != null}
				<div class="score-tile" class:score-strong={getScoreClass(severityScore) === 'success'}>
					<div class="score-visual">
						<ProgressRing
							value={severityScore ?? 0}
							size={48}
							strokeWidth={4}
							color={getScoreClass(severityScore)}
							showValue={true}
						/>
					</div>
					<div class="score-detail">
						<span class="score-name">Pain Severity</span>
						<span class="score-hint">Problem urgency</span>
					</div>
				</div>
			{/if}
		</div>
	</div>

	<!-- Research Stats Strip -->
	<div class="stats-strip">
		<div class="stat-block featured">
			<MessageSquare class="stat-block-icon" />
			<div class="stat-block-content">
				<span class="stat-block-value">{formatNumber(totalDiscussions)}</span>
				<span class="stat-block-label">Discussions</span>
			</div>
		</div>

		<div class="stat-block">
			<Target class="stat-block-icon warning" />
			<div class="stat-block-content">
				<span class="stat-block-value">{formatNumber(painPointsCount)}</span>
				<span class="stat-block-label">Pain Points</span>
			</div>
		</div>

		<div class="stat-block">
			<Search class="stat-block-icon" />
			<div class="stat-block-content">
				<span class="stat-block-value">{formatNumber(totalKeywords)}</span>
				<span class="stat-block-label">Keywords</span>
			</div>
		</div>

		<div class="stat-block">
			<TrendingUp class="stat-block-icon accent" />
			<div class="stat-block-content">
				<span class="stat-block-value">{formatNumber(totalSearchVolume)}</span>
				<span class="stat-block-label">Monthly Searches</span>
			</div>
		</div>
	</div>
</section>

<style>
	/* =========================
	   HERO GATEWAY CONTAINER
	   ========================= */
	.hero-gateway {
		background: var(--color-bg-base);
		padding: 1.5rem;
	}

	/* =========================
	   META BAR
	   ========================= */
	.meta-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1.25rem;
		flex-wrap: wrap;
	}

	.niche-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.12) 0%, rgba(229, 90, 40, 0.04) 100%);
		border: 1px solid rgba(229, 90, 40, 0.3);
		border-radius: 9999px;
	}

	:global(.pill-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: #E55A28;
	}

	.pill-text {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 600;
		color: #E55A28;
		max-width: 260px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta-info {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.meta-item {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		color: #A1A1AA;
	}

	:global(.meta-icon) {
		width: 0.75rem;
		height: 0.75rem;
	}

	.meta-divider {
		color: #71717A;
		opacity: 0.5;
	}

	/* =========================
	   VERDICT BANNER - Primary Decision
	   ========================= */
	.verdict-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 2rem;
		padding: 2rem 2.5rem;
		border-radius: 1rem;
		margin-bottom: 1.5rem;
		position: relative;
		overflow: hidden;
		transition: all 0.2s ease;
	}

	.verdict-banner::before {
		content: '';
		position: absolute;
		inset: 0;
		opacity: 0.03;
		background-image: radial-gradient(circle at 15% 50%, currentColor 1px, transparent 1px);
		background-size: 24px 24px;
		pointer-events: none;
	}

	.verdict-go {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.12) 0%, rgba(34, 197, 94, 0.02) 100%);
		border: 2px solid rgba(34, 197, 94, 0.45);
		color: #22C55E;
	}

	.verdict-conditional {
		background: linear-gradient(135deg, rgba(234, 179, 8, 0.12) 0%, rgba(234, 179, 8, 0.02) 100%);
		border: 2px solid rgba(234, 179, 8, 0.45);
		color: #EAB308;
	}

	.verdict-nogo {
		background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.02) 100%);
		border: 2px solid rgba(239, 68, 68, 0.45);
		color: #EF4444;
	}

	.verdict-unknown {
		background: linear-gradient(135deg, rgba(161, 161, 170, 0.12) 0%, rgba(161, 161, 170, 0.02) 100%);
		border: 2px solid rgba(161, 161, 170, 0.45);
		color: #A1A1AA;
	}

	.verdict-left {
		display: flex;
		align-items: center;
		gap: 1.25rem;
	}

	.verdict-icon-wrap {
		width: 4rem;
		height: 4rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		background: currentColor;
		flex-shrink: 0;
	}

	:global(.verdict-icon) {
		width: 2rem;
		height: 2rem;
		color: white;
	}

	.verdict-text-group {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.verdict-eyebrow {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 600;
		letter-spacing: 0.15em;
		color: #A1A1AA;
		text-transform: uppercase;
	}

	.verdict-main {
		font-family: var(--font-display);
		font-size: clamp(2.25rem, 7vw, 3.25rem);
		font-weight: 800;
		letter-spacing: -0.02em;
		line-height: 1;
		color: currentColor;
	}

	.verdict-subtitle {
		font-size: 0.875rem;
		color: #71717A;
		margin-top: 0.25rem;
	}

	.verdict-right {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
	}

	.confidence-ring {
		position: relative;
	}

	.confidence-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 600;
		letter-spacing: 0.12em;
		color: #A1A1AA;
		text-transform: uppercase;
	}

	/* =========================
	   SOLUTION CARD
	   ========================= */
	.solution-card {
		text-align: center;
		padding: 1.5rem 1.25rem 1.75rem;
		margin-bottom: 1.5rem;
		background: linear-gradient(180deg, rgba(250, 250, 250, 0.8) 0%, transparent 100%);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.875rem;
	}

	.solution-header {
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 0.75rem;
	}

	.solution-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.875rem;
		background: rgba(229, 90, 40, 0.1);
		border-radius: 9999px;
	}

	:global(.badge-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: #E55A28;
	}

	.solution-badge span {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		color: #E55A28;
	}

	.solution-title {
		font-family: var(--font-display);
		font-size: clamp(1.625rem, 4.5vw, 2.25rem);
		font-weight: 800;
		color: #18181B;
		line-height: 1.15;
		margin-bottom: 0.625rem;
	}

	.solution-desc {
		font-size: 0.9375rem;
		color: #71717A;
		max-width: 40rem;
		margin: 0 auto;
		line-height: 1.55;
	}

	/* =========================
	   SCORES PANEL
	   ========================= */
	.scores-panel {
		margin-bottom: 1.25rem;
	}

	.scores-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.875rem;
	}

	:global(.scores-header-icon) {
		width: 1rem;
		height: 1rem;
		color: #E55A28;
	}

	.scores-title {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 700;
		color: #18181B;
	}

	.scores-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.625rem;
	}

	.score-tile {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.875rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.625rem;
		transition: all 0.15s ease;
	}

	.score-tile:hover {
		border-color: rgba(0, 0, 0, 0.15);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
	}

	.score-tile.score-strong {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.06) 0%, transparent 60%);
		border-color: rgba(34, 197, 94, 0.2);
	}

	.score-visual {
		flex-shrink: 0;
	}

	.score-detail {
		display: flex;
		flex-direction: column;
		gap: 0.0625rem;
		min-width: 0;
	}

	.score-name {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: #18181B;
	}

	.score-hint {
		font-size: 0.625rem;
		color: #A1A1AA;
	}

	/* =========================
	   STATS STRIP
	   ========================= */
	.stats-strip {
		display: flex;
		align-items: stretch;
		justify-content: center;
		gap: 0;
		padding: 0;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.625rem;
		overflow: hidden;
	}

	.stat-block {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.625rem;
		padding: 1rem 0.75rem;
		border-right: 1px solid rgba(0, 0, 0, 0.06);
	}

	.stat-block:last-child {
		border-right: none;
	}

	.stat-block.featured {
		background: linear-gradient(180deg, rgba(229, 90, 40, 0.04) 0%, transparent 100%);
	}

	:global(.stat-block-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: #A1A1AA;
		flex-shrink: 0;
	}

	:global(.stat-block-icon.warning) {
		color: #EAB308;
	}

	:global(.stat-block-icon.accent) {
		color: #E55A28;
	}

	.stat-block-content {
		display: flex;
		flex-direction: column;
		gap: 0.0625rem;
	}

	.stat-block-value {
		font-family: var(--font-display);
		font-size: 1.0625rem;
		font-weight: 700;
		color: #18181B;
		line-height: 1.1;
	}

	.stat-block-label {
		font-family: var(--font-mono);
		font-size: 0.5rem;
		font-weight: 500;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* =========================
	   RESPONSIVE ADJUSTMENTS
	   ========================= */
	@media (max-width: 1024px) {
		.scores-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (max-width: 768px) {
		.hero-gateway {
			padding: 1rem;
		}

		.verdict-banner {
			flex-direction: column;
			gap: 1.5rem;
			padding: 1.5rem;
			text-align: center;
		}

		.verdict-left {
			flex-direction: column;
			gap: 1rem;
		}

		.verdict-main {
			font-size: 2.25rem;
		}

		.stats-strip {
			flex-direction: column;
		}

		.stat-block {
			border-right: none;
			border-bottom: 1px solid rgba(0, 0, 0, 0.06);
			justify-content: flex-start;
			padding: 0.875rem 1rem;
		}

		.stat-block:last-child {
			border-bottom: none;
		}
	}

	@media (max-width: 480px) {
		.scores-grid {
			grid-template-columns: 1fr;
		}

		.score-tile {
			padding: 0.75rem;
		}

		.solution-title {
			font-size: 1.375rem;
		}

		.meta-bar {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.75rem;
		}
	}
</style>
