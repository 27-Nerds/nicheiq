<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import { Search } from 'lucide-svelte';
  import { goto, invalidateAll } from '$app/navigation';
  import { page as pageStore } from '$app/stores';

  let { data } = $props();

  const initialSearch = $derived(data.search || '');
  let searchInput = $state('');
  $effect(() => { searchInput = initialSearch; });
  let updatingRole = $state<string | null>(null);

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  }

  function handleSearch(e: Event) {
    e.preventDefault();
    const url = new URL($pageStore.url);
    if (searchInput) {
      url.searchParams.set('search', searchInput);
    } else {
      url.searchParams.delete('search');
    }
    url.searchParams.delete('page');
    goto(url.toString());
  }

  async function toggleRole(userId: string, currentRole: string) {
    if (!confirm(`Change user role to ${currentRole === 'ADMIN' ? 'USER' : 'ADMIN'}? The change takes effect after re-login.`)) {
      return;
    }
    updatingRole = userId;
    try {
      await fetch(`/api/admin/users/${userId}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: currentRole === 'ADMIN' ? 'USER' : 'ADMIN' }),
      });
      await invalidateAll();
    } finally {
      updatingRole = null;
    }
  }
</script>

<svelte:head>
  <title>Users | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold text-text-primary">Users</h2>
  </div>

  <!-- Search -->
  <form onsubmit={handleSearch} class="mb-6">
    <div class="relative max-w-md">
      <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
      <input
        type="text"
        bind:value={searchInput}
        placeholder="Search by email or name..."
        class="w-full pl-10 pr-4 py-2 bg-bg-surface border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
      />
    </div>
  </form>

  {#if data.usersData}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border bg-bg-elevated/50">
              <th class="text-left py-3 px-4 text-text-muted font-medium">Email</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">Name</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">Role</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Credits</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Jobs</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">Joined</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each data.usersData.users as user}
              <tr class="border-b border-border/50">
                <td class="py-3 px-4 text-text-primary">{user.email}</td>
                <td class="py-3 px-4 text-text-secondary">{user.name || '-'}</td>
                <td class="py-3 px-4">
                  <Badge variant={user.role === 'ADMIN' ? 'accent' : 'muted'} size="sm">
                    {user.role}
                  </Badge>
                </td>
                <td class="py-3 px-4 text-right text-text-primary">{user.creditBalance}</td>
                <td class="py-3 px-4 text-right text-text-secondary">{user.jobCount}</td>
                <td class="py-3 px-4 text-text-muted">{formatDate(user.createdAt)}</td>
                <td class="py-3 px-4 text-right">
                  <button
                    class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary disabled:opacity-50"
                    onclick={() => toggleRole(user.id, user.role)}
                    disabled={updatingRole === user.id}
                  >
                    {updatingRole === user.id ? '...' : user.role === 'ADMIN' ? 'Demote' : 'Promote'}
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if data.usersData.users.length === 0}
        <div class="p-8 text-center text-text-muted">No users found.</div>
      {/if}
      <!-- Pagination -->
      {#if data.usersData.totalPages > 1}
        <div class="flex items-center justify-between px-4 py-3 border-t border-border">
          <span class="text-sm text-text-muted">
            Page {data.usersData.page} of {data.usersData.totalPages} ({data.usersData.total} users)
          </span>
          <div class="flex gap-2">
            {#if data.usersData.page > 1}
              <a href="?page={data.usersData.page - 1}{data.search ? `&search=${data.search}` : ''}"
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary">
                Previous
              </a>
            {/if}
            {#if data.usersData.page < data.usersData.totalPages}
              <a href="?page={data.usersData.page + 1}{data.search ? `&search=${data.search}` : ''}"
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary">
                Next
              </a>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load users.</p>
    </div>
  {/if}
</div>
