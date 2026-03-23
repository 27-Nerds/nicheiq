<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import {
    ArrowRight,
    Loader2,
    AlertCircle,
    Coins,
    Shuffle,
    PenLine,
    SlidersHorizontal,
    ChevronUp,
    ChevronDown,
    CheckCircle2,
    Lightbulb,
    Users,
    TrendingUp,
  } from "lucide-svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import EntryModeCards from "$lib/components/new-research/EntryModeCards.svelte";
  import { MODE_COLORS } from "$lib/components/new-research/EntryModeCards.svelte";
  import CatalogTrendingGrid from "$lib/components/new-research/CatalogTrendingGrid.svelte";
  import ProcessTimeline from "$lib/components/new-research/ProcessTimeline.svelte";
  import StickyCtaBar from "$lib/components/new-research/StickyCtaBar.svelte";
  import { DEFAULT_STAGE_COSTS } from "$lib/types/job";
  import type { StageCosts } from "$lib/types/job";
  import type { EntryMode } from "$lib/components/new-research/EntryModeCards.svelte";

  let { data } = $props();

  const MAX_NICHE_LENGTH = 500;
  const PENDING_RESEARCH_KEY = 'nicheiq:pendingResearch';

  function saveFormState() {
    sessionStorage.setItem(PENDING_RESEARCH_KEY, JSON.stringify({
      niche,
      entryMode,
      selectedProjectTypes,
      savedAt: Date.now(),
    }));
  }

  // --- State ---
  let userEdited = $state(false);

  // --- Mode state ---
  let entryMode = $state<EntryMode>("idea");

  onMount(() => {
    // Restore from session storage (returning from billing)
    const saved = sessionStorage.getItem(PENDING_RESEARCH_KEY);
    if (saved) {
      sessionStorage.removeItem(PENDING_RESEARCH_KEY);
      try {
        const state = JSON.parse(saved);
        if (Date.now() - state.savedAt > 3_600_000) return; // expire after 1h
        niche = state.niche ?? '';
        entryMode = state.entryMode ?? 'idea';
        if (Array.isArray(state.selectedProjectTypes)) {
          selectedProjectTypes = state.selectedProjectTypes;
        }
        // Auto-focus on billing return (desktop only)
        if (niche && window.innerWidth >= 768) {
          requestAnimationFrame(() => textareaEl?.focus());
        }
      } catch {}
    }
  });

  // --- Credit data from layout ---
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  const stageCosts = $derived(
    (page.data.stageCosts as StageCosts) ?? DEFAULT_STAGE_COSTS,
  );
  const hasCredits = $derived(creditBalance >= stageCosts.discovery);
  const showCreditBalance = $derived(creditBalance < stageCosts.discovery * 2);

  // --- Project types ---
  const PROJECT_TYPES = [
    { value: "saas", label: "SaaS" },
    { value: "directory", label: "Directory" },
    { value: "aggregator", label: "Aggregator" },
    { value: "comparison-tool", label: "Comparison Tool" },
    { value: "marketplace", label: "Marketplace" },
  ] as const;

  let selectedProjectTypes = $state<string[]>(
    PROJECT_TYPES.map((t) => t.value),
  );
  let showProjectTypes = $state(false);

  function toggleProjectType(value: string) {
    if (selectedProjectTypes.includes(value)) {
      selectedProjectTypes = selectedProjectTypes.filter((t) => t !== value);
    } else {
      selectedProjectTypes = [...selectedProjectTypes, value];
    }
  }

  const projectTypeCountLabel = $derived(
    selectedProjectTypes.length === PROJECT_TYPES.length
      ? "All"
      : `${selectedProjectTypes.length} selected`,
  );

  // --- Input state ---
  let niche = $state("");
  let loading = $state(false);
  let error = $state("");
  let isInsufficientCredits = $state(false);

  // --- Textarea ref + catalog feedback ---
  let textareaEl = $state<HTMLTextAreaElement | null>(null);
  let catalogJustSelected = $state(false);
  let catalogHighlightTimer = $state<ReturnType<typeof setTimeout> | null>(null);
  let textareaFocused = $state(false);
  let pillsHeight = $state(0);

  // --- Sticky CTA ---
  let ctaBarVisible = $state(false);
  let sentinelEl = $state<HTMLDivElement | null>(null);
  let ctaEndEl = $state<HTMLDivElement | null>(null);
  let ctaAboveViewport = $state(false);
  let ctaEndInView = $state(true);

  // --- Submit success flash ---
  let showSuccess = $state(false);

  $effect(() => {
    if (!sentinelEl || !ctaEndEl) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.target === sentinelEl) ctaAboveViewport = !entry.isIntersecting;
          if (entry.target === ctaEndEl) ctaEndInView = entry.isIntersecting;
        }
      },
      { threshold: 0 },
    );
    observer.observe(sentinelEl);
    observer.observe(ctaEndEl);
    return () => observer.disconnect();
  });

  // Show sticky bar only when CTA is scrolled past AND bottom of CTA block isn't visible
  $effect(() => { ctaBarVisible = ctaAboveViewport && !ctaEndInView; });

  // --- Suggest state ---
  let suggestLoading = $state(false);
  let suggestMode = $state<"lucky" | "complete" | null>(null);
  let suggestError = $state("");

  // --- Mode-specific config ---
  const modeConfig = $derived(
    {
      idea: {
        label: "What's your idea?",
        icon: Lightbulb,
        colorClass: "text-accent",
        glowColors: MODE_COLORS.idea,
        placeholder:
          "e.g., Shopify store owners struggling with abandoned cart recovery",
        helpText:
          "The more specific, the better. Name the exact problem or solution you're testing.",
        examples: [
          "Freelance dev admin tools",
          "Small gym vs big chains",
          "Solo recruiter scaling",
          "Real estate lead gen",
        ],
        qualityTiers: {
          bad: { label: "Too vague", example: "Fitness apps" },
          better: { label: "Better", example: "Fitness app for busy professionals" },
          best: { label: "Perfect", example: "Busy professionals struggling to find 10-minute workouts" },
        },
      },
      audience: {
        label: "Who are you building for?",
        icon: Users,
        colorClass: "text-indigo-500",
        glowColors: MODE_COLORS.audience,
        placeholder:
          "e.g., Solo content creators with 10k+ followers struggling to monetize",
        helpText:
          "Tell us who they are and what gets under their skin. We'll find what they're talking about.",
        examples: [
          "Creator monetization",
          "Freelance writer burnout",
          "Remote team async",
          "Bootstrapped founders",
        ],
        qualityTiers: {
          bad: { label: "Too vague", example: "Content creators" },
          better: { label: "Better", example: "Content creators who want to monetize" },
          best: { label: "Perfect", example: "Solo content creators with 10k+ followers struggling to monetize" },
        },
      },
      discovery: {
        label: "What's capturing your attention?",
        icon: TrendingUp,
        colorClass: "text-emerald-500",
        glowColors: MODE_COLORS.discovery,
        placeholder:
          "e.g., AI tools, remote work, creator economy, health tech",
        helpText:
          "Give us a broad topic. We'll surface emerging problems and ideas within it.",
        examples: [
          "AI for small biz",
          "Creator economy",
          "Remote work tools",
          "Health tech",
        ],
        qualityTiers: {
          bad: { label: "Too vague", example: "Technology" },
          better: { label: "Better", example: "AI tools" },
          best: { label: "Perfect", example: "AI tools for small business inventory management" },
        },
      },
    }[entryMode],
  );

  // --- Glow border active state ---
  const glowActive = $derived(niche.trim().length > 0);

  // --- Mode icon (derived for use in template without @const) ---
  const ModeIcon = $derived(modeConfig.icon);

  // --- Catalog selection (Mode 3) ---
  function handleCatalogSelect(text: string) {
    niche = text;
    userEdited = true;
    if (catalogHighlightTimer) clearTimeout(catalogHighlightTimer);
    catalogJustSelected = true;
    textareaEl?.scrollIntoView({ behavior: "smooth", block: "center" });
    catalogHighlightTimer = setTimeout(() => { catalogJustSelected = false; }, 700);
  }

  // --- Textarea input handler ---
  function handleTextareaInput() {
    userEdited = true;
  }

  // --- Surprise me ---
  async function handleFeelingLucky() {
    suggestLoading = true;
    suggestMode = "lucky";
    suggestError = "";

    try {
      const res = await fetch("/api/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "feeling_lucky", count: 1 }),
      });
      const data = await res.json();
      if (!res.ok) {
        suggestError =
          res.status === 429
            ? `Too many requests. Try again in ${Math.ceil((data.retryAfter || 3600) / 60)} minutes.`
            : data.error ||
              "Could not generate a suggestion. Please try again.";
        return;
      }
      if (data.suggestions?.[0]?.niche) {
        niche = data.suggestions[0].niche;
        userEdited = true;
      }
    } catch {
      suggestError = "Connection error. Please try again.";
    } finally {
      suggestLoading = false;
      suggestMode = null;
    }
  }

  // --- Refine input ---
  async function handleExpandThis() {
    if (!niche.trim()) return;
    suggestLoading = true;
    suggestMode = "complete";
    suggestError = "";

    try {
      const res = await fetch("/api/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "auto_complete",
          partial_input: niche.trim(),
          count: 1,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        suggestError =
          res.status === 429
            ? `Too many requests. Try again in ${Math.ceil((data.retryAfter || 3600) / 60)} minutes.`
            : data.error || "Could not refine your input. Please try again.";
        return;
      }
      if (data.suggestions?.[0]?.niche) {
        niche = data.suggestions[0].niche;
      }
    } catch {
      suggestError = "Connection error. Please try again.";
    } finally {
      suggestLoading = false;
      suggestMode = null;
    }
  }

  // --- Submit ---
  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!niche.trim() || loading) return;

    loading = true;
    error = "";
    isInsufficientCredits = false;

    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          niche: niche.trim(),
          ...(selectedProjectTypes.length > 0 && {
            allowedProjectTypes: selectedProjectTypes,
          }),
          entryMode,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 402 && data.code === "INSUFFICIENT_CREDITS") {
          isInsufficientCredits = true;
          error = "You need credits to start a new research.";
          await invalidateAll();
          return;
        }
        const detail = data.details?.[0]?.message;
        throw new Error(detail || data.error || "Failed to start research");
      }

      // Success flash before redirect
      showSuccess = true;
      setTimeout(() => {
        goto(`/jobs/${data.id}`, { invalidateAll: true });
      }, 800);
    } catch (err) {
      error = err instanceof Error ? err.message : "Something went wrong";
    } finally {
      if (!showSuccess) loading = false;
    }
  }
