import type {
  Report,
  MarketSizing,
  SEOStrategy,
  SEOAnalytics,
  CompetitorProfile,
  CompetitiveAnalysis,
  CompetitiveAnalytics,
} from '$lib/types/report';

// ---------------------------------------------------------------------------
// Executive Dashboard placeholder (UnifiedHero takes full Report)
// ---------------------------------------------------------------------------

export function placeholderExecutiveDashboard(niche: string): Report {
  return {
    niche,
    executive_summary: `Preliminary analysis of the ${niche} market indicates strong demand signals across multiple audience segments.`,
    selected_solution_name: `${niche} Opportunity Analyzer`,
    selection_rationale: `High pain point severity combined with underserved audience segments in the ${niche} space.`,
    competitor_profiles: [],
    generated_at: new Date().toISOString(),
    executive_dashboard: {
      recommended_solution_snapshot: {
        name: `${niche} Opportunity Analyzer`,
        tagline: `Turn ${niche} frustrations into validated product ideas`,
        core_value_prop: `Automated market validation for the ${niche} space using real user conversations`,
        project_type: 'SaaS Platform',
      },
      go_no_go_verdict: {
        verdict: 'Go',
        rationale: `Strong demand signals detected across ${niche} communities with clear willingness to pay for solutions.`,
        risk_level: 'Medium',
        primary_concern: 'Market timing and competitive entry window',
      },
      core_pain_point: {
        title: `Fragmented ${niche} workflows`,
        severity_score: 0.78,
        willingness_to_pay_score: 0.65,
        representative_quote: `I spend hours every week trying to piece together ${niche} data from different sources.`,
        source_platform: 'Reddit',
      },
      key_metrics: {
        total_keyword_search_volume: 124000,
        tier0_keyword_count: 3,
        tier1_keyword_count: 8,
        tier2_keyword_count: 15,
        tier3_keyword_count: 22,
        tier4_keyword_count: 12,
        total_keyword_count: 60,
        high_severity_pain_points: 4,
        primary_competitor_count: 6,
        avg_pain_point_severity: 7.2,
        avg_willingness_to_pay: 6.1,
        social_evidence_threads: 79,
        market_fit_score: 0.72,
        competitive_advantage_score: 0.65,
        technical_feasibility_score: 0.78,
        seo_potential_score: 0.68,
        solo_dev_feasibility: 0.7,
      },
      confidence_score: 0.74,
      research_depth_label: 'Standard',
    },
    market_analytics: {
      overall_opportunity_score: 0.72,
      market_size_category: 'Mid-Market',
      selection_confidence: 0.74,
      competitive_intensity: 'Moderate',
      recommendation: `The ${niche} market shows healthy demand with manageable competition.`,
    },
    refinement_highlights: {
      top_strategic_insights: [
        `${niche} users prioritize speed and reliability over feature breadth`,
        'Mobile-first approach could capture underserved segment',
      ],
      geographic_priority: null,
      feature_priority: null,
      category_pivot_recommendation: null,
    },
  };
}

// ---------------------------------------------------------------------------
// Market Sizing placeholder
// ---------------------------------------------------------------------------

