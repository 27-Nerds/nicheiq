<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import { scrollVisible } from "$lib/actions/scrollVisible";
  import type { DiscoveryMethodology } from "$lib/types/discovery";

  interface Props {
    methodology: DiscoveryMethodology;
    subredditNames: string[];
    totalInteractions?: number;
    totalPosts?: number;
    sourcesSearched?: Record<string, { enabled: boolean; posts_found: number }>;
  }

  let { methodology, subredditNames, totalInteractions, totalPosts, sourcesSearched }: Props = $props();

  const PLATFORM_LABELS: Record<string, string> = {
    reddit: "Reddit",
    hackernews: "Hacker News",
    twitter: "Twitter",
    youtube: "YouTube",
  };

  const tierVariant = $derived.by((): "success" | "accent" | "warning" | "muted" => {
    const tier = methodology.quality_tier?.toUpperCase();
    if (tier === "EXCELLENT" || tier === "GOLD") return "success";
    if (tier === "GOOD" || tier === "SILVER") return "accent";
    if (tier === "BRONZE") return "warning";
    return "muted";
  });
</script>

<section class="methodology">
  <div class="section-header-meta">
    <div class="section-header-bar"></div>
    <span class="methodology-label">Research Methodology</span>
  </div>

  <p class="methodology-sentence">
    Analyzed
    <strong class="methodology-num">{(totalPosts ?? 0).toLocaleString()}</strong>
    posts with
    <strong class="methodology-num">{(totalInteractions ?? 0).toLocaleString()}</strong>
    engagement across
    <strong class="methodology-num">{methodology.urls_searched.toLocaleString()}</strong>
    sources
  </p>

  <p class="methodology-pass">
    {methodology.urls_searched.toLocaleString()} checked &rarr; {methodology.urls_relevant.toLocaleString()} relevant
    (<span class="methodology-pct">{methodology.filtering_rate}%</span> pass rate)
  </p>

  <div class="tier-bar" use:scrollVisible>
    <span class="tier-bar-label">Pass rate</span>
    <div class="tier-bar-track">
      <div
        class="tier-bar-fill tier-bar-success"
        style="--fill-pct: {methodology.filtering_rate / 100}"
      ></div>
    </div>
    <span class="tier-bar-count">{methodology.filtering_rate}%</span>
  </div>

  <div class="methodology-sources">
    <div class="methodology-subs">
      {#each subredditNames.slice(0, 5) as sub}
        <Badge variant="muted" size="sm">{sub}</Badge>
      {/each}
    </div>
    <Badge variant={tierVariant} size="sm">{methodology.quality_tier}</Badge>
  </div>

  {#if sourcesSearched}
    <div class="methodology-coverage">
      {#each Object.entries(sourcesSearched) as [platform, info]}
        <span
          class="coverage-item"
          class:found={info.posts_found > 0}
          class:gap={info.enabled && info.posts_found === 0}
          class:skipped={!info.enabled}
        >
          {PLATFORM_LABELS[platform] ?? platform}
          {#if !info.enabled}
            <span class="coverage-count">&mdash;</span>
          {:else if info.posts_found > 0}
            <span class="coverage-count">{info.posts_found}</span>
          {:else}
            <span class="coverage-count coverage-zero">0</span>
          {/if}
        </span>
      {/each}
    </div>
  {/if}
</section>

<style>
  .methodology {
    padding: var(--space-5) 0;
  }

  .methodology-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  .methodology-sentence {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin: var(--space-3) 0 var(--space-2);
  }

  .methodology-num {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: var(--text-xl);
    color: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .methodology-pass {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    margin: 0 0 var(--space-3);
    font-variant-numeric: tabular-nums;
  }

  .methodology-pct {
    color: var(--color-accent);
    font-weight: 600;
  }

  /* Override tier-bar fill to use custom property */
  .methodology :global(.tier-bar-fill) {
    transform: scaleX(0);
  }
  .methodology :global(.tier-bar.visible .tier-bar-fill) {
    transform: scaleX(var(--fill-pct));
  }

  .methodology-sources {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }

  .methodology-subs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .methodology-coverage {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-top: var(--space-3);
  }

  .coverage-item {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    letter-spacing: var(--tracking-wider);
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .coverage-item.found { color: var(--color-text-secondary); }
  .coverage-item.skipped { opacity: var(--opacity-disabled); }

  .coverage-count {
    font-weight: var(--font-bold);
    font-variant-numeric: tabular-nums;
    color: var(--color-text-primary);
    margin-left: var(--space-1);
  }

  .coverage-item.gap .coverage-count { color: var(--color-accent); }
  .coverage-zero { font-weight: var(--font-semibold); }
</style>
