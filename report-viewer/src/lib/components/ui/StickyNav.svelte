<script lang="ts">
	import { onMount } from 'svelte';
	import {
		BarChart3,
		Lightbulb,
		Target,
		Search,
		Users,
		TrendingUp,
		DollarSign,
		Megaphone,
		Wrench,
		ArrowRight
	} from 'lucide-svelte';

	interface Section {
		id: string;
		label: string;
		icon: typeof BarChart3;
	}

	const sections: Section[] = [
		{ id: 'executive', label: 'Executive', icon: BarChart3 },
		{ id: 'solution', label: 'Solution', icon: Lightbulb },
		{ id: 'pain-points', label: 'Pain Points', icon: Target },
		{ id: 'seo', label: 'SEO', icon: Search },
		{ id: 'competitors', label: 'Competitors', icon: Users },
		{ id: 'market', label: 'Market', icon: TrendingUp },
		{ id: 'pricing', label: 'Pricing', icon: DollarSign },
		{ id: 'gtm', label: 'GTM', icon: Megaphone },
		{ id: 'technical', label: 'Technical', icon: Wrench },
		{ id: 'pain-to-solution', label: 'Journey', icon: ArrowRight }
	];

	let activeSection = $state('executive');
	let scrollProgress = $state(0);
	let isVisible = $state(false);

	onMount(() => {
		const handleScroll = () => {
			// Calculate overall scroll progress
			const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
			scrollProgress = scrollHeight > 0 ? (window.scrollY / scrollHeight) * 100 : 0;

			// Show nav after scrolling past hero
			isVisible = window.scrollY > 200;

			// Find active section
			const scrollPosition = window.scrollY + 150;

			for (let i = sections.length - 1; i >= 0; i--) {
				const element = document.getElementById(sections[i].id);
				if (element && element.offsetTop <= scrollPosition) {
					activeSection = sections[i].id;
					break;
				}
			}
		};

		window.addEventListener('scroll', handleScroll, { passive: true });
		handleScroll();

		return () => window.removeEventListener('scroll', handleScroll);
	});

	function scrollToSection(id: string) {
		const element = document.getElementById(id);
		if (element) {
			element.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}
	}
</script>

<nav class="sticky-nav" class:visible={isVisible}>
	<div class="sticky-nav-progress" style="width: {scrollProgress}%"></div>

	<div class="sticky-nav-content">
		<div class="sticky-nav-items">
			{#each sections as section}
				{@const SectionIcon = section.icon}
				<button
					class="sticky-nav-item"
					class:active={activeSection === section.id}
					onclick={() => scrollToSection(section.id)}
					aria-label="Go to {section.label} section"
				>
					<SectionIcon class="w-4 h-4" />
					<span class="sticky-nav-label">{section.label}</span>
				</button>
			{/each}
		</div>
	</div>
</nav>

<style>
	.sticky-nav {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 50;
		background: rgba(8, 8, 10, 0.95);
		backdrop-filter: blur(12px);
		border-bottom: 1px solid var(--color-border);
		transform: translateY(-100%);
		transition: transform 0.3s var(--ease-out);
	}

	.sticky-nav.visible {
		transform: translateY(0);
	}

	.sticky-nav-progress {
		position: absolute;
		top: 0;
		left: 0;
		height: 2px;
		background: linear-gradient(90deg, var(--color-accent), var(--color-accent-light));
		transition: width 0.1s linear;
	}

	.sticky-nav-content {
		max-width: 1400px;
		margin: 0 auto;
		padding: 0.5rem 1rem;
	}

	.sticky-nav-items {
		display: flex;
		gap: 0.25rem;
		overflow-x: auto;
		scrollbar-width: none;
		-ms-overflow-style: none;
	}

	.sticky-nav-items::-webkit-scrollbar {
		display: none;
	}

	.sticky-nav-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		font-family: var(--font-body);
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--color-text-muted);
		background: transparent;
		border: 1px solid transparent;
		border-radius: 6px;
		cursor: pointer;
		white-space: nowrap;
		transition: all 0.2s ease;
	}

	.sticky-nav-item:hover {
		color: var(--color-text-secondary);
		background: var(--color-bg-hover);
	}

	.sticky-nav-item.active {
		color: var(--color-accent);
		background: rgba(245, 158, 11, 0.1);
		border-color: rgba(245, 158, 11, 0.3);
	}

	.sticky-nav-label {
		display: none;
	}

	@media (min-width: 768px) {
		.sticky-nav-item {
			padding: 0.5rem 1rem;
		}

		.sticky-nav-label {
			display: inline;
		}
	}

	@media (min-width: 1024px) {
		.sticky-nav-items {
			justify-content: center;
		}
	}
</style>