export function placeholderMarketSizing(niche: string): MarketSizing {
  return {
    total_addressable_market: '$2.4B',
    serviceable_available_market: '$380M',
    serviceable_obtainable_market_y1: '$4.2M',
    serviceable_obtainable_market_y3: '$18M',
    primary_methodology: 'Bottom-up keyword demand + competitor revenue benchmarking',
    methodology_explanation: `Market size derived from search volume for ${niche}-related queries, competitor pricing data, and audience segment sizing from social evidence.`,
    data_sources_used: [
      'Google Keyword Planner',
      'Competitor pricing pages',
      'Reddit community sizes',
      'Industry reports',
    ],
    segment_sizing: [
      {
        segment_name: 'Solo practitioners',
        tam_estimate: '$800M',
        sam_estimate: '$120M',
        som_estimate: '$1.8M',
        sizing_methodology: 'Keyword volume extrapolation',
        confidence_level: 'Medium',
      },
      {
        segment_name: 'Small teams',
        tam_estimate: '$1.1B',
        sam_estimate: '$180M',
        som_estimate: '$2.0M',
        sizing_methodology: 'Competitor revenue benchmarking',
        confidence_level: 'Medium',
      },
    ],
    keyword_demand_signal: `${niche} solution queries show 15% YoY growth`,
    pain_point_frequency: 'High frequency across 4 major pain categories',
    competitor_market_presence: '6 primary competitors with combined estimated ARR of $45M',
    market_growth_rate: '18% CAGR',
    growth_drivers: [
      `Increasing digitization of ${niche} workflows`,
      'Growing frustration with fragmented tooling',
      'Remote work driving demand for centralized platforms',
    ],
    risk_factors: [
      'Established players may launch competing features',
      'Market timing sensitivity',
    ],
    market_saturation_level: 'Medium',
    market_timing_assessment: 'Growth',
    market_viability_verdict: 'Strong',
    viability_rationale: `The ${niche} market is growing with clear gaps that existing solutions fail to address.`,
    recommended_entry_strategy: `Niche-down on the highest-severity pain point and expand from there.`,
  };
}

// ---------------------------------------------------------------------------
// SEO Strategy + Analytics placeholder
// ---------------------------------------------------------------------------

