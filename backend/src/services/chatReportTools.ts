const REPORT_TOOL_RESULT_LIMIT = 14_000;

export function asReportRecord(report: unknown): Record<string, unknown> {
  return report && typeof report === 'object' && !Array.isArray(report)
    ? report as Record<string, unknown>
    : {};
}

export function getReportPath(report: unknown, requestedPath: string): unknown {
  const root = asReportRecord(report);
  const parts = requestedPath.split('.').map((part) => part.trim()).filter(Boolean);
  let current: unknown = root;
  for (const part of parts) {
    if (!current || typeof current !== 'object' || Array.isArray(current)) return undefined;
    const record = current as Record<string, unknown>;
    const exactKey = Object.keys(record).find((key) => key.toLowerCase() === part.toLowerCase());
    if (!exactKey) return undefined;
    current = record[exactKey];
  }
  return current;
}

export function compactReportValue(value: unknown, maxChars = REPORT_TOOL_RESULT_LIMIT): string {
  const serialized = JSON.stringify(value, null, 2) ?? 'null';
  return serialized.length <= maxChars
    ? serialized
    : serialized.slice(0, maxChars) + '\n… [result truncated; request a narrower section]';
}

export function collectNamedObjects(
  value: unknown,
  name: string,
  path = 'report',
  depth = 0,
): { path: string; value: Record<string, unknown> }[] {
  if (depth > 7 || value == null) return [];
  if (Array.isArray(value)) {
    return value.flatMap(
      (item, index) => collectNamedObjects(item, name, `${path}[${index}]`, depth + 1),
    );
  }
  if (typeof value !== 'object') return [];
  const record = value as Record<string, unknown>;
  const normalized = name.trim().toLowerCase();
  const candidate = [
    record.solution_name,
    record.idea_name,
    record.name,
    record.title,
    record.selected_solution_name,
  ].find((item) => typeof item === 'string' && item.trim().toLowerCase() === normalized);
  const here = candidate ? [{ path, value: record }] : [];
  return here.concat(
    Object.entries(record).flatMap(
      ([key, child]) => collectNamedObjects(child, name, `${path}.${key}`, depth + 1),
    ),
  );
}

export function searchReportEvidence(
  value: unknown,
  query: string,
  path = 'report',
  depth = 0,
): { path: string; value: unknown }[] {
  if (depth > 8 || value == null) return [];
  const needle = query.trim().toLowerCase();
  if (typeof value === 'string') {
    return value.toLowerCase().includes(needle) ? [{ path, value }] : [];
  }
  if (Array.isArray(value)) {
    return value
      .flatMap((item, index) => searchReportEvidence(item, query, `${path}[${index}]`, depth + 1))
      .slice(0, 30);
  }
  if (typeof value !== 'object') return [];
  return Object.entries(value as Record<string, unknown>)
    .flatMap(([key, child]) => searchReportEvidence(child, query, `${path}.${key}`, depth + 1))
    .slice(0, 30);
}

