<script lang="ts">
  import { slide } from "svelte/transition";
  import { SvelteSet } from "svelte/reactivity";
  import {
    Search,
    Radar,
    Waypoints,
    MessageSquare,
    Lightbulb,
    Gem,
    BarChart3,
    FileText,
    ScrollText,
    Eye,
    ChevronDown,
    Clock,
    Users,
    DollarSign,
    PieChart,

  } from "lucide-svelte";

  let showStages = $state(false);
  let expandedStages = new SvelteSet<number>();

  function toggleStage(id: number) {
    if (expandedStages.has(id)) expandedStages.delete(id);
    else expandedStages.add(id);
  }

  const steps = [
    {
      icon: Radar,
      title: "Discover Pain Points & Ideas",
      time: "~15 min",
      description:
        "We scan Reddit, Twitter, and online communities to find pain points people will actually pay to solve. You get 5–10 solution concepts, each backed by real discussions you can verify.",
      cardClass: "",
      dashed: false,
      timePill: false,
    },
    {
      icon: Gem,
      title: "Pick Your Opportunity",
      time: "Your call",
      description:
        "Review the pain points and solution concepts we found. Pick the one that excites you, or let us recommend the strongest signal.",
      cardClass: "",
      dashed: true,
      timePill: true,
    },
    {
      icon: ScrollText,
      title: "Get Your Business Blueprint",
      time: "~30 min",
      description:
        "Competitive analysis, 100+ ranked SEO keywords, market sizing, and pricing strategy. You also get a clear GO or NO-GO verdict and an optional landing page to start capturing leads.",
      cardClass: "",
      dashed: false,
      timePill: false,
    },
  ];

  const phases = [
    {
      number: 1,
      label: "DISCOVERY",
      tagline: "Find Proof",
      stages: [
        {
          id: 1,
          name: "Niche Analysis",
          icon: Waypoints,
          metric: "3–7 segments defined",
          description:
            "Tighten your focus before we search. Wasted effort starts here.",
          details:
            'Your niche gets broken into clear market boundaries, target segments (e.g., "Small e-commerce businesses with 10-50 employees"), and scope definitions — so nothing gets researched that shouldn\'t be.',
        },
        {
          id: 2,
          name: "Search & Discover",
          icon: Search,
          metric: "89+ discussions found",
          description:
            "Find the conversations that prove demand exists (or doesn't).",
          details:
            "Direct access to communities, discussions, and engagement data. 3-layer filtering: relevance validation, engagement quality, deduplication.",
        },
        {
          id: 3,
          name: "Pain Point Analysis",
          icon: MessageSquare,
          metric: "5+ pain points ranked",
          description:
            "Rank which problems people will actually pay to solve, and how much.",
          details:
            "Discussions get categorized, pain points extracted with evidence, and scored by severity and willingness-to-pay. Every insight is traceable to specific posts.",
        },
      ],
    },
    {
      number: 2,
      label: "ANALYSIS",
      tagline: "Understand the Opportunity",
      stages: [
        {
          id: 4,
          name: "Audience Mapping",
          icon: Users,
          metric: "3–5 personas",
          description:
            "Know exactly who you're building for, down to where they hang out and what triggers a purchase.",
          details:
            "Maps your target audience: who they are, where they hang out online, what triggers purchasing decisions, and how to reach them effectively.",
        },
        {
          id: 5,
          name: "Solution Development",
          icon: Lightbulb,
          metric: "3+ solutions generated",
          description:
            "Get 3+ fully-baked solution concepts before you pick one to build.",
          details:
            "Each concept gets ideated, researched against competitors, analyzed for market fit, and refined. Solutions are scored across feasibility, demand, and differentiation.",
        },
        {
          id: 6,
          name: "Competitive Analysis",
          icon: Eye,
          metric: "Competitors + gaps mapped",
          description:
            "Find where you can actually win instead of entering a crowded market.",
          details:
            "Identifies direct, partial, and indirect competitors. Analyzes pricing strategies, feature gaps, and differentiation opportunities.",
        },
      ],
    },
    {
      number: 3,
      label: "VALIDATION",
      tagline: "Get Your Business Case",
      stages: [
        {
          id: 7,
          name: "Pricing Strategy",
          icon: DollarSign,
          metric: "Validated pricing tiers",
          description:
            "Pricing grounded in what people say they'd pay, pulled from actual discussions.",
          details:
            "Analyzes competitor pricing, maps customer willingness-to-pay from discussions, and recommends pricing tiers with positioning rationale.",
        },
        {
          id: 8,
          name: "Market Sizing",
          icon: PieChart,
          metric: "TAM/SAM/SOM calculated",
          description:
            "TAM/SAM/SOM calculated from search volume and community data.",
          details:
            "Estimates Total Addressable Market (TAM), Serviceable Addressable Market (SAM), and Serviceable Obtainable Market (SOM) using keyword volumes and market data.",
        },
        {
          id: 9,
          name: "SEO Strategy",
          icon: BarChart3,
          metric: "100+ keywords tiered",
          description:
            "100+ keywords mapped so you know your month-1 content roadmap and search potential.",
          details:
            "Iterative expansion from seed keywords. Tier 0 (Premium), Tier 1 (Quick Wins), Tier 2 (Growth) classification. Full content strategy included.",
        },
        {
          id: 10,
          name: "Final Report & Landing Page",
          icon: FileText,
          metric: "Go/No-Go verdict",
          description:
            "Your thesis: Should you build this? If yes, here's your landing page.",
          details:
            "80% of the report is hard data — no hallucination possible. The remaining 20% is strategic synthesis. You get a clear go/no-go recommendation with a confidence score.",
        },
      ],
    },
  ];

  // HowTo JSON-LD removed: Google fully deprecated HowTo rich results in
  // 2024 (no SERP feature on any device, no AI-search benefit), so the
  // markup was dead weight. The visible "how it works" UI below is
  // unchanged. If this section needs structured data later, prefer
  // ItemList of steps routed through the central `serializeJsonLd()` helper
  // (frontend/src/lib/seo/jsonld.ts) — never inline raw `JSON.stringify`,
  // which bypasses XSS escaping.
