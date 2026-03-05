<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import { Plus, Trash2 } from "lucide-svelte";
  import { invalidateAll } from "$app/navigation";
  import type { FeatureItem } from "$lib/types/billing";

  let { data } = $props();

  let showCreateForm = $state(false);
  let creating = $state(false);
  let formError = $state("");

  // Create form state — core fields
  let newName = $state("");
  let newDescription = $state("");
  let newCredits = $state(5);
  let newPriceInCents = $state(999);
  let newStripePriceId = $state("");
  let newSortOrder = $state(0);

  // Create form state — rich fields
  let newTagline = $state("");
  let newIncludesLabel = $state("");
  let newCtaText = $state("");
  let newBadgeLabel = $state("");
  let newPromoLine = $state("");
  let newPromoPriceInCents = $state<number | null>(null);
  let newPromoBadge = $state("");
  let newCreditsInfo = $state("");
  let newCtaSubText = $state("");
  let newCtaSubUrl = $state("");
  let newFeatures = $state<FeatureItem[]>([]);

  // Edit state — core fields
  let editingId: string | null = $state(null);
  let saving = $state(false);
  let editError = $state("");
  let editName = $state("");
  let editDescription = $state("");
  let editCredits = $state(0);
  let editPriceInCents = $state(0);
  let editStripePriceId = $state("");
  let editSortOrder = $state(0);

  // Edit state — rich fields
  let editTagline = $state("");
  let editIncludesLabel = $state("");
  let editCtaText = $state("");
  let editBadgeLabel = $state("");
  let editPromoLine = $state("");
  let editPromoPriceInCents = $state<number | null>(null);
  let editPromoBadge = $state("");
  let editCreditsInfo = $state("");
  let editCtaSubText = $state("");
  let editCtaSubUrl = $state("");
  let editFeatures = $state<FeatureItem[]>([]);

  $effect(() => {
    if (editingId && data.packagesData) {
      const pkg = data.packagesData.packages.find((p: { id: string }) => p.id === editingId);
      if (pkg) {
        editName = pkg.name;
        editDescription = pkg.description ?? "";
        editCredits = pkg.credits;
        editPriceInCents = pkg.priceInCents;
        editStripePriceId = pkg.stripePriceId ?? "";
        editSortOrder = pkg.sortOrder;
        editTagline = pkg.tagline ?? "";
        editIncludesLabel = pkg.includesLabel ?? "";
        editCtaText = pkg.ctaText ?? "";
        editBadgeLabel = pkg.badgeLabel ?? "";
        editPromoLine = pkg.promoLine ?? "";
        editPromoPriceInCents = pkg.promoPriceInCents ?? null;
        editPromoBadge = pkg.promoBadge ?? "";
        editCreditsInfo = pkg.creditsInfo ?? "";
        editCtaSubText = pkg.ctaSubText ?? "";
        editCtaSubUrl = pkg.ctaSubUrl ?? "";
        editFeatures = Array.isArray(pkg.features) ? [...pkg.features] : [];
      }
    }
  });

  function startEdit(id: string) {
    editError = "";
    editingId = editingId === id ? null : id;
  }

  function buildRichFields(
    tagline: string, includesLabel: string, creditsInfo: string, ctaText: string, badgeLabel: string,
    promoLine: string, promoPriceInCents: number | null, promoBadge: string,
    ctaSubText: string, ctaSubUrl: string, features: FeatureItem[]
  ) {
    return {
      tagline: tagline || undefined,
      includesLabel: includesLabel || undefined,
      creditsInfo: creditsInfo || undefined,
      ctaText: ctaText || undefined,
      badgeLabel: badgeLabel || undefined,
      promoLine: promoLine || undefined,
      promoPriceInCents: promoPriceInCents || undefined,
      promoBadge: promoBadge || undefined,
      ctaSubText: ctaSubText || undefined,
      ctaSubUrl: ctaSubUrl || undefined,
      features: features.length > 0 ? features : undefined,
    };
  }

  function buildRichFieldsForUpdate(
    tagline: string, includesLabel: string, creditsInfo: string, ctaText: string, badgeLabel: string,
    promoLine: string, promoPriceInCents: number | null, promoBadge: string,
    ctaSubText: string, ctaSubUrl: string, features: FeatureItem[]
  ) {
    return {
      tagline: tagline || null,
      includesLabel: includesLabel || null,
      creditsInfo: creditsInfo || null,
      ctaText: ctaText || null,
      badgeLabel: badgeLabel || null,
      promoLine: promoLine || null,
      promoPriceInCents: promoPriceInCents || null,
      promoBadge: promoBadge || null,
      ctaSubText: ctaSubText || null,
      ctaSubUrl: ctaSubUrl || null,
      features: features.length > 0 ? features : null,
    };
  }

  async function handleEdit() {
    if (!editingId) return;
    saving = true;
    editError = "";
    try {
      const res = await fetch(`/api/admin/packages/${editingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName,
          description: editDescription || undefined,
          credits: editCredits,
          priceInCents: editPriceInCents,
          stripePriceId: editStripePriceId,
          sortOrder: editSortOrder,
          ...buildRichFieldsForUpdate(
            editTagline, editIncludesLabel, editCreditsInfo, editCtaText, editBadgeLabel,
            editPromoLine, editPromoPriceInCents, editPromoBadge,
            editCtaSubText, editCtaSubUrl, editFeatures
          ),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        editError = err.error || "Failed to update package";
        return;
      }
      editingId = null;
      await invalidateAll();
    } catch {
      editError = "Network error";
    } finally {
      saving = false;
    }
  }

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
          ...buildRichFields(
            newTagline, newIncludesLabel, newCreditsInfo, newCtaText, newBadgeLabel,
            newPromoLine, newPromoPriceInCents, newPromoBadge,
            newCtaSubText, newCtaSubUrl, newFeatures
          ),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        formError = err.error || "Failed to create package";
        return;
      }
      // Reset form
      newName = "";
      newDescription = "";
      newCredits = 5;
      newPriceInCents = 999;
      newStripePriceId = "";
      newSortOrder = 0;
      newTagline = "";
      newIncludesLabel = "";
      newCtaText = "";
      newBadgeLabel = "";
      newPromoLine = "";
      newPromoPriceInCents = null;
      newPromoBadge = "";
      newCreditsInfo = "";
      newCtaSubText = "";
      newCtaSubUrl = "";
      newFeatures = [];
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

  function addFeature(list: FeatureItem[]): FeatureItem[] {
    return [...list, { text: "", icon: "check" }];
  }

  function removeFeature(list: FeatureItem[], index: number): FeatureItem[] {
    return list.filter((_, i) => i !== index);
  }

  const inputClass = "w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent";
  const labelClass = "block text-sm font-medium text-text-secondary mb-1";
</script>

<svelte:head>
  <title>Packages | Admin | NicheIQ</title>
</svelte:head>

{#snippet featureEditor(features: FeatureItem[], onUpdate: (updated: FeatureItem[]) => void)}
  <div class="sm:col-span-2">
    <span class={labelClass}>Features</span>
    <p class="text-xs text-text-muted mb-1">Checklist with icons below the "Includes" label.</p>
    <div class="space-y-2 mt-1">
      {#each features as feature, i}
        <div class="flex items-center gap-2">
          <input
            type="text"
            value={feature.text}
            oninput={(e) => {
              const updated = [...features];
              updated[i] = { ...updated[i], text: (e.target as HTMLInputElement).value };
              onUpdate(updated);
            }}
            class={inputClass}
            placeholder="Feature text"
          />
          <select
            value={feature.icon ?? "check"}
            onchange={(e) => {
              const updated = [...features];
              updated[i] = { ...updated[i], icon: (e.target as HTMLSelectElement).value as 'check' | 'plus' | 'star' };
              onUpdate(updated);
            }}
            class="px-2 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm"
          >
            <option value="check">check</option>
            <option value="plus">plus</option>
            <option value="star">star</option>
          </select>
          <label class="flex items-center gap-1 text-xs text-text-muted whitespace-nowrap">
            <input
              type="checkbox"
              checked={feature.highlight ?? false}
              onchange={(e) => {
                const updated = [...features];
                updated[i] = { ...updated[i], highlight: (e.target as HTMLInputElement).checked || undefined };
                onUpdate(updated);
              }}
            />
            HL
          </label>
          <button
            type="button"
            class="p-1.5 text-error/70 hover:text-error rounded"
            onclick={() => onUpdate(removeFeature(features, i))}
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      {/each}
    </div>
    <button
      type="button"
      class="mt-2 text-xs text-accent hover:underline flex items-center gap-1"
      onclick={() => onUpdate(addFeature(features))}
    >
      <Plus class="w-3 h-3" /> Add Feature
    </button>
  </div>
{/snippet}

{#snippet richFields(
  tagline: string, onTagline: (v: string) => void,
  includesLabel: string, onIncludesLabel: (v: string) => void,
  creditsInfo: string, onCreditsInfo: (v: string) => void,
  ctaText: string, onCtaText: (v: string) => void,
  badgeLabel: string, onBadgeLabel: (v: string) => void,
  promoLine: string, onPromoLine: (v: string) => void,
  priceInCents: number,
  promoPriceInCents: number | null, onPromoPriceInCents: (v: number | null) => void,
  promoBadge: string, onPromoBadge: (v: string) => void,
  ctaSubText: string, onCtaSubText: (v: string) => void,
  ctaSubUrl: string, onCtaSubUrl: (v: string) => void,
  features: FeatureItem[], onFeatures: (v: FeatureItem[]) => void
)}
  <!-- Card Customization -->
  <div class="sm:col-span-2 border-t border-accent/30 pt-4 mt-4">
    <h4 class="text-sm font-semibold text-accent mb-1">Card Customization</h4>
    <p class="text-xs text-text-muted mb-4">
      Controls how this package appears on the
      <span class="font-mono text-text-secondary">/billing</span> and
      <span class="font-mono text-text-secondary">landing page</span> pricing cards.
    </p>
  </div>

  <!-- BOTH PAGES -->
  <div class="sm:col-span-2">
    <h4 class="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Both Pages</h4>
  </div>
  <div>
    <label for="" class={labelClass}>Tagline</label>
    <input type="text" value={tagline} oninput={(e) => onTagline((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Plan how to build & profit" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Billing: muted subtitle below name. Landing: bold heading below price.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Badge Label</label>
    <input type="text" value={badgeLabel} oninput={(e) => onBadgeLabel((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Best Value" maxlength={50} />
    <p class="text-xs text-text-muted mt-1">Top pill badge on both pages. Replaces "Most Popular" when set.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Includes Label</label>
    <input type="text" value={includesLabel} oninput={(e) => onIncludesLabel((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Includes: Discovery + Deep Research" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Billing: text line below credits. Landing: accent badge with icon.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Promo Price (cents)</label>
    <input type="number" value={promoPriceInCents ?? ""} oninput={(e) => {
      const val = (e.target as HTMLInputElement).value;
      onPromoPriceInCents(val ? parseInt(val) : null);
    }} class={inputClass} placeholder="1200" min="1" />
    {#if promoPriceInCents}
      <p class="text-xs text-success mt-1">{formatPrice(promoPriceInCents)} <span class="text-text-muted line-through ml-1">{formatPrice(priceInCents)}</span></p>
    {:else}
      <p class="text-xs text-text-muted mt-1">Shown as green price with original crossed out. Leave empty for no promo.</p>
    {/if}
  </div>
  <div>
    <label for="" class={labelClass}>Promo Badge</label>
    <input type="text" value={promoBadge} oninput={(e) => onPromoBadge((e.target as HTMLInputElement).value)} class={inputClass} placeholder="35% Off" maxlength={50} />
    <p class="text-xs text-text-muted mt-1">Green corner badge at top-right.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Promo Line</label>
    <input type="text" value={promoLine} oninput={(e) => onPromoLine((e.target as HTMLInputElement).value)} class={inputClass} placeholder="+1 FREE Discovery (up to 10 ideas)" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Billing: green text above button. Landing: gift-icon badge.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Button Text</label>
    <input type="text" value={ctaText} oninput={(e) => onCtaText((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Get Your Blueprint →" maxlength={100} />
    <p class="text-xs text-text-muted mt-1">Billing defaults to "Buy Now", landing defaults to "Get &#123;name&#125;".</p>
  </div>
  <div>
    <label for="" class={labelClass}>Link Text</label>
    <input type="text" value={ctaSubText} oninput={(e) => onCtaSubText((e.target as HTMLInputElement).value)} class={inputClass} placeholder="See sample Discovery →" maxlength={100} />
    <p class="text-xs text-text-muted mt-1">Small link below the button. Only shows when both text and URL are set.</p>
  </div>
  <div class="sm:col-span-2">
    <label for="" class={labelClass}>Link URL</label>
    <input type="text" value={ctaSubUrl} oninput={(e) => onCtaSubUrl((e.target as HTMLInputElement).value)} class={inputClass} placeholder="/sample-report" maxlength={500} />
    <p class="text-xs text-text-muted mt-1">Where the link points. Needs Link Text to be visible.</p>
  </div>

  <!-- LANDING PAGE ONLY -->
  <div class="sm:col-span-2 border-t border-border/30 pt-3 mt-2">
    <h4 class="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Landing Page Only</h4>
  </div>
  {@render featureEditor(features, onFeatures)}

  <!-- BILLING PAGE ONLY -->
  <div class="sm:col-span-2 border-t border-border/30 pt-3 mt-2">
    <h4 class="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Billing Page Only</h4>
  </div>
  <div>
    <label for="" class={labelClass}>Credits Info</label>
    <input type="text" value={creditsInfo} oninput={(e) => onCreditsInfo((e.target as HTMLInputElement).value)} class={inputClass} placeholder="~1 Discovery run + extras" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Muted text shown below the credits count (e.g., "Discovery + Deep Research").</p>
  </div>
{/snippet}

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
          <label for="pkg-name" class={labelClass}>Name</label>
          <input id="pkg-name" type="text" bind:value={newName} required class={inputClass} placeholder="Pro Pack" />
        </div>
        <div>
          <label for="pkg-credits" class={labelClass}>Credits</label>
          <input id="pkg-credits" type="number" bind:value={newCredits} required min="1" class={inputClass} />
        </div>
        <div>
          <label for="pkg-price" class={labelClass}>Price (cents)</label>
          <input id="pkg-price" type="number" bind:value={newPriceInCents} required min="1" class={inputClass} placeholder="999" />
          <p class="text-xs text-text-muted mt-1">{formatPrice(newPriceInCents)}</p>
        </div>
        <div>
          <label for="pkg-stripe" class={labelClass}>Stripe Price ID</label>
          <input id="pkg-stripe" type="text" bind:value={newStripePriceId} required class={inputClass} placeholder="price_..." />
        </div>
        <div>
          <label for="pkg-sort" class={labelClass}>Sort Order</label>
          <input id="pkg-sort" type="number" bind:value={newSortOrder} class={inputClass} />
        </div>
        <div>
          <label for="pkg-desc" class={labelClass}>Description <span class="text-xs text-text-muted font-normal">(landing page only)</span></label>
          <input id="pkg-desc" type="text" bind:value={newDescription} class={inputClass} placeholder="Best value pack" />
          <p class="text-xs text-text-muted mt-1">Paragraph text shown below the tagline on landing pricing cards.</p>
        </div>

        {@render richFields(
          newTagline, (v) => newTagline = v,
          newIncludesLabel, (v) => newIncludesLabel = v,
          newCreditsInfo, (v) => newCreditsInfo = v,
          newCtaText, (v) => newCtaText = v,
          newBadgeLabel, (v) => newBadgeLabel = v,
          newPromoLine, (v) => newPromoLine = v,
          newPriceInCents,
          newPromoPriceInCents, (v) => newPromoPriceInCents = v,
          newPromoBadge, (v) => newPromoBadge = v,
          newCtaSubText, (v) => newCtaSubText = v,
          newCtaSubUrl, (v) => newCtaSubUrl = v,
          newFeatures, (v) => newFeatures = v
        )}

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
              <th class="text-left py-3 px-4 text-text-muted font-medium">Name</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Credits</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Price</th>
              <th class="text-left py-3 px-4 text-text-muted font-medium">Stripe ID</th>
              <th class="text-center py-3 px-4 text-text-muted font-medium">Active</th>
              <th class="text-center py-3 px-4 text-text-muted font-medium">Popular</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Sort</th>
              <th class="text-right py-3 px-4 text-text-muted font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each data.packagesData.packages as pkg}
              <tr class="border-b border-border/50 {editingId === pkg.id ? 'bg-bg-elevated/30' : ''}">
                <td class="py-3 px-4">
                  <div>
                    <span class="font-medium text-text-primary">{pkg.name}</span>
                    {#if pkg.tagline}
                      <span class="text-xs text-accent ml-1">— {pkg.tagline}</span>
                    {/if}
                  </div>
                  {#if pkg.creditsInfo || pkg.includesLabel || pkg.ctaText || pkg.promoLine || pkg.badgeLabel || (Array.isArray(pkg.features) && pkg.features.length > 0)}
                    <div class="flex flex-wrap gap-1 mt-1">
                      {#if pkg.creditsInfo}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Credits: "{pkg.creditsInfo}"</span>{/if}
                      {#if pkg.includesLabel}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Includes: "{pkg.includesLabel}"</span>{/if}
                      {#if pkg.ctaText}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">CTA: "{pkg.ctaText}"</span>{/if}
                      {#if pkg.promoLine}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Promo: "{pkg.promoLine}"</span>{/if}
                      {#if pkg.badgeLabel}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Badge: "{pkg.badgeLabel}"</span>{/if}
                      {#if Array.isArray(pkg.features) && pkg.features.length > 0}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted">{pkg.features.length} features</span>{/if}
                    </div>
                  {/if}
                </td>
                <td class="py-3 px-4 text-right text-text-primary">{pkg.credits}</td>
                <td class="py-3 px-4 text-right text-text-primary">
                  {formatPrice(pkg.priceInCents)}
                  {#if pkg.promoPriceInCents}
                    <span class="text-xs text-success ml-1">→ {formatPrice(pkg.promoPriceInCents)}</span>
                  {/if}
                </td>
                <td class="py-3 px-4 font-mono text-xs text-text-muted max-w-32 truncate">{pkg.stripePriceId}</td>
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
                <td class="py-3 px-4 text-right text-text-secondary">{pkg.sortOrder}</td>
                <td class="py-3 px-4 text-right">
                  <div class="flex gap-1 justify-end">
                    <button
                      class="text-xs px-2 py-1 rounded border transition-colors {editingId === pkg.id ? 'border-accent bg-accent/10 text-accent' : 'border-border hover:bg-bg-elevated text-text-secondary'}"
                      onclick={() => startEdit(pkg.id)}
                    >
                      {editingId === pkg.id ? "Close" : "Edit"}
                    </button>
                    <button
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                      onclick={() => toggleField(pkg.id, "isActive", pkg.isActive)}
                    >
                      {pkg.isActive ? "Disable" : "Enable"}
                    </button>
                    <button
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                      onclick={() => toggleField(pkg.id, "isPopular", pkg.isPopular)}
                    >
                      {pkg.isPopular ? "Unmark" : "Popular"}
                    </button>
                  </div>
                </td>
              </tr>
              {#if editingId === pkg.id}
                <tr class="border-b border-border/50">
                  <td colspan="8" class="p-0">
                    <div class="bg-bg-surface border-t border-accent/20 p-5">
                      <h4 class="text-sm font-semibold text-text-primary mb-3">Edit Package</h4>
                      {#if editError}
                        <div class="text-sm text-error mb-3 p-2 bg-error/10 rounded-lg">
                          {editError}
                        </div>
                      {/if}
                      <form
                        onsubmit={(e) => {
                          e.preventDefault();
                          handleEdit();
                        }}
                        class="grid grid-cols-1 sm:grid-cols-2 gap-4"
                      >
                        <div>
                          <label for="edit-name" class={labelClass}>Name</label>
                          <input id="edit-name" type="text" bind:value={editName} required class={inputClass} />
                        </div>
                        <div>
                          <label for="edit-credits" class={labelClass}>Credits</label>
                          <input id="edit-credits" type="number" bind:value={editCredits} required min="1" class={inputClass} />
                        </div>
                        <div>
                          <label for="edit-price" class={labelClass}>Price (cents)</label>
                          <input id="edit-price" type="number" bind:value={editPriceInCents} required min="1" class={inputClass} />
                          <p class="text-xs text-text-muted mt-1">{formatPrice(editPriceInCents)}</p>
                        </div>
                        <div>
                          <label for="edit-sort" class={labelClass}>Sort Order</label>
                          <input id="edit-sort" type="number" bind:value={editSortOrder} class={inputClass} />
                        </div>
                        <div>
                          <label for="edit-desc" class={labelClass}>Description <span class="text-xs text-text-muted font-normal">(landing page only)</span></label>
                          <input id="edit-desc" type="text" bind:value={editDescription} class={inputClass} />
                          <p class="text-xs text-text-muted mt-1">Paragraph text shown below the tagline on landing pricing cards.</p>
                        </div>
                        <div>
                          <label for="edit-stripe-price" class={labelClass}>Stripe Price ID</label>
                          <input id="edit-stripe-price" type="text" bind:value={editStripePriceId} required class={inputClass + " font-mono"} />
                          <p class="text-xs text-warning mt-1">Changing this will redirect future purchases to a different Stripe price. Does not affect existing subscriptions.</p>
                        </div>

                        {@render richFields(
                          editTagline, (v) => editTagline = v,
                          editIncludesLabel, (v) => editIncludesLabel = v,
                          editCreditsInfo, (v) => editCreditsInfo = v,
                          editCtaText, (v) => editCtaText = v,
                          editBadgeLabel, (v) => editBadgeLabel = v,
                          editPromoLine, (v) => editPromoLine = v,
                          editPriceInCents,
                          editPromoPriceInCents, (v) => editPromoPriceInCents = v,
                          editPromoBadge, (v) => editPromoBadge = v,
                          editCtaSubText, (v) => editCtaSubText = v,
                          editCtaSubUrl, (v) => editCtaSubUrl = v,
                          editFeatures, (v) => editFeatures = v
                        )}

                        <div class="sm:col-span-2 flex gap-3">
                          <SubmitButton loading={saving} loadingText="Saving..." label="Save Changes" class="btn-primary" />
                          <Button onclick={() => (editingId = null)} label="Cancel" class="btn-secondary" />
                        </div>
                      </form>
                    </div>
                  </td>
                </tr>
              {/if}
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