export function placeholderSEOStrategy(niche: string): {
  strategy: SEOStrategy;
  analytics: SEOAnalytics;
} {
  return {
    strategy: {
      total_keywords_analyzed: 60,
      total_monthly_volume: 124000,
      key_findings: [
        `High search intent for "best ${niche} tools" cluster`,
        `Low competition in long-tail ${niche} comparison queries`,
        'Geographic modifiers present opportunity for local pages',
      ],
      tier_0_keywords: [
        {
          keyword: `best ${niche} software`,
          search_volume: 12100,
          competition: 'medium',
          opportunity_score: 78,
          keyword_difficulty: 42,
          strategy: 'Cornerstone content with comparison angle',
          intent: 'commercial',
          tier: 0,
        },
        {
          keyword: `${niche} platform`,
          search_volume: 8100,
          competition: 'medium',
          opportunity_score: 72,
          keyword_difficulty: 45,
          strategy: 'Product landing page optimization',
          intent: 'commercial',
          tier: 0,
        },
        {
          keyword: `${niche} tools`,
          search_volume: 6600,
          competition: 'low',
          opportunity_score: 82,
          keyword_difficulty: 35,
          strategy: 'Listicle and feature comparison hub',
          intent: 'informational',
          tier: 0,
        },
      ],
      tier_0_strategy: `Dominate core ${niche} commercial queries with comparison and review content.`,
      tier_1_keywords: [
        {
          keyword: `${niche} automation`,
          search_volume: 4400,
          competition: 'low',
          opportunity_score: 85,
          keyword_difficulty: 28,
          strategy: 'Tutorial and use-case content',
          intent: 'informational',
          tier: 1,
        },
        {
          keyword: `${niche} workflow`,
          search_volume: 3600,
          competition: 'low',
          opportunity_score: 80,
          keyword_difficulty: 30,
          strategy: 'Template and guide pages',
          intent: 'informational',
          tier: 1,
        },
        {
          keyword: `${niche} for small business`,
          search_volume: 2900,
          competition: 'low',
          opportunity_score: 76,
          keyword_difficulty: 25,
          strategy: 'Segment-targeted landing pages',
          intent: 'commercial',
          tier: 1,
        },
        {
          keyword: `free ${niche} tool`,
          search_volume: 2400,
          competition: 'medium',
          opportunity_score: 68,
          keyword_difficulty: 38,
          strategy: 'Free tier funnel content',
          intent: 'transactional',
          tier: 1,
        },
        {
          keyword: `${niche} comparison`,
          search_volume: 1900,
          competition: 'low',
          opportunity_score: 74,
          keyword_difficulty: 22,
          strategy: 'Head-to-head comparison pages',
          intent: 'commercial',
          tier: 1,
        },
        {
          keyword: `${niche} reviews`,
          search_volume: 1600,
          competition: 'medium',
          opportunity_score: 70,
          keyword_difficulty: 40,
          strategy: 'User review aggregation content',
          intent: 'commercial',
          tier: 1,
        },
        {
          keyword: `how to choose ${niche} software`,
          search_volume: 1200,
          competition: 'low',
          opportunity_score: 82,
          keyword_difficulty: 18,
          strategy: 'Buyer guide content',
          intent: 'informational',
          tier: 1,
        },
        {
          keyword: `${niche} tips`,
          search_volume: 1100,
          competition: 'low',
          opportunity_score: 72,
          keyword_difficulty: 20,
          strategy: 'Blog content series',
          intent: 'informational',
          tier: 1,
        },
      ],
      tier_1_quick_win_strategy: `Target low-competition ${niche} queries with comparison and guide content for fast organic wins.`,
      tier_2_keywords: [
        {
          keyword: `${niche} integration`,
          search_volume: 880,
          competition: 'low',
          opportunity_score: 65,
          keyword_difficulty: 20,
          strategy: 'Integration partner pages',
          intent: 'informational',
          tier: 2,
        },
        {
          keyword: `${niche} pricing`,
          search_volume: 720,
          competition: 'medium',
          opportunity_score: 60,
          keyword_difficulty: 35,
          strategy: 'Transparent pricing page',
          intent: 'transactional',
          tier: 2,
        },
      ],
      tier_2_strategy: `Build supporting content around ${niche} integration and pricing queries.`,
      tier_3_geographic_groups: [
        {
          region_name: 'United States',
          total_volume: 3200,
          competition_level: 'medium',
          keywords: [
            {
              city: 'New York',
              keyword: `${niche} services New York`,
              search_volume: 1400,
            },
            {
              city: 'San Francisco',
              keyword: `${niche} tools San Francisco`,
              search_volume: 900,
            },
            {
              city: 'Austin',
              keyword: `${niche} solutions Austin`,
              search_volume: 900,
            },
          ],
          strategy_notes: 'US metro areas show strongest localized demand.',
        },
      ],
      tier_4_category_groups: [
        {
          category_name: `${niche} Enterprise`,
          total_volume: 2800,
          keywords: [
            {
              keyword_name: `enterprise ${niche} platform`,
              search_volume: 1600,
              competition: 'high',
              keyword_difficulty: 55,
            },
            {
              keyword_name: `${niche} for teams`,
              search_volume: 1200,
              competition: 'medium',
              keyword_difficulty: 40,
            },
          ],
          strategy_recommendation: 'Long-term play; build authority before targeting.',
        },
      ],
      content_strategy: `Focus on comparison and buyer-guide content targeting ${niche} commercial intent queries.`,
      topic_clusters: [
        {
          cluster_name: `${niche} Getting Started`,
          primary_keyword: `how to use ${niche} tools`,
          supporting_keywords: [
            `${niche} beginner guide`,
            `${niche} setup tutorial`,
            `${niche} first steps`,
          ],
          total_monthly_volume: 4200,
          content_recommendation: 'Comprehensive pillar page with step-by-step tutorials',
          priority: 1,
        },
      ],
      competitive_positioning: `Position as the most accessible and data-driven ${niche} solution for solo practitioners and small teams.`,
      implementation_roadmap: 'Month 1-2: Core pages. Month 3-4: Blog content. Month 5-6: Programmatic pages.',
    },
    analytics: {
      tier0_count: 3,
      tier1_count: 8,
      tier2_count: 15,
      tier3_count: 22,
      tier4_count: 12,
      total_keywords: 60,
      total_search_volume: 124000,
      core_search_volume: 26800,
      avg_competition: 0.42,
      keyword_diversity_score: 7.4,
      high_volume_keywords: 5,
    },
  };
}

// ---------------------------------------------------------------------------
// Competitors placeholder
// ---------------------------------------------------------------------------

