<script lang="ts">
	import { BarChart3, Sparkles, Target, Search, Users, DollarSign, Briefcase, Code, TrendingUp, Lightbulb, UserCheck, MessageSquare, FileText, Database, ClipboardList, Check } from 'lucide-svelte';
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

	// Sections ordered by UX-optimized decision workflow (16 sections total)
	const allSections: Section[] = [
		// Decision Gateway (Go/No-Go)
		{ id: 'executive', label: 'Executive', icon: BarChart3 },
		{ id: 'solution', label: 'Solution', icon: Sparkles },
		// Customer & Problem (Who & Why)
		{ id: 'audience', label: 'Audience', icon: UserCheck },
		{ id: 'pain-analysis', label: 'Pain Points', icon: Target },
		{ id: 'content-insights', label: 'Content', icon: MessageSquare },
		// Market Viability (Is It Worth It?)
		{ id: 'market-sizing', label: 'Market', icon: DollarSign },
		{ id: 'monetization', label: 'Monetization', icon: DollarSign },
		{ id: 'competitors', label: 'Competitors', icon: Users },
		{ id: 'trends', label: 'Trends', icon: TrendingUp },
		// Build Specification (How)
		{ id: 'technical', label: 'Technical', icon: Code },
		{ id: 'seo', label: 'SEO', icon: Search },
		// Execution (Launch)
		{ id: 'gtm-playbook', label: 'GTM', icon: Briefcase },
		{ id: 'data-infrastructure', label: 'Data', icon: Database },
		// Reference (Appendix)
		{ id: 'alternatives', label: 'Alternatives', icon: Lightbulb },
		{ id: 'evidence-appendix', label: 'Evidence', icon: ClipboardList },
		{ id: 'research-metadata', label: 'Research', icon: FileText }
	];

	// Filter sections based on report data availability
	const sections = $derived.by(() => {
		if (!report) return allSections;

		return allSections.filter(section => {
			switch (section.id) {
				case 'solution': return !!report.executive_dashboard;
				case 'audience': return !!report.audience_mapping;
				case 'pain-analysis': return (report.detailed_pain_points?.length ?? 0) > 0;
				case 'content-insights': return !!report.content_categorization || !!report.overall_competitive_insights;
				case 'monetization': return !!report.pricing_strategy || !!report.traffic_monetization;
				case 'competitors': return !!report.competitive_analytics;
				case 'trends': return !!report.trend_longevity;
				case 'seo': return !!report.seo_strategy_report;
				case 'gtm-playbook': return !!report.go_to_market_blueprint;
				case 'data-infrastructure': return !!report.data_source_research_full;
				case 'alternatives': return (report.alternative_solutions?.length ?? 0) > 0;
				case 'evidence-appendix': return !!report.evidence_appendix;
				case 'research-metadata': return !!report.research_metadata;
				default: return true; // Always visible: executive, market-sizing, technical
			}
		});
	});

	let activeSection = $state('executive');
	let scrollProgress = $state(0);
	let isOpen = $state(false);
	let viewedSections = $state<Set<string>>(new Set(['executive']));

	// Progress tracking
	const viewedCount = $derived(viewedSections.size);
	const totalCount = $derived(sections.length);
	const progressPercentage = $derived(Math.round((viewedCount / totalCount) * 100));

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

			// Find active section and track viewed sections
			const sectionElements = sections
				.map((s) => ({ id: s.id, el: document.getElementById(s.id) }))
				.filter((s) => s.el !== null);

			for (let i = sectionElements.length - 1; i >= 0; i--) {
				const section = sectionElements[i];
				if (section.el) {
					const rect = section.el.getBoundingClientRect();
					if (rect.top <= 150) {
						activeSection = section.id;
						// Mark as viewed when scrolled into view
						if (!viewedSections.has(section.id)) {
							viewedSections = new Set([...viewedSections, section.id]);
						}
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
	<!-- Progress header -->
	<div class="nav-progress-header">
		<span class="nav-progress-text">{viewedCount}/{totalCount}</span>
		<span class="nav-progress-label">sections</span>
	</div>

	<!-- Progress bar -->
	<div class="nav-progress-track">
		<div class="nav-progress-fill" style:height="{scrollProgress * 100}%"></div>
	</div>

	<div class="nav-items">
		{#each sections as section}
			{@const Icon = section.icon}
			{@const isViewed = viewedSections.has(section.id)}
			{@const isActive = activeSection === section.id}
			<button
				class="nav-item"
				class:active={isActive}
				class:viewed={isViewed && !isActive}
				onclick={() => scrollToSection(section.id)}
				title={section.label}
			>
				{#if isViewed && !isActive}
					<div class="nav-item-check">
						<Check class="w-3 h-3" />
					</div>
				{/if}
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
		<div class="nav-mobile-header">
			<span class="nav-mobile-progress-count">{viewedCount}/{totalCount}</span>
			<div class="nav-mobile-progress">
				<div class="nav-mobile-progress-fill" style:width="{scrollProgress * 100}%"></div>
			</div>
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
				{@const isViewed = viewedSections.has(section.id)}
				{@const isActive = activeSection === section.id}
				<button
					class="nav-mobile-item"
					class:active={isActive}
					class:viewed={isViewed && !isActive}
					onclick={() => scrollToSection(section.id)}
				>
					{#if isViewed && !isActive}
						<Check class="w-3 h-3 check-icon" />
					{:else}
						<Icon class="w-4 h-4" />
					{/if}
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
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(12px);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		box-shadow: var(--shadow-md);
	}

	@media (min-width: 1280px) {
		.section-nav-desktop {
			display: flex;
		}
	}

	.nav-progress-header {
		display: flex;
		align-items: baseline;
		gap: 0.25rem;
		padding: 0 0.5rem 0.5rem;
		margin-bottom: 0.25rem;
		border-bottom: 1px solid var(--color-border);
	}

	.nav-progress-text {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-accent);
	}

	.nav-progress-label {
		font-size: 0.625rem;
		color: var(--color-text-muted);
	}

	.nav-progress-track {
		position: absolute;
		left: 0;
		top: 3.5rem;
		bottom: 0.75rem;
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
		position: relative;
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
		background: var(--color-accent-subtle);
	}

	.nav-item.viewed {
		color: var(--color-success-dark);
	}

	.nav-item-check {
		position: absolute;
		left: -0.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1rem;
		height: 1rem;
		background: rgba(34, 197, 94, 0.15);
		border-radius: 50%;
		color: var(--color-success);
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
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(12px);
		border: 1px solid var(--color-border);
		border-radius: 2rem;
		color: var(--color-text-primary);
		font-size: 0.75rem;
		font-weight: 600;
		cursor: pointer;
		box-shadow: var(--shadow-md);
	}

	.nav-mobile-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.nav-mobile-progress-count {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 600;
		color: var(--color-accent);
	}

	.nav-mobile-progress {
		width: 60px;
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
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(12px);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		box-shadow: var(--shadow-lg);
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
		background: var(--color-accent-subtle);
	}

	.nav-mobile-item.viewed {
		color: var(--color-success-dark);
	}

	.nav-mobile-item :global(.check-icon) {
		color: var(--color-success);
	}
</style>
