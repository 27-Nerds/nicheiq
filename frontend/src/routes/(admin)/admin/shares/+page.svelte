<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import { invalidateAll } from "$app/navigation";

  let { data } = $props();

  let updatingId = $state<string | null>(null);

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  async function toggleField(id: string, field: "isActive" | "allowIndexing", currentValue: boolean) {
    updatingId = id;
    try {
      await fetch(`/api/admin/shares/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: !currentValue }),
      });
      await invalidateAll();
    } finally {
      updatingId = null;
    }
  }

  function shareUrl(type: string, token: string): string {
    if (type === "report") return `/shared/${token}`;
    return `/shared/discovery/${token}`;
  }
</script>

<svelte:head>
  <title>Shared Links | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold text-text-primary">Shared Links</h2>
  </div>

  {#if data.sharesData}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border bg-bg-elevated/50">
              <th class="text-left py-3 px-4 text-text-muted font-medium">Type</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">Niche</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">User</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">Token</th>
              <th class="text-center py-3 px-4 text-text-muted font-medium">Active</th>
              <th class="text-center py-3 px-4 text-text-muted font-medium">Indexing</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Views</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Votes</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {#each data.sharesData.shares as share}
              <tr class="border-b border-border/50">
                <td class="py-3 px-4">
                  <Badge
                    variant={share.type === "report" ? "accent" : "info"}
                    size="sm"
                  >
                    {share.type}
                  </Badge>
                </td>
                <td class="py-3 px-4 text-text-primary max-w-[200px] truncate" title={share.niche}>
                  {share.niche}
                </td>
                <td class="py-3 px-4 text-text-secondary">
                  {share.userEmail || "\u2014"}
                </td>
                <td class="py-3 px-4">
                  <a
                    href={shareUrl(share.type, share.shareToken)}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-accent hover:underline text-xs font-mono"
                  >
                    {share.shareToken.slice(0, 12)}...
                  </a>
                </td>
                <td class="py-3 px-4 text-center">
                  <button
                    class="text-xs px-2.5 py-1 rounded border transition-colors disabled:opacity-50 {share.isActive
                      ? 'border-success/40 text-success hover:bg-success/10'
                      : 'border-border text-text-muted hover:bg-bg-elevated'}"
                    onclick={() => toggleField(share.id, "isActive", share.isActive)}
                    disabled={updatingId === share.id}
                  >
                    {share.isActive ? "On" : "Off"}
                  </button>
                </td>
                <td class="py-3 px-4 text-center">
                  <button
                    class="text-xs px-2.5 py-1 rounded border transition-colors disabled:opacity-50 {share.allowIndexing
                      ? 'border-accent/40 text-accent hover:bg-accent/10'
                      : 'border-border text-text-muted hover:bg-bg-elevated'}"
                    onclick={() => toggleField(share.id, "allowIndexing", share.allowIndexing)}
                    disabled={updatingId === share.id || !share.isActive}
                    title={!share.isActive ? "Enable share first" : ""}
                  >
                    {share.allowIndexing ? "On" : "Off"}
                  </button>
                </td>
                <td class="py-3 px-4 text-right text-text-secondary">
                  {share.viewCount}
                </td>
                <td class="py-3 px-4 text-right text-text-secondary">
                  {share.type === "discovery" ? share.voteCount : "\u2014"}
                </td>
                <td class="py-3 px-4 text-text-muted">
                  {formatDate(share.createdAt)}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if data.sharesData.shares.length === 0}
        <div class="p-8 text-center text-text-muted">No shared links found.</div>
      {/if}
      <!-- Pagination -->
      {#if data.sharesData.totalPages > 1}
        <div class="flex items-center justify-between px-4 py-3 border-t border-border">
          <span class="text-sm text-text-muted">
            Page {data.sharesData.page} of {data.sharesData.totalPages} ({data.sharesData.total} shares)
          </span>
          <div class="flex gap-2">
            {#if data.sharesData.page > 1}
              <a
                href="?page={data.sharesData.page - 1}"
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
              >
                Previous
              </a>
            {/if}
            {#if data.sharesData.page < data.sharesData.totalPages}
              <a
                href="?page={data.sharesData.page + 1}"
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
              >
                Next
              </a>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load shared links.</p>
    </div>
  {/if}
</div>
