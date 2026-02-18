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
} from 'lucide-svelte';

export interface ReportSectionInfo {
  id: string;
  label: string;
  icon: ComponentType;
}

export const REPORT_SECTIONS: ReportSectionInfo[] = [
  // PHASE 1: DECISION (Go/No-Go verdict)
  { id: 'unified-hero', label: 'Executive', icon: BarChart3 },
  { id: 'solution', label: 'Solution', icon: Rocket },
  // PHASE 2: VALIDATE (Is the opportunity real?)
  { id: 'pain-analysis', label: 'Pain Points', icon: Flame },
  { id: 'market-sizing', label: 'Market', icon: DollarSign },
  { id: 'monetization', label: 'Monetization', icon: Coins },
  { id: 'trends', label: 'Trends', icon: TrendingUp },
  { id: 'competitors', label: 'Competitors', icon: Swords },
  // PHASE 3: EXECUTE (How to launch & build)
  { id: 'audience', label: 'Audience', icon: UserCheck },
  { id: 'content-insights', label: 'Content', icon: MessageSquare },
  { id: 'gtm-playbook', label: 'GTM', icon: Briefcase },
  { id: 'seo', label: 'SEO', icon: Search },
  { id: 'technical', label: 'Technical', icon: Code },
  { id: 'data-infrastructure', label: 'Data', icon: Database },
  // PHASE 4: REFERENCE (Appendix)
  { id: 'alternatives', label: 'Alternatives', icon: GitFork },
  { id: 'evidence-appendix', label: 'Evidence', icon: ClipboardList },
];

export const SECTION_MAP = Object.fromEntries(
  REPORT_SECTIONS.map((s) => [s.id, s])
) as Record<string, ReportSectionInfo>;
