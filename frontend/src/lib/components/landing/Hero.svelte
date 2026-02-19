<script lang="ts">
  import { onMount } from "svelte";
  import { ArrowRight, Sparkles } from "lucide-svelte";
  import { page } from "$app/stores";
  import type { CtaConfig } from "$lib/types/cta";
  import CtaIcon from "$lib/components/ui/CtaIcon.svelte";

  interface Props {
    session?: { user?: { name?: string | null; email?: string | null } } | null;
    hasSampleReport?: boolean;
    ctaTexts?: Record<string, CtaConfig | null>;
  }

  let { session = null, hasSampleReport = false, ctaTexts }: Props = $props();

  let isVisible = $state(false);

  // Terminal animation
  const terminalLines = [
    { text: "> Scanning social media for pain points...", highlight: false },
    { text: "> Found 89 relevant discussions", highlight: false },
    {
      text: "> Extracting 5 pain points with severity scores...",
      highlight: false,
    },
    {
      text: "> Validating 100+ keywords with search data...",
      highlight: false,
    },
    { text: "> Calculating market size (TAM/SAM/SOM)...", highlight: false },
    {
      text: "> Verification: Solo-launchable with minimal budget",
      highlight: true,
    },
    { text: "> Projected revenue: $5K-15K MRR", highlight: true },
    { text: "> VERDICT: GO - Confidence: 87%", highlight: true },
    {
      text: "> Ready: Blueprint + Landing Page. Risk: Medium.",
      highlight: true,
    },
  ];
  let visibleLineCount = $state(0);
  let terminalComplete = $state(false);

  onMount(() => {
    isVisible = true;

    // Start terminal animation after initial fade-in (slower for indie vibe)
    setTimeout(() => {
      const interval = setInterval(() => {
        if (visibleLineCount < terminalLines.length) {
          visibleLineCount++;
        } else {
          terminalComplete = true;
          clearInterval(interval);
        }
      }, 800);

      return () => clearInterval(interval);
    }, 800);
  });

  function scrollToHowItWorks() {
    document
      .getElementById("how-it-works")
      ?.scrollIntoView({ behavior: "smooth" });
  }
</script>