export function placeholderCompetitors(niche: string): {
  profiles: CompetitorProfile[];
  analysis: CompetitiveAnalysis;
  analytics: CompetitiveAnalytics;
} {
  return {
    profiles: [
      {
        name: `${niche}Hub`,
        url: 'https://example.com',
        competitor_type: 'DIRECT',
        description: `Full-stack ${niche} management platform for mid-market teams.`,
        key_features: [
          'Workflow automation',
          'Team collaboration',
          'Analytics dashboard',
          'API integrations',
        ],
        pricing_model: 'Freemium with $29/mo starter tier',
        strengths: [
          'Strong brand recognition',
          'Mature feature set',
          'Active community',
        ],
        weaknesses: [
          'Complex onboarding',
          'Expensive at scale',
          'Slow to ship new features',
        ],
      },
      {
        name: `Quick${niche}`,
        url: 'https://example.com',
        competitor_type: 'DIRECT',
        description: `Lightweight ${niche} tool focused on speed and simplicity.`,
        key_features: [
          'One-click workflows',
          'Mobile app',
          'Basic reporting',
        ],
        pricing_model: 'Flat $19/mo',
        strengths: [
          'Fast onboarding',
          'Clean interface',
          'Affordable pricing',
        ],
        weaknesses: [
          'Limited integrations',
          'No team features',
          'Basic analytics',
        ],
      },
      {
        name: `${niche}Pro`,
        url: 'https://example.com',
        competitor_type: 'PARTIAL',
        description: `Enterprise ${niche} suite with deep analytics and compliance features.`,
        key_features: [
          'Advanced analytics',
          'Compliance reporting',
          'Custom workflows',
          'SSO',
        ],
        pricing_model: 'Custom pricing, estimated $200+/mo',
        strengths: [
          'Enterprise-grade security',
          'Deep analytics',
          'Dedicated support',
        ],
        weaknesses: [
          'Overkill for small teams',
          'Long sales cycle',
          'Steep learning curve',
        ],
      },
    ],
    analysis: {
      solution_landscapes: [
        {
          solution_name: `${niche} Opportunity Analyzer`,
          competitors: [
            `${niche}Hub`,
            `Quick${niche}`,
            `${niche}Pro`,
          ],
          market_gaps: [
            'No existing tool validates market opportunities using real social data',
            'Competitor analytics are backward-looking, not predictive',
            'Solo practitioner segment is underserved by current offerings',
          ],
          differentiation_opportunities: [
            'AI-powered pain point extraction from community discussions',
            'Automated competitive landscape mapping',
            'One-click market validation workflow',
          ],
          competitive_intensity: 'Moderate',
          recommended_positioning: `Position as the intelligence layer that existing ${niche} tools lack.`,
          pricing_insights: 'Market supports $19-49/mo for individual plans.',
        },
      ],
      top_opportunities: [
        'Solo practitioner segment has no dedicated solution',
        'Pain point validation is entirely manual today',
        'SEO opportunity in comparison and review content',
      ],
      strategic_recommendations: `Enter the ${niche} market via the solo practitioner segment with a focused MVP, then expand to teams.`,
    },
    analytics: {
      competitor_count: 6,
      market_saturation_score: 0.45,
      differentiation_strength: 'Moderate',
      market_gaps_identified: 3,
      avg_competitor_features: 8,
    },
  };
}

// ---------------------------------------------------------------------------
// Generation Slideshow data
// ---------------------------------------------------------------------------

export interface GenerationSlide {
  title: string;
  description: string;
  bullets: string[];
  relatedStage?: number;
}

export const DISCOVERY_SLIDES: GenerationSlide[] = [
  {
    title: 'Scanning Communities',
    description: 'Searching Reddit and forums for real conversations about your niche.',
    bullets: [
      'Identifying active subreddits and communities',
      'Filtering for quality discussions with real frustrations',
      'Building a discussion database for analysis',
    ],
    relatedStage: 1,
  },
  {
    title: 'Mining Pain Points',
    description: 'Extracting the specific problems people are struggling with.',
    bullets: [
      'Natural language analysis of complaints and requests',
      'Severity scoring based on frequency and emotional intensity',
      'Willingness-to-pay signals from spending mentions',
    ],
    relatedStage: 3,
  },
  {
    title: 'Mapping Your Audience',
    description: 'Identifying who these people are and what drives them.',
    bullets: [
      'Audience segmentation by behavior and motivation',
      'Community hub identification and influence mapping',
      'Budget sensitivity and purchase intent signals',
    ],
    relatedStage: 4,
  },
  {
    title: 'Generating Opportunities',
    description: 'Turning validated pain points into business ideas you can act on.',
    bullets: [
      'Solution ideation matched to pain severity',
      'Market fit scoring and feasibility analysis',
      'Competitive positioning recommendations',
    ],
    relatedStage: 5,
  },
];

