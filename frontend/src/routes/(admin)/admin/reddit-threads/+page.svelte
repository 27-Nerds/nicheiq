<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import {
    MessageSquare,
    Search,
    Database,
    Globe,
    ArrowUpDown,
    ChevronDown,
    ChevronRight,
    ExternalLink,
    Clock,
    Trash2,
  } from "lucide-svelte";
  import { SvelteSet } from "svelte/reactivity";

  let { data } = $props();

  const stats = $derived(data.stats);
  const threads = $derived(data.threadsData?.threads ?? []);
  const total = $derived(data.threadsData?.total ?? 0);
  const totalPages = $derived(data.threadsData?.totalPages ?? 0);
  const filters = $derived(data.filters);

  let searchInput = $state("");
  let expandedRows = new SvelteSet<string>();
  let isCleaningUp = $state(false);

  $effect(() => {
    searchInput = filters.q;
  });

  function updateFilters(overrides: Record<string, string | number>) {
    const params = new URLSearchParams();
    const merged = { ...filters, ...overrides, page: overrides.page ?? 1 };
    if (merged.q) params.set("q", String(merged.q));
    if (merged.subreddit) params.set("subreddit", String(merged.subreddit));
    params.set("sortBy", String(merged.sortBy));
    params.set("sortDir", String(merged.sortDir));
    params.set("page", String(merged.page));
    goto(`?${params.toString()}`, { keepFocus: true });
  }

  function handleSearch(e: SubmitEvent) {
    e.preventDefault();
    updateFilters({ q: searchInput });
  }

  function toggleSort(col: string) {
    if (filters.sortBy === col) {
      updateFilters({ sortBy: col, sortDir: filters.sortDir === "desc" ? "asc" : "desc" });
    } else {
      updateFilters({ sortBy: col, sortDir: "desc" });
    }
  }

  function toggleRow(id: string) {
    if (expandedRows.has(id)) {
      expandedRows.delete(id);
    } else {
      expandedRows.add(id);
    }
  }

  function filterBySubreddit(sub: string) {
    if (filters.subreddit === sub) {
      updateFilters({ subreddit: "" });
    } else {
      updateFilters({ subreddit: sub });
    }
  }

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  function timeAgo(dateStr: string) {
    const diff = Date.now() - new Date(dateStr).getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return `${Math.floor(days / 30)}mo ago`;
  }

  function sortIndicator(col: string) {
    if (filters.sortBy !== col) return "";
    return filters.sortDir === "desc" ? " ↓" : " ↑";
  }

  async function handleCleanup() {
    if (!confirm("Delete threads older than 60 days?")) return;
    isCleaningUp = true;
    try {
      const res = await fetch("/api/admin/catalog/reddit-threads?action=cleanup", { method: "DELETE" });
      if (res.ok) {
        const data = await res.json();
        alert(`Deleted ${data.deletedCount} old threads.`);
        goto(page.url.pathname + page.url.search, { invalidateAll: true });
      }
    } finally {
      isCleaningUp = false;
    }
  }
</script>

