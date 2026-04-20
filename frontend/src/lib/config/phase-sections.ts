import type { ComponentType } from 'svelte';
import {
  BarChart3,
  Rocket,
  Flame,
  DollarSign,
  Coins,
  TrendingUp,
  Swords,
  UserCheck,
  MessageSquare,
  Briefcase,
  Search,
  Code,
  Database,
  GitFork,
  ClipboardList,
  Compass,
  AlertTriangle,
  Users,
  Globe,
  Lightbulb,
  FileText,
} from 'lucide-svelte';

export interface SectionConfig {
  id: string;
  label: string;
  icon?: ComponentType;
}

export interface PhaseConfig {
  id: string;
  label: string;
  badgeLabel: string;
  badgeColor: 'success' | 'secondary';
  sections: SectionConfig[];
}

export const DISCOVERY_SECTIONS: SectionConfig[] = [
  { id: 'overview', label: 'Overview', icon: Compass },
  { id: 'opportunities', label: 'Opportunities', icon: Lightbulb },
  { id: 'pain-points', label: 'Pain Points', icon: AlertTriangle },
  { id: 'audience', label: 'Audience', icon: Users },
  { id: 'community', label: 'Community', icon: Globe },
];

export const DEEP_RESEARCH_SECTIONS: SectionConfig[] = [
  { id: 'unified-hero', label: 'Executive', icon: BarChart3 },
  { id: 'solution', label: 'Solution', icon: Rocket },
  { id: 'pain-analysis', label: 'Pain Points', icon: Flame },
  { id: 'market-sizing', label: 'Market', icon: DollarSign },
  { id: 'monetization', label: 'Monetization', icon: Coins },
  { id: 'trends', label: 'Trends', icon: TrendingUp },
  { id: 'competitors', label: 'Competitors', icon: Swords },
  { id: 'audience-intelligence', label: 'Audience', icon: UserCheck },
  { id: 'content-insights', label: 'Content', icon: MessageSquare },
  { id: 'gtm-playbook', label: 'GTM', icon: Briefcase },
  { id: 'seo', label: 'SEO', icon: Search },
  { id: 'technical', label: 'Technical', icon: Code },
  { id: 'data-infrastructure', label: 'Data', icon: Database },
  { id: 'alternatives', label: 'Alternatives', icon: GitFork },
  { id: 'evidence-appendix', label: 'Evidence', icon: ClipboardList },
];

export const BUILD_SECTIONS: SectionConfig[] = [
  { id: 'landing-page', label: 'Landing page', icon: FileText },
];

/**
 * Invariants for Phase 2 ID lists (relative to DEEP_RESEARCH_SECTIONS):
 * - BLURRED_PREVIEW_IDS — rendered as scroll-target previews on the page + sidebar
 * - PEEK_ITEMS          — rendered as value-tagline rows in the locked sidebar only
 * - Lists must not overlap; every id must exist in DEEP_RESEARCH_SECTIONS.
 */

/** Deep research sections rendered as blurred previews with scroll targets on the page */
export const DEEP_RESEARCH_BLURRED_PREVIEW_IDS: string[] = [
  'unified-hero',
  'seo',
  'competitors',
];

/**
 * Two locked deep-research sections peeked in the Phase-2 sidebar, with a one-line
 * value tagline each. Order here = render order.
 */
export const DEEP_RESEARCH_PEEK_ITEMS: { id: string; tagline: string }[] = [
  { id: 'market-sizing', tagline: 'TAM · SAM · SOM' },
  { id: 'monetization',  tagline: 'Pricing · LTV:CAC' },
];

if (import.meta.env.DEV) {
  const known = new Set(DEEP_RESEARCH_SECTIONS.map(s => s.id));
  const allSubsetIds = [
    ...DEEP_RESEARCH_BLURRED_PREVIEW_IDS,
    ...DEEP_RESEARCH_PEEK_ITEMS.map(p => p.id),
  ];
  for (const id of allSubsetIds) {
    if (!known.has(id)) {
      throw new Error(`[phase-sections] Unknown section id "${id}" in subset list`);
    }
  }
  const previewSet = new Set(DEEP_RESEARCH_BLURRED_PREVIEW_IDS);
  for (const p of DEEP_RESEARCH_PEEK_ITEMS) {
    if (previewSet.has(p.id)) {
      throw new Error(`[phase-sections] Peek id "${p.id}" also in preview list`);
    }
  }
}

export const PHASES: PhaseConfig[] = [
  {
    id: 'discovery',
    label: 'Phase 1 · Discovery',
    badgeLabel: 'WHAT',
    badgeColor: 'success',
    sections: DISCOVERY_SECTIONS,
  },
  {
    id: 'deep-research',
    label: 'Phase 2 · Deep Research',
    badgeLabel: 'HOW',
    badgeColor: 'secondary',
    sections: DEEP_RESEARCH_SECTIONS,
  },
  {
    id: 'build',
    label: 'Phase 3 · Build',
    badgeLabel: 'GO',
    badgeColor: 'secondary',
    sections: BUILD_SECTIONS,
  },
];
