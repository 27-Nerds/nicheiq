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
  { id: 'pain-points', label: 'Pain Points', icon: AlertTriangle },
  { id: 'audience', label: 'Audience', icon: Users },
  { id: 'community', label: 'Community', icon: Globe },
  { id: 'opportunities', label: 'Opportunities', icon: Lightbulb },
];

export const DEEP_RESEARCH_SECTIONS: SectionConfig[] = [
  { id: 'unified-hero', label: 'Executive', icon: BarChart3 },
  { id: 'solution', label: 'Solution', icon: Rocket },
  { id: 'pain-analysis', label: 'Pain Points', icon: Flame },
  { id: 'market-sizing', label: 'Market', icon: DollarSign },
  { id: 'monetization', label: 'Monetization', icon: Coins },
  { id: 'trends', label: 'Trends', icon: TrendingUp },
  { id: 'competitors', label: 'Competitors', icon: Swords },
  { id: 'audience', label: 'Audience', icon: UserCheck },
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

/** Subset of deep research section IDs shown in nav when the phase is locked (must match LOCKED_PREVIEW_SECTIONS IDs) */
export const DEEP_RESEARCH_PREVIEW_IDS: string[] = [
  'unified-hero',
  'market-sizing',
  'seo',
  'competitors',
];

/** Deep research sections rendered as blurred previews with scroll targets on the page */
export const DEEP_RESEARCH_BLURRED_PREVIEW_IDS: string[] = [
  'unified-hero',
  'competitors',
];

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
