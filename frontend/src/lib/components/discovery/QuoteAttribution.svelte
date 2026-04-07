<script lang="ts">
  import { ArrowUpRight } from "lucide-svelte";

  interface Props {
    upvotes?: number;
    subreddit?: string;
    sourceUrl?: string;
  }

  let { upvotes, subreddit, sourceUrl }: Props = $props();

  // Validate post URL (alphanumeric post IDs only)
  const safeUrl = $derived(
    sourceUrl && /^https:\/\/(www\.)?reddit\.com\//.test(sourceUrl) ? sourceUrl : null
  );
</script>

<span class="attribution">
  {#if upvotes && upvotes > 0}
    <span class="upvotes">&#9650; {upvotes.toLocaleString()}</span>
  {/if}
  {#if subreddit}
    <span class="subreddit">r/{subreddit}</span>
  {/if}
  {#if safeUrl}
    <a href={safeUrl} target="_blank" rel="noopener noreferrer" class="source-link">
      View source <ArrowUpRight size={10} />
    </a>
  {/if}
</span>

<style>
  .attribution {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    margin-top: var(--space-1);
    font-variant-numeric: tabular-nums;
  }

  .upvotes {
    color: var(--color-accent);
    font-weight: 600;
    letter-spacing: -0.01em;
  }

  .subreddit {
    color: var(--color-text-muted);
  }

  .source-link {
    color: var(--color-text-muted);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.125rem;
    transition: color var(--duration-fast) ease;
  }

  .source-link:hover {
    color: var(--color-accent);
  }

  .source-link:active {
    transform: scale(0.98);
  }
</style>
