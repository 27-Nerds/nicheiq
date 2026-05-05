<script lang="ts">
  import { ArrowUpRight } from "lucide-svelte";
  import type { HeroQuote } from "$lib/types/discovery";

  interface Props {
    quote: HeroQuote;
  }

  let { quote }: Props = $props();

  const safeUrl = $derived(
    quote.source_url && /^https:\/\/(www\.)?(reddit\.com|news\.ycombinator\.com|youtube\.com)\//.test(quote.source_url) ? quote.source_url : null
  );
</script>

<section class="billboard">
  <!-- Source attribution header -->
  <div class="billboard-attr">
    {#if quote.subreddit}
      <span class="billboard-sub">{quote.subreddit}</span>
      <span class="billboard-sep">&middot;</span>
    {/if}
    <span class="billboard-upvote">&#9650; {quote.upvotes.toLocaleString()}</span>
    {#if safeUrl}
      <span class="billboard-sep">&middot;</span>
      <a href={safeUrl} target="_blank" rel="noopener noreferrer" class="billboard-link">
        View source <ArrowUpRight size={11} />
      </a>
    {/if}
  </div>

  <hr class="billboard-divider" />

  <!-- Quote text -->
  <p class="billboard-quote">{quote.text}</p>

  <!-- Context: which pain point this came from -->
  <span class="billboard-context">{quote.pain_point_title}</span>
</section>

<style>
  .billboard {
    background: radial-gradient(circle at 15% 30%, rgba(234, 88, 12, 0.06) 0%, transparent 50%);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-8) var(--space-6);
    margin: var(--space-4) 0;
  }

  .billboard-attr {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  .billboard-sub {
    font-weight: 500;
    color: var(--color-text-secondary);
  }

  .billboard-upvote {
    color: var(--color-accent);
    font-weight: 700;
  }

  .billboard-sep {
    opacity: 0.4;
  }

  .billboard-link {
    color: var(--color-text-muted);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.125rem;
    font-size: var(--text-xs);
    transition: color var(--duration-fast) ease;
  }

  .billboard-link:hover {
    color: var(--color-accent);
  }

  .billboard-link:active {
    transform: scale(0.98);
  }

  .billboard-divider {
    border: none;
    height: 1px;
    background: var(--color-border);
    margin: var(--space-3) 0 var(--space-4);
  }

  .billboard-quote {
    font-size: var(--text-xl);
    line-height: var(--leading-relaxed);
    color: var(--color-text-primary);
    margin: 0 0 var(--space-3);
    /* Roman type — real quotes feel more real without italic */
  }

  .billboard-context {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
  }
</style>
