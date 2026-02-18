<script lang="ts">
  import { onMount } from "svelte";
  import {
    Compass,
    Zap,
    BarChart3,
    ArrowRight,
    Check,
    X,
  } from "lucide-svelte";

  let isVisible = $state(false);

  onMount(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          isVisible = true;
        }
      },
      { threshold: 0.1 },
    );

    const section = document.getElementById("who-its-for");
    if (section) observer.observe(section);

    return () => observer.disconnect();
  });

  const personas = [
    {
      icon: Compass,
      title: "Opportunity Hunters",
      tagline: "Find what people will actually pay for",
      accentGradient:
        "linear-gradient(to right, var(--color-accent), var(--color-accent-hover))",
      description:
        "You know your niche but not what to build. NicheIQ scans thousands of real discussions to surface pain points and solution ideas — so you start with proof, not guesses.",
      before: "Scrolling Reddit for weeks, hoping to spot a gap",
      after: "5–10 data-backed ideas in 45 minutes",
      benefits: [
        "Discover pain points people are already begging someone to solve",
        "See willingness-to-pay scores before you commit",
        "Get a full blueprint for the idea you pick",
      ],
    },
    {
      icon: Zap,
      title: "Serial Builders",
      tagline: "Explore more niches, faster",
      accentGradient:
        "linear-gradient(to right, var(--color-accent-light), var(--color-accent))",
      description:
        "You explore multiple niches per month. The faster you find a winner, the sooner you ship. NicheIQ turns niche exploration from a weeks-long grind into an afternoon sprint.",
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
      accentGradient:
        "linear-gradient(to right, var(--color-accent-dark), var(--color-accent-light))",
      description:
        "You need proof before you pivot. Every insight needs a source. Walk into meetings with market data, competitive landscape, and a clear verdict — not opinions.",
      before: "Pitch niche ideas with hunches, debate for weeks",
      after: "Present market proof, get buy-in, ship faster",
      benefits: [
        "Market sizing you can defend in a board meeting",
        "Competitive landscape + demand signals in one report",
        "30-day GTM blueprint — no guessing on launch",
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
    {#if isVisible}
      <!-- Section Header -->
      <div class="mb-12 sm:mb-16">
        <div class="section-header-meta animate-fade-in">
          <div class="section-header-bar"></div>
          <span class="section-counter">[ <span class="section-counter-active">03</span> / 07 ]</span>
          <span class="section-header-dot">·</span>
          <span class="section-label">Who It's For</span>
        </div>
        <h2
          class="animate-fade-in delay-100 font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mt-4 mb-4 sm:mb-6"
        >
          Stop Guessing.
          <span class="text-accent">Start Shipping.</span>
        </h2>
        <p
          class="animate-fade-in delay-200 text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl"
        >
          Give us a niche. We'll find what's worth building in it.
        </p>
      </div>

      <!-- Persona Cards -->
      <div
        class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-3 gap-5 sm:gap-8 mb-10 sm:mb-16"
      >
        {#each personas as persona, i}
          <div
            class="relative flex flex-col bg-bg-elevated border border-border rounded-xl overflow-hidden"
            style="animation-delay: {300 + i * 120}ms"
          >
            <!-- Top accent gradient bar -->
            <div class="h-1.5" style="background: {persona.accentGradient}"></div>

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
                    class="font-mono text-[10px] uppercase tracking-widest text-text-muted flex-shrink-0 mt-0.5"
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
                    class="font-mono text-[10px] uppercase tracking-widest text-accent flex-shrink-0 mt-0.5"
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
      <div class="animate-fade-in delay-500 max-w-2xl mx-auto">
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
    {/if}
  </div>
</section>

<style>
  .arrow-pulse {
    animation: arrow-pulse 2s ease-in-out infinite;
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
