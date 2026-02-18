<script lang="ts">
  import { onMount } from "svelte";
  import {
    MessageSquare,
    MessagesSquare,
    MousePointerClick,
    Eye,
    Quote,
    AlertTriangle,
    Cpu,
  } from "lucide-svelte";

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

    const section = document.getElementById("credibility");
    if (section) observer.observe(section);

    return () => observer.disconnect();
  });

  const sourcePills = [
    { icon: MessageSquare, label: "Real User Problems" },
    { icon: MessagesSquare, label: "Community Voices" },
    { icon: MousePointerClick, label: "Market Intent" },
    { icon: Eye, label: "Competitive Landscape" },
  ];

  const threadCards = [
    {
      community: "r/SaaS",
      title: "Why is content repurposing still so manual in 2025?",
      score: 143,
      num_comments: 47,
      key_insight:
        "Users report spending 3-5 hours weekly reformatting blog posts for social media.",
    },
    {
      community: "r/marketing",
      title: "Tools for automating content across platforms?",
      score: 89,
      num_comments: 34,
      key_insight:
        "Teams struggle to maintain consistent messaging when manually adapting content per channel.",
    },
  ];

  const quoteCard = {
    pain_point_title: "Manual Content Repurposing",
    quote:
      "I spend half my Monday just copying and pasting blog excerpts into different formats for each channel.",
    community: "r/SaaS",
    engagement: "143 upvotes",
  };
</script>

<section id="credibility" class="section-alt">
  <div class="max-w-4xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Header -->
      <div class="mb-12">
        <span class="section-label animate-fade-in">Source-Backed Research</span
        >
        <h2
          class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6"
        >
          Every Claim Links to <span class="text-gradient italic"
            >Its Source.</span
          >
        </h2>
        <div
          class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full animate-fade-in delay-200"
        ></div>
        <p
          class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl"
        >
          Every pain point, every keyword, every competitor — traced to a source
          you can check yourself before you commit.
        </p>
      </div>

      <!-- Source Bar -->
      <div class="animate-fade-in delay-300 mb-12">
        <div class="flex flex-wrap justify-center gap-3">
          {#each sourcePills as pill}
            <span
              class="inline-flex items-center gap-1.5 px-3 py-1.5 font-mono text-sm bg-accent/5 border border-accent/20 rounded-lg text-text-secondary"
            >
              <pill.icon class="w-4 h-4 text-accent" />
              {pill.label}
            </span>
          {/each}
        </div>
        <p class="text-sm text-text-muted text-center mt-4">
          Sourced from forums, social platforms, search data, and web results —
          all verifiable.
        </p>
      </div>

      <!-- Evidence Preview -->
      <div class="max-w-3xl mx-auto space-y-3 mb-6">
        {#each threadCards as thread, i}
          <div
            class="p-5 bg-bg-elevated border border-border border-l-4 border-l-success rounded-r-xl"
            style="animation: fadeIn 0.5s ease-out both; animation-delay: {400 +
              i * 100}ms"
          >
            <div class="flex items-center gap-4">
              <div
                class="flex-shrink-0 w-10 h-10 rounded-lg bg-success/10 border border-success/30 flex items-center justify-center"
              >
                <MessageSquare class="w-5 h-5 text-success" />
              </div>
              <div class="flex-1 min-w-0">
                <span class="text-xs font-semibold text-success"
                  >{thread.community}</span
                >
                <h4 class="font-medium text-text-primary truncate">
                  {thread.title}
                </h4>
                <p class="text-xs text-text-muted italic mt-1 truncate-1">
                  {thread.key_insight}
                </p>
                <div
                  class="flex items-center gap-4 mt-2 text-xs text-text-muted"
                >
                  <span>{thread.score} upvotes</span>
                  <span>{thread.num_comments} comments</span>
                </div>
              </div>
            </div>
          </div>
        {/each}

        <!-- Quote Card -->
        <div
          class="p-4 bg-bg-surface border-l-4 border-l-success rounded-r-xl mt-3"
          style="animation: fadeIn 0.5s ease-out both; animation-delay: 550ms"
        >
          <div class="flex items-start gap-3">
            <Quote class="w-4 h-4 text-success flex-shrink-0 mt-1" />
            <div>
              <p class="text-sm text-text-secondary italic leading-relaxed">
                "{quoteCard.quote}"
              </p>
              <div class="flex items-center gap-3 mt-2 text-xs text-text-muted">
                <span class="font-semibold text-text-primary"
                  >{quoteCard.pain_point_title}</span
                >
                <span>{quoteCard.community}</span>
                <span>{quoteCard.engagement}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Caption -->
      <p
        class="text-center text-sm text-text-muted italic mb-14"
        style="animation: fadeIn 0.5s ease-out both; animation-delay: 550ms"
      >
        In your report, every source links to the original discussion thread.
        Full evidence appendix included.
      </p>

      <!-- Dual Callout -->
      <div
        class="grid grid-cols-1 md:grid-cols-2 gap-6"
        style="animation: fadeIn 0.5s ease-out both; animation-delay: 650ms"
      >
        <!-- Part A: Everything Traces Back to Data -->
        <div class="bg-bg-surface border border-border-accent rounded-xl p-6">
          <div
            class="w-12 h-12 rounded-xl bg-accent/10 border border-accent/30 flex items-center justify-center mb-4"
          >
            <Cpu class="w-6 h-6 text-accent" />
          </div>
          <h3
            class="font-display font-semibold text-lg text-text-primary mb-2"
          >
            Everything Traces Back to Data.
          </h3>
          <p class="text-sm text-text-secondary leading-relaxed">
            Keyword volumes, market sizing, competitor profiles, and the full
            evidence appendix are pulled from real sources. AI is only used for
            synthesis — finding patterns across discussions, shaping strategy,
            and calibrating scores.
          </p>
        </div>

        <!-- Part B: Built for Founder Trust -->
        <div class="bg-bg-surface border border-border rounded-xl p-6">
          <div
            class="w-12 h-12 rounded-xl bg-warning/10 border border-warning/30 flex items-center justify-center mb-4"
          >
            <AlertTriangle class="w-6 h-6 text-warning" />
          </div>
          <h3
            class="font-display font-semibold text-lg text-text-primary mb-2"
          >
            Built for Founder Trust
          </h3>
          <p class="text-sm text-text-secondary leading-relaxed mb-4">
            Every report includes a data quality assessment so you know exactly
            how strong the evidence is — and where the gaps are.
          </p>
          <div class="flex flex-wrap gap-2">
            <span class="badge badge-success">Quality: HIGH</span>
            <span class="badge">Confidence: 82%</span>
            <span class="badge badge-muted">3 caveats disclosed</span>
          </div>
        </div>
      </div>
    {/if}
  </div>
</section>
