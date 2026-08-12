// NicheIQ Report TypeScript Interfaces

import type { IdeaTags, RedTeamFinding, SolutionPreview } from './job';

export interface Report {
	niche: string;
	executive_summary: string;
	/** True when generated from a catalog-seeded run (thinner community evidence). */
	seeded_from_catalog?: boolean;
	/** Guided-mode honesty block (Phase C): true once any gate patch (G1/G2) was applied. */
	user_adjusted?: boolean;
	/** Compact human-readable notes for which gate(s) were adjusted and what changed. */
	user_adjustments?: string[];
	executive_dashboard?: ExecutiveDashboard;
	go_to_market_blueprint?: GoToMarketBlueprint;
	market_analytics?: MarketAnalytics;
	seo_analytics?: SEOAnalytics;
	competitive_analytics?: CompetitiveAnalytics;
	pain_point_analytics?: PainPointAnalytics;
	selected_solution_name: string;
	selection_rationale: string;
	/** Original strategic rationale, preserved verbatim when keyword validation
	 *  pivoted the winner (selection_rationale then carries an appended update). */
	original_selection_reasoning?: string | null;
	// runner_up_solutions removed - extract names from alternative_solutions instead
	// selection_criteria_scores removed - ScoreAccessor is single source of truth
	recommended_focus?: string;
	selected_solution_details?: SolutionDetails;
	solution_user_journey?: string;
	solution_implementation_overview?: string;
	mvp_scope_definition?: string;
	// Site Structure and User Flows (Stage 15 - LLM-generated)
	site_structure?: SiteStructure;
	user_flows?: UserFlowsSection;
	pricing_strategy?: PricingStrategy;
	market_sizing?: MarketSizing;
	trend_longevity?: TrendLongevity;
	// top_pain_points removed - use detailed_pain_points instead
	pain_points_summary?: string;
	// pain_point_categories removed - derive from detailed_pain_points.categories
	audience_mapping?: AudienceMapping;
	recommended_solutions?: string[];
	solutions_summary?: string;
	competitive_summary?: string;
	competitive_analysis?: CompetitiveAnalysis;
	market_validation?: string;
	acquisition_strategy_summary?: string;
	estimated_cac_breakdown?: string;
	keyword_validation_overview?: string;
	solution_keyword_comparison?: string;
	content_strategy_preview?: string;
	data_sourcing_recommendations?: string;
	next_steps?: string[];
	research_metadata?: ResearchMetadata;
	alternative_solutions?: AlternativeSolution[];
	competitive_landscape_matrix?: CompetitiveLandscapeMatrix;
	evidence_appendix?: EvidenceAppendix;
	data_infrastructure_roadmap?: DataInfrastructureRoadmap;
	content_categorization?: ContentCategorization;
	detailed_pain_points?: DetailedPainPoint[];
	solution_innovation_assessment?: Record<string, unknown>;
	// solution_organic_discovery removed - use selected_solution_details.organic_discovery_queries instead
	competitor_profiles: CompetitorProfile[];
	generated_at: string;

	// ========== NEW FULL STAGE DATA FIELDS ==========

	// Stage 1-4: Full Niche Context
	niche_context?: NicheContext;

	// Stage 6: Full SEO Strategy Report (not just seo_strategy)
	seo_strategy_report?: SEOStrategy;
	/** Catalog/report projection of the selected solution's SEO topic clusters.
	 * Legacy reports and runs without SEO research may omit it. */
	keyword_clusters?: TopicCluster[];

	/// Stage 13: Full Data Source Research (not just summary)
	data_source_research_full?: DataSourceResearchFull;

	// Competitive Strategic Insights
	overall_competitive_insights?: string;

	// Traffic Monetization (Stage 8 pricing crew)
	traffic_monetization?: TrafficMonetization;

	// Refinement Highlights (Stage 10 solution refinement)
	refinement_highlights?: RefinementHighlights;

	// SEO Calculation Transparency
	seo_calculation_transparency?: SEOCalculationTransparency;

	// Data Quality Summary (top-level)
	data_quality_summary?: DataQualitySummary;

	// Portfolio-funnel findings: pains/ideas examined but ultimately not carried forward
	// (demoted winners, rejected backfill candidates).
	examined_ruled_out?: RuledOutFinding[];
	// Groups of surviving ideas that are variants of the same underlying product
	// (a merge was proposed but rejected, so they remain separate entries).
	overlap_groups?: OverlapGroup[];

	// Complete thesis-level partition of the visible pool (one entry per buyer-job family)
	// plus the validated families no surviving concept represents. Absent/empty on runs
	// without a non-degraded buyer-job partition — render the flat candidate list instead.
	idea_theses?: IdeaThesisPartition;

	// Web-verified incumbent landscape + niche wallet read, gathered alongside the parity
	// probe (see incumbent_parity on solutions). Absent on legacy/older reports.
	market_reality?: MarketReality;

	// Research Reality Check — candid software-fit verdict
	niche_difficulty_verdict?: NicheDifficultyVerdict;

	/** Version of the scoring formulas that produced this report's scores (e.g. "2026.08").
	 * Absent/null on reports generated before the 2026.08 scoring cutover — scores across
	 * different versions are not comparable. */
	scoring_version?: string;

	// LLM-narrated honest assessment of the visible idea pool (strengths/weaknesses across
	// all candidates), computed once in Stage 5. null when the pool was empty or the
	// grounded LLM pass failed its name-coverage guardrail.
	idea_portfolio_summary?: string | null;

	// Portfolio fingerprint of the exact candidate list `idea_portfolio_summary` was
	// written against. The summary is guidance about THAT list, so it is only current
	// while this equals the live pool's fingerprint; surfaces must compare the two
	// before presenting the summary as a recommendation.
	idea_portfolio_summary_fingerprint?: string | null;

	// Stage timing summary (pipeline execution timing)
	stage_timing_summary?: StageTimingSummary;

	// "Check my idea" (entry_mode='validate_idea') report block — present only on validate
	// runs' preview reports (src/nicheiq/report/idea_validation_block.py). Enum-driven:
	// never string-sniff prose fields for behavior.
	idea_validation?: IdeaValidation | null;

	// Share indexing control (injected by backend for shared reports)
	_shareAllowIndexing?: boolean;
}

// ── "Check my idea" (idea_validation block) ──

export type IdeaValidationOutcome =
	| 'worth_testing'
	| 'occupied'
	| 'premise_unproven'
	| 'ruled_out'
	| 'not_evaluated';

export interface IdeaValidationPart {
	key: 'problem_real' | 'space_occupied' | 'demand';
	/** problem_real: supported|thin|not_found · space_occupied: shipped|partial|adjacent|none_found|review_concerns|not_checked · demand: not_measured */
	state: string;
	answer: string;
	detail: string;
}

export interface IdeaValidationBreadth {
	posts: number;
	/** Distinct posting accounts of the cited threads (quote-level authorship isn't tracked). */
	distinct_authors: number;
	distinct_communities: number;
	months_spanned: number;
	label: string;
}