</script>

<svelte:head>
  <title>New Research - NicheIQ</title>
</svelte:head>

<div class="relative min-h-[calc(100dvh-3.5rem)]">
  <!-- Subtle background depth -->
  <div class="absolute inset-0 bg-radial-amber opacity-40"></div>

  <div class="relative" class:pb-28={ctaBarVisible}>
    <!-- Header -->
    <div class="text-center pt-10 sm:pt-14 pb-2 px-6">
      <p class="text-xs text-text-muted mb-4">
        <a href="/dashboard" class="hover:text-accent transition-colors">Dashboard</a>
        <span class="mx-1.5 opacity-40">/</span>
        <span>New Research</span>
      </p>
      <h1 class="font-display text-2xl sm:text-3xl font-bold tracking-tight text-text-primary mb-2">
        New research
      </h1>
      <p class="text-text-muted text-sm max-w-md mx-auto">
        Tell us what you're exploring. Pick a starting point below.
      </p>
    </div>

    <!-- Mode pills (centered) -->
    <div class="flex justify-center mb-6 px-6">
      <EntryModeCards selected={entryMode} onselect={(mode) => entryMode = mode} />
    </div>

    <!-- Focused form area -->
    <div class="{entryMode === 'discovery' ? 'max-w-3xl' : 'max-w-2xl'} mx-auto px-4 sm:px-6">
      <form onsubmit={handleSubmit}>
        <!-- Catalog Grid (discovery mode only) + connector -->
        {#if entryMode === "discovery"}
          <div class="animate-fade-in mt-2">
            <CatalogTrendingGrid
              painPoints={data.catalogPainPoints}
              ideas={data.catalogIdeas}
              hasCatalogData={data.hasCatalogData}
              onselect={handleCatalogSelect}
              onsurprise={handleFeelingLucky}
              surpriseLoading={suggestLoading && suggestMode === "lucky"}
            />
            <!-- Visual connector -->
            <div class="flex items-center gap-3 my-4 text-text-muted">
              <div class="flex-1 border-t border-border"></div>
              <span class="text-xs">Or describe your own topic</span>
              <div class="flex-1 border-t border-border"></div>
            </div>
          </div>
        {/if}

        <!-- Input card with animated glow border -->
        <div
          class="glow-border-wrapper {entryMode !== 'discovery' ? 'mt-2' : ''} {glowActive ? 'ui-shadow-md' : 'ui-shadow-sm'}"
          class:glow-active={glowActive}
          style="--glow-color-1: {modeConfig.glowColors.c1}; --glow-color-2: {modeConfig.glowColors.c2}"
        >
          <div class="glow-border-inner p-6 sm:p-8">
            <label
              for="niche"
              class="flex items-center gap-2 text-sm font-medium text-text-primary mb-3"
            >
              <ModeIcon class="w-4 h-4 {modeConfig.colorClass}" />
              {modeConfig.label}
            </label>

            <!-- Textarea with pills overlay -->
            <div class="relative">
              <textarea
                id="niche"
                bind:value={niche}
                bind:this={textareaEl}
                rows={3}
                maxlength={MAX_NICHE_LENGTH}
                class="w-full resize-none text-lg bg-bg-elevated border border-border/40 rounded-lg
                       px-4 py-3 min-h-[100px] placeholder:text-text-muted/50
                       focus:outline-none focus:border-accent/30
                       transition-colors duration-200
                       disabled:opacity-50 disabled:cursor-not-allowed
                       {catalogJustSelected ? 'ring-2 ring-accent' : ''}"
                style={!niche.trim() && pillsHeight ? `padding-bottom: ${pillsHeight + 16}px` : ''}
                placeholder={modeConfig.placeholder}
                disabled={loading || showSuccess}
                onfocus={() => textareaFocused = true}
                onblur={() => textareaFocused = false}
                oninput={handleTextareaInput}
              ></textarea>

              {#if !niche.trim()}
                <div
                  bind:clientHeight={pillsHeight}
                  class="absolute bottom-2 left-2 right-2 z-10 pointer-events-none
                         flex items-center gap-1.5 overflow-x-auto scrollbar-none"
                  role="group"
                  aria-label="Example suggestions"
                >
                  {#each modeConfig.examples.slice(0, 3) as example}
                    <button
                      type="button"
                      onclick={() => { niche = example; userEdited = true; }}
                      disabled={loading || showSuccess}
                      aria-label="Insert example: {example}"
                      class="pointer-events-auto shrink-0 text-[11px] px-2.5 py-1.5 rounded-full border border-border/50 bg-bg-elevated
                             hover:border-border-emphasis text-text-muted hover:text-text-secondary
                             transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {example}
                    </button>
                  {/each}
                  {#if entryMode !== "discovery"}
                    <button
                      type="button"
                      onclick={handleFeelingLucky}
                      disabled={loading || suggestLoading || showSuccess}
                      aria-label="Generate random topic"
                      class="pointer-events-auto shrink-0 text-[11px] px-2.5 py-1.5 rounded-full border border-border/50 bg-bg-elevated
                             hover:border-border-emphasis text-text-muted hover:text-text-secondary
                             transition-colors flex items-center gap-1
                             disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {#if suggestLoading && suggestMode === "lucky"}
                        <Loader2 class="w-3 h-3 animate-spin" />
                      {:else}
                        <Shuffle class="w-3 h-3" />
                      {/if}
                      Random
                    </button>
                  {/if}
                </div>
              {/if}
            </div>

            <div class="flex items-center justify-between mt-1.5">
              <p class="text-xs text-text-muted">{modeConfig.helpText}</p>
              {#if niche.length > 0}
                <span
                  class="text-xs tabular-nums shrink-0 ml-2 {niche.length > MAX_NICHE_LENGTH * 0.9
                    ? 'text-warning'
                    : 'text-text-muted'}"
                >
                  {niche.length}/{MAX_NICHE_LENGTH}
                </span>
              {/if}
            </div>

            <!-- Quality tiers hint -->
            <p class="text-xs text-text-muted mt-1.5">
              <span class="line-through opacity-60">{modeConfig.qualityTiers.bad.example}</span>
              <span class="mx-1 opacity-30">&rarr;</span>
              <span class="text-text-secondary">{modeConfig.qualityTiers.best.example}</span>
            </p>

            <!-- Refine (when text present) -->
            {#if niche.trim()}
              <div class="mt-2">
                <button
                  type="button"
                  onclick={handleExpandThis}
                  disabled={loading || suggestLoading || showSuccess}
                  class="pressable text-xs px-3 py-1.5 rounded-md border border-border bg-bg-elevated
                         hover:border-border-emphasis text-text-secondary
                         transition-colors flex items-center gap-1.5
                         disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {#if suggestLoading && suggestMode === "complete"}
                    <Loader2 class="w-3 h-3 animate-spin" />
                    Refining...
                  {:else}
                    <PenLine class="w-3 h-3" />
                    Refine
                  {/if}
                </button>
              </div>
            {/if}

            {#if suggestError}
              <p class="text-xs text-error mt-2">{suggestError}</p>
            {/if}

            <!-- Project types (collapsed) -->
            <div class="mt-4">
              <button type="button" onclick={() => showProjectTypes = !showProjectTypes}
                class="w-full flex items-center justify-between text-sm text-text-secondary hover:text-text-primary transition-colors">
                <span class="flex items-center gap-2">
                  <SlidersHorizontal class="w-3.5 h-3.5" />
                  <span class="font-medium">What kind of business?</span>
                </span>
                <span class="flex items-center gap-2">
                  <span class="text-xs text-text-muted">{projectTypeCountLabel}</span>
                  {#if showProjectTypes}<ChevronUp class="w-4 h-4" />{:else}<ChevronDown class="w-4 h-4" />{/if}
                </span>
              </button>
              {#if showProjectTypes}
                <div class="flex flex-wrap gap-2 mt-3">
                  {#each PROJECT_TYPES as type}
                    <button
                      type="button"
                      onclick={() => toggleProjectType(type.value)}
                      disabled={loading || showSuccess}
                      class="text-xs px-3 py-1.5 rounded-md border transition-colors
                             {selectedProjectTypes.includes(type.value)
                        ? 'bg-accent/10 border-accent/40 text-accent font-medium'
                        : 'bg-bg-elevated border-border text-text-muted hover:border-border-emphasis hover:text-text-secondary'}
                             disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {type.label}
                    </button>
                  {/each}
                </div>
              {/if}
            </div>

            <!-- Submit (inside card) -->
            <div class="mt-5 pt-5 border-t border-border/40">
              <!-- Sentinel for IntersectionObserver -->
              <div bind:this={sentinelEl}></div>

              {#if error}
                <div
                  class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm mb-4"
                >
                  <AlertCircle class="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                  {#if isInsufficientCredits}
                    <a
                      href="/billing"
                      onclick={saveFormState}
                      class="ml-auto text-accent hover:underline text-xs"
                    >
                      Get credits
                    </a>
                  {/if}
                </div>
              {/if}

              {#if showSuccess}
                <div class="w-full py-3 rounded-lg bg-success/10 border border-success/20 text-success text-base font-medium text-center flex items-center justify-center gap-2 transition-all duration-300">
                  <CheckCircle2 class="w-5 h-5" />
                  Analyzing {niche.length > 30 ? niche.slice(0, 30) + '\u2026' : niche}...
                </div>
              {:else if hasCredits}
                <SubmitButton
                  {loading}
                  loadingText="Starting..."
                  icon={ArrowRight}
                  iconPosition="end"
                  label="Start research ({stageCosts.discovery} credits)"
                  disabled={!niche.trim()}
                  class="btn-primary w-full justify-center text-base py-3"
                />
              {:else}
                <Button
                  href="/billing"
                  onclick={saveFormState}
                  icon={Coins}
                  label="Get {stageCosts.discovery} Credits to Start"
                  class="btn-primary w-full justify-center text-base py-3"
                />
              {/if}

              <p class="text-xs text-text-muted text-center mt-2">
                {stageCosts.discovery} credits for discovery &middot; you review ideas before full validation
              </p>

              <!-- End sentinel -->
              <div bind:this={ctaEndEl}></div>
            </div>
          </div>
        </div>

        <!-- Below-card info -->
        <div class="space-y-2 mt-6 text-center">
          {#if showCreditBalance}
            {#if hasCredits}
              <p class="text-xs text-text-muted flex items-center justify-center gap-1.5">
                <Coins class="w-3 h-3 text-accent" />
                <span class="tabular-nums">{creditBalance}</span> credits available
              </p>
            {:else}
              <p class="text-xs text-warning flex items-center justify-center gap-1.5">
                <AlertCircle class="w-3 h-3" />
                You need {stageCosts.discovery} credits to start
              </p>
            {/if}
          {/if}
          <p class="text-xs">
            <a href="/sample-report" class="text-text-muted hover:text-text-secondary underline underline-offset-2 decoration-border">Sample report</a>
          </p>
        </div>

        <!-- ProcessTimeline -->
        <div class="mt-12 pt-8 border-t border-border/30">
          <ProcessTimeline />
        </div>

        <!-- Sticky CTA Bar -->
        <div class="!mt-0">
          <StickyCtaBar
            visible={ctaBarVisible && !textareaFocused}
            {niche}
            creditCost={stageCosts.discovery}
            {loading}
            disabled={!niche.trim()}
            {hasCredits}
            stageCost={stageCosts.discovery}
            onsave={saveFormState}
          />
        </div>
      </form>
    </div>
  </div>
</div>
