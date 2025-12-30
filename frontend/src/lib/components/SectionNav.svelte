<script lang="ts">
	import { BarChart3, Sparkles, Target, Search, Users, DollarSign, Briefcase, Code, TrendingUp, Lightbulb, UserCheck, MessageSquare, FileText, Database } from 'lucide-svelte';
	import type { Report } from '$lib/types/report';

	interface Section {
		id: string;
		label: string;
		icon: typeof BarChart3;
	}

	interface Props {
		report?: Report | null;
	}

	let { report = null }: Props = $props();

	// Sections ordered by the consolidated 7-tier architecture (15 sections total)
	const allSections: Section[] = [
		// Tier 1: Decision (2)
		{ id: 'executive', label: 'Executive', icon: BarChart3 },
		{ id: 'solution', label: 'Solution', icon: Sparkles },
		// Tier 2: Problem Analysis (2)
		{ id: 'pain-analysis', label: 'Pain Analysis', icon: Target },
		{ id: 'content-insights', label: 'Content', icon: MessageSquare },
		// Tier 3: Technical (2)
		{ id: 'technical', label: 'Technical', icon: Code },
		{ id: 'seo', label: 'SEO', icon: Search },
		// Tier 4: Viability (1)
		{ id: 'monetization', label: 'Monetization', icon: DollarSign },
		// Tier 5: Market (4)
		{ id: 'market-sizing', label: 'Market', icon: DollarSign },
		{ id: 'competitors', label: 'Competitors', icon: Users },
		{ id: 'trends', label: 'Trends', icon: TrendingUp },
		{ id: 'audience', label: 'Audience', icon: UserCheck },
		// Tier 6: Execution (2)
		{ id: 'gtm-playbook', label: 'GTM', icon: Briefcase },
		{ id: 'data-infrastructure', label: 'Data', icon: Database },
		// Tier 7: Reference (2)
		{ id: 'alternatives', label: 'Alternatives', icon: Lightbulb },
		{ id: 'research-metadata', label: 'Research', icon: FileText }
	];

	// Filter sections based on report data availability
	const sections = $derived.by(() => {
		if (!report) return allSections;

		return allSections.filter(section => {
			switch (section.id) {
				case 'solution': return !!report.executive_dashboard;
				case 'pain-analysis': return (report.detailed_pain_points?.length ?? 0) > 0;
				case 'content-insights': return !!report.content_categorization || !!report.overall_competitive_insights;
				case 'seo': return !!report.seo_strategy_report;
				case 'monetization': return !!report.pricing_strategy || !!report.traffic_monetization;
				case 'competitors': return !!report.competitive_analytics;
				case 'trends': return !!report.trend_longevity;
				case 'audience': return !!report.audience_mapping;
				case 'gtm-playbook': return !!report.go_to_market_blueprint;
				case 'data-infrastructure': return !!report.data_source_research_full;
				case 'alternatives': return (report.alternative_solutions?.length ?? 0) > 0;
				case 'research-metadata': return !!report.research_metadata;
				default: return true; // Always visible: executive, technical, market-sizing
			}
		});
	});

	let activeSection = $state('executive');
	let scrollProgress = $state(0);
	let isOpen = $state(false);

	function scrollToSection(id: string) {
		const element = document.getElementById(id);
		if (element) {
			element.scrollIntoView({ behavior: 'smooth', block: 'start' });
			isOpen = false;
		}
	}

	$effect(() => {
		if (typeof window === 'undefined') return;

		const handleScroll = () => {
			// Calculate scroll progress
			const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
			scrollProgress = Math.min(window.scrollY / scrollHeight, 1);

			// Find active section
			const sectionElements = sections
				.map((s) => ({ id: s.id, el: document.getElementById(s.id) }))
				.filter((s) => s.el !== null);

			for (let i = sectionElements.length - 1; i >= 0; i--) {
				const section = sectionElements[i];
				if (section.el) {
					const rect = section.el.getBoundingClientRect();
					if (rect.top <= 150) {
						activeSection = section.id;
						break;
					}
				}
			}
		};

		window.addEventListener('scroll', handleScroll, { passive: true });
		handleScroll(); // Initial check

		return () => window.removeEventListener('scroll', handleScroll);
	});
</script>

