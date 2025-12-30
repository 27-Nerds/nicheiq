<script lang="ts">
	import { Rocket, User, MessageSquare, Calendar, Target, Zap, Lightbulb, CheckCircle, ArrowRight } from 'lucide-svelte';
	import type { GoToMarketBlueprint } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		gtmData: GoToMarketBlueprint;
		nextSteps?: string | string[];
	}

	let { gtmData, nextSteps }: Props = $props();

	const icp = $derived(gtmData.ideal_customer_profile);
	const playbook = $derived(gtmData.first_30_days_playbook);

	// Parse next steps - could be string or array
	const steps = $derived.by(() => {
		if (!nextSteps) return [];
		if (Array.isArray(nextSteps)) {
			return nextSteps;
		}
		if (typeof nextSteps === 'string') {
			// Check if it's a numbered list (1. item, 2. item, etc.)
			const numberedListPattern = /^\d+\.\s/m;
			if (numberedListPattern.test(nextSteps)) {
				return nextSteps.split(/\n/).filter(line => line.trim() && /^\d+\./.test(line.trim())).map(line => line.replace(/^\d+\.\s*/, '').trim());
			}
			// Check if it's a bullet list
			const bulletListPattern = /^[-•*]\s/m;
			if (bulletListPattern.test(nextSteps)) {
				return nextSteps.split(/\n/).filter(line => line.trim() && /^[-•*]/.test(line.trim())).map(line => line.replace(/^[-•*]\s*/, '').trim());
			}
			// Just return as single item if no list format detected
			return [nextSteps];
		}
		return [];
	});
</script>