<svelte:head>
  <title>Reddit Threads | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h2 class="text-2xl font-bold text-text-primary">Reddit Threads</h2>
      <p class="text-sm text-text-muted mt-1">Cached Reddit posts used as research input.</p>
    </div>
    <button
      onclick={handleCleanup}
      disabled={isCleaningUp}
      class="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-border text-text-secondary hover:text-error hover:border-error/50 transition-colors disabled:opacity-50"
    >
      <Trash2 class="w-4 h-4" />
      Cleanup Old
    </button>
  </div>

  <!-- Stats -->
  {#if stats}
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-accent/10">
            <Database class="w-5 h-5 text-accent" />
          </div>
          <span class="text-sm text-text-muted">Threads</span>
        </div>
        <p class="text-3xl font-bold text-text-primary">
          {stats.totalThreads.toLocaleString()}
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-secondary/10">
            <Globe class="w-5 h-5 text-secondary" />
          </div>
          <span class="text-sm text-text-muted">Subreddits</span>
        </div>
        <p class="text-3xl font-bold text-text-primary">
          {stats.uniqueSubreddits.toLocaleString()}
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-success/10">
            <MessageSquare class="w-5 h-5 text-success" />
          </div>
          <span class="text-sm text-text-muted">Comments</span>
        </div>
        <p class="text-3xl font-bold text-text-primary">
          {stats.totalComments.toLocaleString()}
        </p>
      </div>

      <div class="bg-bg-surface border border-border rounded-xl p-5">
        <div class="flex items-center gap-3 mb-2">
          <div class="p-2 rounded-lg bg-warning/10">
            <Clock class="w-5 h-5 text-warning" />
          </div>
          <span class="text-sm text-text-muted">Last Fetch</span>
        </div>
        <p class="text-lg font-bold text-text-primary">
          {stats.latestFetch ? timeAgo(stats.latestFetch) : "Never"}
        </p>
      </div>
    </div>

    <!-- Subreddit pills -->
    {#if stats.bySubreddit?.length}
      <div class="mb-6">
        <h3 class="text-sm font-medium text-text-muted mb-2">By Subreddit</h3>
        <div class="flex flex-wrap gap-2">
          {#each stats.bySubreddit as sub}
            <button
              onclick={() => filterBySubreddit(sub.name)}
              class="px-3 py-1 text-sm rounded-full border transition-colors
                {filters.subreddit === sub.name
                  ? 'bg-accent/20 border-accent/50 text-accent'
                  : 'border-border text-text-secondary hover:border-accent/30 hover:text-text-primary'}"
            >
              r/{sub.name}
              <span class="ml-1 text-xs opacity-70">{sub.count}</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  <!-- Search & count -->
  <div class="flex items-center gap-4 mb-4">
    <form onsubmit={handleSearch} class="flex-1 max-w-md">
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          bind:value={searchInput}
          placeholder="Search title..."
          class="w-full pl-10 pr-4 py-2 bg-bg-surface border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50"
        />
      </div>
    </form>
    <span class="text-sm text-text-muted">{total} thread{total !== 1 ? "s" : ""}</span>
  </div>

  <!-- Table -->
  {#if threads.length === 0}
    <div class="bg-bg-surface border border-border rounded-xl p-12 text-center">
      <Database class="w-10 h-10 text-text-muted mx-auto mb-3" />
      {#if filters.q || filters.subreddit}
        <p class="text-text-secondary">No threads match your filters.</p>
        <button
          onclick={() => updateFilters({ q: "", subreddit: "" })}
          class="mt-2 text-sm text-accent hover:underline"
        >
          Clear filters
        </button>
      {:else}
        <p class="text-text-secondary">No cached threads yet.</p>
        <p class="text-sm text-text-muted mt-1">Threads are cached when research jobs fetch Reddit data.</p>
      {/if}
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-border text-left">
            <th class="px-4 py-3 text-text-muted font-medium w-8"></th>
            <th class="px-4 py-3 text-text-muted font-medium">Title</th>
            <th class="px-4 py-3 text-text-muted font-medium">Subreddit</th>
            <th class="px-4 py-3 text-text-muted font-medium">
              <button onclick={() => toggleSort("score")} class="flex items-center gap-1 hover:text-text-primary transition-colors">
                Score{sortIndicator("score")}
                <ArrowUpDown class="w-3 h-3" />
              </button>
            </th>
            <th class="px-4 py-3 text-text-muted font-medium">
              <button onclick={() => toggleSort("numComments")} class="flex items-center gap-1 hover:text-text-primary transition-colors">
                Comments{sortIndicator("numComments")}
                <ArrowUpDown class="w-3 h-3" />
              </button>
            </th>
            <th class="px-4 py-3 text-text-muted font-medium">
              <button onclick={() => toggleSort("redditCreatedAt")} class="flex items-center gap-1 hover:text-text-primary transition-colors">
                Date{sortIndicator("redditCreatedAt")}
                <ArrowUpDown class="w-3 h-3" />
              </button>
            </th>
            <th class="px-4 py-3 text-text-muted font-medium w-8"></th>
          </tr>
        </thead>
        <tbody>
          {#each threads as thread (thread.id)}
            <tr
              class="border-b border-border/50 hover:bg-bg-elevated/50 cursor-pointer transition-colors"
              onclick={() => toggleRow(thread.id)}
            >
              <td class="px-4 py-3 text-text-muted">
                {#if expandedRows.has(thread.id)}
                  <ChevronDown class="w-4 h-4" />
                {:else}
                  <ChevronRight class="w-4 h-4" />
                {/if}
              </td>
              <td class="px-4 py-3 text-text-primary max-w-xs truncate" title={thread.title}>
                {thread.title}
              </td>
              <td class="px-4 py-3 text-text-secondary">r/{thread.subreddit}</td>
              <td class="px-4 py-3 text-text-secondary">{thread.score.toLocaleString()}</td>
              <td class="px-4 py-3 text-text-secondary">{thread.numComments.toLocaleString()}</td>
              <td class="px-4 py-3 text-text-muted text-xs">{formatDate(thread.redditCreatedAt)}</td>
              <td class="px-4 py-3">
                <a
                  href={thread.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onclick={(e) => e.stopPropagation()}
                  class="text-text-muted hover:text-accent transition-colors"
                >
                  <ExternalLink class="w-4 h-4" />
                </a>
              </td>
            </tr>
            {#if expandedRows.has(thread.id)}
              <tr class="bg-bg-elevated/30">
                <td colspan="7" class="px-8 py-4">
                  <p class="text-sm text-text-secondary whitespace-pre-wrap break-words">
                    {thread.selftext
                      ? thread.selftext.length > 500
                        ? thread.selftext.slice(0, 500) + "..."
                        : thread.selftext
                      : "(no selftext)"}
                  </p>
                  <p class="text-xs text-text-muted mt-2">
                    by u/{thread.author} &middot; fetched {timeAgo(thread.fetchedAt)}
                  </p>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    {#if totalPages > 1}
      <div class="flex items-center justify-between mt-4">
        <p class="text-sm text-text-muted">
          Page {filters.page} of {totalPages}
        </p>
        <div class="flex gap-2">
          {#if filters.page > 1}
            <a
              href="?{new URLSearchParams({ ...Object.fromEntries(Object.entries(filters).map(([k, v]) => [k, String(v)])), page: String(filters.page - 1) }).toString()}"
              class="px-3 py-1.5 text-sm rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors"
            >
              Previous
            </a>
          {/if}
          {#if filters.page < totalPages}
            <a
              href="?{new URLSearchParams({ ...Object.fromEntries(Object.entries(filters).map(([k, v]) => [k, String(v)])), page: String(filters.page + 1) }).toString()}"
              class="px-3 py-1.5 text-sm rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors"
            >
              Next
            </a>
          {/if}
        </div>
      </div>
    {/if}
  {/if}
</div>
