/**
 * Phase definitions, stage-to-phase mapping, narrative templates,
 * and celebration tier configuration.
 */

import type { ComponentType } from 'svelte';
import { STAGE_MAP } from '$lib/config/billable-stages';

export type PhaseId = 'discovery' | 'analysis';
export type PhaseStatus = 'locked' | 'pending' | 'active' | 'completed' | 'failed';
export type CelebrationTier = 1 | 2 | 3;

export interface NarrativeTemplate {
  running: string;
  completed: (artifact: Record<string, any>) => string;
  skipped?: (artifact: Record<string, any>) => string;
}

export interface PhaseDefinition {
  id: PhaseId;
  label: string;
  icon: ComponentType;
  description: string;
  stageNumbers: number[];
  artifactStages: number[];
  narrativeTemplates: Record<number, NarrativeTemplate>;
}

export const PHASES: PhaseDefinition[] = [
  {
    id: 'discovery',
    label: 'Discovery',
    icon: STAGE_MAP.discovery.icon,
    description: 'Scanning social discussions and extracting market signals',
    stageNumbers: [1, 2, 3, 4, 5],
    artifactStages: [1, 2, 3, 4],
    narrativeTemplates: {
      1: {
        running: 'Analyzing your niche and identifying market segments...',
        completed: (a) => {
          const segs = a.market_segments?.length;
          return segs
            ? `Identified ${segs} market segments`
            : 'Niche analysis complete';
        },
      },
      2: {
        running: 'Scanning communities for discussions...',
        completed: (a) => {
          const posts = (a.reddit_posts || 0) + (a.twitter_threads || 0);
          const subs = a.subreddit_count || 0;
          return posts
            ? `Found ${posts} posts across ${subs} communities`
            : 'Search complete';
        },
      },
      3: {
        running: 'Extracting pain points from discussions...',
        completed: (a) => {
          const count = a.count || a.top?.length || 0;
          const maxSev = a.top?.[0]?.severity;
          return maxSev
            ? `${count} pain points found, peak severity ${(maxSev * 10).toFixed(0)}/10`
            : count
              ? `${count} pain points found`
              : 'Pain points extracted';
        },
      },
      4: {
        running: 'Profiling target audience segments...',
        completed: (a) => {
          const target = a.primary_target;
          const segs = a.segment_count || 0;
          return target
            ? `Primary: ${target} (${segs} segments)`
            : `${segs} audience segments identified`;
        },
      },
      5: {
        running: 'Generating solution ideas from pain points...',
        completed: (a) => {
          const count = a.solution_count || a.solutions?.length || 0;
          return `${count} solution ideas generated`;
        },
      },
    },
  },
  {
    id: 'analysis',
    label: 'Deep Analysis',
    icon: STAGE_MAP.deep_research.icon,
    description: 'Validating demand, pricing, and market opportunity',
    stageNumbers: [5.5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    artifactStages: [6, 7, 9, 11],
    narrativeTemplates: {
      5.5: {
        running: 'Analyzing competitive landscape...',
        completed: () => 'Competitive landscape mapped',
      },
      6: {
        running: 'Validating keyword volumes and SEO opportunity...',
        completed: (a) => {
          const vol = a.total_volume;
          const kw = a.validated_keywords || 0;
          if (vol) {
            const fmt = vol >= 1000 ? `${(vol / 1000).toFixed(1)}K` : String(vol);
            return `SEO demand: ${fmt} monthly searches, ${kw} keywords`;
          }
          return kw ? `SEO demand: ${kw} keywords validated` : 'SEO demand validated';
        },
      },
      7: {
        running: 'Researching competitor pricing strategies...',
        completed: (a) => {
          const friendlyNames: Record<string, string> = {
            'Ad-Supported-Free': 'Ad-supported',
            'Usage-Based': 'Usage-based',
            'Affiliate-Only': 'Affiliate-based',
          };
          const model = a.pricing_model;
          if (!model) return 'Pricing strategy defined';
          const friendly = friendlyNames[model] || model;
          const tierSuffix =
            a.starter_price && a.pro_price ? ` (${a.starter_price}–${a.pro_price})` : '';
          return `Revenue model: ${friendly}${tierSuffix}`;
        },
        skipped: (a) => a.skip_reason || 'Pricing validation skipped',
      },
      8: {
        running: 'Analyzing monetization opportunities...',
        completed: () => 'Monetization pathways identified',
        skipped: (a) => a.skip_reason || 'Traffic monetization not applicable',
      },
      9: {
        running: 'Sizing addressable market...',
        completed: (a) => {
          if (a.som_y1) return `Addressable market: ${a.som_y1} Year 1`;
          return 'Market opportunity estimated';
        },
        skipped: (a) => a.skip_reason || 'Market sizing skipped',
      },
      10: {
        running: 'Generating strategic recommendations...',
        completed: () => 'Solution concept refined',
        skipped: (a) => a.skip_reason || 'Solution refinement skipped',
      },
      11: {
        running: 'Analyzing market trends and momentum...',
        completed: (a) => {
          const dir = a.trend_direction;
          const timing = a.timing_recommendation;
          if (dir && timing) return `Market trend: ${dir} — ${timing}`;
          if (dir) return `Market trend: ${dir}`;
          return 'Trend analysis complete';
        },
        skipped: (a) => a.skip_reason || 'Trend analysis skipped',
      },
      12: {
        running: 'Refining SEO opportunity scores...',
        completed: () => 'SEO scores recalculated',
        skipped: (a) => a.skip_reason || 'SEO refinement skipped',
      },
      13: {
        running: 'Researching data sources and APIs...',
        completed: () => 'Data sources verified',
      },
      14: {
        running: 'Assembling final research report...',
        completed: () => 'Report complete',
      },
    },
  },
];

/** Stages that run in parallel and should be displayed as one row */
export const PARALLEL_STAGE_GROUPS: Record<
  number,
  { hide: number[]; combinedName: string }
> = {
  3: { hide: [4], combinedName: 'Pain Point & Audience Analysis' },
};

/** Celebration tier per stage — higher tier = bigger celebration */
export const CELEBRATION_TIERS: Record<number, CelebrationTier> = {
  1: 1,
  2: 2,   // search discovery — key data moment
  3: 2,   // pain points — key data moment
  4: 1,
  5: 3,   // phase milestone — discovery complete
  6: 2,   // SEO — key data moment
  7: 1,
  8: 1,
  9: 2,   // market sizing — key data moment
  10: 1,
  11: 2,  // trends — key data moment
  12: 1,
  13: 1,
  14: 3,  // phase milestone — report ready
};

/** Lookup phase for a given stage number */
export function getPhaseForStage(stageNumber: number): PhaseId | null {
  for (const phase of PHASES) {
    if (phase.stageNumbers.includes(stageNumber)) return phase.id;
  }
  return null;
}

/** Get narrative text for a stage based on its status and artifact */
export function getNarrativeText(
  stageNumber: number,
  status: string,
  artifact?: Record<string, any> | null,
): string | undefined {
  for (const phase of PHASES) {
    const tmpl = phase.narrativeTemplates[stageNumber];
    if (!tmpl) continue;
    if (status === 'RUNNING') return tmpl.running;
    if (status === 'COMPLETED') {
      try {
        return tmpl.completed(artifact ?? {});
      } catch {
        return undefined;
      }
    }
    if (status === 'SKIPPED') {
      try {
        return tmpl.skipped
          ? tmpl.skipped(artifact ?? {})
          : `${tmpl.running.replace(/\.\.\.$/, '')} — skipped`;
      } catch {
        return undefined;
      }
    }
  }
  return undefined;
}
