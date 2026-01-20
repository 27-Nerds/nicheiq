// NicheIQ Report TypeScript Interfaces

export interface Report {
	niche: string;
	executive_summary: string;
	executive_dashboard: ExecutiveDashboard;
	go_to_market_blueprint: GoToMarketBlueprint;
	market_analytics: MarketAnalytics;
	seo_analytics: SEOAnalytics;
	competitive_analytics: CompetitiveAnalytics;
	pain_point_analytics: PainPointAnalytics;
	visualization_manifest?: VisualizationManifest;
	selected_solution_name: string;
	selection_rationale: string;
	// runner_up_solutions removed - extract names from alternative_solutions instead
	selection_criteria_scores?: SelectionCriteriaScore[];
	recommended_focus: string;
	selected_solution_details?: SolutionDetails;
	solution_user_journey?: string;
	solution_implementation_overview?: string;
	mvp_scope_definition?: string;
	pricing_strategy: PricingStrategy;
	market_sizing: MarketSizing;
	trend_longevity?: TrendLongevity;
	// top_pain_points removed - use detailed_pain_points instead
	pain_points_summary?: string;
	// pain_point_categories removed - derive from detailed_pain_points.categories
	audience_mapping?: AudienceMapping;
	recommended_solutions?: RecommendedSolution[];
	solutions_summary?: string;
	competitive_summary?: string;
	competitive_analysis: CompetitiveAnalysis;
	market_validation?: MarketValidation;
	acquisition_strategy_summary?: string;
	estimated_cac_breakdown?: CACBreakdown;
	keyword_validation_overview?: string;
	solution_keyword_comparison?: SolutionKeywordComparison[];
	content_strategy_preview?: string;
	data_source_research?: DataSourceResearch;
	data_sourcing_recommendations?: string;
	next_steps: string;
	research_metadata: ResearchMetadata;
	alternative_solutions?: AlternativeSolution[];
	competitive_landscape_matrix?: CompetitiveLandscapeMatrix;
	evidence_appendix?: EvidenceAppendix;
	data_infrastructure_roadmap?: string;
	content_categorization?: ContentCategorization;
	detailed_pain_points: DetailedPainPoint[];
	solution_innovation_assessment?: string;
	// solution_organic_discovery removed - use selected_solution_details.organic_discovery_queries instead
	competitor_profiles: CompetitorProfile[];
	generated_at: string;
	pdf_path?: string;

	// ========== NEW FULL STAGE DATA FIELDS ==========

	// Stage 1-4: Full Niche Context
	niche_context?: NicheContext;

	// Stage 9: Full SEO Strategy Report (not just seo_strategy)
	seo_strategy_report?: SEOStrategy;

	/// Stage 9.7: Full Data Source Research (not just summary)
	data_source_research_full?: DataSourceResearchFull;

	// Competitive Strategic Insights
	overall_competitive_insights?: string;

	// Traffic Monetization (Stage 8 pricing crew)
	traffic_monetization?: TrafficMonetization;

	// Refinement Highlights (Stage 8.7 solution refinement)
	refinement_highlights?: RefinementHighlights;

	// SEO Calculation Transparency
	seo_calculation_transparency?: SEOCalculationTransparency;

	// Data Quality Summary (top-level)
	data_quality_summary?: DataQualitySummary;
}

// Traffic Monetization interface
export interface TrafficMonetization {
	solution_name: string;
	monetization_model: string;
	estimated_monthly_pageviews: string;
	traffic_source_breakdown: Record<string, string>;
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
}

// Refinement Highlights interface
export interface RefinementHighlights {
	top_strategic_insights: string[];
	geographic_priority: string;
	feature_priority: string;
	category_pivot_recommendation: string | null;
}

// SEO Calculation Transparency interface
export interface SEOCalculationTransparency {
	baseline_seo_score: number;
	refined_seo_score: number;
	volume_multiplier: number;
	competition_modifier: number;
	tier1_multiplier: number;
	estimated_year1_pages: number;
	calculation_rationale: string;
}

