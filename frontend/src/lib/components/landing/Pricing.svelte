<script lang="ts">
  import { onMount } from "svelte";
  import {
    Check,
    ShieldCheck,
    Waypoints,
    TrendingUp,
    Eye,
    BarChart3,
    Clock,
    ArrowRight,
    MessageSquare,
    Gift,
  } from "lucide-svelte";

  import type { CtaConfig } from "$lib/types/cta";
  import CtaIcon from "$lib/components/ui/CtaIcon.svelte";

  interface Props {
    session?: { user?: { name?: string | null; email?: string | null } } | null;
    ctaTexts?: Record<string, CtaConfig | null>;
  }

  let { session = null, ctaTexts }: Props = $props();

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

    const section = document.getElementById("pricing");
    if (section) observer.observe(section);

    return () => observer.disconnect();
  });

  const tiers = [
    {
      name: "Starter",
      reports: 1,
      price: 19,
      popular: false,
    },
    {
      name: "Basic",
      reports: 3,
      price: 45,
      popular: true,
    },
    {
      name: "Pro",
      reports: 10,
      price: 100,
      popular: false,
    },
  ];

  const features = [
    { icon: Waypoints, text: "16-stage research pipeline" },
    { icon: MessageSquare, text: "5+ pain points with sources" },
    { icon: TrendingUp, text: "100+ keywords with live search volumes" },
    { icon: Eye, text: "Competitive landscape analysis" },
    { icon: BarChart3, text: "Complete SEO strategy" },
    { icon: Clock, text: "GTM blueprint with 30-day playbook" },
    { icon: ShieldCheck, text: "80% hard data, 20% AI synthesis" },
    { icon: Check, text: "Ready-to-launch landing page (optional)" },
  ];
</script>

<section id="pricing" class="section">
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Section Header -->
      <div class="mb-10 sm:mb-16">
        <div class="section-header-meta animate-fade-in">
          <div class="section-header-bar"></div>
          <span class="section-counter">[ <span class="section-counter-active">07</span> / 07 ]</span>
          <span class="section-header-dot">·</span>
          <span class="section-label">Pricing</span>
        </div>
        <h2
          class="animate-fade-in delay-100 font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mt-4 mb-4 sm:mb-6 text-center"
        >
          Simple Pricing. <span class="text-accent"
            >Full Report.</span
          >
        </h2>
        <p
          class="animate-fade-in delay-200 text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl mx-auto text-center"
        >
          Buy report bundles, use them whenever. No subscription required.
        </p>
        <p
          class="animate-fade-in delay-300 text-sm sm:text-base text-text-secondary mt-3 max-w-2xl mx-auto text-center"
        >
          Every package includes 1 FREE Discovery (up to 10 ideas). Don't worry about your first try.
        </p>
      </div>

      <!-- Pricing Tiers Grid -->
      <div
        class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 max-w-5xl mx-auto"
      >
        {#each tiers as tier}
          <div
            class="relative bg-bg-elevated border rounded-xl overflow-hidden transition-transform hover:scale-[1.02] {tier.popular
              ? 'border-accent md:-translate-y-2'
              : 'border-border'}"
          >
            <!-- Popular Badge -->
            {#if tier.popular}
              <div
                class="absolute top-0 right-0 bg-accent text-white text-xs font-semibold px-3 py-1 rounded-bl-lg"
              >
                Most Popular
              </div>
            {/if}

            <!-- Tier Header -->
            <div
              class="p-6 sm:p-8 pb-4 sm:pb-6 text-center border-b border-border"
            >
              <h3 class="text-lg font-semibold text-text-primary mb-3">
                {tier.name}
              </h3>
              <div class="flex items-baseline justify-center gap-1 mb-2">
                <span
                  class="text-4xl sm:text-5xl font-display font-bold text-text-primary"
                  >${tier.price}</span
                >
              </div>
              <p class="text-text-secondary text-sm sm:text-base">
                <span class="text-text-muted">~</span>{tier.reports}
                {tier.reports === 1 ? "report" : "reports"}<sup class="text-accent text-[10px] ml-0.5 relative -top-1">*</sup>
              </p>
              {#if tier.reports > 1}
                <p class="text-text-muted text-xs mt-1">
                  ${(tier.price / tier.reports).toFixed(0)}/report
                </p>
              {/if}
            </div>

            <!-- CTA -->
            <div class="p-6 sm:p-8">
              <div class="flex items-center justify-center gap-1.5 text-xs font-semibold text-accent bg-accent/[0.06] border border-accent/20 rounded-full px-3 py-1.5 mb-3">
                <Gift class="w-3.5 h-3.5 flex-shrink-0" />
                <span>+1 FREE Discovery</span>
                <span class="text-text-muted font-normal">(up to 10 ideas)</span>
              </div>
              {#if session?.user}
                <a
                  href="/dashboard"
                  class="w-full text-sm sm:text-base py-3 text-center {tier.popular
                    ? 'btn-primary'
                    : 'btn-secondary'}"
                >
                  Go to Dashboard
                  <ArrowRight class="w-4 h-4" />
                </a>
              {:else if ctaTexts?.cta_pricing_button?.visible !== false}
                {@const pricingCta = ctaTexts?.cta_pricing_button}
                {@const pricingText = pricingCta?.text
                  ? pricingCta.text.replace('{count}', String(tier.reports)).replace('(s)', tier.reports === 1 ? '' : 's')
                  : `Get ${tier.reports} ${tier.reports === 1 ? "Report" : "Reports"}`}
                <a
                  href={pricingCta?.url ?? "/register"}
                  class="w-full text-sm sm:text-base py-3 text-center {tier.popular
                    ? 'btn-primary'
                    : 'btn-secondary'}"
                >
                  {pricingText}
                  <CtaIcon name={pricingCta?.icon} class="w-4 h-4" />
                </a>
              {/if}
            </div>
          </div>
        {/each}
      </div>
      <p class="text-xs text-text-muted/70 text-center mt-6">
        *Credit-based system — estimated report count, use however works best for you
      </p>

      <!-- What's Included Section -->
      <div class="animate-fade-in delay-400 mt-12 sm:mt-16 max-w-3xl mx-auto">
        <h3
          class="text-center text-lg sm:text-xl font-semibold text-text-primary mb-6 sm:mb-8"
        >
          What's included in every report
        </h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
          {#each features as feature}
            <div class="flex items-start gap-3">
              <span class="text-accent text-sm mt-0.5 flex-shrink-0">→</span>
              <span class="text-text-secondary text-sm sm:text-base"
                >{feature.text}</span
              >
            </div>
          {/each}
        </div>

        <!-- Guarantee Badge -->
        <div
          class="mt-8 sm:mt-10 p-4 rounded-lg bg-success/5 border border-success/30 flex items-center gap-3 max-w-md mx-auto"
        >
          <ShieldCheck class="w-8 h-8 text-success flex-shrink-0" />
          <div>
            <h4 class="font-semibold text-success text-sm">
              Zero-Risk Guarantee
            </h4>
            <p class="text-xs text-text-muted">
              If a report can't be completed due to insufficient data or any
              other reason, your research credit is automatically returned — no
              risk, no loss.
            </p>
          </div>
        </div>

        {#if !session?.user}
          <p class="text-center text-xs sm:text-sm text-text-muted mt-6">
            Already have an account? <a
              href="/login"
              class="text-accent hover:underline">Sign in</a
            >
          </p>
        {/if}
      </div>
    {/if}
  </div>
</section>
