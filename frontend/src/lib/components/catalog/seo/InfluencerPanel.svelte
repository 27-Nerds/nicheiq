<script lang="ts">
  import Chip from "./Chip.svelte";

  // Renders audience_mapping.key_influencers when ≥ minCount are present.
  // Pydantic shape (research_state.py:1017-1030):
  //   { name, platform, follower_estimate?, relevance_score, content_focus,
  //     engagement_level, outreach_priority, top_subreddits[], top_posts[] }
  // Loose-typed at the boundary because researchContext.audienceMapping is
  // `Json?` — defensively narrow per-field.

  interface Props {
    audienceMapping: unknown;
    /** Minimum count to render — sparse-data guard. Default 3 per plan. */
    minCount?: number;
  }

  let { audienceMapping, minCount = 3 }: Props = $props();

  interface Influencer {
    name: string;
    platform: string;
    followerEstimate: string | null;
    contentFocus: string;
    outreachPriority: string | null;
  }

  function pickStr(o: Record<string, unknown>, k: string): string | null {
    const v = o[k];
    return typeof v === "string" && v.trim() !== "" ? v.trim() : null;
  }

  const influencers = $derived.by<Influencer[]>(() => {
    if (!audienceMapping || typeof audienceMapping !== "object") return [];
    const am = audienceMapping as Record<string, unknown>;
    const raw = am.key_influencers;
    if (!Array.isArray(raw)) return [];
    const out: Influencer[] = [];
    for (const r of raw) {
      if (!r || typeof r !== "object") continue;
      const o = r as Record<string, unknown>;
      const name = pickStr(o, "name");
      const platform = pickStr(o, "platform");
      const contentFocus = pickStr(o, "content_focus") ?? pickStr(o, "contentFocus");
      if (!name || !platform || !contentFocus) continue;
      out.push({
        name,
        platform,
        followerEstimate: pickStr(o, "follower_estimate") ?? pickStr(o, "followerEstimate"),
        contentFocus,
        outreachPriority: pickStr(o, "outreach_priority") ?? pickStr(o, "outreachPriority"),
      });
    }
    return out;
  });

  const show = $derived(influencers.length >= minCount);
</script>

{#if show}
  <ul class="grid">
    {#each influencers as inf}
      <li class="card">
        <header>
          <span class="name">{inf.name}</span>
          <Chip label={inf.platform} mono />
        </header>
        <p class="focus">{inf.contentFocus}</p>
        <footer>
          {#if inf.followerEstimate}
            <span class="meta">{inf.followerEstimate} reach</span>
          {/if}
          {#if inf.outreachPriority}
            <span class="meta priority-{inf.outreachPriority.toLowerCase()}">{inf.outreachPriority} priority</span>
          {/if}
        </footer>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  @media (max-width: 768px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
  .card {
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-surface, #fff);
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }
  .name {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.005em;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .focus {
    margin: 0;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--color-text-secondary, var(--color-text-primary));
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  footer {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding-top: 6px;
    border-top: 1px dashed var(--color-border);
  }
  .meta {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .priority-high {
    color: var(--color-accent);
  }
</style>