export interface ExecutiveDashboard {
	recommended_solution_snapshot: SolutionSnapshot;
	go_no_go_verdict: GoNoGoVerdict;
	core_pain_point: CorePainPoint;
	key_metrics: KeyMetrics;
	confidence_score: number;
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
}

export interface CorePainPoint {
	title: string;
	severity_score: number;
	willingness_to_pay_score: number;
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
	high_priority_pain_points: number;
	primary_competitor_count: number;
	avg_pain_point_severity: number;
	avg_willingness_to_pay: number;
	social_evidence_threads: number;
	market_fit_score?: number | null;
	competitive_advantage_score?: number | null;
	technical_feasibility_score?: number | null;
	seo_potential_score?: number | null;
}

export interface GoToMarketBlueprint {
	ideal_customer_profile: IdealCustomerProfile;
	core_marketing_message: string;
	message_framework: string;
	recommended_channels: RecommendedChannel[];
	example_content_angles: ContentAngle[];
	first_30_days_playbook: Playbook;
	budget_estimate: string;
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
	avg_competition: number;
	keyword_diversity_score: number;
	high_volume_keywords: number;
}

export interface CompetitiveAnalytics {
	competitor_count: number;
	market_saturation_score: number;
	differentiation_strength: string;
	market_gaps_identified: number;
	avg_competitor_features: number;
}

export interface PainPointAnalytics {
	total_pain_points: number;
	high_priority_count: number;
	quadrant_distribution: QuadrantDistribution;
	avg_severity?: number;
	avg_willingness_to_pay?: number;
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
	willingness_to_pay: number;
	opportunity_level: 'high' | 'medium' | 'low';
	representative_quotes: string[];
	source_platforms: string[];
	categories: string[];
	source_post_ids: string[];
	source_engagement_metrics: EngagementMetric[];
	affected_segments?: string[];
}

export interface EngagementMetric {
	post_id: string;
	score: number;  // Matches Python field name (upvotes/engagement score)
}

export interface SEOStrategy {
	seed_keywords_generated?: string[];
	total_keywords_analyzed: number;
	total_monthly_volume: number;
	key_findings?: string[];
	tier_0_keywords: Keyword[];
	tier_0_strategy?: string;
	tier_1_keywords: Keyword[];
	tier_1_quick_win_strategy?: string;
	tier_2_keywords: Keyword[];
	tier_2_strategy?: string;
	tier_3_geographic_groups?: KeywordGroup[];
	tier_4_category_groups?: CategoryKeywordGroup[];
	content_strategy?: string;
	topic_clusters?: TopicCluster[];
	technical_seo_recommendations?: string;
	keyword_driven_site_architecture?: SiteArchitecture;
	keyword_based_page_types?: PageType[];
	competitive_positioning?: string;
	implementation_roadmap?: string;
	key_metrics_to_track?: string[];
	risk_mitigation?: string;
	budget_allocation?: string;
	long_term_strategy?: string;
	conclusion_bottom_line?: string;
	competitive_advantages?: string[];
	critical_success_factors?: string[];
	expected_timeline?: string;
	next_steps_checklist?: string[];
	universal_seo_elements?: UniversalSEOElements;
	page_type_implementations?: PageTypeImplementation[];
	schema_markup_strategy?: SchemaMarkupStrategy;
}

export interface Keyword {
	keyword: string;
	search_volume: number;
	competition: string;
	opportunity_score: number;  // Required, matches Python int
	strategy?: string;
	intent?: string;
	tier?: number;
	tier_rationale?: string;
}

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
	cpc?: number;
}

export interface CategoryKeywordGroup {
	category_name: string;
	total_volume: number;
	keywords: CategoryKeyword[];
	strategy_recommendation?: string;
}

export interface SectionKeywordMapping {
	section_path: string;
	keyword_cluster: string;
}