export const GENERATION_SLIDES: GenerationSlide[] = [
  {
    title: 'Go / No-Go Verdict',
    description: 'We are scoring your opportunity against our validation framework.',
    bullets: [
      'Pain point severity weighted against willingness to pay',
      'Competitive moat assessment',
      'Risk-adjusted confidence score',
    ],
    relatedStage: 6,
  },
  {
    title: 'Market Sizing',
    description: 'Calculating your total addressable market from multiple data signals.',
    bullets: [
      'TAM, SAM, and SOM estimates with methodology',
      'Segment-level breakdown by audience type',
      'Growth rate projections and risk factors',
    ],
    relatedStage: 7,
  },
  {
    title: 'Pricing Strategy',
    description: 'Testing pricing models against competitor benchmarks and willingness to pay.',
    bullets: [
      'Recommended tier pricing with feature allocation',
      'Unit economics: ARPU, LTV, and LTV-to-CAC ratio',
      'Competitive price positioning analysis',
    ],
    relatedStage: 8,
  },
  {
    title: 'Trend Longevity',
    description: 'Measuring whether demand in this space is growing, stable, or declining.',
    bullets: [
      'Keyword volume trend direction and growth rate',
      'Community activity signals and new entrant tracking',
      'Seasonality patterns and reversal risks',
    ],
    relatedStage: 9,
  },
  {
    title: 'Competitive Landscape',
    description: 'Mapping every competitor, their features, and where the gaps are.',
    bullets: [
      'Direct, partial, and indirect competitor profiles',
      'Feature comparison matrix across competitors',
      'Market gaps and differentiation opportunities',
    ],
    relatedStage: 10,
  },
  {
    title: 'SEO Keyword Strategy',
    description: 'Validating search demand with real keyword data and difficulty scores.',
    bullets: [
      'Tiered keyword list: quick wins to long-term plays',
      'Search volume, difficulty, and intent for every keyword',
      'Topic clusters and programmatic page opportunities',
    ],
    relatedStage: 11,
  },
  {
    title: 'Go-to-Market Playbook',
    description: 'Building your 30-day launch plan with channel priorities.',
    bullets: [
      'Ideal customer profile with buying triggers',
      'Channel-by-channel strategy with audience sizing',
      'Week-by-week action plan for the first month',
    ],
    relatedStage: 12,
  },
  {
    title: 'Technical Blueprint',
    description: 'Designing your MVP scope and technical architecture.',
    bullets: [
      'Core feature prioritization and build timeline',
      'Site structure with page types and URL patterns',
      'User flows mapped from entry to conversion',
    ],
    relatedStage: 13,
  },
  {
    title: 'Content and Data Sources',
    description: 'Identifying content opportunities and data infrastructure needs.',
    bullets: [
      'Content categorization from community discussions',
      'Data source evaluation with cost and reliability ratings',
      'Implementation roadmap phased by priority',
    ],
    relatedStage: 14,
  },
];

// ---------------------------------------------------------------------------
// Full-page discovery overlay slides (from waiting.html)
// ---------------------------------------------------------------------------

export interface DiscoverySlide {
  id: string;
  type: 'waiting' | 'edge' | 'step';
  accentLabel?: string;
  stepSymbol?: string;
  stepName?: string;
  headingBefore: string;
  headingEmphasis: string;
  body: string;
  bodyBoldPhrases?: string[];
  comparePills?: {
    without: string;
    withNicheIQ: string;
  };
  relatedStage?: number;
  duration?: number;
}