<section id="gtm-playbook" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<Rocket class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Go-to-Market Playbook</h2>
	</div>

	<!-- Core Marketing Message -->
	<div class="highlight-box mb-8">
		<h3 class="text-lg font-semibold text-accent mb-3">Core Marketing Message</h3>
		<p class="text-xl text-text-primary font-medium">{gtmData.core_marketing_message}</p>
		{#if gtmData.message_framework}
			<div class="markdown-content narrative mt-4">
				{@html renderMarkdown(gtmData.message_framework)}
			</div>
		{/if}
	</div>

	<!-- Budget Estimate -->
	<div class="mb-8 text-center">
		<span class="text-text-muted">Estimated Budget:</span>
		<span class="text-xl font-semibold text-accent ml-2">{gtmData.budget_estimate}</span>
	</div>

	<!-- Ideal Customer Profile -->
	<AnimateOnScroll animation="fade-up">
		<div class="card mb-8">
			<div class="flex items-center gap-3 mb-4">
				<User class="w-5 h-5 text-accent" />
				<h3 class="text-lg font-semibold text-text-primary">Ideal Customer Profile</h3>
			</div>

			<div class="mb-4">
				<h4 class="text-lg font-semibold text-accent">{icp.persona_name}</h4>
			</div>

			<div class="grid md:grid-cols-2 gap-6 items-start">
				<div>
					<h5 class="text-sm font-semibold text-text-muted mb-2">Demographics</h5>
					<p class="text-text-secondary text-sm leading-relaxed">{icp.demographics}</p>
				</div>
				<div>
					<h5 class="text-sm font-semibold text-text-muted mb-2">Psychographics</h5>
					<p class="text-text-secondary text-sm leading-relaxed">{icp.psychographics}</p>
				</div>
			</div>

			{#if icp.pain_points && icp.pain_points.length > 0}
				<div class="mt-4 pt-4 border-t border-border">
					<h5 class="text-sm font-semibold text-text-muted mb-2">Pain Points</h5>
					<ul class="space-y-1">
						{#each icp.pain_points as point}
							<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
								<Target class="w-3 h-3 text-error shrink-0 mt-1" />
								{point}
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			{#if icp.goals && icp.goals.length > 0}
				<div class="mt-4 pt-4 border-t border-border">
					<h5 class="text-sm font-semibold text-text-muted mb-2">Goals</h5>
					<ul class="space-y-1">
						{#each icp.goals.slice(0, 5) as goal}
							<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
								<Zap class="w-3 h-3 text-success shrink-0 mt-1" />
								{goal}
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			<div class="mt-4 pt-4 border-t border-border grid md:grid-cols-2 gap-4 items-start">
				<div>
					<h5 class="text-sm font-semibold text-text-muted mb-1">Buying Triggers</h5>
					<p class="text-sm text-text-secondary leading-relaxed">{icp.buying_triggers}</p>
				</div>
				<div>
					<h5 class="text-sm font-semibold text-text-muted mb-1">Decision Criteria</h5>
					<p class="text-sm text-text-secondary leading-relaxed">{icp.decision_criteria}</p>
				</div>
			</div>
		</div>
	</AnimateOnScroll>

	<!-- Recommended Channels -->
	{#if gtmData.recommended_channels && gtmData.recommended_channels.length > 0}
		<AnimateOnScroll animation="fade-up" delay={100}>
			<div class="mb-8">
				<h3 class="text-lg font-semibold text-text-primary mb-4">Recommended Channels</h3>
				<div class="grid md:grid-cols-2 gap-4">
					{#each gtmData.recommended_channels as channel}
						<div class="card-surface {channel.priority === 'High' ? 'priority-high' : channel.priority === 'Medium' ? 'priority-medium' : 'priority-low'}">
							<div class="flex items-center justify-between mb-2">
								<h4 class="font-semibold text-text-primary">{channel.channel_name}</h4>
								<Badge variant={channel.priority === 'High' ? 'success' : channel.priority === 'Medium' ? 'warning' : 'muted'}>
									{channel.priority}
								</Badge>
							</div>
							<Badge class="mb-3" size="sm">{channel.channel_type}</Badge>
							<p class="text-sm text-text-muted mb-2">{channel.target_audience_size}</p>
							<div class="prose-narrative text-sm mb-3">{channel.rationale}</div>
							<div class="pt-3 border-t border-border">
								<h5 class="text-xs font-semibold text-text-muted mb-1">Strategy</h5>
								<div class="prose-narrative text-sm">{channel.strategy}</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Content Angles -->
	{#if gtmData.example_content_angles && gtmData.example_content_angles.length > 0}
		<AnimateOnScroll animation="fade-up" delay={150}>
			<div class="mb-8">
				<h3 class="text-lg font-semibold text-text-primary mb-4">Content Angles</h3>
				<div class="space-y-4">
					{#each gtmData.example_content_angles as angle}
						<div class="card-surface">
							<div class="flex items-center gap-2 mb-2">
								<Badge size="sm">{angle.content_type}</Badge>
								<span class="text-xs text-text-muted">{angle.target_channel}</span>
							</div>
							<h4 class="font-semibold text-text-primary mb-2">{angle.title}</h4>
							<p class="text-sm text-accent mb-3">{angle.hook}</p>
							{#if angle.key_points && angle.key_points.length > 0}
								<ul class="space-y-1">
									{#each angle.key_points as point}
										<li class="text-sm text-text-secondary leading-relaxed">• {point}</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- 30-Day Playbook -->
	<AnimateOnScroll animation="fade-up" delay={200}>
		<div class="mb-8">
			<div class="flex items-center gap-3 mb-4">
				<Calendar class="w-5 h-5 text-accent" />
				<h3 class="text-lg font-semibold text-text-primary">First 30 Days Playbook</h3>
			</div>

			<div class="grid md:grid-cols-2 gap-4">
				<!-- Week 1 -->
				<div class="playbook-week">
					<h4>Week 1</h4>
					<ul class="space-y-2">
						{#each playbook.week_1_actions as action}
							<li class="text-sm text-text-secondary leading-relaxed">• {action}</li>
						{/each}
					</ul>
				</div>

				<!-- Week 2 -->
				<div class="playbook-week">
					<h4>Week 2</h4>
					<ul class="space-y-2">
						{#each playbook.week_2_actions as action}
							<li class="text-sm text-text-secondary leading-relaxed">• {action}</li>
						{/each}
					</ul>
				</div>

				<!-- Week 3 -->
				<div class="playbook-week">
					<h4>Week 3</h4>
					<ul class="space-y-2">
						{#each playbook.week_3_actions as action}
							<li class="text-sm text-text-secondary leading-relaxed">• {action}</li>
						{/each}
					</ul>
				</div>

				<!-- Week 4 -->
				<div class="playbook-week">
					<h4>Week 4</h4>
					<ul class="space-y-2">
						{#each playbook.week_4_actions as action}
							<li class="text-sm text-text-secondary leading-relaxed">• {action}</li>
						{/each}
					</ul>
				</div>
			</div>
		</div>
	</AnimateOnScroll>

	<!-- Success Metrics -->
	{#if playbook.success_metrics && playbook.success_metrics.length > 0}
		<AnimateOnScroll animation="fade-up" delay={250}>
			<div class="card mb-8">
				<h3 class="text-lg font-semibold text-text-primary mb-4">Success Metrics</h3>
				<ul class="space-y-2">
					{#each playbook.success_metrics as metric}
						<li class="text-text-secondary leading-relaxed flex items-start gap-2">
							<Target class="w-4 h-4 text-success shrink-0 mt-1" />
							{metric}
						</li>
					{/each}
				</ul>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Implementation Checklist (from NextSteps) -->
	{#if nextSteps && (steps.length > 0 || typeof nextSteps === 'string')}
		<AnimateOnScroll animation="fade-up" delay={300}>
			<div class="card border-t-2 border-accent">
				<div class="flex items-center gap-3 mb-4">
					<Lightbulb class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Implementation Checklist</h3>
				</div>

				{#if steps.length > 1}
					<!-- Display as numbered checklist -->
					<div class="space-y-4">
						{#each steps as step, i}
							<div class="flex items-start gap-4 p-4 rounded-lg bg-surface-secondary/30 hover:bg-surface-secondary/50 transition-colors">
								<div class="flex-shrink-0 w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center">
									<span class="text-sm font-bold text-accent">{i + 1}</span>
								</div>
								<div class="flex-1">
									<div class="text-text-primary leading-relaxed">{step}</div>
								</div>
								<ArrowRight class="w-4 h-4 text-text-muted flex-shrink-0 mt-1" />
							</div>
						{/each}
					</div>
				{:else if steps.length === 1}
					<!-- Display as markdown content -->
					<div class="markdown-content narrative">
						{@html renderMarkdown(steps[0])}
					</div>
				{:else if typeof nextSteps === 'string'}
					<!-- Fallback: render as markdown -->
					<div class="markdown-content narrative">
						{@html renderMarkdown(nextSteps)}
					</div>
				{/if}
			</div>
		</AnimateOnScroll>
	{/if}
</section>