export interface IdeaValidationPivot {
	attempted: boolean;
	outcome: 'accepted' | 'rejected' | 'not_attempted';
	trigger_finding?: string | null;
	/** Parsed incumbent name from the trigger — lets the panel say "TeamSnap already
	 * ships part of your mechanism" instead of echoing the raw parity note twice. */
	trigger_incumbent?: string | null;
	because?: string | null;
	keeps?: string | null;
	changes?: string | null;
	reason_not_shown?: string | null;
	/** WHY the drafted revision was rejected — split so the copy can't claim
	 * "scored no better" when the revision scored better but failed parity clearance. */
	rejection_code?: 'no_design' | 'incomplete_scores' | 'not_better' | 'parity_not_cleared';
	rejected_name?: string | null;
	rejected_pitch?: string | null;
	/** The acceptance decision's OWN angle-composite ×100 — deliberately not the
	 * workbench's displayCompositeScore. */
	rejected_composite?: number | null;
	original_composite?: number | null;
	ries_label?: string | null;
	name?: string | null;
	idea_id?: string | null;
	idea_revision?: number | null;
}

export interface IdeaValidationCompetitor {
	name?: string | null;
	what_they_ship?: string | null;
	price_note?: string | null;
	price_caveat?: string | null;
	gap?: string | null;
	url?: string | null;
	/** The vendor the verdict's parity finding named — rendered first with a chip. */
	verdict_trigger?: boolean;
	/** Promoted trigger rows only: the parity probe's capability evidence ("ships
	 * Ratio utility billing (RUBS) and CAM") — the map focus is often broader than
	 * the killing capability, and the row must substantiate the verdict. */
	verdict_evidence?: string | null;
	/** Row synthesized from the parity finding (vendor absent from the incumbent
	 * map): what-they-ship is probe evidence; price/gap/url deliberately empty. */
	synthesized?: boolean;
}

export interface IdeaValidationAlternatives {
	count: number;
	/** Alternatives whose audience_fit judgment says they primarily serve the buyer
	 * the user NAMED — the same field the workbench's Adjacent-audience chip reads,
	 * so the two numbers can never contradict. null = pool carries no audience_fit
	 * verdicts (legacy runs): inconclusive, the sentence is omitted. */
	named_buyer_count?: number | null;
	top: { idea_id?: string | null; name?: string | null; one_liner?: string | null }[];
}

export interface IdeaValidation {
	provisional: true;
	outcome: IdeaValidationOutcome;
	idea_name?: string | null;
	headline: string;
	parts: IdeaValidationPart[];
	score_bands?: Record<string, string>;
	evidence_confidence: 'Low' | 'Moderate' | 'High';
	evidence_confidence_reason: string;
	breadth?: IdeaValidationBreadth | null;
	anchored_pains: {
		pain_title: string;
		severity_band: string;
		/** High/Medium/Low with the dossier's cutoffs — one severity vocabulary per page. */
		severity_label?: string;
		mention_count?: number | null;
		quotes: string[];
	}[];
	/** Near-miss pains: not anchored to the seed but sharing the pitch's own
	 * mechanism/problem vocabulary — each with a disposition so stronger-looking
	 * pains in the dossier can't read as the verdict grading the wrong essay. */
	related_pains?: {
		pain_title: string;
		severity_label: string;
		mention_count?: number | null;
		note: 'risk' | 'unmatched';
	}[];
	/** Non-anchored pains ranking above the idea's own anchored max — the ruled-out
	 * bridge's "where else to look" number. Unanchored seed → 0. */
	stronger_pain_count?: number;
	unanchored_hypothesis?: boolean | null;
	user_idea_text?: string | null;
	user_idea_brief?: string | null;
	/** Echo fields the Stage-1 parser INFERRED rather than read from the pitch. */
	assumed_fields: string[];
	derived_market?: string | null;
	derived_buyer?: string | null;
	incumbent_parity?: string | null;
	existing_equivalent?: string | null;
	competitors: IdeaValidationCompetitor[];
	/** Our own generator independently proposed the same product — a DEMAND signal. */
	duplicate_of?: { idea_id?: string | null; name: string } | null;
	red_team_verdict?: string | null;
	red_team_findings?: RedTeamFinding[] | null;
	kill_risks: {
		claim: string;
		why_it_matters?: string | null;
		falsification?: string | null;
		quote?: string | null;
		/** Provenance of the risk: adversarial review, the score critic's concession,
		 * or the market's own loudest adverse pain. */
		source?: 'adversarial_review' | 'score_critic' | 'market_signal';
		/** market_signal only: the underlying pain's canonical title. */
		pain_title?: string | null;
	}[];
	pivot: IdeaValidationPivot;
	alternatives: IdeaValidationAlternatives;
	seed_candidate_status?: string | null;
	seed_idea_id?: string | null;
	seed_idea_revision?: number | null;
	/** Computed backend-side; gates the "Continue with your idea" commit panel. */
	seed_purchasable: boolean;
	/** The seed's /100 score on the workbench's OWN ranking contract (angle composite
	 * + visible-pool audience-fit coverage) — a demoted seed is absent from the idea
	 * list, so the page cannot derive this number anywhere else. */
	seed_display_composite_score?: number | null;
	demotion_reason?: string | null;
	desk_limits: string[];
	experiment_ladder: { rung: number; action: string; kill_number: string; cost_note: string }[];
	next_experiment_index: number;
	/** The product as the tournament actually graded it (may be a refinement of the pitch). */
	evaluated_idea?: {
		name?: string | null;
		value_proposition?: string | null;
		mechanism_summary?: string | null;
	} | null;
	/** Non-null when the evaluated seed drifted from a stated pitch clause — the
	 * Keeps/Changes/Because delta rendered in the echo card. */
	refinement?: { kept: string[]; changed: string[]; because?: string | null } | null;
	/** Display-only parity note for the PITCHED mechanism (brief-derived probe);
	 * never feeds outcome or confidence. */
	original_mechanism_parity?: string | null;
}

// Stage timing summary
export interface StageTimingSummary {
	total_duration_seconds: number;
	stage_durations: Record<string, number>;
	slowest_stage?: string;
	fastest_stage?: string;
}

// Data Infrastructure Roadmap
export interface DataInfrastructureRoadmap {
	phases: DataInfrastructurePhase[];
	cost_scaling_insight: string;
}

export interface DataInfrastructurePhase {
	phase_number: number;
	phase_name: string;
	timeline: string;
	data_sources: string[];
	estimated_monthly_cost: string;
	key_risks: string[];
}

