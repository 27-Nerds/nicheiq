<script lang="ts">
  import { intersect } from "$lib/actions/intersect";
  import { ArrowRight, Check } from "lucide-svelte";
  import type { CtaConfig } from "$lib/types/cta";
  import CtaIcon from "$lib/components/ui/CtaIcon.svelte";

  interface Props {
    session?: { user?: { name?: string | null; email?: string | null } } | null;
    hasSampleReport?: boolean;
    ctaTexts?: Record<string, CtaConfig | null>;
  }

  let { session = null, hasSampleReport = false, ctaTexts }: Props = $props();

  let isVisible = $state(false);
</script>

<section id="final-cta" class="section relative overflow-hidden" use:intersect={{ threshold: 0.1, onIntersect: () => isVisible = true }}>
  <!-- Background: bottom-anchored warm glow -->
  <div class="absolute inset-0 bg-radial-amber-bottom"></div>
  <!-- Top gradient blending from FAQ section -->
  <div
    class="absolute inset-0 bg-gradient-to-b from-bg-surface via-transparent to-transparent h-[30%]"
  ></div>

  <div class="relative max-w-3xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Verdict card -->
      <div
        class="animate-fade-in bg-bg-elevated rounded-2xl p-8 sm:p-10 lg:p-12 text-center"
      >

        <!-- Headline -->
        <h2
          class="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary tracking-tight mb-4 sm:mb-6"
        >
          45 minutes to <span class="text-accent">a verdict.</span>
        </h2>

        <!-- Subtext -->
        <p
          class="text-base sm:text-lg text-text-muted mb-8 sm:mb-10 max-w-lg mx-auto"
        >
          Pick a niche. Get the full report with a go/no-go verdict. From $19.
        </p>

        <!-- Dual CTA buttons -->
        <div
          class="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 mb-8"
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
            {#if ctaTexts?.cta_final_primary?.visible !== false}
              <a
                href={ctaTexts?.cta_final_primary?.url ?? "/register"}
                class="btn-primary w-full sm:w-auto px-8 py-4 text-base"
              >
                {ctaTexts?.cta_final_primary?.text ?? "Start My Report"}
                <CtaIcon name={ctaTexts?.cta_final_primary?.icon} />
              </a>
            {/if}
            {#if hasSampleReport && ctaTexts?.cta_final_secondary?.visible !== false}
              <a
                href={ctaTexts?.cta_final_secondary?.url ?? "/sample-report"}
                class="btn-secondary w-full sm:w-auto px-6 py-4 text-base"
              >
                {ctaTexts?.cta_final_secondary?.text ?? "See a Sample Report"}
                <CtaIcon name={ctaTexts?.cta_final_secondary?.icon} />
              </a>
            {/if}
          {/if}
        </div>

        <!-- Guarantee badges -->
        <div
          class="flex flex-wrap justify-center gap-x-6 gap-y-2 mb-6 text-sm text-text-muted"
        >
          <span class="flex items-center gap-1.5" aria-hidden="true">
            <Check class="w-4 h-4 text-success flex-shrink-0" />
            Can't complete? Full credit refund.
          </span>
          <span class="flex items-center gap-1.5" aria-hidden="true">
            <Check class="w-4 h-4 text-success flex-shrink-0" />
            No subscription. Pay per report.
          </span>
          <span class="flex items-center gap-1.5" aria-hidden="true">
            <Check class="w-4 h-4 text-success flex-shrink-0" />
            Credits valid forever.
          </span>
        </div>

      </div>
    {/if}
  </div>
</section>
