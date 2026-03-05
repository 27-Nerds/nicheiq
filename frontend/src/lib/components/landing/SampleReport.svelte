<script lang="ts">
  import { fade } from "svelte/transition";
  import { intersect } from "$lib/actions/intersect";
  import PainAnalysis from "$lib/components/sections/PainAnalysis.svelte";
  import SEOKeywords from "$lib/components/sections/SEOKeywords.svelte";
  import Competitors from "$lib/components/sections/Competitors.svelte";
  import MarketSizingSection from "$lib/components/sections/MarketSizing.svelte";
  import type {
    DetailedPainPoint,
    PainPointAnalytics,
    SolutionDetails,
    SEOStrategy,
    SEOAnalytics,
    CompetitorProfile,
    CompetitiveAnalysis,
    CompetitiveAnalytics,
    MarketSizing as MarketSizingType,
  } from "$lib/types/report";
  import type { CtaConfig } from "$lib/types/cta";
  import CtaIcon from "$lib/components/ui/CtaIcon.svelte";

  interface Props {
    hasSampleReport?: boolean;
    ctaTexts?: Record<string, CtaConfig | null>;
  }

  let { hasSampleReport = false, ctaTexts }: Props = $props();

  let isVisible = $state(false);
  let activeTab = $state<
    "pain_points" | "seo_keywords" | "competitors" | "market_size"
  >("pain_points");

  const tabs = [
    { id: "pain_points", label: "Pain Points" },
    { id: "seo_keywords", label: "Keywords" },
    { id: "competitors", label: "Competitors" },
    { id: "market_size", label: "Market Size" },
  ] as const;

  const activeTabLabel = $derived(
    tabs.find((t) => t.id === activeTab)?.label ?? "",
  );


  // --- Mock data ---

  const mockPainPoints: DetailedPainPoint[] = [
    {
      title: "Manual content repurposing consuming 3-5 hours daily",
      description:
        "Creators and marketers spend hours manually reformatting content for different platforms. Copy-pasting, resizing images, rewriting captions — it's repetitive and error-prone.",
      mention_count: 47,
      severity_score: 0.85,
      willingness_to_pay: 0.78,
      opportunity_level: "high",
      representative_quotes: [
        "I spend 3 hours every day just reformatting my YouTube content for Twitter, LinkedIn, and Instagram. It's mind-numbing.",
        "Would happily pay $50/mo to automate this — I'm losing productive hours every week.",
      ],
      source_platforms: ["Reddit", "Twitter"],
      categories: ["Productivity", "Content Creation"],
      source_post_ids: ["r_marketing_xyz789"],
      affected_segments: ["Solo creators", "Marketing teams"],
      solution_approach:
        "Automated multi-platform content adaptation with brand voice preservation",
    },
    {
      title: "Inconsistent brand voice across platforms",
      description:
        "When repurposing manually, tone and messaging drift between platforms. LinkedIn gets too casual, Twitter gets too formal.",
      mention_count: 34,
      severity_score: 0.72,
      willingness_to_pay: 0.65,
      opportunity_level: "high",
      representative_quotes: [
        "Our brand sounds completely different on every platform. It's embarrassing when someone follows us everywhere.",
      ],
      source_platforms: ["Reddit"],
      categories: ["Brand", "Content Creation"],
      source_post_ids: ["r_saas_abc123"],
      affected_segments: ["Marketing teams", "Agencies"],
      solution_approach:
        "Brand voice profiles with per-platform adaptation rules",
    },
    {
      title: "Analytics scattered across 5+ tools",
      description:
        "No single view of how repurposed content performs across platforms. Checking 5 dashboards daily to understand what's working.",
      mention_count: 28,
      severity_score: 0.68,
      willingness_to_pay: 0.71,
      opportunity_level: "medium",
      representative_quotes: [
        "I have Buffer, Hootsuite analytics, native Twitter analytics, LinkedIn stats — it's insane. Just give me one dashboard.",
      ],
      source_platforms: ["Reddit", "Twitter"],
      categories: ["Analytics", "Productivity"],
      source_post_ids: ["r_startups_def456"],
      affected_segments: ["Solo creators", "Small teams"],
      solution_approach:
        "Unified cross-platform content performance dashboard",
    },
  ];

  const mockPainAnalytics: PainPointAnalytics = {
    total_pain_points: 5,
    high_severity_count: 3,
    quadrant_distribution: {
      high_severity_high_wtp: 2,
      high_severity_low_wtp: 1,
      low_severity_high_wtp: 1,
      low_severity_low_wtp: 1,
    },
  };

  const mockSolution: SolutionDetails = {
    solution_name: "ContentFlow",
    description:
      "Content repurposing platform that transforms long-form content into platform-optimized posts while maintaining brand voice.",
    value_proposition:
      "Turn one piece of content into 10+ platform-ready posts in minutes, not hours.",
    core_features: [
      "Auto-format for 6+ platforms",
      "Brand voice matching",
      "Batch processing",
      "Analytics dashboard",
    ],
  };

  const mockSEOStrategy: SEOStrategy = {
    total_keywords_analyzed: 156,
    total_monthly_volume: 89400,
    key_findings: [
      "156 keyword opportunities identified across 5 tiers.",
      "23 quick wins with low competition and decent volume.",
      "Strong commercial intent cluster around 'content repurposing tool' variations.",
    ],
    tier_0_keywords: [
      {
        keyword: "content repurposing tool",
        search_volume: 2400,
        competition: "0.85",
        opportunity_score: 82,
        keyword_difficulty: 72,
        intent: "Commercial",
        strategy: "Target with homepage + comparison pages",
      },
      {
        keyword: "ai content automation",
        search_volume: 1800,
        competition: "0.76",
        opportunity_score: 75,
        keyword_difficulty: 65,
        intent: "Commercial",
      },
    ],
    tier_0_strategy:
      "Target on homepage and key landing pages. These are your money keywords.",
    tier_1_keywords: [
      {
        keyword: "repurpose video content",
        search_volume: 1200,
        competition: "0.38",
        opportunity_score: 88,
        keyword_difficulty: 32,
        intent: "Informational",
      },
      {
        keyword: "content automation software",
        search_volume: 980,
        competition: "0.51",
        opportunity_score: 71,
        keyword_difficulty: 45,
        intent: "Commercial",
      },
      {
        keyword: "social media content from blog",
        search_volume: 720,
        competition: "0.42",
        opportunity_score: 79,
        keyword_difficulty: 38,
        intent: "Informational",
      },
    ],
    tier_1_quick_win_strategy:
      "Low-hanging fruit. Create dedicated blog posts for each within the first month.",
    tier_2_keywords: [
      {
        keyword: "how to repurpose podcast episodes",
        search_volume: 480,
        competition: "0.29",
        opportunity_score: 84,
        keyword_difficulty: 25,
        intent: "Informational",
      },
      {
        keyword: "content calendar automation",
        search_volume: 390,
        competition: "0.55",
        opportunity_score: 62,
        keyword_difficulty: 48,
        intent: "Commercial",
      },
    ],
    tier_2_strategy:
      "Medium-term content targets. Build supporting content that links back to Tier 0 pages.",
    content_strategy:
      "Pillar page strategy: Create 3 pillar pages around content repurposing, automation, and multi-platform publishing.",
    competitive_positioning:
      "Position as the affordable, creator-first alternative to enterprise tools like Sprout Social.",
  };

  const mockSEOAnalytics: SEOAnalytics = {
    total_keywords: 156,
    total_search_volume: 89400,
    avg_competition: 0.52,
    keyword_diversity_score: 0.73,
    high_volume_keywords: 23,
    tier0_count: 5,
    tier1_count: 23,
    tier2_count: 42,
    tier3_count: 48,
    tier4_count: 38,
  };

  const mockCompetitorProfiles: CompetitorProfile[] = [
    {
      name: "OpusClip",
      url: "https://opus.pro",
      competitor_type: "DIRECT",
      description:
        "Video repurposing tool focused on short-form content creation",
      key_features: [
        "Auto-captions",
        "AI scene detection",
        "Multi-platform export",
        "Virality score",
      ],
      pricing_model: "$15-69/mo SaaS subscription",
      strengths: [
        "Strong AI clip selection",
        "Good social integrations",
        "Growing user base",
      ],
      weaknesses: [
        "Video-only (no text/audio)",
        "Limited brand customization",
        "No B-roll library",
      ],
    },
    {
      name: "Descript",
      url: "https://descript.com",
      competitor_type: "DIRECT",
      description:
        "All-in-one video/audio editor with transcription and repurposing features",
      key_features: [
        "Timeline editor",
        "Auto-captions",
        "Transcription",
        "Screen recording",
      ],
      pricing_model: "$24-33/mo SaaS subscription",
      strengths: [
        "Powerful editor",
        "Good transcription",
        "Established brand",
      ],
      weaknesses: [
        "Steep learning curve",
        "Expensive for basic repurposing",
        "No brand voice matching",
      ],
    },
    {
      name: "Buffer",
      url: "https://buffer.com",
      competitor_type: "PARTIAL",
      description: "Social media scheduling and analytics platform",
      key_features: [
        "Multi-platform scheduling",
        "Analytics",
        "Team collaboration",
        "Content calendar",
      ],
      pricing_model: "$6-120/mo SaaS subscription",
      strengths: ["Simple UX", "Wide platform support", "Affordable"],
      weaknesses: [
        "No content transformation",
        "Basic analytics",
        "No AI features",
      ],
    },
  ];

  const mockCompetitiveAnalysis: CompetitiveAnalysis = {
    solution_landscapes: [
      {
        solution_name: "ContentFlow",
        competitors: ["OpusClip", "Descript", "Buffer"],
        market_gaps: [
          "Contextual B-Roll generation",
          "Brand voice matching across platforms",
          "Unified analytics dashboard",
        ],
        differentiation_opportunities: [
          "Multi-format (not just video)",
          "Brand voice preservation",
          "One-click publishing",
        ],
        competitive_intensity: "Medium",
        recommended_positioning:
          "Position as the all-in-one repurposing platform for creators who publish across 5+ channels.",
        pricing_insights:
          "Competitors price $15-69/mo. Sweet spot at $29-79/mo with a free tier.",
      },
    ],
    strategic_recommendations:
      "Focus on the multi-format gap. Most competitors specialize in video-only. Text-to-social and audio-to-social are underserved.",
    top_opportunities: [
      "Underserved text-to-social segment",
      "No strong player in brand voice matching",
    ],
  };

  const mockCompetitiveAnalytics: CompetitiveAnalytics = {
    competitor_count: 5,
    market_saturation_score: 0.55,
    differentiation_strength: "Strong",
    market_gaps_identified: 3,
    avg_competitor_features: 8,
    feature_comparison: {
      feature_groups: [
        {
          group_name: "Auto-Captions",
          description: "Automatic subtitle generation",
          competitors_with_feature: ["OpusClip", "Descript"],
          original_features: [],
        },
        {
          group_name: "Multi-Platform Export",
          description: "Export optimized for each platform",
          competitors_with_feature: ["OpusClip", "Descript", "Buffer"],
          original_features: [],
        },
        {
          group_name: "AI Scene Detection",
          description: "Intelligent content segmentation",
          competitors_with_feature: ["OpusClip"],
          original_features: [],
        },
        {
          group_name: "Brand Voice Matching",
          description: "Maintain consistent voice across platforms",
          competitors_with_feature: [],
          original_features: [],
        },
        {
          group_name: "Contextual B-Roll",
          description: "Auto-suggest relevant B-roll footage",
          competitors_with_feature: [],
          original_features: [],
        },
      ],
      total_unique_groups: 8,
      avg_features_per_competitor: 8,
    },
  };

  const mockMarketSizing: MarketSizingType = {
    market_viability_verdict: "Strong",
    market_growth_rate: "18% YoY",
    market_saturation_level: "Low",
    market_timing_assessment: "Growth",
    total_addressable_market: "$2.4B",
    serviceable_available_market: "$340M",
    serviceable_obtainable_market_y1: "$8.5M",
    serviceable_obtainable_market_y3: "$42M",
    keyword_demand_signal: "High",
    pain_point_frequency: "Very High",
    competitor_market_presence: "Moderate",
    primary_methodology:
      "Bottom-up keyword demand + top-down market reports",
    recommended_entry_strategy:
      "Start with solo creators doing $0-5K/mo in content revenue. Freemium with $29/mo Pro tier.",
    methodology_explanation:
      "Combined search volume analysis with social discussion frequency and competitor revenue estimates.",
    data_sources_used: [
      "Reddit discussions",
      "Google Trends",
      "SEMrush keyword data",
      "Competitor pricing pages",
    ],
    viability_rationale:
      "Strong demand signals from 89+ discussions, growing search volume, and clear competitive gaps support market entry.",
    growth_drivers: [
      "Creator economy growing 20%+ annually",
      "Reducing barrier to entry",
      "Multi-platform publishing becoming standard",
    ],
    risk_factors: [
      "Enterprise players may enter",
      "Commoditization risk",
      "Platform API dependency",
    ],
    segment_sizing: [
      {
        segment_name: "Solo Creators",
        tam_estimate: "$800M",
        sam_estimate: "$120M",
        som_estimate: "$5M",
        confidence_level: "High",
        sizing_methodology:
          "Reddit discussion frequency + creator platform data",
      },
      {
        segment_name: "Marketing Teams (SMB)",
        tam_estimate: "$1.6B",
        sam_estimate: "$220M",
        som_estimate: "$3.5M",
        confidence_level: "Medium",
        sizing_methodology:
          "LinkedIn job postings + SaaS market reports",
      },
    ],
  };