// Traffic Monetization interface
export interface TrafficMonetization {
	solution_name: string;
	monetization_model: string;
	estimated_monthly_pageviews: string;
	traffic_source_breakdown: Array<{ source: string; percentage: string }>;
	estimated_cpm_rate?: string | null;
	estimated_monthly_ad_revenue?: string | null;
	recommended_ad_networks: string[];
	affiliate_commission_rate?: string | null;
	estimated_affiliate_ctr?: string | null;
	estimated_monthly_affiliate_revenue?: string | null;
	recommended_affiliate_programs: string[];
	sponsored_listing_price?: string | null;
	premium_placement_price?: string | null;
	lead_gen_price_per_lead?: string | null;
	estimated_monthly_revenue_range?: string | null;
	estimated_annual_revenue_range?: string | null;
	break_even_traffic_threshold?: string | null;
	monetization_rationale: string;
	scaling_strategy?: string | null;
	monetization_confidence?: 'High' | 'Medium' | 'Low';
	viability_verdict?: 'viable' | 'conditional' | 'nonviable' | null;
	economics_evaluated?: boolean;
	funnel_target?: string | null;
	qualified_actions?: string | null;
	conversion_assumptions?: string[] | null;
	estimated_funnel_value?: string | null;
	unit_value_evidence?: {
		route: 'lead_generation' | 'sponsorship' | 'paid_upgrade_funnel' | 'affiliate';
		candidate_idea_id?: string | null;
		candidate_idea_revision?: number | null;
		source_name: string;
		source_url: string;
		evidence_text: string;
		retrieved_quote?: string | null;
		retrieved_at?: string | null;
		verification_marker?: 'exact_quote_in_fetched_public_content' | null;
		value_low?: number | null;
		value_high?: number | null;
		billing_basis: 'per_lead' | 'per_sponsored_listing_month' | 'per_paid_upgrade_month' | 'affiliate_program';
		commission_pct_low?: number | null;
		commission_pct_high?: number | null;
	} | null;
	saas_alternative_viable: boolean;
	saas_vs_traffic_recommendation: string;
	traffic_methodology?: string | null;
	traffic_data_sources?: string[] | null;
	year3_monthly_pageviews?: string | null;
	year3_monthly_revenue?: string | null;
	full_potential_monthly_pageviews?: string | null;
	full_potential_monthly_revenue?: string | null;
	revenue_growth_note?: string | null;
	revenue_milestones?: Array<{
		traffic: string;
		ad_revenue: string;
		unlock: string;
		total_potential: string;
	}> | null;
}

// Refinement Highlights interface
export interface RefinementHighlights {
	top_strategic_insights: string[];
	geographic_priority?: string | null;
	feature_priority?: string | null;
	category_pivot_recommendation: string | null;
}

// SEO Calculation Transparency interface
export interface SEOCalculationTransparency {
	baseline_seo_score?: number | null;
	refined_seo_score?: number | null;
	volume_multiplier?: number | null;
	competition_modifier?: number | null;
	tier1_multiplier?: number | null;
	estimated_year1_pages?: number | null;
	calculation_rationale?: string | null;
	keyword_evidence_floor?: number | null;
	floor_applied?: boolean | null;
	floor_reason?: string | null;
}

export interface ExecutiveDashboard {
	/**
	 * The only guaranteed section: the pipeline now raises rather than returning a
	 * null verdict, so a completed report cannot ship without one.
	 */
	go_no_go_verdict: GoNoGoVerdict;
	/**
	 * Supporting sections. Any of these may be absent when its generation step
	 * degraded — the section is then named in `unavailable_sections`. Render the
	 * absence explicitly; never substitute a placeholder value.
	 */
	recommended_solution_snapshot?: SolutionSnapshot | null;
	core_pain_point?: CorePainPoint | null;
	key_metrics?: KeyMetrics | null;
	confidence_score?: number | null;
	research_depth_label?: string;
	/** Raw keys of any dashboard section that degraded during generation. */
	unavailable_sections?: string[] | null;
	// niche_description removed - use root report.niche instead
}

export interface SolutionSnapshot {
	name: string;
	tagline: string;
	core_value_prop: string;
	project_type: string;
	delivery_format?: string | null;
}

export interface GoNoGoVerdict {
	verdict: 'Go' | 'No-Go' | 'Conditional';
	rationale: string;
	risk_level: 'Low' | 'Medium' | 'High';
	primary_concern: string | null;
	trend_context?: string | null;
	market_viability_context?: string | null;
	/** Buyer-payability floor explanation (Phase 5), null = no adjustment applied. */
	payability_context?: string | null;
	/** Red-team floor explanation (Phase 5.5) — adversarial weakened/killed finding, null = no adjustment applied. */
	red_team_context?: string | null;
}

export interface CorePainPoint {
	title: string;
	severity_score: number;
	commercial_intent_score: number;
	representative_quote: string;
	source_platform: string;
}

export interface KeyMetrics {
	total_keyword_search_volume: number;
	tier0_keyword_count: number;
	tier1_keyword_count: number;
	tier2_keyword_count: number;
	tier3_keyword_count: number;
	tier4_keyword_count: number;
	total_keyword_count: number;
	high_severity_pain_points?: number;
	high_priority_pain_points?: number; // deprecated: backward compat for old reports
	primary_competitor_count: number;
	avg_pain_point_severity: number;
	avg_commercial_intent: number;
	social_evidence_threads: number;
	market_fit_score?: number | null;
	competitive_advantage_score?: number | null;
	technical_feasibility_score?: number | null;
	seo_potential_score?: number | null;
	solo_dev_feasibility?: number | null;
}

export interface BudgetAllocation {
	content_creation: number;
	paid_advertising: number;
	tools_and_software: number;
	community_and_outreach: number;
}

export interface BudgetEstimate {
	monthly_budget_min: number;
	monthly_budget_max: number;
	allocation: BudgetAllocation;
	rationale: string;
	scaling_guidance: string;
}

export interface GoToMarketBlueprint {
	ideal_customer_profile: IdealCustomerProfile;
	core_marketing_message: string;
	message_framework: string;
	recommended_channels: RecommendedChannel[];
	example_content_angles: ContentAngle[];
	first_30_days_playbook: Playbook;
	budget_estimate: string | BudgetEstimate | null;  // Support both old string and new object
}

export interface IdealCustomerProfile {
	persona_name: string;
	demographics: string;
	psychographics: string;
	pain_points: string[];
	goals: string[];
	buying_triggers: string;
	decision_criteria: string;
}

export interface RecommendedChannel {
	channel_name: string;
	channel_type: string;
	target_audience_size: string;
	rationale: string;
	strategy: string;
	priority: 'High' | 'Medium' | 'Low';
}

export interface ContentAngle {
	title: string;
	content_type: string;
	pain_point_addressed: string;
	hook: string;
	key_points: string[];
	target_channel: string;
}

export interface Playbook {
	week_1_actions: string[];
	week_2_actions: string[];
	week_3_actions: string[];
	week_4_actions: string[];
	success_metrics: string[];
}

export interface MarketAnalytics {
	overall_opportunity_score: number;
	market_size_category: string;
	selection_confidence: number;
	competitive_intensity: string;
	recommendation: string;
}

