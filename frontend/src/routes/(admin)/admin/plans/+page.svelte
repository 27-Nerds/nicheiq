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
  let newMonthlyCredits = $state(0);
  let newPriceInCents = $state(999);
  let newStripePriceId = $state("");
  let newTrialDays = $state<number | null>(null);
  let newStripeCouponId = $state("");
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
  let editMonthlyCredits = $state(0);
  let editPriceInCents = $state(0);
  let editStripePriceId = $state("");
  let editTrialDays = $state<number | null>(null);
  let editStripeCouponId = $state("");
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
    if (editingId && data.plansData) {
      const plan = data.plansData.plans.find((p: { id: string }) => p.id === editingId);
      if (plan) {
        editName = plan.name;
        editDescription = plan.description ?? "";
        editMonthlyCredits = plan.monthlyCredits;
        editPriceInCents = plan.priceInCents;
        editStripePriceId = plan.stripePriceId ?? "";
        editTrialDays = plan.trialDays ?? null;
        editStripeCouponId = plan.stripeCouponId ?? "";
        editSortOrder = plan.sortOrder;
        editTagline = plan.tagline ?? "";
        editIncludesLabel = plan.includesLabel ?? "";
        editCtaText = plan.ctaText ?? "";
        editBadgeLabel = plan.badgeLabel ?? "";
        editPromoLine = plan.promoLine ?? "";
        editPromoPriceInCents = plan.promoPriceInCents ?? null;
        editPromoBadge = plan.promoBadge ?? "";
        editCreditsInfo = plan.creditsInfo ?? "";
        editCtaSubText = plan.ctaSubText ?? "";
        editCtaSubUrl = plan.ctaSubUrl ?? "";
        editFeatures = Array.isArray(plan.features) ? [...plan.features] : [];
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
      const res = await fetch(`/api/admin/plans/${editingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName,
          description: editDescription || undefined,
          monthlyCredits: editMonthlyCredits,
          priceInCents: editPriceInCents,
          stripePriceId: editStripePriceId,
          trialDays: editTrialDays ?? null,
          stripeCouponId: editStripeCouponId || null,
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
        editError = err.error || "Failed to update plan";
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
      const res = await fetch("/api/admin/plans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName,
          description: newDescription || undefined,
          monthlyCredits: newMonthlyCredits,
          priceInCents: newPriceInCents,
          stripePriceId: newStripePriceId,
          trialDays: newTrialDays ?? undefined,
          stripeCouponId: newStripeCouponId || undefined,
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
        formError = err.error || "Failed to create plan";
        return;
      }
      // Reset form
      newName = "";
      newDescription = "";
      newMonthlyCredits = 0;
      newPriceInCents = 999;
      newStripePriceId = "";
      newTrialDays = null;
      newStripeCouponId = "";
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
    await fetch(`/api/admin/plans/${id}`, {
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

  const inputClass = "input";
  const labelClass = "block text-sm font-medium text-text-secondary mb-1";
</script>

<svelte:head>
  <title>Plans | Admin | NicheIQ</title>
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
            class="input"
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
      class="mt-2 text-xs text-[color:var(--color-accent-dark)] hover:underline flex items-center gap-1"
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
  <div class="sm:col-span-2 border-t border-border pt-4 mt-4">
    <h4 class="text-sm font-semibold text-[color:var(--color-accent-dark)] mb-1">Card Customization</h4>
    <p class="text-xs text-text-muted mb-4">
      Controls how this plan appears on the
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
    <input type="text" value={tagline} oninput={(e) => onTagline((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Validate ideas every month" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Billing: muted subtitle below name. Landing: bold heading below price.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Badge Label</label>
    <input type="text" value={badgeLabel} oninput={(e) => onBadgeLabel((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Best Value" maxlength={50} />
    <p class="text-xs text-text-muted mt-1">Top pill badge on both pages. Replaces "Most Popular" when set.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Includes Label</label>
    <input type="text" value={includesLabel} oninput={(e) => onIncludesLabel((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Includes: Full catalog access" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Billing: text line below credits. Landing: accent badge with icon.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Promo Price (cents)</label>
    <input type="number" value={promoPriceInCents ?? ""} oninput={(e) => {
      const val = (e.target as HTMLInputElement).value;
      onPromoPriceInCents(val ? parseInt(val) : null);
    }} class={inputClass} placeholder="1200" min="1" />
    {#if promoPriceInCents}
      <p class="text-xs text-[color:var(--color-success-text)] mt-1">{formatPrice(promoPriceInCents)} <span class="text-text-muted line-through ml-1">{formatPrice(priceInCents)}</span></p>
    {:else}
      <p class="text-xs text-text-muted mt-1">Editorial only. The real discount comes from the attached Stripe coupon. Keep this consistent with the coupon. Leave empty for no promo.</p>
    {/if}
  </div>
  <div>
    <label for="" class={labelClass}>Promo Badge</label>
    <input type="text" value={promoBadge} oninput={(e) => onPromoBadge((e.target as HTMLInputElement).value)} class={inputClass} placeholder="35% Off" maxlength={50} />
    <p class="text-xs text-text-muted mt-1">Green corner badge at top-right. Editorial only.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Promo Line</label>
    <input type="text" value={promoLine} oninput={(e) => onPromoLine((e.target as HTMLInputElement).value)} class={inputClass} placeholder="First month 50% off" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Billing: green text above button. Landing: gift-icon badge.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Button Text</label>
    <input type="text" value={ctaText} oninput={(e) => onCtaText((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Subscribe →" maxlength={100} />
    <p class="text-xs text-text-muted mt-1">Defaults to "Subscribe" on both pages.</p>
  </div>
  <div>
    <label for="" class={labelClass}>Link Text</label>
    <input type="text" value={ctaSubText} oninput={(e) => onCtaSubText((e.target as HTMLInputElement).value)} class={inputClass} placeholder="See sample report →" maxlength={100} />
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
    <input type="text" value={creditsInfo} oninput={(e) => onCreditsInfo((e.target as HTMLInputElement).value)} class={inputClass} placeholder="Resets every month" maxlength={200} />
    <p class="text-xs text-text-muted mt-1">Muted text shown below the monthly-credits count.</p>
  </div>
{/snippet}

<div class="max-w-6xl">
  <div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold text-text-primary">Subscription Plans</h2>
    <Button onclick={() => (showCreateForm = !showCreateForm)} icon={Plus} label="Create Plan" class="btn-primary flex items-center gap-2" />
  </div>

  <!-- Create Form -->
  {#if showCreateForm}
    <div class="bg-bg-surface border border-border rounded-xl p-5 mb-6">
      <h3 class="text-lg font-semibold text-text-primary mb-4">New Plan</h3>
      {#if formError}
        <div class="text-sm text-[color:var(--color-error-text)] mb-3 p-2 bg-error/10 rounded-lg">
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
          <label for="plan-name" class={labelClass}>Name</label>
          <input id="plan-name" type="text" bind:value={newName} required class={inputClass} placeholder="Founder" />
        </div>
        <div>
          <label for="plan-credits" class={labelClass}>Monthly credits</label>
          <input id="plan-credits" type="number" bind:value={newMonthlyCredits} required min="0" class={inputClass} />
          <p class="text-xs text-text-muted mt-1">Credits granted each cycle. 0 = catalog access only.</p>
        </div>
        <div>
          <label for="plan-price" class={labelClass}>Price (cents)</label>
          <input id="plan-price" type="number" bind:value={newPriceInCents} required min="1" class={inputClass} placeholder="999" />
          <p class="text-xs text-text-muted mt-1">{formatPrice(newPriceInCents)} / month</p>
        </div>
        <div>
          <label for="plan-stripe" class={labelClass}>Stripe Price ID</label>
          <input id="plan-stripe" type="text" bind:value={newStripePriceId} required class={inputClass} placeholder="price_..." />
          <p class="text-xs text-text-muted mt-1">Must be a recurring monthly price.</p>
        </div>
        <div>
          <label for="plan-trial" class={labelClass}>Trial days <span class="text-xs text-text-muted font-normal">(optional)</span></label>
          <input id="plan-trial" type="number" value={newTrialDays ?? ""} oninput={(e) => {
            const val = (e.target as HTMLInputElement).value;
            newTrialDays = val ? parseInt(val) : null;
          }} min="0" class={inputClass} placeholder="0" />
          <p class="text-xs text-text-muted mt-1">Trial grants catalog access; monthly credits unlock on first paid invoice.</p>
        </div>
        <div>
          <label for="plan-coupon" class={labelClass}>Stripe Coupon ID <span class="text-xs text-text-muted font-normal">(optional)</span></label>
          <input id="plan-coupon" type="text" bind:value={newStripeCouponId} class={inputClass} placeholder="coupon_..." />
          <p class="text-xs text-text-muted mt-1">Auto-applied at checkout. Keep promo display fields consistent with it.</p>
        </div>
        <div>
          <label for="plan-sort" class={labelClass}>Sort Order</label>
          <input id="plan-sort" type="number" bind:value={newSortOrder} class={inputClass} />
        </div>
        <div>
          <label for="plan-desc" class={labelClass}>Description <span class="text-xs text-text-muted font-normal">(landing page only)</span></label>
          <input id="plan-desc" type="text" bind:value={newDescription} class={inputClass} placeholder="For founders validating monthly" />
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
          <SubmitButton loading={creating} loadingText="Creating..." label="Create Plan" class="btn-primary" />
          <Button onclick={() => (showCreateForm = false)} label="Cancel" class="btn-secondary" />
        </div>
      </form>
    </div>
  {/if}

  <!-- Plans Table -->
  {#if data.plansData}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th class="num">Monthly credits</th>
              <th class="num">Price</th>
              <th class="num">Trial</th>
              <th>Stripe ID</th>
              <th style="text-align: center">Active</th>
              <th style="text-align: center">Popular</th>
              <th class="num">Sort</th>
              <th style="text-align: right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each data.plansData.plans as plan}
              <tr class={editingId === plan.id ? 'bg-bg-elevated/30' : ''}>
                <td>
                  <div>
                    <span class="font-medium text-text-primary">{plan.name}</span>
                    {#if plan.tagline}
                      <span class="text-xs text-[color:var(--color-accent-dark)] ml-1">· {plan.tagline}</span>
                    {/if}
                  </div>
                  {#if plan.creditsInfo || plan.includesLabel || plan.ctaText || plan.promoLine || plan.badgeLabel || plan.stripeCouponId || (Array.isArray(plan.features) && plan.features.length > 0)}
                    <div class="flex flex-wrap gap-1 mt-1">
                      {#if plan.creditsInfo}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Credits: "{plan.creditsInfo}"</span>{/if}
                      {#if plan.includesLabel}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Includes: "{plan.includesLabel}"</span>{/if}
                      {#if plan.ctaText}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">CTA: "{plan.ctaText}"</span>{/if}
                      {#if plan.promoLine}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Promo: "{plan.promoLine}"</span>{/if}
                      {#if plan.badgeLabel}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Badge: "{plan.badgeLabel}"</span>{/if}
                      {#if plan.stripeCouponId}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted truncate max-w-48">Coupon: {plan.stripeCouponId}</span>{/if}
                      {#if Array.isArray(plan.features) && plan.features.length > 0}<span class="inline-block text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-muted">{plan.features.length} features</span>{/if}
                    </div>
                  {/if}
                </td>
                <td class="num cell-primary">
                  {#if plan.monthlyCredits === 0}
                    <span class="text-text-muted">Catalog only</span>
                  {:else}
                    {plan.monthlyCredits}
                  {/if}
                </td>
                <td class="num cell-primary">
                  {formatPrice(plan.priceInCents)}<span class="text-xs text-text-muted">/mo</span>
                  {#if plan.promoPriceInCents}
                    <span class="text-xs text-[color:var(--color-success-text)] ml-1">→ {formatPrice(plan.promoPriceInCents)}</span>
                  {/if}
                </td>
                <td class="num text-text-secondary">{plan.trialDays ? `${plan.trialDays}d` : "-"}</td>
                <td class="font-mono text-xs cell-muted max-w-32 truncate">{plan.stripePriceId}</td>
                <td class="text-center">
                  <Badge variant={plan.isActive ? "success" : "muted"} size="sm">
                    {plan.isActive ? "Yes" : "No"}
                  </Badge>
                </td>
                <td class="text-center">
                  {#if plan.isPopular}
                    <Badge variant="accent" size="sm">Popular</Badge>
                  {:else}
                    <span class="text-text-muted">-</span>
                  {/if}
                </td>
                <td class="num text-text-secondary">{plan.sortOrder}</td>
                <td class="text-right">
                  <div class="flex gap-1 justify-end">
                    <button
                      class="text-xs px-2 py-1 rounded border transition-colors {editingId === plan.id ? 'border-accent bg-accent/10 text-[color:var(--color-accent-dark)]' : 'border-border hover:bg-bg-elevated text-text-secondary'}"
                      onclick={() => startEdit(plan.id)}
                    >
                      {editingId === plan.id ? "Close" : "Edit"}
                    </button>
                    <button
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                      onclick={() => toggleField(plan.id, "isActive", plan.isActive)}
                    >
                      {plan.isActive ? "Disable" : "Enable"}
                    </button>
                    <button
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                      onclick={() => toggleField(plan.id, "isPopular", plan.isPopular)}
                    >
                      {plan.isPopular ? "Unmark" : "Popular"}
                    </button>
                  </div>
                </td>
              </tr>
              {#if editingId === plan.id}
                <tr>
                  <td colspan="9" class="p-0">
                    <div class="bg-bg-surface border-t border-border p-5">
                      <h4 class="text-sm font-semibold text-text-primary mb-3">Edit Plan</h4>
                      {#if editError}
                        <div class="text-sm text-[color:var(--color-error-text)] mb-3 p-2 bg-error/10 rounded-lg">
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
                          <label for="edit-credits" class={labelClass}>Monthly credits</label>
                          <input id="edit-credits" type="number" bind:value={editMonthlyCredits} required min="0" class={inputClass} />
                          <p class="text-xs text-text-muted mt-1">0 = catalog access only.</p>
                        </div>
                        <div>
                          <label for="edit-price" class={labelClass}>Price (cents)</label>
                          <input id="edit-price" type="number" bind:value={editPriceInCents} required min="1" class={inputClass} />
                          <p class="text-xs text-text-muted mt-1">{formatPrice(editPriceInCents)} / month</p>
                        </div>
                        <div>
                          <label for="edit-trial" class={labelClass}>Trial days <span class="text-xs text-text-muted font-normal">(optional)</span></label>
                          <input id="edit-trial" type="number" value={editTrialDays ?? ""} oninput={(e) => {
                            const val = (e.target as HTMLInputElement).value;
                            editTrialDays = val ? parseInt(val) : null;
                          }} min="0" class={inputClass} />
                        </div>
                        <div>
                          <label for="edit-coupon" class={labelClass}>Stripe Coupon ID <span class="text-xs text-text-muted font-normal">(optional)</span></label>
                          <input id="edit-coupon" type="text" bind:value={editStripeCouponId} class={inputClass + " mono-field"} placeholder="coupon_..." />
                          <p class="text-xs text-text-muted mt-1">Auto-applied at checkout. Keep promo display fields consistent with it.</p>
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
                          <input id="edit-stripe-price" type="text" bind:value={editStripePriceId} required class={inputClass + " mono-field"} />
                          <p class="text-xs text-[color:var(--color-warning-text)] mt-1">Changing this points new subscriptions at a different Stripe price. Existing subscribers keep their current price until they switch plans via the portal.</p>
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
      {#if data.plansData.plans.length === 0}
        <div class="p-8 text-center text-text-muted">No plans yet.</div>
      {/if}
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load plans.</p>
    </div>
  {/if}
</div>

<style>
  /* .input's font-family is unlayered global CSS, so a Tailwind font-mono
     utility can't win against it (cascade layers rank utilities below
     unlayered rules) — this scoped class out-specificities it instead. */
  .mono-field {
    font-family: var(--font-mono);
  }

  /* .data-table td's color is unlayered global CSS, so a Tailwind text-color
     utility can't win against it (cascade layers rank utilities below
     unlayered rules) — these scoped classes out-specificity it instead. */
  .cell-primary {
    color: var(--color-text-primary);
  }
  .cell-muted {
    color: var(--color-text-muted);
  }
</style>
