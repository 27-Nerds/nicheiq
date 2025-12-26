<script lang="ts">
	import { Users, UserCheck, MessageSquare, Hash, Star } from 'lucide-svelte';
	import type { AudienceMapping } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		data: AudienceMapping;
	}

	let { data }: Props = $props();

	// Map segment size to badge variant
	const getSizeVariant = (size: string | undefined) => {
		const s = size?.toLowerCase() || '';
		if (s.includes('large')) return 'success';
		if (s.includes('medium')) return 'warning';
		return 'muted';
	};
</script>

<section id="audience" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<Users class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Audience Intelligence</h2>
	</div>

	<!-- Primary Target Segment -->
	{#if data.primary_target_segment}
		<AnimateOnScroll animation="fade-up">
			<div class="highlight-box mb-8">
				<div class="flex items-center gap-3">
					<UserCheck class="w-5 h-5 text-accent" />
					<div>
						<span class="text-text-muted">Primary Target:</span>
						<span class="text-lg font-semibold text-accent ml-2">{data.primary_target_segment}</span>
					</div>
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Audience Segments Grid -->
	{#if data.audience_segments && data.audience_segments.length > 0}
		<div class="mb-8">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Audience Segments</h3>
			<div class="grid md:grid-cols-2 gap-4">
				{#each data.audience_segments as segment}
					<AnimateOnScroll animation="fade-up">
						<div class="card h-full">
							<div class="flex items-center justify-between mb-3">
								<h4 class="font-semibold text-text-primary">{segment.segment_name}</h4>
								{#if segment.size_estimate}
									<Badge variant={getSizeVariant(segment.size_estimate)}>{segment.size_estimate}</Badge>
								{/if}
							</div>

							{#if segment.pain_point_alignment && segment.pain_point_alignment.length > 0}
								<div class="mb-3">
									<div class="text-xs text-text-muted mb-2">Pain Point Alignment</div>
									<ul class="space-y-1">
										{#each segment.pain_point_alignment.slice(0, 3) as painPoint}
											<li class="text-xs text-text-secondary flex items-start gap-1">
												<span class="text-accent">•</span>
												{painPoint}
											</li>
										{/each}
									</ul>
								</div>
							{/if}

							<div class="space-y-2 text-sm">
								{#if segment.expertise_level}
									<div class="flex justify-between">
										<span class="text-text-muted">Expertise:</span>
										<span class="text-text-primary">{segment.expertise_level}</span>
									</div>
								{/if}
								{#if segment.budget_sensitivity}
									<div class="flex justify-between">
										<span class="text-text-muted">Budget Sensitivity:</span>
										<span class="text-text-primary">{segment.budget_sensitivity}</span>
									</div>
								{/if}
							</div>

							{#if segment.discovery_channels && segment.discovery_channels.length > 0}
								<div class="mt-3 pt-3 border-t border-border">
									<div class="text-xs text-text-muted mb-2">Discovery Channels</div>
									<div class="flex flex-wrap gap-1">
										{#each segment.discovery_channels as channel}
											<span class="text-xs px-2 py-0.5 rounded bg-bg-surface border border-border text-text-muted">{channel}</span>
										{/each}
									</div>
								</div>
							{/if}

							{#if segment.motivation_drivers && segment.motivation_drivers.length > 0}
								<div class="mt-3 pt-3 border-t border-border">
									<div class="text-xs text-text-muted mb-2">Motivation Drivers</div>
									<ul class="space-y-1">
										{#each segment.motivation_drivers.slice(0, 3) as driver}
											<li class="text-xs text-text-secondary flex items-start gap-1">
												<span class="text-accent">•</span>
												{driver}
											</li>
										{/each}
									</ul>
								</div>
							{/if}
						</div>
					</AnimateOnScroll>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Key Influencers -->
	{#if data.key_influencers && data.key_influencers.length > 0}
		<div class="card mb-8">
			<div class="flex items-center gap-2 mb-4">
				<Star class="w-5 h-5 text-accent" />
				<h3 class="text-lg font-semibold text-text-primary">Key Influencers</h3>
				<Badge>{data.key_influencers.length} identified</Badge>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-border">
							<th class="text-left py-2 text-text-muted font-medium">Name</th>
							<th class="text-left py-2 text-text-muted font-medium">Platform</th>
							<th class="text-right py-2 text-text-muted font-medium">Followers</th>
							<th class="text-center py-2 text-text-muted font-medium">Priority</th>
						</tr>
					</thead>
					<tbody>
						{#each data.key_influencers as influencer}
							<tr class="border-b border-border/50 hover:bg-bg-surface/50 transition-colors">
								<td class="py-2 text-text-primary font-medium">{influencer.name}</td>
								<td class="py-2 text-text-secondary">{influencer.platform}</td>
								<td class="py-2 text-right text-text-secondary">
									{influencer.follower_estimate?.toLocaleString() ?? '-'}
								</td>
								<td class="py-2 text-center">
									<Badge variant={influencer.outreach_priority === 'High' ? 'success' : influencer.outreach_priority === 'Medium' ? 'warning' : 'muted'}>
										{influencer.outreach_priority ?? 'N/A'}
									</Badge>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- Messaging & Communication -->
	<div class="grid md:grid-cols-2 gap-6 items-start">
		<!-- Messaging Frameworks -->
		{#if data.messaging_frameworks && data.messaging_frameworks.length > 0}
			<div class="card">
				<div class="flex items-center gap-2 mb-4">
					<MessageSquare class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Messaging Frameworks</h3>
				</div>
				<ul class="space-y-2">
					{#each data.messaging_frameworks as msg}
						<li class="text-text-secondary text-sm leading-relaxed flex items-start gap-2">
							<span class="text-accent">"</span>
							{msg}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Common Vocabulary -->
		{#if data.common_vocabulary && data.common_vocabulary.length > 0}
			<div class="card">
				<div class="flex items-center gap-2 mb-4">
					<Hash class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Common Vocabulary</h3>
				</div>
				<div class="flex flex-wrap gap-2">
					{#each data.common_vocabulary as term}
						<span class="text-sm px-3 py-1 rounded-full bg-accent/10 border border-accent/30 text-accent">{term}</span>
					{/each}
				</div>
			</div>
		{/if}
	</div>

	<!-- Community Hubs -->
	{#if data.community_hubs && data.community_hubs.length > 0}
		<div class="card mt-6">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Community Hubs</h3>
			<div class="flex flex-wrap gap-2">
				{#each data.community_hubs as hub}
					<span class="text-sm px-3 py-1 rounded bg-bg-surface border border-border text-text-secondary">{hub}</span>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Early Adopter Tactics -->
	{#if data.early_adopter_tactics}
		<div class="card mt-6">
			<h3 class="text-lg font-semibold text-success mb-4">Early Adopter Tactics</h3>
			<div class="markdown-content narrative text-text-secondary text-sm">
				{@html renderMarkdown(data.early_adopter_tactics)}
			</div>
		</div>
	{/if}
</section>