</script>

<section id="sample-report" class="section" use:intersect={{ threshold: 0.1, onIntersect: () => isVisible = true }}>
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Section Header -->
      <div class="mb-12">
        <div class="section-header-meta animate-fade-in">
          <div class="section-header-bar"></div>
          <span class="section-counter">[ <span class="section-counter-active">01</span> / 07 ]</span>
          <span class="section-header-dot">·</span>
          <span class="section-label">Inside the Report</span>
        </div>
        <h2
          class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6"
        >
          What You <span class="text-accent">Actually Get</span>
        </h2>
        <p
          class="animate-fade-in delay-200 text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl"
        >
          See the exact research that tells you whether an idea is worth
          building.
        </p>
        <p
          class="animate-fade-in delay-300 text-sm sm:text-base text-text-muted mt-4 sm:mt-5 max-w-2xl"
        >
          This is a real report for a content repurposing tool. Pain points,
          keywords, competitors, and the final verdict, all from a single run.
        </p>
      </div>

      <!-- Hero Stat Strip -->
      <div
        class="animate-fade-in delay-300 flex justify-center gap-6 sm:gap-10 mb-8 text-center"
      >
        <div>
          <div class="text-2xl font-display font-bold text-accent">156</div>
          <div class="text-xs text-text-muted">Keywords</div>
        </div>
        <div>
          <div class="text-2xl font-display font-bold text-text-primary">
            5+
          </div>
          <div class="text-xs text-text-muted">Pain Points</div>
        </div>
        <div>
          <div class="text-2xl font-display font-bold text-text-primary">
            $2.4B
          </div>
          <div class="text-xs text-text-muted">TAM</div>
        </div>
        <div>
          <div class="text-2xl font-display font-bold text-success">GO</div>
          <div class="text-xs text-text-muted">Verdict</div>
        </div>
      </div>

      <!-- Pill Tab Navigation -->
      <div
        class="animate-fade-in delay-300 flex justify-center gap-1 mb-8
               bg-bg-elevated border border-border rounded-lg p-1 max-w-fit mx-auto"
      >
        {#each tabs as tab}
          <button
            onclick={() => (activeTab = tab.id)}
            class="px-3 sm:px-4 py-2.5 rounded-md text-sm font-medium transition-all
              {activeTab === tab.id
              ? 'bg-accent/10 text-accent shadow-sm'
              : 'text-text-muted hover:text-text-secondary'}"
          >
            {tab.label}
          </button>
        {/each}
      </div>

      <!-- Report Window Frame -->
      <div
        class="animate-fade-in delay-400 max-w-5xl mx-auto rounded-xl border border-border
               overflow-hidden shadow-sm"
      >
        <!-- Toolbar strip -->
        <div
          class="flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2.5 bg-bg-surface border-b border-border"
        >
          <div
            class="w-2.5 sm:w-3 h-2.5 sm:h-3 rounded-full bg-[#FF5F57]"
          ></div>
          <div
            class="w-2.5 sm:w-3 h-2.5 sm:h-3 rounded-full bg-[#FEBC2E]"
          ></div>
          <div
            class="w-2.5 sm:w-3 h-2.5 sm:h-3 rounded-full bg-[#28C840]"
          ></div>
          <span
            class="ml-auto text-[10px] sm:text-xs text-text-muted font-mono font-medium tracking-wide"
            >report — content-repurposing-tool</span
          >
          {#if hasSampleReport}
            <span class="text-border mx-1 hidden sm:inline">|</span>
            <a
              href="/sample-report"
              class="text-[10px] sm:text-xs text-accent hover:underline hidden sm:inline"
            >
              Open full report &rarr;
            </a>
          {/if}
        </div>

        <!-- Constrained content area -->
        <div
          class="relative bg-bg-elevated min-h-[800px] sm:min-h-[1000px]"
        >
          <div
            class="report-preview max-h-[800px] sm:max-h-[1000px] overflow-hidden"
          >
            {#key activeTab}
              <div in:fade={{ duration: 200 }}>
                {#if activeTab === "pain_points"}
                  <PainAnalysis
                    painPoints={mockPainPoints}
                    analytics={mockPainAnalytics}
                    solution={mockSolution}
                  />
                {:else if activeTab === "seo_keywords"}
                  <SEOKeywords
                    strategy={mockSEOStrategy}
                    analytics={mockSEOAnalytics}
                  />
                {:else if activeTab === "competitors"}
                  <Competitors
                    profiles={mockCompetitorProfiles}
                    analysis={mockCompetitiveAnalysis}
                    analytics={mockCompetitiveAnalytics}
                    selectedSolutionName="ContentFlow"
                  />
                {:else if activeTab === "market_size"}
                  <MarketSizingSection data={mockMarketSizing} />
                {/if}
              </div>
            {/key}
          </div>

          <!-- Fade overlay -->
          <div class="report-fade-overlay"></div>
        </div>
      </div>

      <!-- Preview hint -->
      <p class="text-xs text-text-muted text-center mt-4">
        Previewing <span class="font-semibold">{activeTabLabel}</span> &middot;
        1 of 10+ report sections
      </p>

      <!-- CTA -->
      {@const sampleCta = ctaTexts?.cta_sample_button}
      {#if hasSampleReport && sampleCta?.visible !== false}
        <div class="mt-8 text-center">
          <a
            href={sampleCta?.url ?? "/sample-report"}
            class="btn-primary inline-flex items-center gap-2 px-6 py-3"
          >
            {sampleCta?.text ?? "See the Full Report"}
            <CtaIcon name={sampleCta?.icon} class="w-4 h-4" />
          </a>
          <p class="text-xs text-text-muted mt-3">
            All 10+ sections included
          </p>
        </div>
      {/if}
    {/if}
  </div>
</section>

<style>
  /* Force all AnimateOnScroll elements visible inside preview.
     IntersectionObserver won't fire for elements clipped by overflow-hidden,
     so we override the opacity/transform the same way prefers-reduced-motion does. */
  .report-preview :global(.animate-fade-up),
  .report-preview :global(.animate-fade-in-triggered),
  .report-preview :global(.animate-scale-in),
  .report-preview :global(.animate-slide-left),
  .report-preview :global(.animate-slide-right) {
    opacity: 1 !important;
    transform: none !important;
  }

  /* Fade overlay — uses CSS variable so it matches bg-elevated exactly */
  .report-fade-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 8rem;
    background: linear-gradient(
      to top,
      var(--color-bg-elevated) 0%,
      var(--color-bg-elevated) 10%,
      transparent 100%
    );
    pointer-events: none;
    z-index: 10;
  }
</style>