<section class="relative min-h-screen flex items-center overflow-hidden">
  <!-- Ambient background -->
  <div class="absolute inset-0 bg-bg-base"></div>
  <div class="absolute inset-0 bg-radial-amber"></div>

  <div
    class="relative z-10 w-full max-w-5xl mx-auto px-6 lg:px-12 py-20 sm:py-24 lg:py-32"
  >
    {#if isVisible}
      <!-- Centered Content -->
      <div class="text-center">
        <!-- Badge -->
        <div class="animate-fade-in mb-6 sm:mb-8 inline-flex">
          <span class="inline-flex items-center gap-2 badge">
            <Sparkles class="w-3.5 h-3.5" />
            For solo founders. By a solo founder
          </span>
        </div>

        <!-- Main Headline - Mobile optimized: text-3xl (30px) on mobile, scaling up -->
        <h1
          class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl lg:text-7xl font-bold tracking-tight text-text-primary leading-[1.1] mb-6 sm:mb-8"
        >
          Discover your next SaaS opportunity in <span
            class="text-gradient-animated">45 minutes</span
          >
        </h1>

        <p
          class="animate-fade-in delay-300 text-lg sm:text-xl text-text-secondary leading-relaxed mb-3 sm:mb-4 max-w-xl mx-auto"
        >
          NicheIQ helps solo founders get clear answers on <strong
            class="text-text-primary">what to build</strong
          >
          and <strong class="text-text-primary">how to profit</strong>.
        </p>
        <p
          class="animate-fade-in delay-200 text-base sm:text-lg text-text-muted italic leading-relaxed mb-4 sm:mb-6 max-w-xl mx-auto"
        >
          Now 45 minutes feels like 3 weeks of research.
        </p>

        <!-- CTA Buttons - Mobile optimized with full width on small screens -->
        <div
          class="animate-fade-in delay-400 flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 mb-8 sm:mb-10"
        >
          {#if session?.user}
            <a
              href="/dashboard"
              class="btn-primary w-full sm:w-auto px-8 py-4 text-base"
            >
              Go to Dashboard
              <ArrowRight class="w-5 h-5" />
            </a>
          {:else}
            {@const heroPrimary = ctaTexts?.cta_hero_primary}
            {@const heroSecondary = ctaTexts?.cta_hero_secondary}
            {@const secondaryUrl = heroSecondary?.url ?? "#how-it-works"}
            {#if heroPrimary?.visible !== false}
              <a
                href={heroPrimary?.url ?? "/register"}
                class="btn-primary w-full sm:w-auto px-8 py-4 text-base"
              >
                {heroPrimary?.text ?? "Get Started"}
                <CtaIcon name={heroPrimary?.icon} />
              </a>
            {/if}
            {#if heroSecondary?.visible !== false}
              <a
                href={secondaryUrl}
                onclick={(e) => {
                  if (secondaryUrl.startsWith('#')) {
                    e.preventDefault();
                    document.getElementById(secondaryUrl.slice(1))?.scrollIntoView({ behavior: 'smooth' });
                  }
                }}
                class="btn-secondary w-full sm:w-auto px-8 py-4 text-base"
              >
                {heroSecondary?.text ?? "See How It Works"}
                <CtaIcon name={heroSecondary?.icon} />
              </a>
            {/if}
          {/if}
        </div>

        <!-- Terminal Animation - Full container width, aligned with hero text -->
        <div
          class="animate-fade-in delay-400 bg-bg-elevated border border-accent/15 rounded-xl p-3 sm:p-4 font-mono text-xs sm:text-sm mb-8 sm:mb-10 text-left w-full"
        >
          <!-- Terminal Header -->
          <div
            class="flex items-center gap-1.5 sm:gap-2 mb-3 sm:mb-4 pb-2 border-b border-border"
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
              class="ml-auto text-[10px] sm:text-xs text-text-muted font-medium tracking-wide"
              >nicheiq-terminal</span
            >
          </div>
          <!-- Terminal Content - responsive height -->
          <div
            class="space-y-1 sm:space-y-1.5 min-h-[180px] sm:min-h-[220px]"
          >
            {#each terminalLines.slice(0, visibleLineCount) as line, i}
              <div
                class={line.highlight
                  ? "text-accent font-semibold"
                  : "text-text-muted"}
              >
                {line.text}{#if !terminalComplete && i === visibleLineCount - 1}<span
                    class="inline-block w-2 h-4 bg-accent animate-pulse ml-1 align-middle"
                  ></span>{/if}
              </div>
            {/each}
            {#if !terminalComplete && visibleLineCount === 0}
              <span class="inline-block w-2 h-4 bg-accent animate-pulse"></span>
            {/if}
          </div>
        </div>


        <!-- View Sample Report Link -->
        {#if hasSampleReport && ctaTexts?.cta_view_sample_link?.visible !== false}
          <a
            href={ctaTexts?.cta_view_sample_link?.url ?? "/sample-report"}
            class="animate-fade-in delay-600 mt-6 sm:mt-8 text-text-muted hover:text-accent transition-colors text-sm underline underline-offset-4 inline-flex items-center gap-1.5"
          >
            {ctaTexts?.cta_view_sample_link?.text ?? "View Sample Report"}
            <CtaIcon name={ctaTexts?.cta_view_sample_link?.icon} class="w-4 h-4" />
          </a>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Scroll Indicator - Hidden on mobile for cleaner look -->
  <div class="absolute bottom-8 left-1/2 -translate-x-1/2 hidden sm:block">
    <div class="flex flex-col items-center gap-2 text-text-muted">
      <span class="small-caps text-xs">Scroll</span>
      <div
        class="w-px h-8 bg-gradient-to-b from-border-emphasis to-transparent"
      ></div>
    </div>
  </div>
</section>