export const DISCOVERY_FULLPAGE_SLIDES: DiscoverySlide[] = [
  {
    id: 'waiting',
    type: 'waiting',
    headingBefore: 'Your niche is being',
    headingEmphasis: 'researched right now.',
    body: 'This takes up to 15 minutes. We\u2019ll email you the moment it\u2019s ready.',
    bodyBoldPhrases: ['up to 15 minutes.'],
    duration: 10_000,
  },
  {
    id: 'edge',
    type: 'edge',
    accentLabel: 'Our edge',
    headingBefore: 'Real research',
    headingEmphasis: 'takes real time.',
    body: 'We work with primary sources \u2014 live Reddit discussions, real search data, actual timestamps. AI is just a tool here. What matters is the data, and when it was collected.',
    bodyBoldPhrases: ['primary sources'],
    comparePills: {
      without: 'AI summaries with no source or date',
      withNicheIQ: 'Primary sources \u00b7 real-time \u00b7 timestamped',
    },
  },
  {
    id: 'step-1',
    type: 'step',
    accentLabel: 'Discovery \u00b7 Step 1',
    stepSymbol: '\u2299',
    stepName: 'Overview',
    headingBefore: 'Your niche,',
    headingEmphasis: 'at a glance.',
    body: 'Before the details \u2014 a clear picture of the market. Size, activity level, and whether there\u2019s real demand worth going after.',
    bodyBoldPhrases: ['Size, activity level, and whether there\u2019s real demand'],
    comparePills: {
      without: 'Hours of research just to know where to start',
      withNicheIQ: 'Market snapshot \u00b7 ready in seconds',
    },
    relatedStage: 1,
  },
  {
    id: 'step-2',
    type: 'step',
    accentLabel: 'Discovery \u00b7 Step 2',
    stepSymbol: '\u25b3',
    stepName: 'Pain Points',
    headingBefore: 'Which problems are',
    headingEmphasis: 'worth solving?',
    body: 'Every pain point scored by severity, frequency, and willingness to pay. Numbers, not guesses.',
    bodyBoldPhrases: ['Numbers, not guesses.'],
    comparePills: {
      without: 'ChatGPT: \u201cUsers likely experience frustration\u2026\u201d',
      withNicheIQ: '7.5/10 severity \u00b7 $$ WTP \u00b7 \u201ctook 3 hours and I gave up\u201d',
    },
    relatedStage: 3,
  },
  {
    id: 'step-3',
    type: 'step',
    accentLabel: 'Discovery \u00b7 Step 3',
    stepSymbol: '\u2043',
    stepName: 'Audience',
    headingBefore: 'Who actually cares',
    headingEmphasis: 'about this niche?',
    body: 'Real segments from real discussions \u2014 ranked by signal strength. Not invented personas.',
    bodyBoldPhrases: ['Not invented personas.'],
    comparePills: {
      without: '\u201cMy audience is probably young professionals who\u2026\u201d',
      withNicheIQ: '45 posts \u00b7 6,127 engagement \u00b7 4/5 pain points hit',
    },
    relatedStage: 4,
  },
  {
    id: 'step-4',
    type: 'step',
    accentLabel: 'Discovery \u00b7 Step 4',
    stepSymbol: '\u2295',
    stepName: 'Community',
    headingBefore: 'What are people',
    headingEmphasis: 'actually saying?',
    body: 'Top posts from the most relevant communities \u2014 ranked by engagement, with direct Reddit links. Raw evidence, not a summary someone made up.',
    bodyBoldPhrases: ['Raw evidence, not a summary someone made up.'],
    comparePills: {
      without: 'Browse Reddit for 2 days, lose track of what matters',
      withNicheIQ: '73 posts \u00b7 7 communities \u00b7 filtered & ranked',
    },
  },
  {
    id: 'step-5',
    type: 'step',
    accentLabel: 'Discovery \u00b7 Step 5',
    stepSymbol: '\u25ce',
    stepName: 'Opportunities',
    headingBefore: 'Where\u2019s the gap',
    headingEmphasis: 'no one is filling?',
    body: 'Audience size, monthly search volume, top keywords \u2014 mapped to each segment and pain point. Segment + problem + search query = your biggest opportunity.',
    bodyBoldPhrases: ['Segment + problem + search query = your biggest opportunity.'],
    comparePills: {
      without: 'Keyword Planner + Reddit + spreadsheet. 3 weeks.',
      withNicheIQ: '38,400 searches/mo \u00b7 24 keywords \u00b7 14 low difficulty',
    },
    relatedStage: 5,
  },
];