const METRIC_EXPLANATIONS: Record<string, string> = {
  market_fit_score: 'A calibrated solution-evaluation score grounded in the addressed pain, segment payability, evidence quality, and parity findings. It may be capped by calibration rules; it is not derived from the final report value. Source: UnifiedSolutionCrew._calibrate_batch.',
  technical_feasibility_score: 'The stored technical-feasibility evaluation, subject to buildability calibration. The independent build-feasibility critic can lower ranking impact when build feasibility is below technical feasibility, but never raises it. Source: feasibility_adjusted_composite.',
  feasibility_score: 'Alias of technical_feasibility_score when the report uses the shorter field name.',
  competitive_advantage_score: 'The calibrated differentiation/novelty dimension for the idea. It is evaluated against incumbent and adjacent-market parity findings and can be capped when the mechanism is insufficiently distinct. Source: UnifiedSolutionCrew._calibrate_batch.',
  novelty_score: 'Alias of competitive_advantage_score in report sections that label the differentiation dimension as novelty.',
  seo_scalability_score: 'The solution evaluation pipeline’s SEO/distribution dimension. Quote the stored value and retrieve its keyword evidence; do not infer it from total search volume alone.',
  composite_score: 'A mean of the present market-fit, technical-feasibility, competitive-advantage, and SEO scores. With a winning angle it uses that angle’s configured weights and renormalizes over present dimensions. A lower independent build-feasibility score can only reduce it, and an idea serving an adjacent audience loses a small fixed penalty here (see audience_fit). Sources: _composite_for_angle, feasibility_adjusted_composite, and apply_audience_fit_penalty.',
  adjusted_composite_score: 'Post-keyword-validation ranking score: 70% composite score plus 30% keyword demand score, rounded to four decimals. When demand is unmeasured there is no blend and this equals the raw composite score (see demand_unmeasured), and the solution is ranked below every measured one regardless of the number. Sources: blend_adjusted_composite and rerank_solutions_by_adjusted_score.',
  demand_adjusted_composite: 'Alias of adjusted_composite_score: 0.7 × composite score + 0.3 × keyword demand score, or the raw composite when demand is unmeasured.',
  keyword_demand_score: 'Demand over the RELEVANCE-GRADED, on-idea keyword set only — keywords judged to be about this idea rather than the broad category it sits in. The base ratio is 55% graded-keyword yield (len(validated_keywords) against a 20-seed denominator), 25% per-keyword volume-and-competition opportunity, and 20% rankability from keyword difficulty; without difficulty data it falls back to 60% yield plus 40% opportunity. That base is then blended 50/50 with min(log10(volume + 1) / 5, 1) when niche-relevant volume is positive; an explicitly zero niche-relevant volume adds no magnitude credit. Sources: _calculate_difficulty_adjusted_score and demand_with_beachhead_magnitude. Two limits that must be stated when quoting it: an idea whose graded set came back empty has NO demand score at all (see demand_unmeasured), and in narrow or technical B2B niches several ideas routinely land on the SAME value because the on-idea vocabulary is thin. A tie or near-tie means demand could not separate those ideas; it is never evidence that they are equally wanted.',
  demand_unmeasured: 'True when keyword validation graded a solution’s keywords and none of them passed. Demand is then unmeasured, NOT zero and not low: keyword_demand_score is left absent rather than filled with a fabricated number, the adjusted composite equals the raw composite with no demand blend, and two-tier ranking places the solution below every solution whose demand was measured. Never read this as weak demand; read it as "nobody searches this exact thing yet", which a genuinely new product can honestly produce. Sources: the keyword-validation stage in research_flow and rerank_solutions_by_adjusted_score.',
  validated_count: 'The number of GRADED, on-idea keywords for a solution — canonically the length of its validated-keyword list, not the unfiltered expansion pool the expansion step produced. Reports written before August 2026 stored the pool size here (observed live: 50 stored against one graded keyword), so the graded list is the authority whenever it is present. Expect small numbers: a small graded count is the relevance filter working, not missing research. Sources: finalize_graded_validation and KeywordValidationResult.graded_keyword_count.',
  graded_keyword_count: 'Alias of validated_count under its unambiguous name: the count of keywords graded as being about this idea rather than its broad category.',
  confidence_score: 'Base confidence is the average of market fit and competitive advantage. When pain/social quality inputs are present, downgrade-only multiplicative quality penalties apply, with a 0.10 floor. Source: ScoreAccessor.get_confidence_score and ConfidenceAdjuster.',
  selection_confidence: 'In market analytics, this is the same average of the selected solution’s available market-fit, competitive-advantage, technical-feasibility, and canonical SEO scores as overall_opportunity_score. Source: ReportGenerator._compute_market_analytics.',
  overall_opportunity_score: 'Arithmetic mean of the selected solution’s available market-fit, competitive-advantage, technical-feasibility, and canonical SEO scores; defaults to 0.5 only if none are available. Source: ReportGenerator._compute_market_analytics.',
  market_size_category: 'Uses primary niche search volume, falling back to total keyword volume: Large above 10,000; Medium above 1,000; otherwise Small. Source: ReportGenerator._compute_market_analytics.',
  competitive_intensity: 'Low, Medium, or High from competitor count using deployment-configured low/high thresholds. Source: ReportGenerator._compute_market_analytics.',
  go_no_go: 'Go/Conditional/No-Go starts from configured average-score and minimum-gating-dimension thresholds, includes buildability, then permits downgrade-only adjustments for trend, market viability, and payability risk. Source: ReportGenerator._compute_go_no_go_verdict and VerdictValidator.',
  opportunity_level: 'High when both severity and commercial intent meet their configured high cutoffs; Medium when exactly one does; Low when neither does. The pipeline may downgrade, but not upgrade, this formula for universal-theme or tool-addressability concerns. Source: compute_opportunity_level.',
  commercial_intent: 'An evidence-grounded 0–1 pain score for credible buying, budget, workaround-spend, or switching signals. It is produced with severity by the pain scoring pipeline; quote its stored evidence rather than treating discussion volume as purchase intent. Source: PainPointScoring and resolve_pain_point_scores.',
  severity_score: 'An evidence-grounded 0–1 pain intensity score produced by the pain scoring pipeline. It is distinct from commercial intent and should be explained with supporting quotes/frequency, not reverse-engineered from opportunity level. Source: PainPointScoring and resolve_pain_point_scores.',
  segment_payability: 'A 0–1 LLM-assisted assessment of the segment’s ability and habit of paying for software, grounded in wallet authority and incumbent spending evidence. Pain intensity alone cannot raise it. Source: score_segment_payability and blend_payability.',
  red_team_verdict: 'The adversarial review’s verdict on the premise it tested. Tool results already present it in product wording: a reason-specific verified finding when typed counterevidence exists, "incomplete decision-critical evidence" for a typed evidence gap, or the legacy "Premise unproven" fallback when no typed findings were stored. Quote the wording provided; never infer a class from caveat prose or translate it back to killed, dead, or rejected. No verdict mutates a stored score or rank, and the idea stays selectable. Sources: red_team_review, apply_red_team_downgrade, and choose_auto_pick.',
  red_team_findings: 'Typed adversarial-review findings. Verified incumbent overlap, a verified free or bundled alternative, payer mismatch, and modal failure are affirmative counterevidence. Evidence gap means the review could not establish the claim; it is incomplete evidence, not counterevidence. Classify only from kind, never from words in claim.',
  red_team_caveats: 'The evidence-cited objections the adversarial review raised against an idea, at most three. They are objections under the review’s own heading, never competitor findings. Source: red_team_review.',
  incumbent_parity: 'The web-verified finding on whether an existing product already ships this idea’s core mechanism. Every tool result already presents it in product wording — "Already shipped by X", "Partly covered by X", "Buyers already get this outcome from X", "Already included free with X", or "No competing product found", each followed by its evidence — so quote the phrasing you were given rather than any shorthand for it. A finding requires a NAMED vendor and evidence from a search run for that specific idea; with no named vendor there is no parity finding at all. Since 2026-08-02 the adversarial review no longer writes into this channel, so its objections appear as review caveats and never borrow a competitor’s authority. Findings cap scores downward only. Sources: _probe_mechanism_parity and _validate_idea_caps.',
  adjacent_market_parity: 'The same named-vendor competition check run after stripping the audience out of the idea’s framing, so the commercial category the mechanism actually belongs to gets searched. Same evidence bar and same downgrade-only effect as incumbent_parity. Source: the adjacent-market parity probe in UnifiedSolutionCrew.',
  audience_fit: 'Whether the idea serves the audience the run was asked about (true), an adjacent one (false), or was never tagged (absent). False subtracts a small configured penalty from the RANKING composite only, and only once enough of the pool is tagged for the comparison to mean anything. The stored market-fit score is never mutated and the penalty can never raise a score. Sources: apply_audience_fit_penalty and audience_fit_coverage.',
  idea_theses: 'The complete grouping of the visible idea pool into product theses: one buyer job per thesis, with every idea that renders it nested beneath as a variant. Four similar ideas under one thesis are four renderings of ONE business, not four opportunities. It also lists validated buyer jobs with no surviving idea, which are unexamined rather than ruled out. A deterministic rollup of signals already stamped on the ideas; it carries no score and changes no ranking. Source: build_idea_theses.',
  refine_binding_constraint: 'The single constraint the improvement loop’s reviewer judged most binding on the winning revision, plus its directive. It records what most limited the idea at refinement time, not a score. Source: idea_improvement_loop_v4.',
};

