<script lang="ts">
  import { onMount } from "svelte";
  import { slide } from "svelte/transition";
  import {
    Check,
    X,
    Minus,
    Clock,
    DollarSign,
    Database,
    Link,
    Search,
    Eye,
    FileText,
    ChevronDown,
    Layers,
    Scale,
    TrendingUp,
    PanelTop,
    Tag,
    MessageSquare,
  } from "lucide-svelte";

  let isVisible = $state(false);
  let expandedFeature = $state<number | null>(null);

  function toggleFeature(index: number) {
    expandedFeature = expandedFeature === index ? null : index;
  }

  onMount(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          isVisible = true;
        }
      },
      { threshold: 0.1 },
    );

    const section = document.getElementById("comparison");
    if (section) observer.observe(section);

    return () => observer.disconnect();
  });

  type FeatureValue = "check" | "cross" | "partial" | string;

  interface Feature {
    name: string;
    icon: typeof Clock;
    nicheiq: FeatureValue;
    perplexity: FeatureValue;
    grok: FeatureValue;
    painonsocial: FeatureValue;
  }

  const features: Feature[] = [
    {
      name: "Time to Results",
      icon: Clock,
      nicheiq: "45 minutes",
      perplexity: "3-5 min",
      grok: "3-5 min",
      painonsocial: "~10 min",
    },
    {
      name: "Cost",
      icon: DollarSign,
      nicheiq: "Starting at $19",
      perplexity: "$20/mo",
      grok: "Free-$30/mo",
      painonsocial: "Varies",
    },
    {
      name: "Direct Social Access",
      icon: Database,
      nicheiq: "check",
      perplexity: "cross",
      grok: "cross",
      painonsocial: "check",
    },
    {
      name: "Keyword Validation",
      icon: Search,
      nicheiq: "Real Data",
      perplexity: "cross",
      grok: "cross",
      painonsocial: "cross",
    },
    {
      name: "Source Attribution",
      icon: Link,
      nicheiq: "check",
      perplexity: "check",
      grok: "partial",
      painonsocial: "check",
    },
    {
      name: "Structured Report",
      icon: FileText,
      nicheiq: "50+ fields",
      perplexity: "Chat",
      grok: "Chat",
      painonsocial: "partial",
    },
    {
      name: "SEO Strategy",
      icon: Search,
      nicheiq: "100+ keywords",
      perplexity: "cross",
      grok: "cross",
      painonsocial: "cross",
    },
    {
      name: "Competitive Analysis",
      icon: Eye,
      nicheiq: "check",
      perplexity: "partial",
      grok: "partial",
      painonsocial: "cross",
    },
    {
      name: "Market Sizing (TAM/SAM/SOM)",
      icon: Layers,
      nicheiq: "check",
      perplexity: "cross",
      grok: "cross",
      painonsocial: "cross",
    },
    {
      name: "Pricing Strategy",
      icon: Tag,
      nicheiq: "check",
      perplexity: "cross",
      grok: "cross",
      painonsocial: "cross",
    },
    {
      name: "Risk Assessment",
      icon: Scale,
      nicheiq: "Go/No-Go",
      perplexity: "cross",
      grok: "cross",
      painonsocial: "cross",
    },
  ];

  function isIcon(value: FeatureValue): value is "check" | "cross" | "partial" {
    return value === "check" || value === "cross" || value === "partial";
  }
</script>

