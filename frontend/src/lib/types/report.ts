// NicheIQ Report TypeScript Interfaces

import type { IdeaTags, SolutionPreview } from './job';

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

	// Web-verified incumbent landscape + niche wallet read, gathered alongside the parity
	// probe (see incumbent_parity on solutions). Absent on legacy/older reports.
	market_reality?: MarketReality;

	// Research Reality Check — candid software-fit verdict
	niche_difficulty_verdict?: NicheDifficultyVerdict;

	// LLM-narrated honest assessment of the visible idea pool (strengths/weaknesses across
	// all candidates), computed once in Stage 5. null when the pool was empty or the
	// grounded LLM pass failed its name-coverage guardrail.
	idea_portfolio_summary?: string | null;

	// Stage timing summary (pipeline execution timing)
	stage_timing_summary?: StageTimingSummary;

	// Share indexing control (injected by backend for shared reports)
	_shareAllowIndexing?: boolean;
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
	estimated_cpm_rate?: string;
	estimated_monthly_ad_revenue: string;
	recommended_ad_networks: string[];
	affiliate_commission_rate?: string;
	estimated_affiliate_ctr?: string;
	estimated_monthly_affiliate_revenue: string;
	recommended_affiliate_programs: string[];
	sponsored_listing_price?: string;
	premium_placement_price?: string;
	lead_gen_price_per_lead?: string;
	estimated_monthly_revenue_range: string;
	estimated_annual_revenue_range: string;
	break_even_traffic_threshold?: string;
	monetization_rationale: string;
	scaling_strategy: string;
	monetization_confidence?: 'High' | 'Medium' | 'Low';
	saas_alternative_viable: boolean;
	saas_vs_traffic_recommendation: string;
	traffic_methodology?: string;
	traffic_data_sources?: string[];
	year3_monthly_pageviews?: string;
	year3_monthly_revenue?: string;
	full_potential_monthly_pageviews?: string;
	full_potential_monthly_revenue?: string;
	revenue_growth_note?: string;
	revenue_milestones?: Array<{
		traffic: string;
		ad_revenue: string;
		unlock: string;
		total_potential: string;
	}>;
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
	recommended_solution_snapshot: SolutionSnapshot;
	go_no_go_verdict: GoNoGoVerdict;
	core_pain_point: CorePainPoint;
	key_metrics: KeyMetrics;
	confidence_score: number | null;
	research_depth_label?: string;
	// niche_description removed - use root report.niche instead
}

export interface SolutionSnapshot {
	name: string;
	tagline: string;
	core_value_prop: string;
	project_type: string;
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
	total_monthly_volume: number;
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
	key_challenges: string[];
	low_confidence: boolean;
	/** Who actually pays here: budgeted-business | smb-operator | prosumer | indie-hobbyist | consumer | mixed. */
	buyer_class?: string | null;
	/** One-liner on what the buyer class means for monetization. */
	buyer_class_note?: string | null;
}

export interface DataQualitySummary {
	social_content_quality_tier?: string; // EXCELLENT, GOOD, MINIMAL, INSUFFICIENT
	pain_point_quality_tier?: string; // GOLD, SILVER, BRONZE, INSUFFICIENT (evidence-based: measures research quality, not niche attractiveness)
	pain_point_confidence_score?: number; // 0-1 (based on unique sources, subreddit diversity, quote density, pain point count)
	overall_data_quality: string; // HIGH, MEDIUM, LOW
	quality_caveats: string[];
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
	programmatic_seo_opportunity?: string;
	programmatic_seo_opportunity_refined?: string;
	content_generation_model?: string;
	organic_discovery_queries?: string[];
	estimated_cac_organic?: string;
	estimated_cac_organic_refined?: string;
	estimated_cac_paid?: string;
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
	source_segment_payability?: number | null; // 0-1 buyer-wallet strength of the source segment (permanent signal; null = segment map failed)
	source_segment_payability_class?: string | null; // corporate-budget | smb-budget | prosumer-wallet | personal-wallet | mixed
	// Multi-Frame Idea Generation Portfolio: which generation frame minted this idea's cell.
	// CODE-FILLED, never LLM-set. pain | gap | data_asset | spend_adjacent | workflow
	source_frame?: string | null;

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
	subreddit: string;
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