export interface SiteArchitecture {
	url_hierarchy_diagram?: string;
	section_keyword_mapping?: SectionKeywordMapping[];
	total_pages_from_keywords?: number;
	keyword_coverage_explanation?: string;
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
	estimated_page_count: number;
	priority: number;
	required_schema?: string[];
	seo_optimization_notes?: string;
}


export interface UniversalSEOElements {
	title_tag_formula?: string;
	title_tag_guidelines?: string;
	meta_description_guidelines?: string;
	canonical_url_strategy?: string;
	open_graph_tags?: string;
	robots_meta_guidelines?: string;
	robots_meta_guidelines_note?: string | null;
}

export interface PageTypeImplementation {
	page_type: string;
	url_pattern?: string;
	target_keywords?: string[];
	title_tag_example?: string;
	meta_description_example?: string;
	h1_structure?: string;
	h2_structure?: string[] | string; // Support both old (string) and new (array) formats
	schema_types?: string[];
	internal_linking_strategy?: string;
	content_guidelines?: string;
	priority?: 'High' | 'Medium' | 'Low';
}

export interface SchemaExample {
	schema_type: string;
	json_ld_code: string;
}

export interface SchemaMarkupStrategy {
	why_schema_matters?: string;
	priority_schema_types?: string[];
	implementation_method?: string;
	schema_examples?: SchemaExample[];
	testing_validation?: string;
}

export interface CompetitiveAnalysis {
	solution_landscapes: SolutionLandscape[];
	top_opportunities: string[];
	strategic_recommendations: string;
}

export interface SolutionLandscape {
	solution_name: string;
	competitors: string[];
	positioning?: string;
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
	market_segment_pricing?: MarketSegmentPricing[];
}

export interface MarketSegmentPricing {
	segment: string;
	recommended_price: string;
	rationale?: string;
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
	peak_periods?: string | null;

	// Assessment
	market_maturity?: string;
	longevity_verdict?: string; // Sustainable | Risky | Fad
	longevity_rationale?: string;
	timing_recommendation?: string;
	risk_factors?: string[];

	// Metadata
	data_sources_analyzed?: string;
	analysis_timeframe?: string;

	// Legacy fields (for backward compatibility)
	overall_score?: number;
	trend_analysis?: string;
	longevity_factors?: string[];
}

export interface ResearchMetadata {
	// Python backend fields (primary)
	reddit_posts_analyzed?: number;
	reddit_comments_analyzed?: number;
	twitter_threads_analyzed?: number;
	top_subreddits?: SubredditBreakdown[];
	collection_date?: string;
	data_size_mb?: number;
	completed_stages?: number[];
	fallback_stages?: number[];
	filtering_stats?: Record<string, unknown>;
	// Legacy/optional fields
	research_id?: string;
	started_at?: string;
	completed_at?: string;
	total_duration_minutes?: number;
	stages_completed?: string[];
	data_sources?: DataSource[];
	token_usage?: TokenUsage;
	data_quality_summary?: DataQualitySummary;
}

export interface SubredditBreakdown {
	name: string;
	post_count: number;
}

export interface DataQualitySummary {
	social_content_quality_tier?: string; // EXCELLENT, GOOD, MINIMAL, INSUFFICIENT
	pain_point_quality_tier?: string; // GOLD, SILVER, BRONZE, INSUFFICIENT
	pain_point_confidence_score?: number; // 0-1
	overall_data_quality: string; // HIGH, MEDIUM, LOW
	quality_caveats: string[];
	stages_with_fallback_data?: string[];
}

export interface DataSource {
	source: string;
	items_collected: number;
	quality_score?: number;
}

export interface TokenUsage {
	total_tokens?: number;
	prompt_tokens?: number;
	completion_tokens?: number;
	estimated_cost?: string;
}

export interface VisualizationManifest {
	charts?: ChartConfig[];
	generated_at?: string;
}

