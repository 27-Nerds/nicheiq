<script lang="ts">
  import { intersect } from "$lib/actions/intersect";
  import { Star, Quote } from "lucide-svelte";

  let { reportsDelivered = null }: { reportsDelivered?: number | null } =
    $props();

  let isVisible = $state(false);

  const testimonials = [
    {
      name: "S.K.",
      role: "Bootstrapped Founder",
      avatar: "SK",
      quote:
        "Saved me 3 weeks of manual research. Found a pain point I never would have discovered on my own—now it's my main feature.",
      rating: 5,
    },
    {
      name: "M.T.",
      role: "Solo SaaS",
      avatar: "MT",
      quote:
        "I'd wasted $500 on other tools that gave me garbage. NicheIQ gave me 23 verified pain points with actual Reddit links. Launched in 2 weeks.",
      rating: 5,
    },
    {
      name: "E.R.",
      role: "Side Project Builder",
      avatar: "ER",
      quote:
        "Killed 2 ideas before I built anything. The third one? $2k MRR in month 2. The SEO keywords alone paid for the report.",
      rating: 5,
    },
  ];

  const stats = $derived([
    { value: reportsDelivered?.toString() || "47", label: "Reports delivered" },
    { value: "800+", label: "Pain points discovered" },
    { value: "89%", label: "Satisfaction rate" },
    { value: "45 min", label: "Average delivery" },
  ]);
</script>

<section
  id="social-proof"
  class="py-12 sm:py-16 bg-bg-elevated border-y border-border"
  use:intersect={{ threshold: 0.1, onIntersect: () => isVisible = true }}
>
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Stats Bar - Mobile optimized -->
      <div
        class="animate-fade-in grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6 mb-10 sm:mb-16"
      >
        {#each stats as stat, i}
          <div class="text-center" style="animation-delay: {i * 100}ms">
            <div
              class="text-2xl sm:text-3xl font-display font-bold text-accent mb-1"
            >
              {stat.value}
            </div>
            <div class="text-xs sm:text-sm text-text-muted">{stat.label}</div>
          </div>
        {/each}
      </div>

      <!-- Section Header - Mobile optimized -->
      <div class="animate-fade-in delay-200 text-center mb-8 sm:mb-12">
        <h2
          class="font-display text-xl sm:text-2xl font-semibold text-text-primary mb-2"
        >
          Join Founders Who Ship
        </h2>
        <p class="text-text-muted text-sm sm:text-base">
          You're not alone in researching smarter
        </p>
      </div>

      <!-- Testimonials Grid - Mobile optimized -->
      <div
        class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6"
      >
        {#each testimonials as testimonial, i}
          <div
            class="relative p-5 sm:p-6 bg-bg-elevated border border-border rounded-xl hover:border-border-accent hover:shadow-md transition-all group"
            style="animation-delay: {300 + i * 100}ms"
          >
            <!-- Quote Icon -->
            <Quote
              class="absolute top-3 sm:top-4 right-3 sm:right-4 w-6 sm:w-8 h-6 sm:h-8 text-accent/15 group-hover:text-accent/25 transition-colors"
            />

            <!-- Rating -->
            <div class="flex gap-0.5 sm:gap-1 mb-3 sm:mb-4">
              {#each Array(testimonial.rating) as _, j}
                <Star
                  class="w-3.5 sm:w-4 h-3.5 sm:h-4 fill-warning text-warning"
                />
              {/each}
            </div>

            <!-- Quote -->
            <p
              class="text-text-secondary leading-relaxed mb-4 sm:mb-6 text-xs sm:text-sm italic"
            >
              "{testimonial.quote}"
            </p>

            <!-- Author -->
            <div
              class="flex items-center gap-2.5 sm:gap-3 pt-4 border-t border-border"
            >
              <div
                class="w-9 sm:w-10 h-9 sm:h-10 rounded-full bg-gradient-to-br from-accent to-accent-dark flex items-center justify-center shadow-sm"
              >
                <span class="text-white font-bold text-xs sm:text-sm"
                  >{testimonial.avatar}</span
                >
              </div>
              <div>
                <div class="font-semibold text-text-primary text-xs sm:text-sm">
                  {testimonial.name}
                </div>
                <div class="text-[10px] sm:text-xs text-text-muted">
                  {testimonial.role}
                </div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</section>
