<script lang="ts">
  import { onMount } from "svelte";
  import { tweened } from "svelte/motion";
  import { cubicOut } from "svelte/easing";
  import { ArrowRight, Sparkles } from "lucide-svelte";
  import { page } from "$app/stores";

  interface Props {
    session?: { user?: { name?: string | null; email?: string | null } } | null;
  }

  let { session = null }: Props = $props();

  let isVisible = $state(false);

  // Animated counters
  const minuteCount = tweened(0, { duration: 2000, easing: cubicOut });
  const painPointCount = tweened(0, { duration: 2000, easing: cubicOut });
  const verifyCount = tweened(0, { duration: 2000, easing: cubicOut });

  // Terminal animation
  const terminalLines = [
    { text: "> Scanning social media for pain points...", highlight: false },
    { text: "> Found 89 relevant discussions", highlight: false },
    { text: "> Extracting 18 pain points with severity scores...", highlight: false },
    { text: "> Validating 150+ keywords with search data...", highlight: false },
    { text: "> Calculating market size (TAM/SAM/SOM)...", highlight: false },
    { text: "> Verification: Solo-launchable with minimal budget", highlight: true },
    { text: "> Projected revenue: $5K-15K MRR", highlight: true },
    { text: "> VERDICT: GO - Confidence: 87%", highlight: true },
    { text: "> Ready: Blueprint + Landing Page. Risk: Medium.", highlight: true },
  ];
  let visibleLineCount = $state(0);
  let terminalComplete = $state(false);

  onMount(() => {
    isVisible = true;

    // Start terminal animation after initial fade-in
    setTimeout(() => {
      const interval = setInterval(() => {
        if (visibleLineCount < terminalLines.length) {
          visibleLineCount++;
        } else {
          terminalComplete = true;
          clearInterval(interval);
        }
      }, 600);

      return () => clearInterval(interval);
    }, 800);
  });

  // Trigger counting when visible
  $effect(() => {
    if (isVisible) {
      minuteCount.set(12);
      painPointCount.set(18);
      verifyCount.set(100);
    }
  });

  function scrollToSample() {
    document
      .getElementById("sample-report")
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
    class="relative z-10 w-full max-w-5xl mx-auto px-6 lg:px-12 py-24 lg:py-32"
  >
    {#if isVisible}
      <!-- Centered Content -->
      <div class="text-center">
        <!-- Badge -->
        <div class="animate-fade-in mb-8 inline-flex">
          <span class="inline-flex items-center gap-2 badge">
            <Sparkles class="w-3.5 h-3.5" />
            For solo founders. By a solo founder
          </span>
        </div>

        <!-- Main Headline -->
        <h1
          class="animate-fade-in delay-100 font-display text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-text-primary leading-[1.05] mb-8"
        >
          YOU CHOOSE <span class="text-gradient-animated">THE NICHE.</span>
          <br />
          WE FIND. VALIDATE. DELIVER <span class="text-gradient-animated">OPPORTUNITIES.</span>
          <br />
          YOU BUILD ACTUALLY WANTED, PROFITABLE <span class="text-gradient-animated">MICRO-BUSINESS.</span>
        </h1>

        <!-- Accent line -->
        <div
          class="animate-fade-in delay-200 w-24 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full mx-auto mb-8"
        ></div>

        <!-- Subheadline -->
        <p
          class="animate-fade-in delay-200 text-xl sm:text-2xl text-text-secondary leading-relaxed mb-6 max-w-2xl mx-auto"
        >
          Real data.
          <span class="text-text-primary font-medium">Verified sources.</span>
        </p>

        <p
          class="animate-fade-in delay-300 text-lg text-text-muted leading-relaxed mb-8 max-w-xl mx-auto"
        >
          Get validated market research with real pain points, market sizing,
          pricing strategy, and a clear go/no-go verdict. All in 12 minutes.
        </p>

        <!-- Terminal Animation -->
        <div
          class="animate-fade-in delay-400 bg-bg-base border border-border rounded-lg p-4 font-mono text-sm max-w-2xl mx-auto mb-10 text-left shadow-lg"
        >
          <!-- Terminal Header -->
          <div class="flex items-center gap-2 mb-4 pb-2 border-b border-border">
            <div class="w-3 h-3 rounded-full bg-error/50"></div>
            <div class="w-3 h-3 rounded-full bg-warning/50"></div>
            <div class="w-3 h-3 rounded-full bg-success/50"></div>
            <span class="ml-auto text-xs text-text-muted">NicheIQ v2.1</span>
          </div>
          <!-- Terminal Content -->
          <div class="space-y-1.5 h-[220px]">
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

        <!-- CTA Buttons -->
        <div class="animate-fade-in delay-400 flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
          {#if session?.user}
            <a
              href="/dashboard"
              class="btn-primary px-8 py-4 text-base"
            >
              Go to Dashboard
              <ArrowRight class="w-5 h-5" />
            </a>
          {:else}
            <a
              href="/register"
              class="btn-primary px-8 py-4 text-base"
            >
              Get Started Free
              <ArrowRight class="w-5 h-5" />
            </a>
            <a
              href="/login"
              class="btn-secondary px-6 py-3"
            >
              Sign In
            </a>
          {/if}
        </div>

        <!-- Stats Row with Animated Numbers -->
        <div
          class="animate-fade-in delay-500 flex flex-wrap justify-center gap-6"
        >
          <div class="stat-card px-5 py-4">
            <span class="block text-2xl font-display font-bold text-accent">
              {Math.round($minuteCount)} min
            </span>
            <span class="small-caps">To validated research</span>
          </div>
          <div class="stat-card px-5 py-4">
            <span class="block text-2xl font-display font-bold text-accent">
              {Math.round($painPointCount)}+
            </span>
            <span class="small-caps">Pain points found</span>
          </div>
          <div class="stat-card px-5 py-4">
            <span class="block text-2xl font-display font-bold text-accent">
              {Math.round($verifyCount)}%
            </span>
            <span class="small-caps">Claims verifiable</span>
          </div>
        </div>

        <!-- View Sample Report Link -->
        <button
          onclick={scrollToSample}
          class="animate-fade-in delay-600 mt-8 text-text-muted hover:text-accent transition-colors text-sm underline underline-offset-4"
        >
          View Sample Report
        </button>
      </div>
    {/if}
  </div>

  <!-- Scroll Indicator -->
  <div class="absolute bottom-8 left-1/2 -translate-x-1/2">
    <div class="flex flex-col items-center gap-2 text-text-muted">
      <span class="small-caps text-xs">Scroll</span>
      <div
        class="w-px h-8 bg-gradient-to-b from-border-emphasis to-transparent"
      ></div>
    </div>
  </div>
</section>
