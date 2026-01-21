<script lang="ts">
	import { Users, UserCheck, MessageSquare, Hash, Star, Target, Briefcase, DollarSign, Sparkles, ChevronDown, Globe } from 'lucide-svelte';
	import type { AudienceMapping } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import SectionHeader from '$lib/components/ui/SectionHeader.svelte';
	import ExpandableSection from '$lib/components/ui/ExpandableSection.svelte';
	import HeroStat from '$lib/components/ui/HeroStat.svelte';

	interface Props {
		data: AudienceMapping;
	}

	let { data }: Props = $props();

	// Expandable states
	let showInfluencers = $state(false);
	let showMessaging = $state(false);
	let showTactics = $state(false);

	// Map segment size to badge variant
	const getSizeVariant = (size: string | undefined) => {
		const s = size?.toLowerCase() || '';
		if (s.includes('large')) return 'success';
		if (s.includes('medium')) return 'warning';
		return 'muted';
	};

	// Count total segments
	const totalSegments = $derived(data.audience_segments?.length ?? 0);
	const totalInfluencers = $derived(data.key_influencers?.length ?? 0);
	const totalCommunities = $derived(data.community_hubs?.length ?? 0);
</script>

<section id="audience" class="report-section">
	<SectionHeader
		icon={Users}
		title="Audience Intelligence"
		subtitle="Target segments and engagement strategy"
	/>

	<!-- Hero Strip: Primary Target + Stats -->
	<div class="hero-strip">
		{#if data.primary_target_segment}
			<div class="hero-primary">
				<UserCheck class="hero-primary-icon" />
				<div class="hero-primary-content">
					<span class="hero-label">PRIMARY TARGET</span>
					<span class="hero-value">{data.primary_target_segment}</span>
				</div>
			</div>
		{/if}

		<div class="hero-stats">
			<div class="hero-stat">
				<span class="hero-stat-value">{totalSegments}</span>
				<span class="hero-stat-label">Segments</span>
			</div>
			<div class="hero-stat">
				<span class="hero-stat-value">{totalInfluencers}</span>
				<span class="hero-stat-label">Influencers</span>
			</div>
			<div class="hero-stat">
				<span class="hero-stat-value">{totalCommunities}</span>
				<span class="hero-stat-label">Communities</span>
			</div>
		</div>
	</div>

	<!-- Audience Segments Grid -->
	{#if data.audience_segments && data.audience_segments.length > 0}
		<div class="segments-section">
			<div class="subsection-header">
				<Target class="subsection-icon" />
				<span class="subsection-title">Audience Segments</span>
			</div>

			<div class="segments-grid">
				{#each data.audience_segments as segment, i}
					<div class="segment-card" class:primary={i === 0}>
						<div class="segment-top">
							<h4 class="segment-name">{segment.segment_name}</h4>
							{#if segment.size_estimate}
								<Badge variant={getSizeVariant(segment.size_estimate)} size="sm">{segment.size_estimate}</Badge>
							{/if}
						</div>

						{#if segment.pain_point_alignment && segment.pain_point_alignment.length > 0}
							<div class="segment-pains">
								<span class="segment-pains-label">Pain Alignment</span>
								<ul class="pains-list">
									{#each segment.pain_point_alignment.slice(0, 3) as painPoint}
										<li>{painPoint}</li>
									{/each}
								</ul>
							</div>
						{/if}

						<div class="segment-meta">
							{#if segment.expertise_level}
								<div class="meta-item">
									<Briefcase class="meta-icon" />
									<span>{segment.expertise_level}</span>
								</div>
							{/if}
							{#if segment.budget_sensitivity}
								<div class="meta-item">
									<DollarSign class="meta-icon" />
									<span>{segment.budget_sensitivity}</span>
								</div>
							{/if}
						</div>

						{#if segment.discovery_channels && segment.discovery_channels.length > 0}
							<div class="segment-channels">
								{#each segment.discovery_channels as channel}
									<span class="channel-tag">{channel}</span>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Community Hubs Strip -->
	{#if data.community_hubs && data.community_hubs.length > 0}
		<div class="communities-strip">
			<div class="communities-label">
				<Globe class="communities-icon" />
				<span>Community Hubs</span>
			</div>
			<div class="communities-tags">
				{#each data.community_hubs as hub}
					<span class="community-tag">{hub}</span>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Expandable: Key Influencers -->
	{#if data.key_influencers && data.key_influencers.length > 0}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => showInfluencers = !showInfluencers}>
				<div class="expandable-title">
					<Star class="expandable-icon warning" />
					<span>Key Influencers</span>
					<Badge variant="muted" size="sm">{data.key_influencers.length}</Badge>
				</div>
				<ChevronDown class="chevron-icon {showInfluencers ? 'expanded' : ''}" />
			</button>

			{#if showInfluencers}
				<div class="expandable-content">
					<div class="influencers-grid">
						{#each data.key_influencers as influencer}
							<div class="influencer-card">
								<div class="influencer-top">
									<span class="influencer-name">{influencer.name}</span>
									{#if influencer.outreach_priority}
										<Badge variant={influencer.outreach_priority === 'High' ? 'success' : influencer.outreach_priority === 'Medium' ? 'warning' : 'muted'} size="sm">
											{influencer.outreach_priority}
										</Badge>
									{/if}
								</div>
								<div class="influencer-meta">
									<span class="influencer-platform">{influencer.platform}</span>
									{#if influencer.follower_estimate}
										<span class="influencer-followers">{influencer.follower_estimate.toLocaleString()} followers</span>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Messaging & Vocabulary -->
	{#if (data.messaging_frameworks && data.messaging_frameworks.length > 0) || (data.common_vocabulary && data.common_vocabulary.length > 0)}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => showMessaging = !showMessaging}>
				<div class="expandable-title">
					<MessageSquare class="expandable-icon" />
					<span>Messaging & Vocabulary</span>
				</div>
				<ChevronDown class="chevron-icon {showMessaging ? 'expanded' : ''}" />
			</button>

			{#if showMessaging}
				<div class="expandable-content">
					<div class="messaging-grid">
						{#if data.messaging_frameworks && data.messaging_frameworks.length > 0}
							<div class="messaging-box">
								<h4 class="messaging-box-title">Messaging Frameworks</h4>
								<div class="messaging-list">
									{#each data.messaging_frameworks as msg}
										<div class="messaging-item">
											<span class="quote-mark">"</span>
											<span class="messaging-text">{msg}</span>
										</div>
									{/each}
								</div>
							</div>
						{/if}

						{#if data.common_vocabulary && data.common_vocabulary.length > 0}
							<div class="messaging-box">
								<h4 class="messaging-box-title">
									<Hash class="box-title-icon" />
									Common Vocabulary
								</h4>
								<div class="vocab-tags">
									{#each data.common_vocabulary as term}
										<span class="vocab-tag">{term}</span>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Early Adopter Tactics -->
	{#if data.early_adopter_tactics}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => showTactics = !showTactics}>
				<div class="expandable-title">
					<Sparkles class="expandable-icon success" />
					<span>Early Adopter Tactics</span>
				</div>
				<ChevronDown class="chevron-icon {showTactics ? 'expanded' : ''}" />
			</button>

			{#if showTactics}
				<div class="expandable-content tactics-bg">
					<div class="tactics-content">
						{@html renderMarkdown(data.early_adopter_tactics)}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</section>

<style>
	/* =========================
	   HERO STRIP
	   ========================= */
	.hero-strip {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.5rem;
		padding: 1.125rem 1.25rem;
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.08) 0%, rgba(229, 90, 40, 0.02) 100%);
		border: 1px solid rgba(229, 90, 40, 0.2);
		border-radius: 0.75rem;
		margin-bottom: 1.25rem;
		flex-wrap: wrap;
	}

	.hero-primary {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex: 1;
		min-width: 180px;
	}

	:global(.hero-primary-icon) {
		width: 1.75rem;
		height: 1.75rem;
		color: #E55A28;
	}

	.hero-primary-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.hero-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 600;
		color: #A1A1AA;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.hero-value {
		font-family: var(--font-display);
		font-size: 1rem;
		font-weight: 600;
		color: #E55A28;
	}

	.hero-stats {
		display: flex;
		gap: 1.5rem;
	}

	.hero-stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
	}

	.hero-stat-value {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
		color: #18181B;
		line-height: 1.1;
	}

	.hero-stat-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* =========================
	   SEGMENTS
	   ========================= */
	.segments-section {
		margin-bottom: 1rem;
	}

	.subsection-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}

	:global(.subsection-icon) {
		width: 1rem;
		height: 1rem;
		color: #E55A28;
	}

	.subsection-title {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #18181B;
	}

	.segments-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 0.75rem;
	}

	.segment-card {
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.625rem;
		padding: 1rem;
		transition: all 0.15s ease;
	}

	.segment-card:hover {
		border-color: rgba(229, 90, 40, 0.3);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
	}

	.segment-card.primary {
		border-left: 3px solid #E55A28;
	}

	.segment-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}

	.segment-name {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #18181B;
		margin: 0;
	}

	.segment-pains {
		margin-bottom: 0.75rem;
	}

	.segment-pains-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 600;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		display: block;
		margin-bottom: 0.25rem;
	}

	.pains-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.pains-list li {
		position: relative;
		padding-left: 0.75rem;
		font-size: 0.75rem;
		color: #71717A;
		line-height: 1.45;
		margin-bottom: 0.125rem;
	}

	.pains-list li::before {
		content: '•';
		position: absolute;
		left: 0;
		color: #E55A28;
	}

	.segment-meta {
		display: flex;
		gap: 0.75rem;
		padding: 0.5rem 0;
		border-top: 1px solid rgba(0, 0, 0, 0.06);
		border-bottom: 1px solid rgba(0, 0, 0, 0.06);
		margin-bottom: 0.625rem;
	}

	.meta-item {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	:global(.meta-icon) {
		width: 0.75rem;
		height: 0.75rem;
		color: #A1A1AA;
	}

	.meta-item span {
		font-size: 0.6875rem;
		color: #71717A;
	}

	.segment-channels {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
	}

	.channel-tag {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		padding: 0.125rem 0.375rem;
		background: rgba(0, 0, 0, 0.03);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.25rem;
		color: #A1A1AA;
	}

	/* =========================
	   COMMUNITIES STRIP
	   ========================= */
	.communities-strip {
		display: flex;
		align-items: center;
		gap: 0.875rem;
		padding: 0.75rem 1rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.5rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}

	.communities-label {
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	:global(.communities-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: #E55A28;
	}

	.communities-label span {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 600;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.communities-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}

	.community-tag {
		font-size: 0.75rem;
		padding: 0.25rem 0.625rem;
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 9999px;
		color: #71717A;
	}

	/* =========================
	   EXPANDABLE SECTIONS
	   ========================= */
	.expandable-section {
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.75rem;
		margin-bottom: 0.75rem;
		overflow: hidden;
	}

	.expandable-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.875rem 1rem;
		background: #FFFFFF;
		border: none;
		cursor: pointer;
		transition: background-color 0.15s;
	}

	.expandable-header:hover {
		background: rgba(0, 0, 0, 0.02);
	}

	.expandable-title {
		display: flex;
		align-items: center;
		gap: 0.625rem;
	}

	:global(.expandable-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: #E55A28;
	}

	:global(.expandable-icon.warning) {
		color: #EAB308;
	}

	:global(.expandable-icon.success) {
		color: #22C55E;
	}

	.expandable-title span {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #18181B;
	}

	:global(.chevron-icon) {
		width: 1rem;
		height: 1rem;
		color: #A1A1AA;
		transition: transform 0.2s;
	}

	:global(.chevron-icon.expanded) {
		transform: rotate(180deg);
	}

	.expandable-content {
		padding: 0 1rem 1rem;
		background: #FFFFFF;
	}

	/* Influencers Grid */
	.influencers-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.625rem;
	}

	.influencer-card {
		padding: 0.75rem;
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.5rem;
	}

	.influencer-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.375rem;
	}

	.influencer-name {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: #18181B;
	}

	.influencer-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.influencer-platform {
		font-size: 0.6875rem;
		color: #E55A28;
		font-weight: 500;
	}

	.influencer-followers {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		color: #A1A1AA;
	}

	/* Messaging Grid */
	.messaging-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 0.75rem;
	}

	.messaging-box {
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.5rem;
		padding: 0.875rem;
	}

	.messaging-box-title {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: #18181B;
		margin-bottom: 0.625rem;
	}

	:global(.box-title-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: #E55A28;
	}

	.messaging-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.messaging-item {
		display: flex;
		align-items: flex-start;
		gap: 0.125rem;
	}

	.quote-mark {
		color: #E55A28;
		font-size: 1rem;
		line-height: 1;
		font-weight: 500;
	}

	.messaging-text {
		font-size: 0.75rem;
		color: #71717A;
		line-height: 1.5;
	}

	.vocab-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}

	.vocab-tag {
		font-size: 0.6875rem;
		padding: 0.25rem 0.5rem;
		background: rgba(229, 90, 40, 0.08);
		border: 1px solid rgba(229, 90, 40, 0.2);
		border-radius: 9999px;
		color: #E55A28;
	}

	/* Tactics */
	.tactics-bg {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.04) 0%, transparent 100%);
	}

	.tactics-content {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.65;
	}

	.tactics-content :global(p) {
		margin-bottom: 0.5rem;
	}

	.tactics-content :global(p:last-child) {
		margin-bottom: 0;
	}

	/* =========================
	   RESPONSIVE
	   ========================= */
	@media (max-width: 768px) {
		.hero-strip {
			flex-direction: column;
			align-items: stretch;
			gap: 1rem;
		}

		.hero-primary {
			min-width: unset;
		}

		.hero-stats {
			justify-content: space-around;
		}

		.segments-grid {
			grid-template-columns: 1fr;
		}

		.influencers-grid {
			grid-template-columns: 1fr;
		}

		.messaging-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 480px) {
		.segment-meta {
			flex-direction: column;
			gap: 0.375rem;
		}

		.hero-stats {
			gap: 1rem;
		}
	}
</style>