export interface SEOAnalytics {
	tier0_count: number;
	tier1_count: number;
	tier2_count: number;
	tier3_count: number;
	tier4_count: number;
	total_keywords: number;
	total_search_volume: number;
	core_search_volume?: number;
	avg_competition: number;
	keyword_diversity_score: number;
	high_volume_keywords: number;
}

export interface OriginalFeature {
	competitor: string;
	feature_text: string;
}

export interface FeatureGroup {
	group_name: string;
	description: string;
	competitors_with_feature: string[];
	original_features: OriginalFeature[];
}

export interface FeatureComparison {
	feature_groups: FeatureGroup[];
	total_unique_groups: number;
	avg_features_per_competitor: number;
}

export interface CompetitiveAnalytics {
	competitor_count: number;
	market_saturation_score: number;
	differentiation_strength: string;
	market_gaps_identified: number;
	avg_competitor_features: number;
	feature_comparison?: FeatureComparison;
}

export interface PainPointAnalytics {
	total_pain_points: number;
	high_severity_count?: number;
	high_priority_count?: number; // deprecated: backward compat for old reports
	high_opportunity_count?: number;
	quadrant_distribution: QuadrantDistribution;
	avg_severity?: number;
	avg_commercial_intent?: number;
	top_pain_point_title?: string;
}

export interface QuadrantDistribution {
	high_severity_high_wtp: number;
	high_severity_low_wtp: number;
	low_severity_high_wtp: number;
	low_severity_low_wtp: number;
}

export interface DetailedPainPoint {
	title: string;
	description: string;
	mention_count: number;
	severity_score: number;
	commercial_intent: number;
	opportunity_level: 'high' | 'medium' | 'low';
	/** Present when the LLM justifiably downgraded opportunity_level below the
	 *  severity/WTP formula (universal-theme or niche-specificity cap). */
	opportunity_downgrade_reason?: string | null;
	representative_quotes: string[];
	source_platforms: string[];
	categories: string[];
	source_post_ids: string[];
	affected_segments?: string[];
	solution_approach?: string;
}

// Deterministic SEO-thesis stress test for a distribution_seo idea (present only for that angle).
export interface SeoKillQuestion {
	indexable_page_ceiling: number;
	head_count: number;
	mid_count: number;
	tail_count: number;
	median_keyword_difficulty?: number | null;
	winnable_pages: number;
	kd_sample_size: number;
	forum_soft_serp_share?: number | null;
	institutional_serp_share?: number | null;
	serp_sampled: number;
	penalty_risk_flag: boolean;
	verdict: string;
	rationale: string;
}

export interface SEOStrategy {
	total_keywords_analyzed: number;
	/** Combined volume of every analyzed keyword — category reach, NOT validated idea demand. */
	total_monthly_volume: number;
	/** Volume carried by keywords that actually match the idea. Null on legacy reports and
	 *  whenever the backend's intent-grader coverage guard trips. */
	idea_intent_monthly_volume?: number | null;
	/** Share of total_monthly_volume carried by off-topic (grade-0) keywords. */
	offtopic_volume_share?: number | null;
	/** Share of total_monthly_volume carried by broader category (grade-1 + ungraded) keywords. */
	category_volume_share?: number | null;
	key_findings?: string[];
	tier_0_keywords: Keyword[];
	tier_0_strategy?: string;
	tier_1_keywords: Keyword[];
	tier_1_quick_win_strategy?: string;
	tier_2_keywords: Keyword[];
	tier_2_strategy?: string;
	tier_3_geographic_groups?: GeographicKeywordGroup[];
	tier_4_category_groups?: CategoryKeywordGroup[];
	// untiered_keywords removed - internal recovery tracking
	content_strategy?: string;
	topic_clusters?: TopicCluster[];
	technical_seo_recommendations?: string;
	// keyword_driven_site_architecture removed - overlaps with keyword_based_page_types
	keyword_based_page_types?: PageType[];
	competitive_positioning?: string;
	implementation_roadmap?: string;
	// key_metrics_to_track removed - generic boilerplate
	// risk_mitigation removed - generic boilerplate
	budget_allocation?: string;
	seo_kill_question?: SeoKillQuestion | null;
	// long_term_strategy removed - duplicates implementation_roadmap
	// conclusion_bottom_line removed - generic boilerplate
	// competitive_advantages removed - redundant with competitive_positioning
	// critical_success_factors removed - generic boilerplate
	// expected_timeline removed - duplicates implementation_roadmap
	// next_steps_checklist removed - generic boilerplate
	// universal_seo_elements removed - Task 5/6 deleted, technical SEO in technical_seo_recommendations
	// page_type_implementations removed - Task 5/6 deleted
	// schema_markup_strategy removed - Task 5/6 deleted
}

export interface Keyword {
	keyword: string;
	search_volume: number;
	competition: string;
	opportunity_score: number;  // Required, matches Python int
	keyword_difficulty?: number;  // SEO difficulty score 0-100 (lower=easier to rank)
	strategy?: string;
	intent?: string;
	tier?: number;
	tier_rationale?: string;
}

// Geographic keyword entry (Tier 3)
export interface GeographicKeywordEntry {
	city: string;
	keyword: string;
	search_volume: number;
	notes?: string;
}

// Geographic keyword group (Tier 3)
export interface GeographicKeywordGroup {
	region_name: string;
	total_volume: number;
	competition_level: string;
	keywords: GeographicKeywordEntry[];
	strategy_notes: string;
}

// Legacy KeywordGroup for backwards compatibility
export interface KeywordGroup {
	group_name: string;
	keywords: Keyword[];
	total_volume?: number;
	strategy?: string;
}

export interface CategoryKeyword {
	keyword_name: string;
	search_volume: number;
	competition: string;
	keyword_difficulty?: number;  // SEO difficulty score 0-100 (lower=easier to rank)
	cpc?: number;
}

export interface CategoryKeywordGroup {
	category_name: string;
	total_volume: number;
	keywords: CategoryKeyword[];
	strategy_recommendation?: string;
}

export interface TopicCluster {
	// Primary fields matching Python backend
	cluster_name: string;
	primary_keyword: string;
	supporting_keywords: string[];
	total_monthly_volume?: number;
	content_recommendation?: string;
	estimated_traffic_potential?: string;
	priority?: number;
}

export interface PageType {
	// Primary field matching Python backend
	page_type_name: string;
	url_pattern: string;
	target_keyword_cluster: string;
	example_keywords: string[];
	primary_intent: string;

	priority: number;
	required_schema?: string[];
	seo_optimization_notes?: string;
}



export interface CompetitiveAnalysis {
	solution_landscapes: SolutionLandscape[];
	top_opportunities: string[];
	strategic_recommendations: string;
}

export interface SolutionLandscape {
	solution_name: string;
	competitors: CompetitorProfile[] | string[];  // Support both full objects and string names
	market_gaps: string[];
	differentiation_opportunities: string[];
	competitive_intensity: string;
	recommended_positioning: string;
	pricing_insights: string;
}

