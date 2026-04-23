<script lang="ts">
  import {
    Compass,
    Zap,
    BarChart3,
    ArrowRight,
    Check,
    X,
  } from "lucide-svelte";

  const personas = [
    {
      icon: Compass,
      title: "Opportunity Hunters",
      tagline: "Find what people will actually pay for",
      description:
        "You know your niche but not what to build. NicheIQ scans thousands of real discussions to surface pain points and solution ideas, so you start with proof instead of hunches.",
      before: "Scrolling Reddit for weeks, hoping to spot a gap",
      after: "5–10 data-backed ideas in 45 minutes",
      benefits: [
        "Find pain points people are already asking someone to solve",
        "See willingness-to-pay scores before you commit",
        "Get a full blueprint for the idea you pick",
      ],
    },
    {
      icon: Zap,
      title: "Serial Builders",
      tagline: "Explore more niches, faster",
      description:
        "You explore multiple niches per month. The faster you find a winner, the sooner you ship. NicheIQ compresses weeks of research into an afternoon.",
      before: "Explore one niche for weeks, hope you picked right",
      after: "Scan 5 niches in one afternoon, chase the best signal",
      benefits: [
        "Explore 5 niches in a single afternoon",
        "See which pain points have real demand — not just noise",
        "Skip the manual keyword and competitor research entirely",
      ],
    },
    {
      icon: BarChart3,
      title: "Data-Driven Teams",
      tagline: "Gut feelings don't impress stakeholders",
      description:
        "You need proof before you pivot. Your stakeholders need sources. Walk into meetings with market data, a competitive landscape, and a clear verdict instead of opinions.",
      before: "Pitch niche ideas with hunches, debate for weeks",
      after: "Present market proof, get buy-in, ship faster",
      benefits: [
        "Market sizing you can defend in a board meeting",
        "Competitive landscape + demand signals in one report",
        "30-day GTM blueprint so you know what to do on day one",
      ],
    },
  ];

  const antiPersonas = [
    "Qualitative interviews or custom user research (we use public data)",
    "White-label or agency reselling",
    "Non-English markets",
  ];
</script>

<section id="who-its-for" class="section">
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
      <!-- Section Header -->
      <div class="mb-12 sm:mb-16">
        <div class="section-header-meta">
          <span class="section-counter">[ <span class="section-counter-active">03</span> / 07 ]</span>
        </div>
        <h2
          class="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mt-4 mb-4 sm:mb-6"
        >
          Built for People Who <span class="text-accent">Actually Ship.</span>
        </h2>
        <p
          class="text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl"
        >
          Give us a niche. We'll find what's worth building in it.
        </p>
      </div>

      <!-- Persona Cards -->
      <div
        class="grid grid-cols-1 md:grid-cols-3 gap-5 sm:gap-8 mb-10 sm:mb-16"
      >
        {#each personas as persona, i}
          <div
            class="relative flex flex-col bg-bg-elevated border border-border rounded-xl overflow-hidden"
            style="animation-delay: {300 + i * 120}ms"
          >
            <!-- Card content -->
            <div class="relative flex flex-col flex-1 p-6 sm:p-8">
              <!-- Icon + Title + Tagline -->
              <div class="flex items-start gap-3 mb-4">
                <persona.icon class="w-5 h-5 text-accent flex-shrink-0 mt-1" />
                <div>
                  <h3
                    class="font-display font-semibold text-lg sm:text-xl text-text-primary"
                  >
                    {persona.title}
                  </h3>
                  <p class="text-accent text-xs sm:text-sm font-medium mt-0.5">
                    {persona.tagline}
                  </p>
                </div>
              </div>

              <!-- Description -->
              <p class="text-text-secondary text-sm leading-relaxed mb-5">
                {persona.description}
              </p>

              <!-- Before/After transformation strip -->
              <div class="rounded-lg border border-border overflow-hidden mb-5">
                <!-- Before -->
                <div
                  class="flex items-start gap-2.5 px-3.5 py-2.5 bg-bg-surface"
                >
                  <X class="w-4 h-4 text-text-muted/50 flex-shrink-0 mt-0.5" />
                  <span
                    class="text-[10px] font-medium text-text-muted flex-shrink-0 mt-0.5"
                    >Before</span
                  >
                  <span class="text-sm text-text-muted line-through"
                    >{persona.before}</span
                  >
                </div>

                <!-- Pulsing arrow divider -->
                <div class="flex items-center justify-center py-1.5 relative">
                  <div class="absolute inset-x-0 top-1/2 h-px bg-border"></div>
                  <div
                    class="arrow-pulse relative z-10 w-7 h-7 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center"
                  >
                    <ArrowRight class="w-3.5 h-3.5 text-accent" />
                  </div>
                </div>

                <!-- After -->
                <div
                  class="flex items-start gap-2.5 px-3.5 py-2.5 border-l-2 border-accent/30 bg-gradient-to-r from-accent/[0.06] via-accent/[0.03] to-transparent"
                >
                  <Check class="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                  <span
                    class="text-[10px] font-medium text-accent flex-shrink-0 mt-0.5"
                    >After</span
                  >
                  <span class="text-sm text-text-primary font-semibold"
                    >{persona.after}</span
                  >
                </div>
              </div>

              <!-- Benefits -->
              <ul class="space-y-2.5 flex-1">
                {#each persona.benefits as benefit}
                  <li class="flex items-start gap-2.5 text-sm">
                    <span class="text-accent text-sm mt-0.5 flex-shrink-0">→</span>
                    <span class="text-text-muted text-sm leading-relaxed"
                      >{benefit}</span
                    >
                  </li>
                {/each}
              </ul>

            </div>
          </div>
        {/each}
      </div>

      <!-- Anti-Persona Section -->
      <div class="max-w-2xl mx-auto">
        <div class="p-5 sm:p-6 bg-bg-surface border border-border rounded-xl">
          <h4
            class="font-display font-semibold text-text-primary mb-3 sm:mb-4 text-center text-sm sm:text-base"
          >
            We're not for everyone
          </h4>
          <p
            class="text-text-muted text-xs sm:text-sm text-center mb-3 sm:mb-4"
          >
            NicheIQ is built for fast SaaS niche research. These use cases need
            different tools:
          </p>
          <ul class="space-y-2">
            {#each antiPersonas as antiPersona}
              <li
                class="flex items-center gap-2.5 sm:gap-3 text-xs sm:text-sm"
              >
                <X
                  class="w-3.5 sm:w-4 h-3.5 sm:h-4 text-text-muted flex-shrink-0"
                />
                <span class="text-text-muted">{antiPersona}</span>
              </li>
            {/each}
          </ul>
        </div>
      </div>
  </div>
</section>

<style>
  .arrow-pulse {
    animation: arrow-pulse 1s ease-in-out 1;
  }

  @keyframes arrow-pulse {
    0%,
    100% {
      opacity: 0.7;
      transform: scale(0.9);
    }
    50% {
      opacity: 1;
      transform: scale(1.1);
    }
  }
</style>