</script>

<section id="how-it-works" class="section-alt">
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
      <!-- Section Header -->
      <div class="mb-10 sm:mb-16">
        <div class="section-header-meta">
          <span class="section-counter">[ <span class="section-counter-active">02</span> / 07 ]</span>
        </div>
        <h2
          class="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mt-4 mb-4 sm:mb-6"
        >
          How It <span class="text-accent">Works</span>
        </h2>
        <p
          class="text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl"
        >
          3 stages. 45 minutes. A GO or NO-GO verdict you can trust.
        </p>
      </div>

      <!-- Desktop: unified card series (md+) -->
      <ol class="hidden md:grid md:grid-cols-3 md:gap-6 mb-10 sm:mb-16">
        <!-- Step 1 -->
        <li class="flex flex-col rounded-xl border border-border bg-bg-elevated p-6">
          <div class="font-mono text-xs text-text-muted tracking-wide mb-3">01</div>
          <h3 class="font-display text-xl font-semibold text-text-primary mb-3">
            Discover Pain Points &amp; Ideas
          </h3>
          <p class="text-text-secondary leading-relaxed text-sm mb-5 flex-1">
            We scan Reddit, Twitter, and online communities to find pain points people will actually pay to solve. You get 5&ndash;10 solution concepts, each backed by real discussions you can verify.
          </p>
          <p class="font-mono text-xs text-text-muted">
            89+ discussions · 5 pain points · 5&ndash;10 ideas · Source links · ~15 min
          </p>
        </li>

        <!-- Step 2 (dashed border preserves the "your call" semantic) -->
        <li class="flex flex-col rounded-xl border border-dashed border-accent/40 bg-bg-elevated p-6">
          <div class="font-mono text-xs text-text-muted tracking-wide mb-3">02</div>
          <h3 class="font-display text-xl font-semibold text-text-primary mb-3">
            Pick Your Opportunity
          </h3>
          <p class="text-text-secondary leading-relaxed text-sm mb-5 flex-1">
            Review the pain points and solution concepts we found. Pick the one that excites you, or let us recommend the strongest signal.
          </p>
          <p class="font-mono text-xs text-text-muted">
            Your call.
          </p>
        </li>

        <!-- Step 3 -->
        <li class="flex flex-col rounded-xl border border-border bg-bg-elevated p-6">
          <div class="font-mono text-xs text-text-muted tracking-wide mb-3">03</div>
          <h3 class="font-display text-xl font-semibold text-text-primary mb-3">
            Get Your Business Blueprint
          </h3>
          <p class="text-text-secondary leading-relaxed text-sm mb-5 flex-1">
            Competitive analysis, 100+ ranked SEO keywords, market sizing, and pricing strategy. You also get a clear GO or NO-GO verdict and an optional landing page to start capturing leads.
          </p>
          <p class="font-mono text-xs text-text-muted">
            Competitors · SEO · Market sizing · Pricing · GO/NO-GO · ~30 min
          </p>
        </li>
      </ol>

      <!-- Mobile: Vertical timeline (<md) -->
      <ol class="md:hidden flex flex-col mb-10">
        {#each steps as step, i}
          <li class="flex gap-4">
            <!-- Timeline column -->
            <div class="flex flex-col items-center">
              <div
                class="w-10 h-10 rounded-full border-2 border-accent bg-bg-elevated
                       flex items-center justify-center font-display text-base font-bold text-accent
                       shrink-0"
              >
                {i + 1}
              </div>
              {#if i < steps.length - 1}
                <div class="flex-1 w-0.5 bg-border my-2"></div>
              {/if}
            </div>
            <!-- Card -->
            <div
              class="flex-1 pb-8 flex flex-col rounded-xl border bg-bg-elevated p-5 mb-2
                     {step.dashed
                ? 'border-dashed border-accent/40'
                : 'border-border'}"
            >
              <!-- Icon -->
              <div
                class="w-10 h-10 rounded-xl bg-accent/10 border border-accent/30
                       flex items-center justify-center mb-3"
              >
                <step.icon class="w-5 h-5 text-accent" />
              </div>
              <!-- Title -->
              <h3
                class="font-display font-semibold text-lg text-text-primary mb-1.5"
              >
                {step.title}
              </h3>
              <!-- Time -->
              {#if step.timePill}
                <div class="mb-2">
                  <span
                    class="inline-flex px-2.5 py-0.5 rounded-full text-[10px] uppercase tracking-widest
                           bg-accent/10 text-accent border border-accent/20 font-medium"
                  >
                    {step.time}
                  </span>
                </div>
              {:else}
                <div class="flex items-center gap-1.5 mb-2">
                  <Clock class="w-3.5 h-3.5 text-text-muted" />
                  <span class="text-xs text-accent font-medium"
                    >{step.time}</span
                  >
                </div>
              {/if}
              <!-- Description -->
              <p class="text-text-secondary leading-relaxed text-sm">
                {step.description}
              </p>
            </div>
          </li>
        {/each}
      </ol>

      <!-- Expandable: Under the Hood Section -->
      <div>
        <button
          onclick={() => (showStages = !showStages)}
          class="w-full flex items-center justify-center gap-3 py-3 sm:py-4 text-text-secondary hover:text-accent transition-colors group"
        >
          <span class="font-medium text-sm sm:text-base"
            >Peek inside the pipeline</span
          >
          <ChevronDown
            class="w-4 sm:w-5 h-4 sm:h-5 transition-transform duration-300
						{showStages ? 'rotate-180' : ''}"
          />
        </button>

        {#if showStages}
          <div transition:slide={{ duration: 400 }} class="mt-6 sm:mt-8">
            <!-- Section Header for Stages -->
            <div class="text-center mb-8 sm:mb-12">
              <h3
                class="font-display text-xl sm:text-2xl font-semibold text-text-primary mb-2"
              >
                How we turn discussions into decisions
              </h3>
              <p class="text-text-muted text-xs sm:text-sm">
                Each stage isolates a specific signal so you can trust the verdict.
              </p>
            </div>

            <!-- Phases -->
            <div class="space-y-8 sm:space-y-10">
              {#each phases as phase}
                <div>
                  <!-- Phase Header -->
                  <div class="flex items-center gap-3 mb-5">
                    <span
                      class="w-7 h-7 rounded-full bg-accent/15 border border-accent/30
                             flex items-center justify-center shrink-0
                             text-accent font-display text-sm font-bold
"
                    >
                      {phase.number}
                    </span>
                    <div class="shrink-0">
                      <span class="text-xs font-semibold uppercase tracking-wider text-accent">
                        {phase.label}
                      </span>
                      <span class="text-text-muted text-xs ml-1.5">&mdash; {phase.tagline}</span>
                    </div>
                    <div
                      class="flex-1 h-px bg-gradient-to-r from-border to-transparent hidden sm:block"
                      aria-hidden="true"
                    ></div>
                  </div>

                  <!-- Stages in this phase -->
                  <div class="border-t border-border">
                    {#each phase.stages as stage}
                      <div class="border-b border-border">
                        <button
                          onclick={() => toggleStage(stage.id)}
                          class="w-full text-left py-4 sm:py-5 hover:bg-accent/[0.03] transition-colors duration-200 group"
                        >
                          <div class="flex items-start gap-3 sm:gap-4">
                            <!-- Icon -->
                            <div
                              class="flex-shrink-0 w-9 sm:w-10 h-9 sm:h-10 rounded-lg border
                                     flex items-center justify-center transition-all duration-200
                                     {expandedStages.has(stage.id)
                                ? 'border-border-accent bg-accent/10 scale-105'
                                : 'border-border bg-bg-elevated group-hover:border-border-emphasis'}"
                            >
                              <stage.icon
                                class="w-4 sm:w-5 h-4 sm:h-5 transition-colors duration-200
                                  {expandedStages.has(stage.id) ? 'text-accent' : 'text-text-muted group-hover:text-text-secondary'}"
                              />
                            </div>

                            <!-- Content -->
                            <div class="flex-1 min-w-0">
                              <div class="flex items-center gap-2 sm:gap-4 mb-1">
                                <span class="text-[11px] font-mono text-text-muted/70 tabular-nums">
                                  {String(stage.id).padStart(2, '0')}
                                </span>
                                <span
                                  class="text-[10px] sm:text-xs text-accent font-semibold uppercase tracking-wider"
                                >
                                  {stage.metric}
                                </span>
                              </div>

                              <h4
                                class="font-display font-semibold text-base sm:text-lg text-text-primary mb-1
                                       group-hover:text-accent transition-colors"
                              >
                                {stage.name}
                              </h4>

                              <p class="text-text-secondary text-sm leading-relaxed">
                                {stage.description}
                              </p>
                            </div>

                            <!-- Expand Icon -->
                            <ChevronDown
                              class="flex-shrink-0 w-4 h-4 text-text-muted transition-transform duration-300
                              {expandedStages.has(stage.id) ? 'rotate-180 text-accent' : ''}"
                            />
                          </div>
                        </button>

                        <!-- Expanded Details -->
                        {#if expandedStages.has(stage.id)}
                          <div
                            transition:slide={{ duration: 300 }}
                            class="pb-4 sm:pb-5 pl-12 sm:pl-14"
                          >
                            <p
                              class="text-text-secondary text-sm leading-relaxed
                                     bg-bg-surface border-l-2 border-l-accent/20 border border-border
                                     p-3 sm:p-4 rounded-lg"
                            >
                              {stage.details}
                            </p>
                          </div>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
  </div>
</section>
