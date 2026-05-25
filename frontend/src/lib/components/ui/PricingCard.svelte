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
  import type { TokenPackage, SubscriptionPlan, FeatureItem } from "$lib/types/billing";

  interface Props {
    // One-time package (legacy / default)
    pkg?: TokenPackage;
    // Recurring subscription plan
    plan?: SubscriptionPlan;
    variant?: "full" | "compact";
    actions?: Snippet;
  }

  let { pkg, plan, variant = "full", actions }: Props = $props();

  // Discriminate by which prop is provided.
  const isPlan = $derived(!!plan);

  // Normalized shape shared by both kinds. For plans, `credits` carries
  // monthlyCredits; the credits-line rendering handles the recurring framing.
  interface NormalizedCard {
    name: string;
    description: string | null;
    credits: number;
    priceInCents: number;
    isPopular: boolean;
    tagline: string | null;
    includesLabel: string | null;
    creditsInfo: string | null;
    features: FeatureItem[] | null;
    badgeLabel: string | null;
    promoLine: string | null;
    promoPriceInCents: number | null;
    promoBadge: string | null;
    ctaSubText: string | null;
    ctaSubUrl: string | null;
    interval: string | null;
  }

  const card = $derived<NormalizedCard>(
    plan
      ? {
          name: plan.name,
          description: plan.description,
          credits: plan.monthlyCredits,
          priceInCents: plan.priceInCents,
          isPopular: plan.isPopular,
          tagline: plan.tagline,
          includesLabel: plan.includesLabel,
          creditsInfo: plan.creditsInfo,
          features: plan.features,
          badgeLabel: plan.badgeLabel,
          promoLine: plan.promoLine,
          promoPriceInCents: plan.promoPriceInCents,
          promoBadge: plan.promoBadge,
          ctaSubText: plan.ctaSubText,
          ctaSubUrl: plan.ctaSubUrl,
          interval: plan.interval,
        }
      : {
          name: pkg!.name,
          description: pkg!.description,
          credits: pkg!.credits,
          priceInCents: pkg!.priceInCents,
          isPopular: pkg!.isPopular,
          tagline: pkg!.tagline,
          includesLabel: pkg!.includesLabel,
          creditsInfo: pkg!.creditsInfo,
          features: pkg!.features,
          badgeLabel: pkg!.badgeLabel,
          promoLine: pkg!.promoLine,
          promoPriceInCents: pkg!.promoPriceInCents,
          promoBadge: pkg!.promoBadge,
          ctaSubText: pkg!.ctaSubText,
          ctaSubUrl: pkg!.ctaSubUrl,
          interval: null,
        },
  );

  const badgeText = $derived(card.badgeLabel || (card.isPopular ? "Most Popular" : null));
  const hasBadges = $derived(!!badgeText || !!card.promoBadge);
  // A subscription with 0 monthly credits is catalog-access-only.
  const catalogOnly = $derived(isPlan && card.credits === 0);

  function formatPrice(cents: number): string {
    const dollars = cents / 100;
    return dollars % 1 === 0 ? `$${dollars}` : `$${dollars.toFixed(2)}`;
  }

  // "/mo" for monthly plans, blank otherwise.
  const intervalSuffix = $derived(card.interval === "month" ? "/mo" : "");
</script>

<div
  class="relative bg-bg-elevated border rounded-xl overflow-hidden flex flex-col transition-all {card.isPopular
    ? 'border-accent ring-1 ring-accent/20'
    : 'border-border'} hover:border-border-emphasis hover:shadow-[0_1px_2px_rgba(24,24,27,0.04),0_4px_12px_rgba(24,24,27,0.06)]"
>
  <!-- Promo Badge (top-left) -->
  {#if card.promoBadge}
    <div
      class="absolute top-0 left-0 rounded-full bg-success/10 text-success ring-1 ring-success/20 text-xs font-semibold px-3 py-1 m-3"
    >
      {card.promoBadge}
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
    <p class="text-xs uppercase tracking-wider text-text-muted font-medium">{card.name}</p>

    <!-- Tagline / Description -->
    {#if variant === "full"}
      {#if card.tagline}
        <p class="text-base sm:text-lg font-bold text-text-primary mt-2">{card.tagline}</p>
      {/if}
      {#if card.description}
        <p class="text-sm text-text-muted mt-1.5 leading-relaxed">{card.description}</p>
      {/if}
    {:else}
      {#if card.tagline}
        <p class="text-sm text-text-muted mt-1">{card.tagline}</p>
      {:else if card.description}
        <p class="text-sm text-text-muted mt-1">{card.description}</p>
      {/if}
    {/if}

    <!-- Price block -->
    <div class="flex items-baseline gap-2 mt-3">
      {#if card.promoPriceInCents}
        <span class="text-lg font-display text-text-muted line-through">{formatPrice(card.priceInCents)}{intervalSuffix}</span>
        <span class="text-[2.75rem] sm:text-5xl font-display font-bold text-success leading-tight">{formatPrice(card.promoPriceInCents)}</span>
        {#if intervalSuffix}<span class="text-base text-text-muted font-medium">{intervalSuffix}</span>{/if}
      {:else}
        <span class="text-[2.75rem] sm:text-5xl font-display font-bold text-text-primary leading-tight">{formatPrice(card.priceInCents)}</span>
        {#if intervalSuffix}<span class="text-base text-text-muted font-medium">{intervalSuffix}</span>{/if}
      {/if}
    </div>

    <!-- Credits line -->
    <div class="flex items-center gap-2 text-sm text-text-muted mt-1">
      {#if catalogOnly}
        <Layers class="w-4 h-4 text-accent" />
        <span class="font-medium text-text-primary">Full catalog access</span>
      {:else}
        <Coins class="w-4 h-4 text-accent" />
        <span class="font-mono tabular-nums font-bold text-text-primary"
          >{card.credits}</span
        >
        <span>{card.credits === 1 ? "credit" : "credits"}{isPlan ? "/mo" : ""}</span>
      {/if}
    </div>

    <!-- Credits info -->
    {#if variant === "compact" && card.creditsInfo}
      <p class="text-xs text-text-muted mt-2">{card.creditsInfo}</p>
    {/if}

    <!-- Includes label -->
    {#if card.includesLabel}
      <div class="mt-5 flex items-center gap-2">
        <span class="flex items-center gap-1.5 text-xs font-medium text-text-muted bg-accent/[0.06] px-2 py-0.5 rounded">
          <Layers class="w-4 h-4 text-accent" />
          {card.includesLabel}
        </span>
      </div>
    {/if}

    <!-- Feature list (full variant only) -->
    {#if variant === "full" && card.features && card.features.length > 0}
      <div class="mt-5 space-y-2.5">
        {#each card.features as feature}
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
    {#if card.promoLine}
      <div class="flex items-center gap-1.5 text-xs font-semibold text-accent bg-accent/[0.06] border border-accent/20 rounded-full px-3 py-1.5 mt-5 w-fit">
        <Gift class="w-3.5 h-3.5 flex-shrink-0" />
        <span>{card.promoLine}</span>
      </div>
    {/if}
  </div>

  <!-- CTA area -->
  <div class="px-7 sm:px-9 pb-7 sm:pb-9 mt-auto">
    {#if actions}
      {@render actions()}
    {/if}

    {#if card.ctaSubText && card.ctaSubUrl}
      <a href={card.ctaSubUrl} class="block text-xs text-accent hover:underline mt-3">{card.ctaSubText}</a>
    {/if}
  </div>
</div>