export function metricExplanation(metric: string): string | null {
  const normalized = metric.trim().toLowerCase().replace(/[\s-]+/g, '_');
  return METRIC_EXPLANATIONS[normalized] ?? null;
}

export function encodeExportQuery(format: string, sections: string[]): string {
  const params = new URLSearchParams({ sections: sections.join(',') });
  return `/api/jobs/__JOB_ID__/chat/export/${format}?${params.toString()}`;
}

function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ');
}

export function buildReportExport(
  report: unknown,
  sections: string[],
  format: 'markdown' | 'csv' | 'json',
): string {
  const selected = Object.fromEntries(
    sections.map((section) => [section, getReportPath(report, section)]),
  );
  if (format === 'json') return JSON.stringify(selected, null, 2);

  if (format === 'markdown') {
    return sections.map((section) => {
      const value = selected[section];
      const title = section.split('.').map(humanizeKey).join(' / ');
      if (typeof value === 'string') return `## ${title}\n\n${value}`;
      return `## ${title}\n\n\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``;
    }).join('\n\n');
  }

  const rows: Record<string, string>[] = [];
  for (const section of sections) {
    const value = selected[section];
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) {
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        rows.push(Object.fromEntries([
          ['section', section],
          ...Object.entries(item as Record<string, unknown>).map(([key, cell]) => [
            key,
            typeof cell === 'string' ? cell : JSON.stringify(cell),
          ]),
        ]));
      } else {
        rows.push({ section, value: typeof item === 'string' ? item : JSON.stringify(item) });
      }
    }
  }
  const headers = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const escape = (value: string | undefined) => `"${String(value ?? '').replace(/"/g, '""')}"`;
  return [
    headers.map(escape).join(','),
    ...rows.map((row) => headers.map((header) => escape(row[header])).join(',')),
  ].join('\n');
}
