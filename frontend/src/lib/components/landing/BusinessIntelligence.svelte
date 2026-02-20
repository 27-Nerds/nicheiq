<script lang="ts">
  import { onMount } from "svelte";
  import { PieChart, Tag, Scale, CheckCircle2 } from "lucide-svelte";

  let isVisible = $state(false);

  onMount(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          isVisible = true;
        }
      },
      { threshold: 0.2 },
    );

    const section = document.getElementById("business-intelligence");
    if (section) observer.observe(section);

    return () => observer.disconnect();
  });

  const blocks = [
    {
      icon: PieChart,
      color: "accent" as const,
      question: "How big is this opportunity?",
      narrative:
        "Your total addressable market, narrowed to a realistic year-one target. We size it using keyword demand, how competitive the space is, and how often the pain point comes up.",
      points: [
        "TAM → SAM → SOM funnel with your year-one slice",
        "Monthly search volume aggregated across your niche",
      ],
      highlight: "Sized from actual keyword demand",
    },
    {
      icon: Tag,
      color: "accent" as const,
      question: "What should I charge?",
      narrative:
        "Pricing tiers, unit economics, and willingness-to-pay scores. We match these to one of eight monetization models based on what people in your market say they'd actually pay.",
      points: [
        "Tiered pricing or alternative monetization paths",
        "Revenue projections: ARPU, lifetime value, payback ratio",
        "Eight monetization models covered",
        "Willingness-to-pay signals from real discussions",
      ],
      highlight: "Matched to community willingness-to-pay signals",
    },
    {
      icon: Scale,
      color: "accent" as const,
      question: "Should I build this?",
      narrative:
        "Clear Go, No-Go, or Conditional verdict backed by a confidence score, risk assessment, and trend analysis.",
      points: [
        "Verdict with rationale",
        "Confidence from market fit, competition, feasibility, and SEO",
        "Trend momentum and longevity",
      ],
      highlight: "Multi-factor risk assessment",
    },
  ];
</script>