export interface CompetitorProfile {
	name: string;
	url: string;
	competitor_type: 'DIRECT' | 'PARTIAL' | 'INDIRECT';
	description: string;
	key_features: string[];
	pricing_model: string;
	strengths: string[];
	weaknesses: string[];
}

export interface PricingStrategy {
	solution_name: string;

	// Standard tier prices (optional for Ad-Supported-Free/Affiliate-Only models)
	recommended_starter_price?: string | null;
	recommended_pro_price?: string | null;
	recommended_enterprise_price?: string | null;

	// Pricing model type (expanded to support diverse models)
	pricing_model:
		| 'Freemium'          // Free tier + paid upgrades (3-tier)
		| 'Freemium-Lite'     // Free + single paid tier (2-tier)
		| 'Subscription'      // Pure subscription (no free tier)
		| 'Hybrid'            // Subscription + usage-based
		| 'One-time'          // Single purchase
		| 'Usage-Based'       // Pay-per-use (API calls, credits)
		| 'Ad-Supported-Free' // Free tool, monetized by ads only
		| 'Affiliate-Only'    // Free tool, monetized by affiliate links only
		| string;             // Fallback for backward compatibility

	pricing_rationale: string;

	// Feature tiers (optional for Ad-Supported-Free/Affiliate-Only models)
	free_tier_features?: string[];
	starter_tier_features?: string[];
	pro_tier_features?: string[];

	// Ad/Affiliate revenue fields (for Ad-Supported-Free/Affiliate-Only models)
	estimated_monthly_ad_revenue?: string;
	estimated_monthly_affiliate_revenue?: string;
	estimated_cpm_rate?: string;
	recommended_ad_networks?: string[];

	// Unit economics
	estimated_arpu?: string;
	estimated_ltv?: string;
	ltv_to_cac_ratio?: string;

	// Competitive positioning
	price_vs_competitors?: string;
	value_proposition_delta?: string;
	pricing_confidence?: 'High' | 'Medium' | 'Low';
	wtp_validation?: string;
	market_segment_pricing?: Array<{ segment: string; price: string | null }>;
}

export interface MarketSizing {
	total_addressable_market: string;
	serviceable_available_market: string;
	serviceable_obtainable_market_y1: string;
	serviceable_obtainable_market_y3?: string;
	primary_methodology: string;
	methodology_explanation: string;
	data_sources_used: string[];
	segment_sizing?: SegmentSizing[];
	keyword_demand_signal?: string;
	pain_point_frequency?: string;
	competitor_market_presence?: string;
	market_growth_rate?: string;
	growth_drivers?: string[];
	risk_factors?: string[];
	// Market assessment fields
	market_saturation_level?: string; // Low, Medium, High
	market_timing_assessment?: string; // Early, Growth, Mature
	market_viability_verdict?: string; // Strong, Moderate, Weak
	viability_rationale?: string;
	recommended_entry_strategy?: string;
}

export interface SegmentSizing {
	segment_name: string;
	tam_estimate: string;
	sam_estimate: string;
	som_estimate: string;
	sizing_methodology: string;
	confidence_level: string;
}

export interface TrendLongevity {
	// Core trend indicators
	trend_direction?: string; // Growing | Stable | Declining
	trend_confidence?: 'High' | 'Medium' | 'Low';
	momentum_score?: number;
	keyword_volume_trend?: string;
	volume_growth_rate?: string;
	trend_duration?: string;
	discussion_frequency_trend?: string;

	// Community and market signals
	community_growth_indicators?: string[];
	new_entrants_trend?: string;
	competitive_activity_level?: string;
	discussion_recency?: 'Recent' | 'Moderate' | 'Dated';

	// Seasonality
	seasonal_pattern?: string;
	peak_periods?: string[] | null;

	// Assessment
	market_maturity?: string;
	longevity_verdict?: string; // Sustainable | Risky | Fad
	longevity_rationale?: string;
	timing_recommendation?: string;
	trend_reversal_risks?: string[];

	// Metadata
	data_sources_analyzed?: string[];
	analysis_timeframe?: string;
}

export interface ResearchMetadata {
	// Python backend fields (primary)
	reddit_posts_analyzed?: number;
	reddit_comments_analyzed?: number;
	twitter_threads_analyzed?: number;
	generic_posts_analyzed?: number;
	top_subreddits?: SubredditBreakdown[];
	collection_date?: string;
	data_size_mb?: number;
	completed_stages?: number[];
	fallback_stages?: number[];
	filtering_stats?: Record<string, unknown>;
	// Timing metadata
	started_at?: string;
	// Quality summary
	data_quality_summary?: DataQualitySummary;
	// Portfolio-funnel stage counts (pains_identified, cells_run, concepts_generated,
	// survived_critics, winners, salvaged, demoted, merge_groups, variants_absorbed,
	// backfill_run, backfill_accepted, candidates_shown — any key may be absent).
	funnel_counts?: Record<string, number>;
}

export interface SubredditBreakdown {
	name: string;
	post_count: number;
}

export interface NicheDifficultyVerdict {
	difficulty_level: string; // low | medium | high | very_high
	software_addressability: number; // 0-1
	headline: string;
	narrative_summary: string;
	/** Frictions only. Never render these as strengths. */
	key_challenges: string[];
	/** What makes the niche favourable. Populated only for a strong-fit niche; absent on legacy reports. */
	key_strengths?: string[];
	low_confidence: boolean;
	/** Who actually pays here: budgeted-business | smb-operator | prosumer | indie-hobbyist | consumer | mixed. */
	buyer_class?: string | null;
	/** One-liner on what the buyer class means for monetization. */
	buyer_class_note?: string | null;
	/** Structured requested -> dossier -> recommendation audience mismatch. */
	audience_drift_notice?: AudienceDriftNotice | null;
}

export interface DataQualitySummary {
	social_content_quality_tier?: string; // EXCELLENT, GOOD, MINIMAL, INSUFFICIENT
	pain_point_quality_tier?: string; // GOLD, SILVER, BRONZE, INSUFFICIENT (evidence-based: measures research quality, not niche attractiveness)
	pain_point_confidence_score?: number; // 0-1 (based on unique sources, subreddit diversity, quote density, pain point count)
	overall_data_quality: string; // HIGH, MEDIUM, LOW
	quality_caveats: string[];
	/** Final-report location for weak ideas that were considered and ruled out.
	 * Older preview payloads may still expose the same records at the report root. */
	examined_ruled_out?: RuledOutFinding[];
}

