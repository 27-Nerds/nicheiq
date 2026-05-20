<script lang="ts">
  import type { Job, ReportSummary } from "$lib/types/job";
  import { mapVerdict } from "$lib/types/publicCatalog";
  import { summaryToScores } from "$lib/utils/solution-utils";
  import { titleCase } from "$lib/utils/format";
  import CatalogTable from "$lib/components/catalog/seo/CatalogTable.svelte";
  import Trifecta from "$lib/components/catalog/seo/Trifecta.svelte";
  import VerdictBadge from "$lib/components/catalog/seo/VerdictBadge.svelte";
  import ArrowRight from "lucide-svelte/icons/arrow-right";
  import MoreVertical from "lucide-svelte/icons/more-vertical";
  import Download from "lucide-svelte/icons/download";

  // Completed-jobs editorial table — the catalog IdeasListTable grammar applied
  // to the dashboard's completed history. Rows are NOT full <a> tags (the kebab
  // contains <a download> links → nested-anchor invalidity); instead each row is
  // a <div> with an absolute stretched-link overlay and the kebab layered above.

  interface Props {
    jobs: Job[];
    summaries: Record<string, ReportSummary>;
  }

  let { jobs, summaries }: Props = $props();

  // Show the verdict column only when at least one visible row has a real verdict.
  const hasAnyVerdict = $derived(
    jobs.some((j) => mapVerdict(summaries[j.id]?.verdict) != null),
  );

  // Self-contained overflow-menu state (download exports). Scoped to the table
  // so it doesn't entangle with the dashboard's search keyboard handler.
  let openMenuId = $state<string | null>(null);
  function toggleMenu(jobId: string, e: MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    openMenuId = openMenuId === jobId ? null : jobId;
  }

  function rowTitle(job: Job): string {
    return summaries[job.id]?.solution_name ?? titleCase(job.niche);
  }

  function formatRelativeDate(dateStr: string): string {
    const date = new Date(dateStr);
    const diffMs = Date.now() - date.getTime();
    const mins = Math.floor(diffMs / 60000);
    const hrs = Math.floor(diffMs / 3600000);
    const days = Math.floor(diffMs / 86400000);
    if (mins < 1) return "now";
    if (mins < 60) return `${mins}m`;
    if (hrs < 24) return `${hrs}h`;
    if (days === 1) return "1d";
    if (days < 7) return `${days}d`;
    if (days < 30) return `${Math.floor(days / 7)}w`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
</script>

<svelte:window
  onclick={(e) => {
    if (openMenuId && !(e.target as HTMLElement).closest("[data-menu-container]")) {
      openMenuId = null;
    }
  }}
/>

<CatalogTable>
  <div class="ct-head" class:with-verdict={hasAnyVerdict}>
    <span class="head-rank">#</span>
    <span>Idea</span>
    <span class="col-prompt">From prompt</span>
    <span class="col-scores">D / F / O</span>
    {#if hasAnyVerdict}<span class="col-verdict">Verdict</span>{/if}
    <span class="col-date">Done</span>
    <span aria-hidden="true"></span>
  </div>

  {#each jobs as job, i (job.id)}
    {@const scores = summaryToScores(summaries[job.id])}
    {@const tagline = summaries[job.id]?.solution_tagline}
    <div class="ct-row" class:with-verdict={hasAnyVerdict}>
      <a
        class="row-link"
        href="/jobs/{job.id}/report"
        aria-label="View report for {rowTitle(job)}"
      ></a>

      <span class="cell-rank">{String(i + 1).padStart(2, "0")}</span>

      <div class="cell-idea">
        <h4 class="idea-title">{rowTitle(job)}</h4>
        {#if tagline}<p class="idea-tagline">{tagline}</p>{/if}
      </div>

      <span class="cell-prompt col-prompt">{job.niche}</span>

      <span class="cell-scores col-scores">
        {#if scores}<Trifecta {scores} size="md" />{/if}
      </span>

      {#if hasAnyVerdict}
        <span class="cell-verdict col-verdict">
          {#if mapVerdict(summaries[job.id]?.verdict) != null}
            <VerdictBadge verdict={summaries[job.id]?.verdict} />
          {:else}
            <span class="verdict-empty">—</span>
          {/if}
        </span>
      {/if}

      <span class="cell-date col-date">{formatRelativeDate(job.completedAt || job.createdAt)}</span>

      <div class="cell-actions" data-menu-container>
        <button
          class="kebab"
          onclick={(e) => toggleMenu(job.id, e)}
          aria-label="Downloads"
          aria-haspopup="menu"
          aria-expanded={openMenuId === job.id}
        >
          <MoreVertical size={16} />
        </button>
        {#if openMenuId === job.id}
          <div class="menu" role="menu">
            <a href="/api/jobs/{job.id}/reportjson" download role="menuitem">
              <Download size={14} /> Export JSON
            </a>
            {#if job.hasLandingPage}
              <a
                href="/api/jobs/{job.id}/landingpage?download=true"
                download
                role="menuitem"
              >
                <Download size={14} /> Export HTML
              </a>
            {/if}
          </div>
        {/if}
        <span class="arrow" aria-hidden="true"><ArrowRight size={14} /></span>
      </div>
    </div>
  {/each}
</CatalogTable>

<style>
  .ct-head,
  .ct-row {
    grid-template-columns: 44px minmax(0, 1fr) 200px auto 88px 64px;
    gap: 16px;
  }
  .ct-head.with-verdict,
  .ct-row.with-verdict {
    grid-template-columns: 44px minmax(0, 1fr) 200px auto 100px 88px 64px;
  }

  .row-link {
    position: absolute;
    inset: 0;
    z-index: 0;
  }

  .head-rank,
  .cell-rank {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 600;
    align-self: start;
    padding-top: 2px;
  }

  .cell-idea {
    min-width: 0;
  }
  .idea-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.005em;
    line-height: 1.35;
    margin: 0 0 3px;
  }
  .idea-tagline,
  .cell-prompt {
    font-size: 12.5px;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .verdict-empty {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-muted);
  }

  .cell-date {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  /* Interactive cell sits above the stretched link overlay. */
  .cell-actions {
    position: relative;
    z-index: 10;
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 6px;
  }
  .kebab {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    color: var(--color-text-muted);
    opacity: 0;
    transition:
      opacity 0.12s,
      background 0.12s,
      color 0.12s;
    cursor: pointer;
  }
  /* Keyboard-reachable: reveal on row hover OR focus-within. */
  .ct-row:hover .kebab,
  .ct-row:focus-within .kebab {
    opacity: 1;
  }
  .kebab:hover {
    background: var(--color-bg-hover);
    color: var(--color-text-primary);
  }
  .menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    min-width: 160px;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow:
      0 1px 2px rgba(24, 24, 27, 0.04),
      0 4px 12px rgba(24, 24, 27, 0.06);
    padding: 4px;
    z-index: 50;
  }
  .menu a {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 10px;
    border-radius: 6px;
    font-size: 13px;
    color: var(--color-text-secondary);
    text-decoration: none;
  }
  .menu a:hover {
    background: var(--color-bg-hover);
    color: var(--color-text-primary);
  }
  .arrow {
    color: var(--color-text-muted);
    display: inline-flex;
    align-items: center;
    transition:
      transform 0.15s,
      color 0.15s;
  }
  .ct-row:hover .arrow {
    color: var(--color-text-primary);
    transform: translateX(2px);
  }

  @media (max-width: 900px) {
    .ct-head,
    .ct-row,
    .ct-head.with-verdict,
    .ct-row.with-verdict {
      grid-template-columns: 36px minmax(0, 1fr) 64px;
      gap: 10px;
    }
    .col-prompt,
    .col-scores,
    .col-verdict,
    .col-date {
      display: none;
    }
    .kebab {
      opacity: 1;
    }
  }
</style>