<section id="business-intelligence" class="section-alt">
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Section Header -->
      <div class="mb-16">
        <div class="section-header-meta animate-fade-in">
          <div class="section-header-bar"></div>
          <span class="section-counter">[ <span class="section-counter-active">04</span> / 07 ]</span>
          <span class="section-header-dot">·</span>
          <span class="section-label">The Numbers</span>
        </div>
        <h2
          class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6"
        >
          Real Numbers. <span class="text-accent"
            >Not Vibes.</span
          >
        </h2>
        <p
          class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl"
        >
          The business data behind the decision. Market sizing, pricing, and a clear verdict.
        </p>
      </div>

      <!-- Data Blocks -->
      <div class="space-y-10 sm:space-y-14">
        {#each blocks as block, i}
          <div
            class="animate-fade-in grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8"
            style="animation-delay: {300 + i * 200}ms"
          >
            <!-- Metric Callout (first on mobile, right on desktop) -->
            <div class="order-1 md:order-2">
              {#if block.question === "How big is this opportunity?"}
                <!-- Block 1: Funnel Bars -->
                <div
                  class="border-l-4 border-accent bg-bg-elevated rounded-r-xl p-5 sm:p-6"
                  role="img"
                  aria-label="Market funnel: TAM $2.4B, SAM $630M, SOM $12M"
                >
                  <div class="space-y-2.5">
                    <div class="flex items-center gap-3">
                      <span class="font-mono text-xs text-text-muted w-8"
                        >TAM</span
                      >
                      <div
                        class="flex-1 h-3 rounded-full bg-bg-surface overflow-hidden"
                      >
                        <div
                          class="h-full w-full rounded-full bg-accent"
                        ></div>
                      </div>
                      <span class="font-mono text-sm font-semibold text-accent"
                        >$2.4B</span
                      >
                    </div>
                    <div class="flex items-center gap-3">
                      <span class="font-mono text-xs text-text-muted w-8"
                        >SAM</span
                      >
                      <div
                        class="flex-1 h-3 rounded-full bg-bg-surface overflow-hidden"
                      >
                        <div
                          class="h-full w-[55%] rounded-full bg-secondary"
                        ></div>
                      </div>
                      <span class="font-mono text-sm font-semibold text-secondary"
                        >$630M</span
                      >
                    </div>
                    <div class="flex items-center gap-3">
                      <span class="font-mono text-xs text-text-muted w-8"
                        >SOM</span
                      >
                      <div
                        class="flex-1 h-3 rounded-full bg-bg-surface overflow-hidden"
                      >
                        <div
                          class="h-full w-[30%] rounded-full bg-warning"
                        ></div>
                      </div>
                      <span class="font-mono text-sm font-semibold text-warning"
                        >$12M</span
                      >
                    </div>
                  </div>
                </div>
              {:else if block.question === "What should I charge?"}
                <!-- Block 2: Tier Pills -->
                <div
                  class="border-l-4 border-accent/70 bg-bg-elevated rounded-r-xl p-5 sm:p-6"
                >
                  <div class="flex flex-col sm:flex-row flex-wrap gap-2 mb-3">
                    <span
                      class="px-3 py-1.5 rounded-lg bg-accent/10 border border-accent/30 font-mono text-sm font-semibold text-accent"
                      >Starter $19/mo</span
                    >
                    <span
                      class="px-3 py-1.5 rounded-lg bg-bg-surface border border-border font-mono text-sm text-text-secondary"
                      >Pro $49/mo</span
                    >
                    <span
                      class="px-3 py-1.5 rounded-lg bg-bg-surface border border-border font-mono text-sm text-text-secondary"
                      >Enterprise $149/mo</span
                    >
                  </div>
                  <div
                    class="flex flex-wrap gap-x-4 gap-y-1 font-mono text-sm text-text-muted"
                  >
                    <span
                      >ARPU <span class="text-text-secondary font-semibold"
                        >$32/mo</span
                      ></span
                    >
                    <span
                      >LTV <span class="text-text-secondary font-semibold"
                        >$384–960</span
                      ></span
                    >
                    <span
                      >Demand <span class="text-text-secondary font-semibold"
                        >0.58</span
                      ></span
                    >
                  </div>
                </div>
              {:else}
                <!-- Block 3: Verdict Badge -->
                <div
                  class="border-l-4 border-accent bg-bg-elevated rounded-r-xl p-5 sm:p-6"
                >
                  <div class="flex flex-wrap items-center gap-3 mb-3">
                    <span
                      class="px-4 py-2 rounded-lg bg-success/15 border border-success/40 font-display text-lg font-bold text-success"
                      >GO</span
                    >
                    <div class="flex items-center gap-2">
                      <span class="font-mono text-xs text-text-muted"
                        >Confidence</span
                      >
                      <div
                        class="w-20 h-2 rounded-full bg-bg-surface overflow-hidden"
                        role="progressbar"
                        aria-valuenow={72}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label="Confidence score"
                      >
                        <div
                          class="h-full w-[72%] rounded-full bg-accent"
                        ></div>
                      </div>
                      <span class="font-mono text-sm font-semibold text-accent"
                        >72%</span
                      >
                    </div>
                  </div>
                  <div class="flex gap-3 font-mono text-sm">
                    <span class="text-text-muted">Risk: Medium</span>
                    <span class="text-success">Trend: Growing ↑</span>
                  </div>
                </div>
              {/if}
            </div>

            <!-- Narrative (second on mobile, left on desktop) -->
            <div class="order-2 md:order-1">
              <div class="flex items-start gap-3 mb-3">
                <div
                  class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-accent/10 border border-accent/30"
                >
                  <block.icon class="w-5 h-5 text-accent" />
                </div>
                <h3
                  class="font-display text-lg sm:text-xl font-semibold text-text-primary pt-1.5"
                >
                  {block.question}
                </h3>
              </div>

              <p class="text-text-secondary text-sm leading-relaxed mb-4">
                {block.narrative}
              </p>

              <div class="space-y-2 mb-4">
                {#each block.points as point}
                  <div class="flex items-start gap-2.5">
                    <CheckCircle2
                      class="w-4 h-4 shrink-0 mt-0.5 text-accent"
                    />
                    <span class="text-sm text-text-muted">{point}</span>
                  </div>
                {/each}
              </div>

              <span
                class="inline-flex items-center gap-2 text-xs font-semibold text-accent"
              >
                <CheckCircle2 class="w-3.5 h-3.5" />
                {block.highlight}
              </span>
            </div>
          </div>
        {/each}
      </div>

      <!-- Bottom Tagline -->
      <div class="animate-fade-in delay-500 text-center mt-12">
        <div class="divider max-w-xs mx-auto"></div>
        <p class="text-text-muted italic text-lg mt-8">
          Built on search volume data and community signals. No surveys. No gut feelings.
        </p>
      </div>
    {/if}
  </div>
</section>
