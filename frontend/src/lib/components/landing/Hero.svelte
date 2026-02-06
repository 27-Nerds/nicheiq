<script lang="ts">
  import { onMount } from "svelte";
  import { tweened } from "svelte/motion";
  import { cubicOut } from "svelte/easing";
  import { ArrowRight, Sparkles } from "lucide-svelte";
  import { page } from "$app/stores";

  interface Props {
    session?: { user?: { name?: string | null; email?: string | null } } | null;
    hasSampleReport?: boolean;
  }

  let { session = null, hasSampleReport = false }: Props = $props();

  let isVisible = $state(false);

  // Animated counters
  const minuteCount = tweened(0, { duration: 2000, easing: cubicOut });
  const painPointCount = tweened(0, { duration: 2000, easing: cubicOut });
  const verifyCount = tweened(0, { duration: 2000, easing: cubicOut });

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

  // Trigger counting when visible
  $effect(() => {
    if (isVisible) {
      minuteCount.set(45);
      painPointCount.set(5);
      verifyCount.set(100);
    }
  });

  function scrollToHowItWorks() {
    document
      .getElementById("how-it-works")
      ?.scrollIntoView({ behavior: "smooth" });
  }
</script>

<section class="relative min-h-screen flex items-center overflow-hidden">
  <!-- Ambient background effects -->
  <div class="absolute inset-0 bg-bg-base"></div>
  <div class="absolute inset-0 bg-radial-amber"></div>

  <!-- Subtle grid pattern -->
  <div
    class="absolute inset-0 opacity-[0.02]"
    style="background-image: linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px); background-size: 60px 60px;"
  ></div>

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

        <!-- Accent line -->
        <div
          class="animate-fade-in delay-200 w-16 sm:w-24 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full mx-auto mb-6 sm:mb-8"
        ></div>

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
            <a
              href="/register"
              class="btn-primary w-full sm:w-auto px-8 py-4 text-base"
            >
              Get Started
              <ArrowRight class="w-5 h-5" />
            </a>
            <button
              onclick={scrollToHowItWorks}
              class="btn-secondary w-full sm:w-auto px-8 py-4 text-base"
            >
              See How It Works
            </button>
          {/if}
        </div>

        <!-- Terminal Animation - Mobile optimized with responsive height -->
        <div
          class="animate-fade-in delay-400 bg-bg-elevated border border-border-emphasis rounded-xl p-3 sm:p-4 font-mono text-xs sm:text-sm max-w-2xl mx-auto mb-8 sm:mb-10 text-left shadow-lg"
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
            class="space-y-1 sm:space-y-1.5 h-[180px] sm:h-[220px] overflow-y-auto"
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

        <!-- Stats Row with Animated Numbers - Mobile optimized with tighter gap -->
        <div
          class="animate-fade-in delay-500 flex flex-wrap justify-center gap-3 sm:gap-4"
        >
          <div
            class="stat-card px-4 sm:px-6 py-3 sm:py-4 border-l-2 border-l-accent hover:shadow-md transition-shadow"
          >
            <span
              class="block text-2xl sm:text-3xl font-display font-bold text-accent tracking-tight"
            >
              {Math.round($minuteCount)}<span
                class="text-lg sm:text-xl font-semibold ml-0.5">min</span
              >
            </span>
            <span class="small-caps text-[10px] sm:text-xs mt-1 block"
              >To your verdict</span
            >
          </div>
          <div
            class="stat-card px-4 sm:px-6 py-3 sm:py-4 border-l-2 border-l-success hover:shadow-md transition-shadow"
          >
            <span
              class="block text-2xl sm:text-3xl font-display font-bold text-success tracking-tight"
            >
              {Math.round($painPointCount)}<span
                class="text-lg sm:text-xl font-semibold">+</span
              >
            </span>
            <span class="small-caps text-[10px] sm:text-xs mt-1 block"
              >Pain points found</span
            >
          </div>
          <div
            class="stat-card px-4 sm:px-6 py-3 sm:py-4 border-l-2 border-l-secondary hover:shadow-md transition-shadow"
          >
            <span
              class="block text-2xl sm:text-3xl font-display font-bold text-secondary tracking-tight"
            >
              {Math.round($verifyCount)}<span
                class="text-lg sm:text-xl font-semibold">%</span
              >
            </span>
            <span class="small-caps text-[10px] sm:text-xs mt-1 block"
              >Claims verifiable</span
            >
          </div>
        </div>

        <!-- View Sample Report Link -->
        {#if hasSampleReport}
          <a
            href="/sample-report"
            class="animate-fade-in delay-600 mt-6 sm:mt-8 text-text-muted hover:text-accent transition-colors text-sm underline underline-offset-4"
          >
            View Sample Report
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
