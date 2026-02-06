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
  let newCode = $state("");
  let newCreditAmount = $state(10);
  let newMaxRedemptions = $state(1);
  let newExpiresAt = $state("");
  let newDescription = $state("");

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "Never";
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  async function handleCreate() {
    creating = true;
    formError = "";
    try {
      const res = await fetch("/api/admin/promo-codes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: newCode,
          creditAmount: newCreditAmount,
          maxRedemptions: newMaxRedemptions,
          expiresAt: newExpiresAt || null,
          description: newDescription || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        formError = err.error || "Failed to create promo code";
        return;
      }
      // Reset form and refresh
      newCode = "";
      newCreditAmount = 10;
      newMaxRedemptions = 1;
      newExpiresAt = "";
      newDescription = "";
      showCreateForm = false;
      await invalidateAll();
    } catch {
      formError = "Network error";
    } finally {
      creating = false;
    }
  }

  async function toggleActive(id: string, currentActive: boolean) {
    await fetch(`/api/admin/promo-codes/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isActive: !currentActive }),
    });
    await invalidateAll();
  }
</script>

<svelte:head>
  <title>Promo Codes | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold text-text-primary">Promo Codes</h2>
    <Button onclick={() => (showCreateForm = !showCreateForm)} icon={Plus} label="Create Code" class="btn-primary flex items-center gap-2" />
  </div>

  <!-- Create Form -->
  {#if showCreateForm}
    <div class="bg-bg-surface border border-border rounded-xl p-5 mb-6">
      <h3 class="text-lg font-semibold text-text-primary mb-4">
        New Promo Code
      </h3>
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
            for="code"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Code</label
          >
          <input
            id="code"
            type="text"
            bind:value={newCode}
            required
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
            placeholder="WELCOME50"
          />
        </div>
        <div>
          <label
            for="credits"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Credit Amount</label
          >
          <input
            id="credits"
            type="number"
            bind:value={newCreditAmount}
            required
            min="1"
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label
            for="maxRedemptions"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Max Redemptions</label
          >
          <input
            id="maxRedemptions"
            type="number"
            bind:value={newMaxRedemptions}
            required
            min="1"
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label
            for="expiresAt"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Expires At (optional)</label
          >
          <input
            id="expiresAt"
            type="date"
            bind:value={newExpiresAt}
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div class="sm:col-span-2">
          <label
            for="description"
            class="block text-sm font-medium text-text-secondary mb-1"
            >Description (optional)</label
          >
          <input
            id="description"
            type="text"
            bind:value={newDescription}
            class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
            placeholder="Internal notes about this code"
          />
        </div>
        <div class="sm:col-span-2 flex gap-3">
          <SubmitButton loading={creating} loadingText="Creating..." label="Create Promo Code" class="btn-primary" />
          <Button onclick={() => (showCreateForm = false)} label="Cancel" class="btn-secondary" />
        </div>
      </form>
    </div>
  {/if}

  <!-- Promo Codes Table -->
  {#if data.promoData}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border bg-bg-elevated/50">
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Code</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Credits</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Uses</th
              >
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Expires</th
              >
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Status</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Actions</th
              >
            </tr>
          </thead>
          <tbody>
            {#each data.promoData.promoCodes as promo}
              <tr class="border-b border-border/50">
                <td class="py-3 px-4 font-mono font-semibold text-text-primary"
                  >{promo.code}</td
                >
                <td class="py-3 px-4 text-right text-text-primary"
                  >{promo.creditAmount}</td
                >
                <td class="py-3 px-4 text-right text-text-secondary">
                  {promo.currentUses} / {promo.maxRedemptions}
                </td>
                <td class="py-3 px-4 text-text-muted"
                  >{formatDate(promo.expiresAt)}</td
                >
                <td class="py-3 px-4">
                  <Badge
                    variant={promo.isActive ? "success" : "muted"}
                    size="sm"
                  >
                    {promo.isActive ? "Active" : "Inactive"}
                  </Badge>
                </td>
                <td class="py-3 px-4 text-right">
                  <button
                    class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                    onclick={() => toggleActive(promo.id, promo.isActive)}
                  >
                    {promo.isActive ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if data.promoData.promoCodes.length === 0}
        <div class="p-8 text-center text-text-muted">No promo codes yet.</div>
      {/if}
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load promo codes.</p>
    </div>
  {/if}
</div>
