<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import {
    ArrowRight,
    Loader2,
    AlertCircle,
    Coins,
    Shuffle,
    WandSparkles,
    CheckCircle2,
    ChevronDown,
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
  import InputQualityMeter from "$lib/components/new-research/InputQualityMeter.svelte";
  import { DEFAULT_STAGE_COSTS } from "$lib/types/job";
  import type { StageCosts } from "$lib/types/job";
  import type { EntryMode } from "$lib/components/new-research/EntryModeCards.svelte";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";

  let { data } = $props();

  const MAX_NICHE_LENGTH = 500;

  // --- State ---
  let userEdited = $state(false);

  // --- Mode state ---
  let entryMode = $state<EntryMode>("idea");

  // --- Credit data from layout ---
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  const stageCosts = $derived(
    (page.data.stageCosts as StageCosts) ?? DEFAULT_STAGE_COSTS,
  );
  const hasCredits = $derived(creditBalance >= stageCosts.discovery);
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
  const projectTypeCountLabel = $derived(
    selectedProjectTypes.length === PROJECT_TYPES.length
      ? "All"
      : `${selectedProjectTypes.length} selected`,
  );
  function toggleProjectType(value: string) {
    if (selectedProjectTypes.includes(value)) {
      selectedProjectTypes = selectedProjectTypes.filter((t) => t !== value);
    } else {
      selectedProjectTypes = [...selectedProjectTypes, value];
    }
  }

  // --- Input state ---
  let niche = $state("");
  let loading = $state(false);
  let error = $state("");

  // --- Textarea ref ---
  let textareaEl = $state<HTMLTextAreaElement | null>(null);
  let textareaFocused = $state(false);

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
        label: "What niche are you exploring?",
        icon: Lightbulb,
        colorClass: "text-accent",
        glowColors: MODE_COLORS.idea,
        placeholders: [
          "e.g., Shopify store owners struggling with abandoned cart recovery",
          "e.g., Independent contractors who can't track expenses across clients",
          "e.g., Small bakeries losing walk-in customers to delivery apps",
          "e.g., Property managers drowning in maintenance request coordination",
          "e.g., Yoga studio owners competing with free YouTube workout videos",
        ],
        helpText:
          "The more specific, the better. Name the exact problem or solution you're testing.",
        examples: [
          "Freelance dev admin tools", "Small gym vs big chains", "Pet sitter scheduling",
          "Restaurant waste tracking", "Clinic no-show prevention", "Food truck route planning",
          "Salon booking automation", "Landlord tenant messaging", "Tutor parent updates",
          "Indie game dev marketing", "Solo recruiter scaling", "Real estate lead gen",
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
        placeholders: [
          "e.g., Solo content creators with 10k+ followers struggling to monetize",
          "e.g., First-time parents overwhelmed by conflicting baby care advice",
          "e.g., Part-time Etsy sellers who can't keep up with shipping logistics",
          "e.g., Junior developers feeling stuck after their first year on the job",
          "e.g., Retired professionals looking for meaningful part-time consulting",
        ],
        helpText:
          "Tell us who they are and what gets under their skin. We'll find what they're talking about.",
        examples: [
          "Bootstrapped founders", "Part-time Etsy sellers", "Solo consultants",
          "Homeschool parents", "Indie podcast hosts", "Local shop owners",
          "Junior developers", "Remote team leads", "First-time parents",
          "Retired professionals", "Nonprofit volunteers", "Freelance designers",
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
        placeholders: [
          "e.g., AI tools, remote work, creator economy, health tech",
          "e.g., Senior care technology, aging in place, caregiver burnout",
          "e.g., Local food systems, farm-to-table logistics, food waste",
          "e.g., Micro-SaaS, one-person startups, indie hacker tools",
          "e.g., Digital wellness, screen time, attention management apps",
        ],
        helpText:
          "Give us a broad topic. We'll surface emerging problems and ideas within it.",
        examples: [
          "AI for small biz", "Creator economy", "Remote work tools",
          "Health tech", "Senior care tech", "Local food systems",
          "Micro-SaaS", "Digital wellness", "Pet tech",
          "Climate adaptation", "Trade skills gap", "Solo aging",
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

  // --- Background atmosphere per mode ---
  const bgRadialClass = $derived(
    ({ idea: "bg-radial-amber", audience: "bg-radial-indigo", discovery: "bg-radial-emerald" } as const)[entryMode]
  );

  // --- Random example selection ---
  function pickRandom<T>(arr: readonly T[], count: number): T[] {
    const copy = [...arr];
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy.slice(0, count);
  }

  let displayedExamples = $state<string[]>([]);
  let displayedPlaceholder = $state("");
  $effect(() => {
    displayedExamples = pickRandom(modeConfig.examples, 3);
    displayedPlaceholder = pickRandom(modeConfig.placeholders, 1)[0];
  });

  // --- Catalog selection (Mode 3) ---
  function handleCatalogSelect(text: string) {
    niche = text;
    userEdited = true;
    textareaEl?.scrollIntoView({ behavior: "smooth", block: "center" });
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
          creditTopUp.show({
            balance: data.balance ?? 0,
            required: data.required ?? stageCosts.discovery,
            stageName: "discovery",
          });
          loading = false;
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
  <!-- Subtle background depth — shifts color with mode -->
  <div class="absolute inset-0 {bgRadialClass} opacity-40 transition-all duration-300"></div>

  <div class="relative pb-16" class:pb-28={ctaBarVisible}>
    <!-- Header -->
    <div class="text-center pt-10 sm:pt-14 pb-2 px-6">
      <p class="text-xs text-text-muted mb-4">
        <a href="/dashboard" class="hover:text-accent transition-colors">Dashboard</a>
        <span class="mx-1.5 opacity-40">/</span>
        <span>New Research</span>
      </p>
      <h1 class="font-display text-2xl sm:text-3xl font-bold tracking-tight text-text-primary mb-2" style="text-wrap: balance">
        New research
      </h1>
      <p class="text-text-muted text-sm max-w-md mx-auto">
        Tell us what you're exploring. Pick a starting point below.
      </p>
    </div>

    <!-- Mode cards -->
    <div class="max-w-3xl mx-auto mb-6 px-4 sm:px-6">
      <EntryModeCards selected={entryMode} onselect={(mode) => entryMode = mode} />
    </div>

    <!-- Focused form area -->
    <div class="max-w-2xl mx-auto px-4 sm:px-6">
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
          </div>
        {/if}

        <!-- Input card with animated glow border -->
        <div
          class="glow-border-wrapper mt-4 {glowActive ? 'ui-shadow-md' : 'ui-shadow-sm'}"
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
                class="w-full resize-none text-lg sm:text-xl bg-transparent
                       px-0 py-4 min-h-[120px] placeholder:text-text-muted/50
                       focus:outline-none focus-visible:outline-none
                       transition-colors duration-200
                       disabled:opacity-50 disabled:cursor-not-allowed"
                style={niche.trim() ? 'padding-right: 4rem' : ''}
                placeholder={displayedPlaceholder}
                disabled={loading || showSuccess}
                onfocus={() => textareaFocused = true}
                onblur={() => textareaFocused = false}
                oninput={handleTextareaInput}
              ></textarea>

              {#if !niche.trim()}
                <div class="absolute bottom-3 left-0 right-0 z-10 pointer-events-none">
                  <p class="text-xs text-text-secondary">
                    Try:
                    {#each displayedExamples as example, i}
                      {#if i > 0}<span class="mx-1 text-text-muted/40">·</span>{/if}
                      <button
                        type="button"
                        onclick={() => { niche = example; userEdited = true; }}
                        disabled={loading || showSuccess}
                        class="pointer-events-auto hover:text-text-primary underline underline-offset-2 decoration-border/50
                               hover:decoration-text-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {example}
                      </button>
                    {/each}
                  </p>
                </div>
              {:else}
                <!-- Floating text actions inside textarea -->
                <div class="absolute bottom-3 right-0 z-10 flex gap-1.5">
                  <button
                    type="button"
                    onclick={handleFeelingLucky}
                    disabled={loading || suggestLoading || showSuccess}
                    title="Try a different topic"
                    class="pressable pointer-events-auto w-8 h-8 flex items-center justify-center rounded-md
                           border border-border bg-bg-elevated text-text-muted
                           hover:border-border-emphasis hover:text-text-primary
                           transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {#if suggestLoading && suggestMode === "lucky"}
                      <Loader2 class="w-4 h-4 animate-spin" />
                    {:else}
                      <Shuffle class="w-4 h-4" />
                    {/if}
                  </button>
                  <button
                    type="button"
                    onclick={handleExpandThis}
                    disabled={loading || suggestLoading || showSuccess}
                    title="Refine with AI"
                    class="pressable pointer-events-auto w-8 h-8 flex items-center justify-center rounded-md
                           border border-border bg-bg-elevated text-text-muted
                           hover:border-border-emphasis hover:text-text-primary
                           transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {#if suggestLoading && suggestMode === "complete"}
                      <Loader2 class="w-4 h-4 animate-spin" />
                    {:else}
                      <WandSparkles class="w-4 h-4" />
                    {/if}
                  </button>
                </div>
              {/if}
            </div>

            <!-- Help text / quality hint (single row, swaps content) -->
            <div class="flex items-center justify-between mt-1.5">
              <InputQualityMeter {niche} qualityTiers={modeConfig.qualityTiers} helpText={modeConfig.helpText} />
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

            {#if suggestError}
              <p class="text-xs text-error mt-1.5">{suggestError}</p>
            {/if}
          </div>
        </div>

        <!-- Submit section (outside glow card) -->
        <div class="mt-4 px-1">
          <div class="mb-4">
            <button
              type="button"
              onclick={() => showProjectTypes = !showProjectTypes}
              class="text-xs text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1"
            >
              <span class="font-medium">Business types</span>
              <span>·</span>
              <span>{projectTypeCountLabel}</span>
              <ChevronDown class="w-3 h-3 transition-transform duration-200 {showProjectTypes ? 'rotate-180' : ''}" />
            </button>
            {#if showProjectTypes}
              {@const allSelected = selectedProjectTypes.length === PROJECT_TYPES.length}
              <div class="flex flex-wrap gap-2 mt-2">
                <button
                  type="button"
                  onclick={() => selectedProjectTypes = allSelected ? [] : PROJECT_TYPES.map(t => t.value)}
                  disabled={loading || showSuccess}
                  class="text-xs py-1.5 transition-colors
                    {allSelected ? 'text-accent font-medium' : 'text-text-muted hover:text-text-secondary'}
                    disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  All
                </button>
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

          <div bind:this={sentinelEl}></div>

          <!-- Process timeline (contextual, near submit) -->
          <div class="mb-4">
            <ProcessTimeline {stageCosts} />
          </div>

          {#if error}
            <div class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm mb-4">
              <AlertCircle class="w-4 h-4 shrink-0" />
              <span>{error}</span>
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
              label="Discover ideas (~5 min)"
              disabled={!niche.trim()}
              class="btn-primary w-full justify-center text-base py-3"
            />
          {:else}
            <button
              type="button"
              onclick={() => creditTopUp.show({ balance: creditBalance, required: stageCosts.discovery, stageName: 'discovery' })}
              class="btn-primary w-full justify-center text-base py-3 flex items-center gap-2"
            >
              <Coins class="w-4 h-4" />
              Get {stageCosts.discovery} Credits to Start
            </button>
          {/if}

          <p class="text-xs text-text-muted text-center mt-2">
            {stageCosts.discovery} credits &middot; you choose which ideas to validate further
          </p>
          <p class="text-xs text-center mt-1">
            <a href="/sample-report" class="text-text-muted hover:text-text-secondary underline underline-offset-2 decoration-border">Sample report</a>
          </p>

          <div bind:this={ctaEndEl}></div>
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
          />
        </div>
      </form>
    </div>
  </div>
</div>
