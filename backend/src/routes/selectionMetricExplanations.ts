import { Router, type Response } from 'express';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { getSelectionCapThresholds } from '../config.js';

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
    summary: 'A relative ranking of the ideas in this Discovery run, combining demand fit, buildability, differentiation, and organic-discovery potential. It is not a prediction of success.',
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
    caveat: 'Legacy reports without adjusted_composite_score use the client fallback: a fixed five-field mean of market fit, SEO, novelty, technical feasibility, and solo-dev feasibility. A missing field contributes zero in that fallback.',
  },
  {
    key: 'market_fit',
    label: 'Market fit',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'How strongly this exact product addresses an important, evidence-backed problem for buyers likely to pay.',
    method: 'Stage 7 assigns market_fit_score from the addressed validated pains. An independent realism critic re-scores it, then deterministic rules can only lower it when the data or mechanism is unverified, buyer payability is weak, verified incumbent parity occupies the position, or the value depends on an unsupported self-issued trust claim.',
    sourceFields: ['market_fit_score'],
  },
  {
    key: 'technical_feasibility',
    label: 'Feasibility',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'Whether a working version is technically possible with available tools and obtainable data. This is not a build-time estimate.',
    method: 'Stage 7 assigns technical_feasibility_score from the proposed architecture and data route, and the independent realism critic may re-score it. The displayed row is this assessment; an independent build-feasibility score does not overwrite it, but can lower the Research score and the later verdict.',
    sourceFields: ['technical_feasibility_score'],
  },
  {
    key: 'distribution_seo',
    label: 'Organic discovery',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'How readily the product can attract search traffic through useful, public, indexable content.',
    method: 'Stage 7 assigns seo_scalability_score from the content-generation model and available corpus. The realism critic may re-score it, and downgrade-only rules cap account-gated or restricted models, small estimated page inventories, and search results already owned by an incumbent. A separate provisional ceiling may apply only when this score contributes to ranking.',
    sourceFields: ['seo_scalability_score'],
  },
  {
    key: 'originality',
    label: 'Distinctiveness',
    kind: 'assessed_score',
    range: '0-100',
    summary: 'How meaningfully the idea differs from obvious approaches and existing alternatives.',
    method: 'When obviousness_score is present, the comparison displays 1 minus obviousness. Legacy records without obviousness display novelty_score. Both are labeled Distinctiveness for users; Research score always uses novelty_score rather than the displayed obviousness conversion.',
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
    method: 'The comparison shows the adversarial review first: typed affirmative findings name verified counterevidence, while an evidence_gap means the decision-critical evidence is incomplete. Historical records without typed findings keep the exact "Premise unproven" fallback. It then uses the realism critic\'s market-fit concern, a web-verified incumbent-parity finding, or data-acquisition notes.',
    sourceFields: ['red_team_verdict', 'red_team_findings', 'red_team_caveats', 'critic_concern', 'incumbent_parity', 'data_acquisition_notes'],
  },
];

export const selectionMetricExplanationsRouter = Router();

selectionMetricExplanationsRouter.get(
  '/metric-explanations',
  requireInternalAuth,
  (_req: AuthenticatedRequest, res: Response) => {
    res.setHeader('Cache-Control', 'private, no-store');
    // capThresholds mirror the env-overridable Python cap settings (read at request
    // time) so the frontend can explain when a score was constrained without exposing
    // implementation thresholds to the user.
    res.json({ schemaVersion: 1, metrics: METRICS, capThresholds: getSelectionCapThresholds() });
  },
);
