<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import { Plus } from "lucide-svelte";
  import { invalidateAll } from "$app/navigation";

  let { data } = $props();

  let showCreateForm = $state(false);
  let creating = $state(false);
  let formError = $state("");

  // Create form state
  let newName = $state("");
  let newDescription = $state("");
  let newCredits = $state(5);
  let newPriceInCents = $state(999);
  let newStripePriceId = $state("");
  let newSortOrder = $state(0);

  function formatPrice(cents: number): string {
    return `$${(cents / 100).toFixed(2)}`;
  }

  async function handleCreate() {
    creating = true;
    formError = "";
    try {
      const res = await fetch("/api/admin/packages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName,
          description: newDescription || undefined,
          credits: newCredits,
          priceInCents: newPriceInCents,
          stripePriceId: newStripePriceId,
          sortOrder: newSortOrder,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        formError = err.error || "Failed to create package";
        return;
      }
      // Reset form and refresh
      newName = "";
      newDescription = "";
      newCredits = 5;
      newPriceInCents = 999;
      newStripePriceId = "";
      newSortOrder = 0;
      showCreateForm = false;
      await invalidateAll();
    } catch {
      formError = "Network error";
    } finally {
      creating = false;
    }
  }

  async function toggleField(
    id: string,
    field: "isActive" | "isPopular",
    current: boolean,
  ) {
    await fetch(`/api/admin/packages/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: !current }),
    });
    await invalidateAll();
  }
</script>

<svelte:head>
  <title>Packages | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold text-text-primary">Token Packages</h2>
    <Button onclick={() => (showCreateForm = !showCreateForm)} icon={Plus} label="Create Package" class="btn-primary flex items-center gap-2" />
  </div>

  <!-- Create Form -->
  {#if showCreateForm}
    <div class="bg-bg-surface border border-border rounded-xl p-5 mb-6">
      <h3 class="text-lg font-semibold text-text-primary mb-4">New Package</h3>
      {#if formError}
        <div class="text-sm text-error mb-3 p-2 bg-error/10 rounded-lg">
          {formError}
        </div>
      {/if}
      <form
        onsubmit={(e) => {
          e.preventDefault();
          handleCreate();
        }}
        class="grid grid-cols-1 sm:grid-cols-2 gap-4"
      >
        <div>
          <label
            for="pkg-name"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Name</label
          >
          <input
            id="pkg-name"
            type="text"
            bind:value={newName}
            required
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
            placeholder="Pro Pack"
          />
        </div>
        <div>
          <label
            for="pkg-credits"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Credits</label
          >
          <input
            id="pkg-credits"
            type="number"
            bind:value={newCredits}
            required
            min="1"
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label
            for="pkg-price"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Price (cents)</label
          >
          <input
            id="pkg-price"
            type="number"
            bind:value={newPriceInCents}
            required
            min="1"
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
            placeholder="999"
          />
          <p class="text-xs text-text-muted mt-1">
            {formatPrice(newPriceInCents)}
          </p>
        </div>
        <div>
          <label
            for="pkg-stripe"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Stripe Price ID</label
          >
          <input
            id="pkg-stripe"
            type="text"
            bind:value={newStripePriceId}
            required
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
            placeholder="price_..."
          />
        </div>
        <div>
          <label
            for="pkg-sort"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Sort Order</label
          >
          <input
            id="pkg-sort"
            type="number"
            bind:value={newSortOrder}
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label
            for="pkg-desc"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Description (optional)</label
          >
          <input
            id="pkg-desc"
            type="text"
            bind:value={newDescription}
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
            placeholder="Best value pack"
          />
        </div>
        <div class="sm:col-span-2 flex gap-3">
          <SubmitButton loading={creating} loadingText="Creating..." label="Create Package" class="btn-primary" />
          <Button onclick={() => (showCreateForm = false)} label="Cancel" class="btn-secondary" />
        </div>
      </form>
    </div>
  {/if}

  <!-- Packages Table -->
  {#if data.packagesData}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border bg-bg-elevated/50">
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Name</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Credits</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Price</th
              >
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Stripe ID</th
              >
              <th class="text-center py-3 px-4 text-text-muted font-medium"
                >Active</th
              >
              <th class="text-center py-3 px-4 text-text-muted font-medium"
                >Popular</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Sort</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Actions</th
              >
            </tr>
          </thead>
          <tbody>
            {#each data.packagesData.packages as pkg}
              <tr class="border-b border-border/50">
                <td class="py-3 px-4 font-medium text-text-primary"
                  >{pkg.name}</td
                >
                <td class="py-3 px-4 text-right text-text-primary"
                  >{pkg.credits}</td
                >
                <td class="py-3 px-4 text-right text-text-primary"
                  >{formatPrice(pkg.priceInCents)}</td
                >
                <td
                  class="py-3 px-4 font-mono text-xs text-text-muted max-w-32 truncate"
                  >{pkg.stripePriceId}</td
                >
                <td class="py-3 px-4 text-center">
                  <Badge variant={pkg.isActive ? "success" : "muted"} size="sm">
                    {pkg.isActive ? "Yes" : "No"}
                  </Badge>
                </td>
                <td class="py-3 px-4 text-center">
                  {#if pkg.isPopular}
                    <Badge variant="accent" size="sm">Popular</Badge>
                  {:else}
                    <span class="text-text-muted">-</span>
                  {/if}
                </td>
                <td class="py-3 px-4 text-right text-text-secondary"
                  >{pkg.sortOrder}</td
                >
                <td class="py-3 px-4 text-right">
                  <div class="flex gap-1 justify-end">
                    <button
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                      onclick={() =>
                        toggleField(pkg.id, "isActive", pkg.isActive)}
                    >
                      {pkg.isActive ? "Disable" : "Enable"}
                    </button>
                    <button
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                      onclick={() =>
                        toggleField(pkg.id, "isPopular", pkg.isPopular)}
                    >
                      {pkg.isPopular ? "Unmark" : "Popular"}
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if data.packagesData.packages.length === 0}
        <div class="p-8 text-center text-text-muted">No packages yet.</div>
      {/if}
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load packages.</p>
    </div>
  {/if}
</div>