<!-- Desktop Sidebar -->
<nav class="section-nav-desktop">
	<!-- Progress bar -->
	<div class="nav-progress-track">
		<div class="nav-progress-fill" style:height="{scrollProgress * 100}%"></div>
	</div>

	<div class="nav-items">
		{#each sections as section}
			{@const Icon = section.icon}
			<button
				class="nav-item"
				class:active={activeSection === section.id}
				onclick={() => scrollToSection(section.id)}
				title={section.label}
			>
				<Icon class="w-4 h-4" />
				<span class="nav-item-label">{section.label}</span>
			</button>
		{/each}
	</div>
</nav>

<!-- Mobile Bottom Bar -->
<nav class="section-nav-mobile" class:open={isOpen}>
	<!-- Toggle button -->
	<button class="nav-mobile-toggle" onclick={() => (isOpen = !isOpen)}>
		<div class="nav-mobile-progress">
			<div class="nav-mobile-progress-fill" style:width="{scrollProgress * 100}%"></div>
		</div>
		<span class="nav-mobile-current">
			{sections.find((s) => s.id === activeSection)?.label || 'Navigate'}
		</span>
	</button>

	<!-- Expanded menu -->
	{#if isOpen}
		<div class="nav-mobile-menu">
			{#each sections as section}
				{@const Icon = section.icon}
				<button
					class="nav-mobile-item"
					class:active={activeSection === section.id}
					onclick={() => scrollToSection(section.id)}
				>
					<Icon class="w-4 h-4" />
					<span>{section.label}</span>
				</button>
			{/each}
		</div>
	{/if}
</nav>

<style>
	/* Desktop Navigation */
	.section-nav-desktop {
		position: fixed;
		left: 1rem;
		top: 50%;
		transform: translateY(-50%);
		z-index: 100;
		display: none;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.75rem;
		background: rgba(15, 15, 18, 0.9);
		backdrop-filter: blur(12px);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
	}

	@media (min-width: 1280px) {
		.section-nav-desktop {
			display: flex;
		}
	}

	.nav-progress-track {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 3px;
		background: var(--color-bg-surface);
		border-radius: 2px;
		overflow: hidden;
	}

	.nav-progress-fill {
		width: 100%;
		background: var(--color-accent);
		border-radius: 2px;
		transition: height 0.1s linear;
	}

	.nav-items {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding-left: 0.75rem;
	}

	.nav-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: transparent;
		border: none;
		border-radius: 0.5rem;
		color: var(--color-text-muted);
		font-size: 0.75rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s ease;
		white-space: nowrap;
	}

	.nav-item:hover {
		color: var(--color-text-primary);
		background: var(--color-bg-hover);
	}

	.nav-item.active {
		color: var(--color-accent);
		background: rgba(245, 158, 11, 0.1);
	}

	.nav-item-label {
		opacity: 0;
		max-width: 0;
		overflow: hidden;
		transition: all 0.2s ease;
	}

	.section-nav-desktop:hover .nav-item-label {
		opacity: 1;
		max-width: 100px;
		margin-left: 0.25rem;
	}

	/* Mobile Navigation */
	.section-nav-mobile {
		position: fixed;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		z-index: 100;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	@media (min-width: 1280px) {
		.section-nav-mobile {
			display: none;
		}
	}

	.nav-mobile-toggle {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
		padding: 0.75rem 1.5rem;
		background: rgba(15, 15, 18, 0.95);
		backdrop-filter: blur(12px);
		border: 1px solid var(--color-border);
		border-radius: 2rem;
		color: var(--color-text-primary);
		font-size: 0.75rem;
		font-weight: 600;
		cursor: pointer;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
	}

	.nav-mobile-progress {
		width: 100px;
		height: 3px;
		background: var(--color-bg-surface);
		border-radius: 2px;
		overflow: hidden;
	}

	.nav-mobile-progress-fill {
		height: 100%;
		background: var(--color-accent);
		border-radius: 2px;
		transition: width 0.1s linear;
	}

	.nav-mobile-current {
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.nav-mobile-menu {
		position: absolute;
		bottom: 100%;
		left: 50%;
		transform: translateX(-50%);
		margin-bottom: 0.5rem;
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0.25rem;
		padding: 0.5rem;
		background: rgba(15, 15, 18, 0.95);
		backdrop-filter: blur(12px);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
		animation: slideUp 0.2s ease;
	}

	@keyframes slideUp {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}

	.nav-mobile-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.625rem 0.875rem;
		background: transparent;
		border: none;
		border-radius: 0.5rem;
		color: var(--color-text-muted);
		font-size: 0.75rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s ease;
		white-space: nowrap;
	}

	.nav-mobile-item:hover {
		color: var(--color-text-primary);
		background: var(--color-bg-hover);
	}

	.nav-mobile-item.active {
		color: var(--color-accent);
		background: rgba(245, 158, 11, 0.1);
	}
</style>
