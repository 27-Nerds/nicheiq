<script lang="ts">
  import {
    Check,
    Plus,
    Star,
    Gift,
    Layers,
    Coins,
  } from "lucide-svelte";
  import type { Snippet } from "svelte";
  import type { TokenPackage } from "$lib/types/billing";

  interface Props {
    pkg: TokenPackage;
    variant?: "full" | "compact";
    actions?: Snippet;
  }

  let { pkg, variant = "full", actions }: Props = $props();

  const badgeText = $derived(pkg.badgeLabel || (pkg.isPopular ? "Most Popular" : null));
  const hasBadges = $derived(!!badgeText || !!pkg.promoBadge);

  function formatPrice(cents: number): string {
    const dollars = cents / 100;
    return dollars % 1 === 0 ? `$${dollars}` : `$${dollars.toFixed(2)}`;
  }
</script>

<div
  class="relative bg-bg-elevated border rounded-xl overflow-hidden flex flex-col transition-colors {pkg.isPopular
    ? 'border-accent ring-1 ring-accent/20'
    : 'border-border'} hover:border-border-emphasis hover:shadow-md"
>
  <!-- Promo Badge (top-left) -->
  {#if pkg.promoBadge}
    <div
      class="absolute top-0 left-0 rounded-full bg-success/10 text-success ring-1 ring-success/20 text-xs font-semibold px-3 py-1 m-3"
    >
      {pkg.promoBadge}
    </div>
  {/if}

  <!-- Popular/Custom Badge (top-right) -->
  {#if badgeText}
    <div class="absolute top-0 right-0 m-3">
      <span
        class="rounded-full bg-accent text-white text-xs font-semibold px-3 py-1 flex items-center gap-1"
      >
        <Star class="w-3 h-3" />
        {badgeText}
      </span>
    </div>
  {/if}

  <!-- Content area -->
  <div class="p-7 sm:p-9 flex-1 text-left {hasBadges ? 'pt-10' : ''}">
    <!-- Name -->
    <p class="text-xs uppercase tracking-wider text-text-muted font-medium">{pkg.name}</p>

    <!-- Tagline / Description -->
    {#if variant === "full"}
      {#if pkg.tagline}
        <p class="text-base sm:text-lg font-bold text-text-primary mt-2">{pkg.tagline}</p>
      {/if}
      {#if pkg.description}
        <p class="text-sm text-text-muted mt-1.5 leading-relaxed">{pkg.description}</p>
      {/if}
    {:else}
      {#if pkg.tagline}
        <p class="text-sm text-text-muted mt-1">{pkg.tagline}</p>
      {:else if pkg.description}
        <p class="text-sm text-text-muted mt-1">{pkg.description}</p>
      {/if}
    {/if}

    <!-- Price block -->
    <div class="flex items-baseline gap-2 mt-3">
      {#if pkg.promoPriceInCents}
        <span class="text-lg font-display text-text-muted line-through">{formatPrice(pkg.priceInCents)}</span>
        <span class="text-[2.75rem] sm:text-5xl font-display font-bold text-success leading-tight">{formatPrice(pkg.promoPriceInCents)}</span>
      {:else}
        <span class="text-[2.75rem] sm:text-5xl font-display font-bold text-text-primary leading-tight">{formatPrice(pkg.priceInCents)}</span>
      {/if}
    </div>

    <!-- Credits line -->
    <div class="flex items-center gap-2 text-sm text-text-muted mt-1">
      <Coins class="w-4 h-4 text-accent" />
      <span class="font-bold text-text-primary">{pkg.credits}</span>
      <span>{pkg.credits === 1 ? "credit" : "credits"}</span>
    </div>

    <!-- Credits info -->
    {#if variant === "compact" && pkg.creditsInfo}
      <p class="text-xs text-text-muted mt-2">{pkg.creditsInfo}</p>
    {/if}

    <!-- Includes label -->
    {#if pkg.includesLabel}
      <div class="mt-5 flex items-center gap-2">
        <span class="flex items-center gap-1.5 text-xs font-medium text-text-muted bg-accent/[0.06] px-2 py-0.5 rounded">
          <Layers class="w-4 h-4 text-accent" />
          {pkg.includesLabel}
        </span>
      </div>
    {/if}

    <!-- Feature list (full variant only) -->
    {#if variant === "full" && pkg.features && pkg.features.length > 0}
      <div class="mt-5 space-y-2.5">
        {#each pkg.features as feature}
          <div class="flex items-center gap-3 {feature.highlight ? 'text-accent font-semibold' : 'text-text-secondary'}">
            <span class="flex-shrink-0 {feature.highlight ? 'text-accent' : 'text-accent/70'}">
              {#if feature.icon === 'star'}
                <Star class="w-4 h-4" />
              {:else if feature.icon === 'plus'}
                <Plus class="w-4 h-4" />
              {:else}
                <Check class="w-4 h-4" />
              {/if}
            </span>
            <span class="text-sm leading-snug">{feature.text}</span>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Promo line -->
    {#if pkg.promoLine}
      <div class="flex items-center gap-1.5 text-xs font-semibold text-accent bg-accent/[0.06] border border-accent/20 rounded-full px-3 py-1.5 mt-5 w-fit">
        <Gift class="w-3.5 h-3.5 flex-shrink-0" />
        <span>{pkg.promoLine}</span>
      </div>
    {/if}
  </div>

  <!-- CTA area -->
  <div class="px-7 sm:px-9 pb-7 sm:pb-9 mt-auto">
    {#if actions}
      {@render actions()}
    {/if}

    {#if pkg.ctaSubText && pkg.ctaSubUrl}
      <a href={pkg.ctaSubUrl} class="block text-xs text-accent hover:underline mt-3">{pkg.ctaSubText}</a>
    {/if}
  </div>
</div>
