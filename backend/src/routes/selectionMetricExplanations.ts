import { Router, type Response } from 'express';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';

type MetricKind = 'derived_score' | 'assessed_score' | 'estimate' | 'evidence' | 'context';

interface SelectionMetricExplanation {
  key: string;
  label: string;
  kind: MetricKind;
  range: '0-100' | 'text';
  summary: string;
  method: string;
  sourceFields: string[];
  caveat?: string;
}

const METRICS: SelectionMetricExplanation[] = [
  {
    key: 'research_score',
    label: 'Research score',
    kind: 'derived_score',
    range: '0-100',
    summary: 'A ranking score that combines the research dimensions; it is not a probability of success.',
    method: 'Current reports use adjusted_composite_score: an angle-weighted mean of market fit, technical feasibility, novelty, and SEO, renormalized over present scores. Distribution/SEO ideas use 30/15/15/40 weights; novel-differentiation ideas use 30/20/40/10; vertical-workflow ideas use 35/35/20/10. Unknown angles use an equal mean. Provisional SEO is capped for ranking only, and a lower independent build-feasibility assessment subtracts the corresponding feasibility contribution.',
    sourceFields: [
      'adjusted_composite_score',
      'winning_angle',
      'market_fit_score',
      'technical_feasibility_score',
      'novelty_score',
      'seo_scalability_score',
      'build_feasibility_score',
    ],
    caveat: 'Legacy reports without adjusted_composite_score fall back in the client to an equal mean of market fit, SEO, novelty, technical feasibility, and solo-dev feasibility.',
  },
  {
    key: 'market_fit',
    label: 'Market fit',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'How strongly the exact product addresses validated, severe pains in an addressable market.',
    method: 'Stage 7 assigns market_fit_score from the addressed validated pains. An independent realism critic re-scores it, then deterministic rules can only lower it when the data or mechanism is unverified, buyer payability is weak, verified incumbent parity occupies the position, or the value depends on an unsupported self-issued trust claim.',
    sourceFields: ['market_fit_score'],
  },
  {
    key: 'technical_feasibility',
    label: 'Feasibility',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'Whether the product can be built with currently available technology and obtainable data.',
    method: 'Stage 7 assigns technical_feasibility_score from the proposed architecture and data route, and the independent realism critic may re-score it. The displayed row is this assessment; an independent build-feasibility score does not overwrite it, but can lower the Research score and the later verdict.',
    sourceFields: ['technical_feasibility_score'],
  },
  {
    key: 'distribution_seo',
    label: 'Distribution / SEO',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'How readily the product can grow organic traffic through useful, indexable content at scale.',
    method: 'Stage 7 assigns seo_scalability_score from the content-generation model and available corpus. The realism critic may re-score it, and downgrade-only realism rules cap account-gated, thin-content, or hand-seeded models. A separate provisional ceiling may apply only when this score contributes to ranking.',
    sourceFields: ['seo_scalability_score'],
  },
  {
    key: 'originality',
    label: 'Originality',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'How meaningfully the product differs from the approach competent builders would usually propose.',
    method: 'The comparison uses novelty_score when present. For older ideas it displays 1 minus obviousness_score. The realism critic can re-score both, and deterministic consistency rules prevent novelty from materially exceeding the independent non-obviousness assessment, with a separate moderate ceiling for distribution/SEO ideas.',
    sourceFields: ['novelty_score', 'obviousness_score'],
  },
  {
    key: 'build_estimate',
    label: 'Build estimate',
    kind: 'estimate',
    range: 'text',
    summary: 'A realistic range for one developer to ship a working MVP, not a polished product.',
    method: 'The final Stage 7 pass decomposes the MVP into standard and hard components, considers the technical approach, data route, build/data feasibility, and comparable web evidence, then reconciles the estimate to a fixed complexity band.',
    sourceFields: ['estimated_development_time', 'dev_time_rationale'],
  },
  {
    key: 'evidence_anchor',
    label: 'Evidence anchor',
    kind: 'evidence',
    range: 'text',
    summary: 'The validated pain this candidate was generated to address.',
    method: 'The comparison shows source_pain, then the first pain_points_addressed entry. An unanchored user hypothesis is labeled explicitly instead of being presented as validated research.',
    sourceFields: ['unanchored_hypothesis', 'source_pain', 'pain_points_addressed'],
  },
  {
    key: 'audience',
    label: 'Audience',
    kind: 'context',
    range: 'text',
    summary: 'The audience segment whose needs framed the candidate.',
    method: 'The comparison shows the code-stamped source_segment when available, then the first generated target_personas entry.',
    sourceFields: ['source_segment', 'target_personas'],
  },
  {
    key: 'distinctive_wedge',
    label: 'Distinctive wedge',
    kind: 'context',
    range: 'text',
    summary: 'Where the candidate is intended to differ from conventional or incumbent approaches.',
    method: 'The comparison uses differentiation_locus, then innovation_angle, the first differentiation_factors entry, and finally value_proposition.',
    sourceFields: ['differentiation_locus', 'innovation_angle', 'differentiation_factors', 'value_proposition'],
  },
  {
    key: 'known_concern',
    label: 'Known concern',
    kind: 'evidence',
    range: 'text',
    summary: 'The strongest recorded reason the candidate may underperform or be difficult to execute.',
    method: 'The comparison shows the realism critic\'s market-fit concern, then a web-verified incumbent-parity finding, then data-acquisition notes.',
    sourceFields: ['critic_concern', 'incumbent_parity', 'data_acquisition_notes'],
  },
];

export const selectionMetricExplanationsRouter = Router();

selectionMetricExplanationsRouter.get(
  '/metric-explanations',
  requireInternalAuth,
  (_req: AuthenticatedRequest, res: Response) => {
    res.setHeader('Cache-Control', 'private, no-store');
    res.json({ schemaVersion: 1, metrics: METRICS });
  },
);