// A pain/idea that was examined during the portfolio funnel but ultimately not carried
// forward — either a winner demoted for thin market signal, or a backfill candidate
// rejected on review. Surfaced so users see the pains that were considered, not just the
// ones that survived.
export interface RuledOutFinding {
	pain_title: string;
	reason: string;
	market_fit: number | null;
	market_fit_band: 'very-low' | 'low';
	prior_tier: string;
	source: 'demoted_winner' | 'backfill_rejected' | 'no_buyer';
	evidence: string;
	/** The idea's actual name — the panel's real primary (pain_title is secondary
	 *  provenance). Optional so older cached reports without it still render. */
	idea_name?: string | null;
	/** Which generation frame minted the idea (see sourceFrameLabels.ts's closed
	 *  vocabulary) — 'user_seed' marks a chat-composed idea seed that was tested
	 *  and demoted, rendered with a "Your idea" badge. */
	source_frame?: string | null;
	/** Durable identity of the paid evaluation that produced this finding. */
	evaluation_id?: string | null;
	dispatch_id?: string | null;
	generation_operation_id?: string | null;
	generation_batch_ordinal?: number | null;
	evaluation_source_message_id?: string | null;
	proposed_title?: string | null;
	/** Full evaluated payload when available. It remains read-only because the market-fit
	 *  verdict ruled it out, but users can still inspect the analysis. */
	idea?: SolutionPreview | null;
}

// A set of surviving ideas identified as variants of the same underlying product. A merge
// was proposed but rejected, so the ideas remain as separate list entries.
export interface OverlapGroup {
	idea_names: string[];
	shared_product: string;
}

// ── Thesis-level portfolio partition (docs/DIVERSITY_DECISION_2026-08.md) ──
// The pool of N ideas collapses into a handful of buyer-job families; this is the COMPLETE
// partition of it (unlike OverlapGroup, which only reports rejected 2+ variant merges).

/** One deterministic kill-signal already stamped on a member idea, attributed to the field it
 *  came from so the UI can cite it instead of asserting it in NicheIQ's own voice. */
export interface ThesisFatalAssumption {
	/** Which member idea carries the signal. */
	idea_name: string;
	/** Source field: 'red_team_verdict' | 'data_access_model' | 'audience_fit' |
	 *  'demand_unmeasured' | 'data_sources' | 'refine_binding_constraint'. */
	source_field: string;
	assumption: string;
}

/** One variant nested under a thesis. `name` joins back to the full idea the detail overlay
 *  renders. `winning_angle` stays at VARIANT level on purpose — the GTM lens is orthogonal to
 *  the buyer job, so there is no thesis-level angle to render. */
export interface ThesisMember {
	name: string;
	/** 'vertical_workflow' | 'distribution_seo' | 'novel_differentiation'; null when angle
	 *  evaluation was off or the classifier abstained. */
	winning_angle?: string | null;
	/** Birth provenance: 'single' | 'salvaged' | 'bundle' | 'merged'. */
	idea_tier?: string;
	/** Generation frame: 'pain' | 'gap' | 'data_asset' | 'workflow' | 'user_seed'. */
	source_frame?: string;
}

/** One product thesis: a buyer-job family with every visible idea that renders it. */
export interface IdeaThesis {
	family_id: string;
	display_label: string;
	/** The role who pays. Empty string on a family the labeler left unlabeled. */
	buyer: string;
	triggering_job: string;
	economic_outcome: string;
	/** Every visible idea in this thesis, best-first by the same composite the grid ranks on. */
	members: ThesisMember[];
	lead_idea_name: string;
	/** Rolled up from members' incumbent_parity stamps. 'unknown' = vendor-less stamps or no
	 *  parity data — NOT evidence of an open market. */
	incumbent_status: 'occupied' | 'partial' | 'open' | 'unknown';
	/** Named vendors from the members' parity stamps (vendor-less adversarial
	 *  "shipped by evidence" findings are excluded — they are not parity claims). */
	incumbent_vendors: string[];
	fatal_assumptions: ThesisFatalAssumption[];
}

/** A validated buyer-job family with no surviving concept — shown so the run cannot claim it
 *  examined an opportunity space it never covered. */
export interface UncoveredFamily {
	family_id: string;
	display_label: string;
	member_pain_ids: string[];
	/** 'no_cell_allocated' (the allocator never spent a generator cell here) |
	 *  'no_surviving_idea' (a cell ran, nothing survived) | 'unknown' (no telemetry). */
	reason: 'no_cell_allocated' | 'no_surviving_idea' | 'unknown';
	reason_detail?: string;
}

export interface IdeaThesisPartition {
	/** 'llm' — the only source a thesis IA is built on (a degraded partition yields no theses). */
	family_source?: string;
	theses: IdeaThesis[];
	uncovered_families: UncoveredFamily[];
	/** Visible ideas that could not be mapped to any family. Never silently dropped. */
	unassigned: { idea_name: string; reason: string }[];
}

// A single web-verified incumbent tool found while probing the niche's competitive
// landscape (distinct from the per-idea incumbent_parity/adjacent_market_parity strings —
// this is the aggregated niche-level tool list shown in the "Market reality" disclosure).
export interface MarketRealityIncumbent {
	name: string;
	pricing?: string | null;
	focus?: string | null;
	gap?: string | null;
	source?: string | null;
}

// The niche's buyer-wallet read, gathered alongside the incumbent probe.
export interface MarketRealityWallet {
	wallet_class?: string | null;
	evidence?: string | null;
	free_density?: string | null;
}

export interface MarketReality {
	incumbents: MarketRealityIncumbent[];
	wallet?: MarketRealityWallet | null;
}

// RunnerUpSolution interface removed - use alternative_solutions instead

// SelectionCriteriaScore removed - ScoreAccessor is single source of truth

export interface SolutionDetails {
	// Basic info
	idea_id?: string;
	idea_revision?: number;
	solution_name?: string;
	headline?: string;
	short_description?: string;
	description: string;
	estimated_development_time?: string;

