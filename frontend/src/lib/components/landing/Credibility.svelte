<script lang="ts">
  import { onMount } from "svelte";
  import { Shield, Database, Link, Cpu, ExternalLink } from "lucide-svelte";

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

    const section = document.getElementById("credibility");
    if (section) observer.observe(section);

    return () => observer.disconnect();
  });

  const trustElements = [
    {
      icon: Shield,
      title: "80% Real Data. Zero Made-Up Numbers.",
      description:
        "80% of the report is programmatic data assembly. Only 20% uses LLM synthesis.",
      metric: "<1%",
      metricLabel: "Hallucination Rate",
    },
    {
      icon: Database,
      title: "Live Data Integration",
      description:
        "Real keyword data from search APIs. Direct social media access. Verified sources you can click and verify.",
      metric: "3",
      metricLabel: "Live Data Sources",
    },
    {
      icon: Link,
      title: "Source Attribution",
      description:
        "Every pain point links to a specific Reddit post. Click through, read the discussion, verify it yourself.",
      metric: "100%",
      metricLabel: "Claims Traceable",
    },
  ];

  const sampleEvidence = [
    {
      subreddit: "r/marketing",
      title: "How do you repurpose blog content efficiently?",
      upvotes: 143,
      comments: 47,
      date: "Mar 15, 2024",
      relevance: 0.89,
    },
    {
      subreddit: "r/SaaS",
      title: "Tools for automating content across platforms?",
      upvotes: 89,
      comments: 34,
      date: "Mar 12, 2024",
      relevance: 0.82,
    },
  ];
</script>

<section id="credibility" class="section-alt">
  <div class="max-w-6xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Section Header -->
      <div class="mb-16">
        <span class="section-label animate-fade-in">Verified Research</span>
        <h2
          class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6"
        >
          Every Claim. Verified. <span class="text-gradient italic"
            >Clickable.</span
          >
        </h2>
        <div
          class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full animate-fade-in delay-200"
        ></div>
        <p
          class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl"
        >
          Every claim links to its source. Click through, verify it yourself,
          then decide whether to build.
        </p>
      </div>

      <!-- Trust Elements Grid -->
      <div
        class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-3 gap-8 mb-16"
      >
        {#each trustElements as element, i}
          <div class="text-center">
            <div
              class="inline-flex items-center justify-center w-14 h-14 rounded-lg bg-success/10 border border-success/50 mb-6"
            >
              <element.icon class="w-7 h-7 text-success" />
            </div>

            <h3
              class="font-display font-semibold text-xl text-text-primary mb-3"
            >
              {element.title}
            </h3>

            <p class="text-text-secondary mb-6 leading-relaxed">
              {element.description}
            </p>

            <div class="divider max-w-[80px] mx-auto mb-4"></div>

            <div class="text-3xl font-display font-bold text-success mb-1">
              {element.metric}
            </div>
            <div class="small-caps">{element.metricLabel}</div>
          </div>
        {/each}
      </div>

      <!-- Evidence Preview -->
      <div class="animate-fade-in delay-400">
        <h3
          class="font-display font-semibold text-xl text-text-primary mb-6 text-center"
        >
          Sample Evidence Appendix
        </h3>

        <div class="max-w-3xl mx-auto space-y-4">
          {#each sampleEvidence as evidence}
            <div
              class="group cursor-pointer p-5 bg-bg-elevated border border-border rounded-xl hover:border-border-accent transition-all"
            >
              <div class="flex items-center gap-4">
                <!-- Reddit Logo -->
                <div
                  class="flex-shrink-0 w-12 h-12 rounded-lg bg-bg-surface border border-border flex items-center justify-center"
                >
                  <svg
                    class="w-6 h-6 text-[#FF4500]"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path
                      d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"
                    />
                  </svg>
                </div>

                <!-- Content -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="text-xs font-semibold text-[#FF4500]"
                      >{evidence.subreddit}</span
                    >
                    <span class="text-xs text-text-muted">-</span>
                    <span class="text-xs text-text-muted">{evidence.date}</span>
                  </div>
                  <h4
                    class="font-medium text-text-primary truncate group-hover:text-accent transition-colors"
                  >
                    {evidence.title}
                  </h4>
                  <div
                    class="flex items-center gap-4 mt-2 text-xs text-text-muted"
                  >
                    <span>{evidence.upvotes} upvotes</span>
                    <span>{evidence.comments} comments</span>
                    <span class="text-success"
                      >Relevance: {evidence.relevance}</span
                    >
                  </div>
                </div>

                <!-- Link Icon -->
                <ExternalLink
                  class="flex-shrink-0 w-5 h-5 text-text-muted group-hover:text-accent transition-colors"
                />
              </div>
            </div>
          {/each}
        </div>

        <p class="text-center text-sm text-text-muted mt-6 italic">
          Click any source to verify on Reddit. Full appendix included in every
          report.
        </p>
      </div>

      <!-- Hybrid Architecture Callout -->
      <div class="animate-fade-in delay-500 mt-16">
        <div
          class="max-w-3xl mx-auto p-8 bg-bg-surface border border-border-accent rounded-xl"
        >
          <div class="flex flex-col sm:flex-row items-center gap-6">
            <div
              class="flex-shrink-0 w-16 h-16 rounded-xl bg-accent/10 border border-border-accent flex items-center justify-center"
            >
              <Cpu class="w-8 h-8 text-accent" />
            </div>

            <div class="text-center sm:text-left">
              <h3
                class="font-display font-semibold text-xl text-text-primary mb-2"
              >
                Hybrid Architecture
              </h3>
              <p class="text-text-secondary leading-relaxed">
                <span class="text-accent font-semibold"
                  >80% automated verification</span
                >
                (zero hallucination) +
                <span class="text-accent-light font-semibold">20% AI</span> strategic
                synthesis. The data comes from real sources, not AI imagination.
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Benefit Trust Badges -->
      <div class="animate-fade-in delay-600 mt-12">
        <div
          class="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8"
        >
          <span class="small-caps text-text-muted">What you get</span>
          <div class="flex flex-wrap items-center justify-center gap-3">
            <span class="badge">
              <Shield class="w-4 h-4" />
              Verified Data
            </span>
            <span class="badge">
              <Database class="w-4 h-4" />
              Real Keywords
            </span>
            <span class="badge">
              <Link class="w-4 h-4" />
              Source Links
            </span>
            <span class="badge">
              <svg
                class="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              No Guessing
            </span>
          </div>
        </div>
      </div>
    {/if}
  </div>
</section>
