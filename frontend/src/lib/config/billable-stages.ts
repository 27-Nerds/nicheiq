import { Radar, ScrollText, FileText, Lightbulb, BookOpen } from 'lucide-svelte';
import type { ComponentType } from 'svelte';
import type { BillableStageName } from '$lib/types/job';

export interface BillableStageInfo {
	key: BillableStageName;
	label: string;
	icon: ComponentType;
	description: string;
	tier: 'core' | 'addon';
}

/** Icons match the landing page HowItWorks.svelte for visual consistency */
export const BILLABLE_STAGES: BillableStageInfo[] = [
	{
		key: 'discovery',
		label: 'Discovery',
		icon: Radar,
		description: 'Validate your niche, uncover pain points, map audience, and generate solution ideas',
		tier: 'core',
	},
	{
		key: 'deep_research',
		label: 'Deep Research',
		icon: ScrollText,
		description: 'SEO playbook, pricing analysis, traffic potential, market sizing, and full report',
		tier: 'core',
	},
	{
		key: 'landing_page',
		label: 'Landing Page',
		icon: FileText,
		description: 'AI-ready landing page with copy, structure, and conversion-optimized layout',
		tier: 'addon',
	},
	{
		key: 'regenerate_ideas',
		label: 'New Ideas',
		icon: Lightbulb,
		description: 'Get fresh solution ideas and explore more angles on your niche',
		tier: 'addon',
	},
];

export const STAGE_MAP = Object.fromEntries(
	BILLABLE_STAGES.map((s) => [s.key, s])
) as Record<BillableStageName, BillableStageInfo>;

/** Icon for the final research report — reusable across job page, report page, etc. */
export const REPORT_ICON = BookOpen;

export const CORE_STAGES = BILLABLE_STAGES.filter((s) => s.tier === 'core');
export const ADDON_STAGES = BILLABLE_STAGES.filter((s) => s.tier === 'addon');