	// Extended solution data
	value_proposition?: string;
	pain_points_addressed?: string[];
	core_features?: string[];
	target_personas?: string[];
	technical_approach?: string;
	differentiation_factors?: string[];
	requires_data_aggregation?: boolean;
	data_sources?: string[];
	pricing_strategy?: string;
	market_fit_score?: number;
	technical_feasibility_score?: number;
	project_type?: string;
	delivery_format?: string | null;
	programmatic_seo_opportunity?: string;
	programmatic_seo_opportunity_refined?: string;
	content_generation_model?: string;
	organic_discovery_queries?: string[];
	estimated_cac_organic?: string;
	estimated_cac_organic_refined?: string;
	estimated_cac_paid?: string;
	/** 'parity_pivot' | 'variant_merge' | 'red_team_revision' when this idea replaced an
	 *  earlier one that was rebuilt mid-run. A rebuild does not carry acquisition cost
	 *  forward — the old figure priced the product it replaced — so the CAC fields above
	 *  are deliberately absent, and this is what lets the UI say so. */
	rebuild_origin?: string | null;
	seo_scalability_score?: number;
	seo_scalability_score_refined?: number;
	estimated_indexable_pages?: number;
	novelty_score?: number;
	obviousness_score?: number | null; // 0-1, lower = less obvious; displayed as "Distinctiveness" (1 - this)
	conventional_approach?: string;
	innovation_angle?: string;
	why_it_works?: string;
	why_it_works_short?: string;
	solo_dev_feasibility?: number;
	// Portfolio-funnel provenance tier: 'single' (cell winner) | 'salvaged' (critic-rescued loser)
	// | 'bundle' (synthesis-stage multi-pain product) | 'merged' (synthesized from overlapping
	// variants). Absent on legacy reports = 'single'.
	idea_tier?: string;
	// Portfolio-funnel lifecycle status: 'active' | 'demoted' | 'restored' | 'absorbed'.
	candidate_status?: string | null;
	// Names of the variant ideas synthesized into this one (only set when idea_tier === 'merged').
	merged_from?: string[] | null;
	// Angle-aware evaluation (set when angle eval is on; absent otherwise)
	winning_angle?: string | null; // distribution_seo | novel_differentiation | vertical_workflow
	angle_rationale?: string | null; // user-facing comment: the angle + where differentiation lives
	novelty_rationale?: string | null; // stable field name; user-facing explanation of distinctiveness for this project type
	differentiation_locus?: string | null; // WHERE the edge lives (or honest "thin me-too")
	// Multi-Frame Idea Generation Portfolio: which generation frame minted this idea's cell.
	// CODE-FILLED, never LLM-set. pain | gap | data_asset | spend_adjacent | workflow
	source_frame?: string | null;
	// Data feasibility (annotate-only; from the ideation feasibility critic)
	data_feasibility_score?: number;
	data_access_model?: string; // public | freemium | paywalled | unofficial | restricted | blocked | unverified
	data_acquisition_notes?: string;
	build_feasibility_score?: number; // independent critic's build-feasibility estimate (0-1)
	keyword_geographic_priorities?: string[];
	keyword_feature_priorities?: string[];
	keyword_strategic_insights?: string;
	category_pivot_suggestion?: string | null;
	// Closed-vocabulary idea-stage facets carried into the selected solution record.
	tags?: IdeaTags | null;
	seo_refinement_metadata?: {
		baseline_volume_used?: number;
		volume_multiplier?: number;
		tier1_multiplier?: number;
		competition_modifier?: number;
		base_cac?: number;
		difficulty_multiplier?: number;
		volume_discount?: number;
		estimated_year1_pages?: number;
	};
}

// PainPointCategory interface removed - derive from detailed_pain_points.categories

export interface AudienceMapping {
	// Core segments
	audience_segments?: AudienceSegment[];
	primary_target_segment?: string;
	segment_prioritization_rationale?: string;
	audience_drift_notice?: AudienceDriftNotice | null;

	// Influencers and community
	key_influencers?: Influencer[];
	community_hubs?: string[];

	// Communication
	common_vocabulary?: string[];
	content_preferences?: string;
	messaging_frameworks?: string[];

	// Existing tools and frustrations
	tools_currently_used?: string[];
	frustrations_with_existing?: string[];

	// Strategy
	recommended_channels?: string[];
	early_adopter_tactics?: string;
}

export interface AudienceDriftNotice {
	requested_audience: string;
	dossier_primary_segment: string;
	recommended_source_segments: string[];
	message: string;
}

export interface InfluencerTopPost {
	title: string;
	subreddit: string;
	score: number;
	url: string;
}

export interface Influencer {
	name: string;
	platform: string;
	follower_estimate?: string;
	relevance_score?: number;
	engagement_level?: string;
	outreach_priority?: string;
	content_focus?: string;
	top_subreddits?: string[];
	top_posts?: InfluencerTopPost[];
}

export interface AudienceSegment {
	segment_name: string;
	size_estimate?: string;
	pain_point_alignment?: string[];
	motivation_drivers?: string[];
	expertise_level?: string;
	budget_sensitivity?: string;
	discovery_channels?: string[];
	influencers_followed?: string[];
}

export interface AlternativeSolution {
	// Core identification
	solution_name: string;
	headline?: string;
	short_description?: string;
	summary: string;

	// Description
	description?: string;

	// Existing score fields
	market_fit_score?: number;
	technical_feasibility_score?: number;
	competitive_advantage_score?: number;
	seo_growth_potential_score?: number;

	// Existing strategic fields
	key_differentiator?: string;
	best_suited_for?: string;
	pivot_trigger?: string;

	// Core solution details
	value_proposition?: string;
	core_features?: string[];
	target_personas?: string[];
	technical_approach?: string;
	delivery_format?: string | null;

	// Additional scores and feasibility
	novelty_score?: number;
	obviousness_score?: number | null; // 0-1, lower = less obvious; displayed as "Distinctiveness" (1 - this)
	solo_dev_feasibility?: number; // 0-1 scale matching Python float
	// Portfolio-funnel provenance tier (see selected_solution_details.idea_tier)
	idea_tier?: string;
	// Portfolio-funnel lifecycle status: 'active' | 'demoted' | 'restored' | 'absorbed'.
	candidate_status?: string | null;
	// Names of the variant ideas synthesized into this one (only set when idea_tier === 'merged').
	merged_from?: string[] | null;
	// Angle-aware evaluation (set when angle eval is on; absent otherwise)
	winning_angle?: string | null;
	angle_rationale?: string | null;
	novelty_rationale?: string | null;
	differentiation_locus?: string | null; // WHERE the edge lives (or honest "thin me-too")
	// Data feasibility (annotate-only; from the ideation feasibility critic)
	data_feasibility_score?: number;
	build_feasibility_score?: number; // independent critic's build-feasibility estimate (0-1)
	data_access_model?: string; // public | freemium | paywalled | unofficial | restricted | blocked | unverified
	data_acquisition_notes?: string;

	// Honest brief: evidence + the critic's voice (mirrors Python AlternativeSolution)
	demand_quotes?: string[] | null; // verbatim community quotes for the addressed pains (max 3)
	critic_concern?: string | null; // calibration critic's market_fit reason — the bear case
	incumbent_parity?: string | null; // web-verified mechanism parity for top ideas ("shipped by MoeGo: …" | "substitute (…)" | "none found")
	adjacent_market_parity?: string | null; // audience-independent incumbent where the mechanism monetizes ("HigherGov (govcon intel): …"), null = none found
	red_team_verdict?: string | null; // adversarial pass verdict: survives | weakened | killed
	red_team_caveats?: string[] | null; // evidence-cited caveats from the red-team pass
	red_team_findings?: RedTeamFinding[] | null;
	/** 'parity_pivot' | 'variant_merge' | 'red_team_revision' when this idea replaced an
	 *  earlier one that was rebuilt mid-run. Used to explain a missing CAC figure rather
	 *  than hiding the tile — the old estimate priced a product that no longer exists. */
	rebuild_origin?: string | null;
	source_segment_payability?: number | null; // 0-1 buyer-wallet strength of the source segment (permanent signal; null = segment map failed)
	source_segment_payability_class?: string | null; // corporate-budget | smb-budget | prosumer-wallet | personal-wallet | mixed
	// Multi-Frame Idea Generation Portfolio: which generation frame minted this idea's cell.
	// CODE-FILLED, never LLM-set; also carries owner_synthesis/additional_batch.
	source_frame?: string | null;
	evaluation_id?: string | null;
	evaluation_source_message_id?: string | null;
	proposed_title?: string | null;
	synthesis_evaluation?: Record<string, unknown> | null;
	generation_operation_id?: string | null;
	generation_batch_ordinal?: number | null;