export interface ChartConfig {
	chart_id: string;
	chart_type: string;
	title: string;
	data_source: string;
}

// RunnerUpSolution interface removed - use alternative_solutions instead

// Selection criteria score - array format matching Python backend
export interface SelectionCriteriaScore {
	criterion: string;
	score: number;
	justification: string;
}

export interface SolutionDetails {
	// Basic info (may use solution_name or name)
	name?: string;
	solution_name?: string;
	description: string;
	key_features?: string[];
	target_audience?: string;
	unique_value_proposition?: string;
	technical_requirements?: string[];
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
	novelty_justification?: string;
	solo_dev_feasibility?: number;
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
	// MVP complexity indicator
	mvp_complexity?: string;
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
	content_strategy_direction?: string;
	early_adopter_tactics?: string;

	// Legacy fields (for backward compatibility)
	primary_segments?: AudienceSegment[];
	secondary_segments?: AudienceSegment[];
}

export interface Influencer {
	name: string;
	platform: string;
	follower_estimate?: number;
	relevance_score?: number;
	engagement_level?: string;
	outreach_priority?: string;
	content_focus?: string;
}

export interface AudienceSegment {
	segment_name: string;
	size_estimate?: string;
	pain_point_alignment?: string[];
	motivation_drivers?: string[];
	expertise_level?: string;
	budget_sensitivity?: string;
	discovery_channels?: string[];

	// Legacy fields (for backward compatibility)
	characteristics?: string[];
	pain_points?: string[];
	channels?: string[];
}

export interface RecommendedSolution {
	name: string;
	description: string;
	fit_score: number;
	rationale: string;
}

export interface MarketValidation {
	validation_score: number;
	key_indicators: string[];
	risks: string[];
	opportunities: string[];
}

export interface CACBreakdown {
	paid_acquisition?: string;
	organic_acquisition?: string;
	referral?: string;
	blended_cac?: string;
}

export interface SolutionKeywordComparison {
	solution_name: string;
	total_volume: number;
	keyword_count: number;
	avg_difficulty?: number;
}

export interface DataSourceResearch {
	recommended_sources: DataSourceRecommendation[];
	integration_complexity?: string;
	estimated_costs?: string;
}

export interface DataSourceRecommendation {
	source_name: string;
	source_type: string;
	relevance: string;
	access_method?: string;
}

// Full data source research from Stage 9.7 (when requires_data_aggregation=true)
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
	rate_limits?: string;
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

export interface AlternativeSolution {
	// Core identification
	solution_name: string;
	summary: string;

	// Legacy fields (for backward compatibility)
	name?: string;
	description?: string;
	pros?: string[];
	cons?: string[];
	fit_score?: number;

	// Existing score fields
	market_fit_score?: number;
	technical_feasibility_score?: number;
	competitive_advantage_score?: number;
	seo_growth_potential_score?: number;

	// Existing strategic fields
	key_differentiator?: string;
	best_suited_for?: string;
	pivot_trigger?: string;

	// NEW: Core solution details
	value_proposition?: string;
	core_features?: string[];
	target_personas?: string[];
	technical_approach?: string;

	// NEW: Additional scores and feasibility
	novelty_score?: number;
	solo_dev_feasibility?: number; // 0-1 scale matching Python float

	// NEW: Competitive landscape for this solution
	top_competitors?: string[];
	market_gaps?: string[];
	competitive_intensity?: string; // LOW, MEDIUM, HIGH

	// NEW: Economic indicators
	estimated_development_time?: string;
	estimated_cac_organic?: string;  // Matches Python: str format like "$15-30"
	pricing_model?: string;
}

export interface CompetitiveLandscapeMatrix {
	all_solutions_analyzed: string[];
	selected_solution_competitors?: string[];
	competitor_overlap: CompetitorOverlap[];
	competitive_intensity_by_solution?: SolutionIntensity[];
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
	key_insight: string;
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
	discussion_quality_assessment: string;
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
}