<section id="comparison" class="section-alt">
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Section Header -->
      <div class="mb-16">
        <span class="section-label animate-fade-in">The Comparison</span>
        <h2
          class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6"
        >
          How NicheIQ <span class="text-gradient italic">Compares</span>
        </h2>
        <div
          class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full animate-fade-in delay-200"
        ></div>
        <p
          class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl"
        >
          Compare NicheIQ against the latest AI research tools and
          Reddit-focused competitors.
        </p>
      </div>

      <!-- Mobile Accordion View -->
      <div class="animate-fade-in delay-300 md:hidden space-y-3">
        {#each features as feature, i}
          <div
            class="bg-bg-elevated border border-border rounded-lg overflow-hidden"
          >
            <button
              onclick={() => toggleFeature(i)}
              class="w-full p-4 flex items-center justify-between text-left hover:bg-bg-hover transition-colors"
            >
              <div class="flex items-center gap-3">
                <feature.icon class="w-4 h-4 text-text-muted" />
                <span class="font-medium text-text-primary">{feature.name}</span
                >
              </div>
              <ChevronDown
                class="w-5 h-5 text-text-muted transition-transform duration-300 {expandedFeature ===
                i
                  ? 'rotate-180'
                  : ''}"
              />
            </button>

            {#if expandedFeature === i}
              <div
                transition:slide={{ duration: 300 }}
                class="px-4 pb-4 space-y-3"
              >
                <!-- NicheIQ -->
                <div
                  class="flex items-center justify-between p-3 rounded-lg bg-accent/5 border border-accent/20"
                >
                  <div class="flex items-center gap-1.5">
                    <img src="/niche-logo-beta.svg" alt="NicheIQ" class="h-4" />
                  </div>
                  {#if isIcon(feature.nicheiq)}
                    {#if feature.nicheiq === "check"}
                      <Check class="w-5 h-5 text-success" />
                    {:else if feature.nicheiq === "cross"}
                      <X class="w-5 h-5 text-error" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning" />
                    {/if}
                  {:else}
                    <span class="font-semibold text-accent text-sm"
                      >{feature.nicheiq}</span
                    >
                  {/if}
                </div>

                <!-- Perplexity -->
                <div
                  class="flex items-center justify-between p-3 rounded-lg bg-bg-surface"
                >
                  <div class="flex items-center gap-1.5">
                    <img src="/icons/perplexity.svg" alt="Perplexity" class="w-4 h-4 rounded" />
                    <span class="text-text-muted text-sm">Perplexity</span>
                  </div>
                  {#if isIcon(feature.perplexity)}
                    {#if feature.perplexity === "check"}
                      <Check class="w-5 h-5 text-success" />
                    {:else if feature.perplexity === "cross"}
                      <X class="w-5 h-5 text-error" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning" />
                    {/if}
                  {:else}
                    <span class="text-text-muted text-sm"
                      >{feature.perplexity}</span
                    >
                  {/if}
                </div>

                <!-- Grok -->
                <div
                  class="flex items-center justify-between p-3 rounded-lg bg-bg-surface"
                >
                  <div class="flex items-center gap-1.5">
                    <img src="/icons/grok.svg" alt="Grok" class="w-4 h-4 rounded" />
                    <span class="text-text-muted text-sm">Grok</span>
                  </div>
                  {#if isIcon(feature.grok)}
                    {#if feature.grok === "check"}
                      <Check class="w-5 h-5 text-success" />
                    {:else if feature.grok === "cross"}
                      <X class="w-5 h-5 text-error" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning" />
                    {/if}
                  {:else}
                    <span class="text-text-muted text-sm">{feature.grok}</span>
                  {/if}
                </div>

                <!-- PainOnSocial -->
                <div
                  class="flex items-center justify-between p-3 rounded-lg bg-bg-surface"
                >
                  <div class="flex items-center gap-1.5">
                    <img src="/icons/painonsocial.png" alt="PainOnSocial" class="h-3.5" />
                  </div>
                  {#if isIcon(feature.painonsocial)}
                    {#if feature.painonsocial === "check"}
                      <Check class="w-5 h-5 text-success" />
                    {:else if feature.painonsocial === "cross"}
                      <X class="w-5 h-5 text-error" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning" />
                    {/if}
                  {:else}
                    <span class="text-text-muted text-sm"
                      >{feature.painonsocial}</span
                    >
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Desktop Table -->
      <div class="animate-fade-in delay-300 overflow-x-auto hidden md:block">
        <table class="dark-table w-full min-w-[640px]">
          <!-- Header -->
          <thead>
            <tr>
              <th class="text-left w-1/5"></th>
              <th class="text-center w-1/5 nicheiq-col">
                <div class="flex flex-col items-center gap-1.5">
                  <span
                    class="text-[10px] font-mono uppercase tracking-widest text-accent font-semibold animate-pulse-glow"
                    >Recommended</span
                  >
                  <div class="h-8 flex items-center justify-center">
                    <img
                      src="/niche-logo-beta.svg"
                      alt="NicheIQ"
                      class="h-6"
                    />
                  </div>
                  <div class="api-badge api-badge-success">Verified Data</div>
                </div>
              </th>
              <th class="text-center w-1/5">
                <div class="flex flex-col items-center gap-1.5">
                  <div class="h-8 flex items-center justify-center">
                    <img
                      src="/icons/perplexity.svg"
                      alt=""
                      class="w-7 h-7 rounded-lg"
                    />
                  </div>
                  <span
                    class="font-display font-semibold text-sm text-text-muted normal-case tracking-normal"
                    >Perplexity</span
                  >
                  <div class="api-badge api-badge-muted">Web Search</div>
                </div>
              </th>
              <th class="text-center w-1/5">
                <div class="flex flex-col items-center gap-1.5">
                  <div class="h-8 flex items-center justify-center">
                    <img
                      src="/icons/grok.svg"
                      alt=""
                      class="w-7 h-7 rounded-lg"
                    />
                  </div>
                  <span
                    class="font-display font-semibold text-sm text-text-muted normal-case tracking-normal"
                    >Grok</span
                  >
                  <div class="api-badge api-badge-muted">X/Twitter</div>
                </div>
              </th>
              <th class="text-center w-1/5">
                <div class="flex flex-col items-center gap-1.5">
                  <div class="h-8 flex items-center justify-center">
                    <img
                      src="/icons/painonsocial.png"
                      alt="PainOnSocial"
                      class="h-[18px] w-auto object-contain"
                    />
                  </div>
                  <span
                    class="font-display font-semibold text-sm text-text-muted normal-case tracking-normal"
                    >PainOnSocial</span
                  >
                  <div class="api-badge api-badge-warning">Reddit Only</div>
                </div>
              </th>
            </tr>
          </thead>

          <!-- Body -->
          <tbody>
            {#each features as feature, i}
              <tr
                class="animate-fade-in"
                style="animation-delay: {300 + i * 50}ms"
              >
                <!-- Feature Name -->
                <td class="py-5">
                  <div class="flex items-center gap-3">
                    <feature.icon class="w-4 h-4 text-text-muted" />
                    <span class="font-medium text-text-primary"
                      >{feature.name}</span
                    >
                  </div>
                </td>

                <!-- NicheIQ (Highlighted) -->
                <td
                  class="py-5 text-center nicheiq-col border-x border-border-accent/30"
                >
                  {#if isIcon(feature.nicheiq)}
                    {#if feature.nicheiq === "check"}
                      <Check class="w-5 h-5 text-success mx-auto" />
                    {:else if feature.nicheiq === "cross"}
                      <X class="w-5 h-5 text-error mx-auto" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning mx-auto" />
                    {/if}
                  {:else}
                    <span class="font-semibold text-accent"
                      >{feature.nicheiq}</span
                    >
                  {/if}
                </td>

                <!-- Perplexity -->
                <td class="py-5 text-center">
                  {#if isIcon(feature.perplexity)}
                    {#if feature.perplexity === "check"}
                      <Check class="w-5 h-5 text-success mx-auto" />
                    {:else if feature.perplexity === "cross"}
                      <X class="w-5 h-5 text-error mx-auto" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning mx-auto" />
                    {/if}
                  {:else}
                    <span class="text-sm text-text-muted"
                      >{feature.perplexity}</span
                    >
                  {/if}
                </td>

                <!-- Grok -->
                <td class="py-5 text-center">
                  {#if isIcon(feature.grok)}
                    {#if feature.grok === "check"}
                      <Check class="w-5 h-5 text-success mx-auto" />
                    {:else if feature.grok === "cross"}
                      <X class="w-5 h-5 text-error mx-auto" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning mx-auto" />
                    {/if}
                  {:else}
                    <span class="text-sm text-text-muted">{feature.grok}</span>
                  {/if}
                </td>

                <!-- PainOnSocial -->
                <td class="py-5 text-center">
                  {#if isIcon(feature.painonsocial)}
                    {#if feature.painonsocial === "check"}
                      <Check class="w-5 h-5 text-success mx-auto" />
                    {:else if feature.painonsocial === "cross"}
                      <X class="w-5 h-5 text-error mx-auto" />
                    {:else}
                      <Minus class="w-5 h-5 text-warning mx-auto" />
                    {/if}
                  {:else}
                    <span class="text-sm text-text-muted"
                      >{feature.painonsocial}</span
                    >
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Key Differentiator Callouts -->
      <div
        class="animate-fade-in delay-500 mt-10 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        <div class="differentiator-callout">
          <MessageSquare class="w-5 h-5 text-accent flex-shrink-0" />
          <span><strong>Verified Pain Points</strong> — Every pain point traced to a discussion thread you can check before you commit.</span>
        </div>
        <div class="differentiator-callout">
          <Layers class="w-5 h-5 text-accent flex-shrink-0" />
          <span><strong>Market Sizing Built In</strong> — Know your total market and year-one target before you write a line of code.</span>
        </div>
        <div class="differentiator-callout">
          <Tag class="w-5 h-5 text-accent flex-shrink-0" />
          <span><strong>Pricing Backed by Demand</strong> — See what customers say they'll pay — sourced from community discussions, not guesswork.</span>
        </div>
        <div class="differentiator-callout">
          <TrendingUp class="w-5 h-5 text-accent flex-shrink-0" />
          <span><strong>Validated Search Volumes</strong> — Every keyword comes with actual monthly search volume and difficulty score.</span>
        </div>
        <div class="differentiator-callout">
          <Scale class="w-5 h-5 text-accent flex-shrink-0" />
          <span><strong>Go / No-Go Verdict</strong> — Know whether to build, pivot, or walk away — with the risk factors laid out.</span>
        </div>
        <div class="differentiator-callout">
          <PanelTop class="w-5 h-5 text-accent flex-shrink-0" />
          <span><strong>Launch-Ready Landing Page</strong> — Full HTML landing page — copy, design, and CTAs — ready to start testing.</span>
        </div>
      </div>

      <!-- Bottom Note -->
      <div class="animate-fade-in delay-600 mt-10 text-center">
        <p class="text-text-muted text-sm italic">
          Everything in the table above ships in a single report — full niche validation for one price.
        </p>
      </div>
    {/if}
  </div>
</section>
