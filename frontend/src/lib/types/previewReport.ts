import type { Report } from './report';

export type PreviewReport = Partial<Report> & {
  niche: string;
  generated_at: string;
  detailed_pain_points: Report['detailed_pain_points'];
  audience_mapping: Report['audience_mapping'];
};

export interface LockedSectionConfig {
  id: string;
  sectionNumber: string;
  title: string;
  teaser: string;
  phase: string;
}

export const LOCKED_PREVIEW_SECTIONS: LockedSectionConfig[] = [
  {
    id: 'unified-hero',
    sectionNumber: '06',
    title: 'Go / No-Go Verdict',
    teaser: 'See how your pain point signals score against our validation framework',
    phase: 'Decision',
  },
  {
    id: 'market-sizing',
    sectionNumber: '07',
    title: 'Market Sizing',
    teaser: 'Estimated revenue potential and addressable market for this niche',
    phase: 'Validate',
  },
  {
    id: 'seo',
    sectionNumber: '08',
    title: 'SEO Keyword Strategy',
    teaser: 'Full keyword map with search volumes and difficulty scores',
    phase: 'Execute',
  },
  {
    id: 'competitors',
    sectionNumber: '09',
    title: 'Competitive Landscape',
    teaser: 'Who else is building in this space and where the gaps are',
    phase: 'Validate',
  },
];

export const ADDITIONAL_LOCKED_SECTIONS = [
  'Pricing & Revenue Model',
  'Trend Longevity Analysis',
  'Go-to-Market Playbook',
  'Technical Blueprint & MVP Scope',
  'Data Infrastructure Roadmap',
];