	// Competitive landscape for this solution
	top_competitors?: string[];
	market_gaps?: string[];
	competitive_intensity?: string; // LOW, MEDIUM, HIGH

	// Economic indicators
	estimated_development_time?: string;
	estimated_cac_organic?: string;  // Matches Python: str format like "$15-30"
	pricing_model?: string;

	// Closed-vocabulary filter facets (chips + future filtering). See docs/IDEA_TAGS.md.
	tags?: IdeaTags | null;
}

export interface CompetitiveLandscapeMatrix {
	all_solutions_analyzed: string[];
	selected_solution_competitors?: string[];
	competitor_overlap: CompetitorOverlap[];
	competitive_intensity_by_solution?: SolutionIntensity[];
	market_insight?: string;
}

export interface CompetitorOverlap {
	competitor_name: string;
	solutions_competed: string[];
	competitor_type?: string;
	threat_level?: string;
}

export interface SolutionIntensity {
	solution_name: string;
	intensity: string;
}

export interface EvidenceAppendix {
	top_reddit_threads: RedditThread[];
	pain_point_quote_sources: PainPointQuoteSource[];
}

export interface RedditThread {
	post_id: string;
	title: string;
	subreddit: string;
	score: number;
	num_comments: number;
	url: string;
	created_utc?: string;
	key_insight: string;
	platform?: string; // "reddit", "hackernews", "youtube" — defaults to "reddit" for backward compat
}

export interface PainPointQuoteSource {
	pain_point_title: string;
	quotes_with_sources: QuoteWithSource[];
}

export interface QuoteWithSource {
	quote: string;
	post_id: string;
	/** Current reports serialize the platform-neutral model field by name. */
	source_label?: string;
	/** Legacy reports serialized the same field through its Reddit-era alias. */
	subreddit?: string;
	score: string;
}

export interface ContentCategorization {
	executive_summary: string;
	theme_categories: ThemeCategory[];
	user_segments: UserSegment[];
	overall_quality: string;
	overall_quality_justification: string;
}

export interface ThemeCategory {
	category_name: string;
	definition: string;
	frequency: string;
	mention_count: number;
	primary_user_segments: string[];
	representative_quotes: string[];
}

export interface UserSegment {
	segment_name: string;
	primary_concerns: string[];
	mention_frequency: string;
}

// Utility types
export type ReportSection =
	| 'solution'
	| 'technical'
	| 'journey'
	| 'executive'
	| 'pain-points'
	| 'seo'
	| 'competitors'
	| 'market-sizing'
	| 'pricing'
	| 'gtm'
	| 'trends'
	| 'audience'
	| 'alternatives'
	| 'evidence'
	| 'metadata';

export interface NavigationItem {
	id: ReportSection;
	label: string;
	icon: string;
}

// New NicheContext interface for full niche context data
export interface NicheContext {
	niche_input: string;
	niche_description: string;
	market_segments: string[];
	industry_boundaries: string;
	// Audience-framing (Stage 1 intent classification) — output framing only.
	user_target_audience?: string | null;
	resolved_primary_audience?: string | null;
	audience_scope?: string | null;
}

// =============================================================================
// Site Structure (Stage 15 - LLM-generated)
// =============================================================================

export interface SitePage {
	page_name: string;
	url_pattern: string;
	page_type: 'static' | 'programmatic' | 'dynamic';
	purpose: string;
	estimated_count?: number;
	priority: 'P0' | 'P1' | 'P2';
}

export interface SiteSection {
	section_name: string;
	description: string;
	pages: SitePage[];
}

export interface SiteStructure {
	overview: string;
	sections: SiteSection[];
	total_static_pages: number;
	total_programmatic_pages: number;
	mvp_page_count: number;
	tech_stack_recommendation?: string;
}

// =============================================================================
// User Flows (Stage 15 - LLM-generated)
// =============================================================================

export interface UserFlowStep {
	step_number: number;
	action: string;
	page: string;
	system_response?: string;
}

export interface UserFlow {
	flow_name: string;
	persona: string;
	goal: string;
	entry_point: string;
	steps: UserFlowStep[];
	conversion_point: string;
	success_metric: string;
}

export interface UserFlowsSection {
	flows: UserFlow[];
	key_insight?: string;
}

// Full data source research from Stage 13 (when requires_data_aggregation=true)
export interface DataSourceResearchFull {
	solution_name: string;
	primary_data_sources: DataSourceProvider[];
	fallback_sources?: DataSourceProvider[];
	source_evaluation?: SourceEvaluationReport;
	implementation_phases?: DataRoadmapPhase[];
	data_partnerships_needed?: DataPartnership[];
	estimated_monthly_cost?: string;
	data_quality_risks?: string[];
	implementation_roadmap: string;
	competitive_data_insights?: string;
	seo_aligned_priorities?: string;
}

export interface DataSourceProvider {
	provider: string;
	url?: string;
	access_model: string;
	cost_estimate?: string;
	coverage?: string;
	update_frequency?: string;
	integration_effort?: string;
	data_format?: string;
	relevance_score?: number;
	reliability_rating?: string;
}

export interface SourceEvaluationReport {
	evaluated_sources: EvaluatedDataSource[];
	recommended_stack: string[];
	total_mvp_cost?: string;
	total_scale_cost?: string;
	primary_risks: string[];
	risk_mitigation_strategies?: string[];
	seo_keyword_alignment?: string;
}

export interface EvaluatedDataSource {
	provider: string;
	url?: string;
	priority: string;
	priority_rationale: string;
	quality_metrics: DataQualityMetrics;
	mvp_cost_estimate?: string;
	scale_cost_estimate?: string;
	integration_risks?: string[];
	alternatives?: string[];
}

export interface DataQualityMetrics {
	coverage_score?: string;
	freshness?: string;
	integration_complexity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'LOW-MEDIUM' | 'MEDIUM-HIGH';
	cost_viability?: string;
	quality_assessment?: string;
}

export interface DataRoadmapPhase {
	phase_number: number;
	phase_name: string;
	timeline: string;
	goal: string;
	data_sources: string[];
	estimated_monthly_cost: string;
	key_milestones: string[];
	fallback_strategies: string[];
}

export interface DataPartnership {
	partner_type: string;
	potential_partners?: string[];
	value_exchange?: string;
	acquisition_difficulty?: string;
}
