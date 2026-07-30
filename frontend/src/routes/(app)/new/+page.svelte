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
  import CatalogTrendingGrid from "$lib/components/new-research/CatalogTrendingGrid.svelte";
  import ProcessTimeline from "$lib/components/new-research/ProcessTimeline.svelte";
  import StickyCtaBar from "$lib/components/new-research/StickyCtaBar.svelte";
  import InputQualityMeter from "$lib/components/new-research/InputQualityMeter.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";
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
  let chatMode = $state(false);

  // --- Credit data from layout ---
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  const stageCosts = $derived(
    (page.data.stageCosts as StageCosts) ?? DEFAULT_STAGE_COSTS,
  );
  const guidedEntryCost = $derived(
    Number.isInteger(stageCosts.guided?.s1) && (stageCosts.guided?.s1 ?? -1) >= 0
      ? stageCosts.guided!.s1
      : null,
  );
  const entryCost = $derived(chatMode ? guidedEntryCost : stageCosts.discovery);
  const entryPriceUnavailable = $derived(
    (chatMode
      ? Boolean(page.data.billingLoadState?.guidedCostsUnavailable)
      : Boolean(page.data.billingLoadState?.discoveryCostUnavailable))
    || entryCost === null
    || !Number.isInteger(entryCost)
    || entryCost < 0,
  );
  const displayEntryCost = $derived(entryCost ?? 0);
  const entryCreditLabel = $derived(
    `${displayEntryCost} ${displayEntryCost === 1 ? "credit" : "credits"}`,
  );
  const hasCredits = $derived(!entryPriceUnavailable && creditBalance >= displayEntryCost);
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
      if (selectedProjectTypes.length === 1) return;
      selectedProjectTypes = selectedProjectTypes.filter((t) => t !== value);
    } else {
      selectedProjectTypes = [...selectedProjectTypes, value];
    }
  }

  // --- Idea focus (GTM angle steer) ---
  const IDEA_FOCUSES = [
    { value: "auto", label: "Auto", hint: "Pick the best angle for each idea (recommended)" },
    { value: "novelty", label: "Differentiation", hint: "Favor distinct, defensible mechanisms" },
    { value: "distribution", label: "Distribution", hint: "Favor SEO/directory plays you can rank fast" },
  ] as const;
  let selectedFocus = $state<"auto" | "novelty" | "distribution">("auto");
  let showFocus = $state(false);

  // --- Guided research (Phase B — chatMode opt-in, paid-gated) ---
  // Exact server-owned grant. This includes admin, subscription/full-catalog entitlement,
  // and a manual Analyst grant, matching the backend's hasAnalystAccess() contract.
  const hasAnalystAccess = $derived(page.data.featureAccess?.analyst === true);
  let showGuided = $state(false);

  // --- Input state ---
  let niche = $state("");
  const nicheIsValid = $derived(niche.trim().length >= 10);
  let loading = $state(false);
  let error = $state("");

  // --- Retry-from-job (replaces deprecated NewResearchModal flow) ---
  const fromJobId = $derived(page.url.searchParams.get("fromJob") ?? "");
  const prefilledNiche = $derived(
    page.url.searchParams.get("prefilled") ??
      page.url.searchParams.get("niche") ??
      "",
  );
  // Apply prefilled niche + force entryMode=idea on initial mount. Untracked
  // so subsequent niche edits don't re-trigger.
  $effect(() => {
    if (prefilledNiche && !userEdited) {
      niche = prefilledNiche;
      entryMode = "idea";
      userEdited = true;
    }
  });

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
          if (entry.target === sentinelEl) {
            ctaAboveViewport =
              !entry.isIntersecting && entry.boundingClientRect.top < 0;
          }
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
        colorClass: "text-accent",
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
        colorClass: "text-accent",
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

  // --- Input filled state (controls focus emphasis) ---
  const inputFilled = $derived(niche.trim().length > 0);

  // --- Mode icon (derived for use in template without @const) ---
  const ModeIcon = $derived(modeConfig.icon);

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
    if (!nicheIsValid || loading || entryPriceUnavailable || entryCost === null) return;

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
          ...(selectedFocus !== "auto" && { ideaFocus: selectedFocus }),
          ...(chatMode && hasAnalystAccess && { chatMode: true }),
          expectedCost: entryCost,
          entryMode,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 402 && data.code === "INSUFFICIENT_CREDITS") {
          creditTopUp.show({
            balance: data.balance ?? 0,
            required: data.required ?? displayEntryCost,
            stageName: chatMode ? "guided research" : "discovery",
          });
          loading = false;
          return;
        }
        const detail = data.details?.[0]?.message;
        if (res.status === 409 && data.code === "PRICE_CHANGED") {
          await invalidateAll();
          throw new Error("The research price changed. Review the updated cost and start again.");
        }
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

<div class="min-h-[calc(100dvh-3.5rem)]">
  <div class="pb-16" class:pb-28={ctaBarVisible}>
    <!-- Editorial hero -->
    <header class="max-w-3xl mx-auto px-4 sm:px-6 new-hero">
      <p class="new-kicker">
        <span class="k-accent">NEW RESEARCH</span>
      </p>
      <h1 class="new-h1">What are you exploring?</h1>
      <p class="new-lede">
        Get 5–10 scored product ideas from real Reddit &amp; Hacker News
        discussions — first ideas in ~15 minutes. You pick which one is worth
        full validation.
      </p>
    </header>

    <!-- Mode cards -->
    <div class="max-w-3xl mx-auto mb-6 px-4 sm:px-6">
      <SectionDivider label="Starting point" />
      <EntryModeCards selected={entryMode} onselect={(mode) => entryMode = mode} />
    </div>

    <!-- Focused form area -->
    <div class="max-w-3xl mx-auto px-4 sm:px-6">
      {#if fromJobId}
        <div class="mb-3 flex justify-center">
          <span
            class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border-emphasis bg-bg-elevated text-[11px] font-mono uppercase tracking-[0.08em] text-text-secondary"
          >
            <span
              class="w-1.5 h-1.5 rounded-full bg-accent"
              aria-hidden="true"
            ></span>
            Retrying from #{fromJobId.slice(0, 7)}
          </span>
        </div>
      {/if}
      <form onsubmit={handleSubmit}>
        <!-- Catalog Grid (discovery mode only) + connector -->
        {#if entryMode === "discovery"}
          <div class="animate-fade-in mt-2">
            <CatalogTrendingGrid
              painPoints={data.catalogPainPoints}
              hasCatalogData={data.hasCatalogData}
              onselect={handleCatalogSelect}
              onsurprise={handleFeelingLucky}
              surpriseLoading={suggestLoading && suggestMode === "lucky"}
            />
          </div>
        {/if}

        <!-- Input card — hairline surface, catalog ink-black focus -->
        <div class="input-shell mt-4" class:filled={inputFilled}>
          <div class="input-shell-inner p-6 sm:p-8">
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
                <div class="example-row pointer-events-none">
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
                    aria-label="Try a different topic"
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
                    aria-label="Refine with AI"
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
                    ? 'text-[color:var(--color-warning-text)]'
                    : 'text-text-muted'}"
                >
                  {niche.length}/{MAX_NICHE_LENGTH}
                </span>
              {/if}
            </div>
            {#if niche.trim() && !nicheIsValid}
              <p class="text-xs text-[color:var(--color-error-text)] mt-1.5" role="alert">
                Add a little more detail — at least 10 characters are required.
              </p>
            {/if}

            {#if suggestError}
              <p
                class="text-xs text-[color:var(--color-error-text)] mt-1.5"
                aria-live="polite"
              >
                {suggestError}
              </p>
            {/if}
          </div>
        </div>

        <!-- Submit section (outside glow card) -->
        <div class="mt-4 px-1">
          <div class="mb-4">
            <button
              type="button"
              onclick={() => showProjectTypes = !showProjectTypes}
              aria-expanded={showProjectTypes}
              aria-controls="business-model-panel"
              class="text-xs text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1"
            >
              <span class="font-medium">Business model filter</span>
              <span>·</span>
              <span>{projectTypeCountLabel}</span>
              <ChevronDown class="w-3 h-3 transition-transform duration-200 {showProjectTypes ? 'rotate-180' : ''}" />
            </button>
            <p class="text-[11px] text-text-muted mt-1">
              Tip: leave all selected if you're exploring multiple approaches.
            </p>
            {#if showProjectTypes}
              {@const allSelected = selectedProjectTypes.length === PROJECT_TYPES.length}
              <div id="business-model-panel" class="flex flex-wrap gap-2 mt-2">
                <button
                  type="button"
                  onclick={() => selectedProjectTypes = PROJECT_TYPES.map(t => t.value)}
                  disabled={loading || showSuccess}
                  aria-pressed={allSelected}
                  class="text-xs py-1.5 transition-colors
                    {allSelected ? 'text-[color:var(--color-accent-dark)] font-medium' : 'text-text-muted hover:text-text-secondary'}
                    disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  All
                </button>
                {#each PROJECT_TYPES as type}
                  <button
                    type="button"
                    onclick={() => toggleProjectType(type.value)}
                    disabled={loading || showSuccess}
                    aria-pressed={selectedProjectTypes.includes(type.value)}
                    class="text-xs px-3 py-1.5 rounded-md border transition-colors
                      {selectedProjectTypes.includes(type.value)
                      ? 'bg-[color:var(--color-accent-subtle)] border-[color:var(--color-border-accent)] text-[color:var(--color-accent-dark)] font-medium'
                      : 'bg-bg-elevated border-border text-text-muted hover:border-border-emphasis hover:text-text-secondary'}
                      disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {type.label}
                  </button>
                {/each}
              </div>
            {/if}
          </div>

          <div class="mb-4">
            <button
              type="button"
              onclick={() => showFocus = !showFocus}
              aria-expanded={showFocus}
              aria-controls="idea-focus-panel"
              class="text-xs text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1"
            >
              <span class="font-medium">Idea focus</span>
              <span>·</span>
              <span>{IDEA_FOCUSES.find((f) => f.value === selectedFocus)?.label ?? "Auto"}</span>
              <ChevronDown class="w-3 h-3 transition-transform duration-200 {showFocus ? 'rotate-180' : ''}" />
            </button>
            {#if showFocus}
              <div id="idea-focus-panel" class="flex flex-wrap gap-2 mt-2">
                {#each IDEA_FOCUSES as focus}
                  <button
                    type="button"
                    onclick={() => selectedFocus = focus.value}
                    disabled={loading || showSuccess}
                    title={focus.hint}
                    aria-pressed={selectedFocus === focus.value}
                    class="text-xs px-3 py-1.5 rounded-md border transition-colors
                      {selectedFocus === focus.value
                      ? 'bg-[color:var(--color-accent-subtle)] border-[color:var(--color-border-accent)] text-[color:var(--color-accent-dark)] font-medium'
                      : 'bg-bg-elevated border-border text-text-muted hover:border-border-emphasis hover:text-text-secondary'}
                      disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {focus.label}
                  </button>
                {/each}
              </div>
              <p class="text-xs text-text-muted mt-1.5">
                {IDEA_FOCUSES.find((f) => f.value === selectedFocus)?.hint}
              </p>
            {/if}
          </div>

          <div class="mb-4">
            <button
              type="button"
              onclick={() => (showGuided = !showGuided)}
              aria-expanded={showGuided}
              aria-controls="guided-research-panel"
              class="text-xs text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1"
            >
              <span class="font-medium">Guided research</span>
              <span>&middot;</span>
              <span>{chatMode ? "On" : "Off"}</span>
              <ChevronDown class="w-3 h-3 transition-transform duration-200 {showGuided ? 'rotate-180' : ''}" />
            </button>
            {#if showGuided}
              <div id="guided-research-panel" class="mt-2 flex items-start gap-3 rounded-md border border-border bg-bg-elevated p-3">
                <div class="flex-1 min-w-0">
                  <p class="text-xs font-medium text-text-primary">Pause at checkpoints to review and steer the research</p>
                  <p class="text-[11px] text-text-muted mt-1">
                    Research stops after the niche is validated, and again after pain points and audience are mapped &mdash; chat with the analyst or adjust scope before it continues.
                  </p>
                </div>
                {#if hasAnalystAccess}
                  <button
                    type="button"
                    role="switch"
                    aria-checked={chatMode}
                    aria-label="Guided research"
                    onclick={() => (chatMode = !chatMode)}
                    disabled={loading || showSuccess}
                    class="shrink-0 relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                      {chatMode ? 'bg-[color:var(--color-accent)]' : 'bg-border'}
                      disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <span
                      class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform {chatMode ? 'translate-x-6' : 'translate-x-1'}"
                    ></span>
                  </button>
                {:else}
                  <div class="shrink-0 text-right">
                    <span
                      role="switch"
                      aria-checked="false"
                      aria-disabled="true"
                      aria-label="Guided research is not enabled for this account"
                      class="relative inline-flex h-6 w-11 items-center rounded-full bg-border opacity-50 cursor-not-allowed"
                    >
                      <span class="inline-block h-4 w-4 translate-x-1 transform rounded-full bg-white"></span>
                    </span>
                    <a class="block mt-1 text-[11px] text-accent-dark hover:text-accent-hover" href="/billing#plans">
                      See access options
                    </a>
                  </div>
                {/if}
              </div>
            {/if}
          </div>

          <!-- Process timeline (contextual, near submit) -->
          <div class="mb-4">
            <ProcessTimeline {stageCosts} guided={chatMode} />
          </div>

          {#if error}
            <div
              role="alert"
              class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-[color:var(--color-error-text)] text-sm mb-4"
            >
              <AlertCircle class="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          {/if}

          <div bind:this={sentinelEl}></div>

          {#if showSuccess}
            <div
              aria-live="polite"
              class="w-full py-3 rounded-lg bg-success/10 border border-success/20 text-[color:var(--color-success-text)] text-base font-medium text-center flex items-center justify-center gap-2 transition-all duration-300"
            >
              <CheckCircle2 class="w-5 h-5" />
              Analyzing {niche.length > 30 ? niche.slice(0, 30) + '\u2026' : niche}...
            </div>
          {:else if entryPriceUnavailable}
            <button
              type="button"
              class="btn-secondary w-full justify-center text-base py-3"
              onclick={() => invalidateAll()}
            >
              Pricing unavailable · try again
            </button>
          {:else if hasCredits}
            <SubmitButton
              {loading}
              loadingText="Starting..."
              icon={ArrowRight}
              iconPosition="end"
              label={chatMode ? "Start guided research" : "Discover ideas"}
              disabled={!nicheIsValid}
              class="btn-primary w-full justify-center text-base py-3 min-w-[12rem]"
            />
          {:else}
            <Button
              onclick={() => creditTopUp.show({ balance: creditBalance, required: displayEntryCost, stageName: chatMode ? 'guided research' : 'discovery' })}
              icon={Coins}
              label="Get {entryCreditLabel} to Start"
              class="btn-primary w-full justify-center text-base py-3"
            />
          {/if}

          <p class="text-xs text-text-muted text-center mt-2">
            {#if chatMode}
              {entryCreditLabel} to start &middot; you approve each later Discovery segment
            {:else}
              {entryCreditLabel} &middot; see every idea before paying for validation
            {/if}
          </p>
          <p class="text-[11px] text-text-muted text-center mt-1">
            Credits auto-refund if a run can't complete.
          </p>
          <p class="text-center mt-1">
            <a href="/sample-report" class="font-mono text-[11px] text-text-muted hover:text-text-secondary">See a sample report &rarr;</a>
          </p>

          <div bind:this={ctaEndEl}></div>
        </div>

        <!-- Sticky CTA Bar -->
        <div class="!mt-0">
          <StickyCtaBar
            visible={ctaBarVisible && !textareaFocused}
            {niche}
            creditCost={displayEntryCost}
            {loading}
            disabled={!nicheIsValid}
            {hasCredits}
            stageCost={displayEntryCost}
            priceAvailable={!entryPriceUnavailable}
            stageName={chatMode ? "guided research" : "discovery"}
            ctaLabel={chatMode ? "Start guided research" : "Discover ideas"}
          />
        </div>
      </form>
    </div>
  </div>
</div>

<style>
  /* Editorial hero — mirrors CatalogIndexHero, left-aligned. */
  .new-hero {
    padding: 40px 0 24px;
  }
  .new-kicker {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 14px;
  }
  .new-kicker .k-accent {
    color: var(--color-accent-dark);
  }
  .new-h1 {
    font-family: var(--font-display);
    font-size: clamp(1.75rem, 4vw, 2.25rem);
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.1;
    color: var(--color-text-primary);
    margin: 0;
  }
  .new-lede {
    font-size: 15px;
    line-height: 1.6;
    color: var(--color-text-secondary);
    margin: 12px 0 0;
    max-width: 620px;
  }

  /* Input card — hairline surface, catalog ink-black focus (no rainbow glow). */
  .input-shell {
    border: 1px solid var(--color-border);
    border-radius: 12px;
    background: var(--color-bg-elevated);
    transition:
      border-color 0.15s ease,
      box-shadow 0.15s ease;
  }
  .input-shell.filled {
    border-color: var(--color-border-emphasis);
  }
  .input-shell:focus-within {
    border-color: var(--color-text-primary);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }
  .input-shell-inner :global(textarea:focus-visible) {
    outline: none;
  }

  .example-row {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0.75rem;
    z-index: 10;
  }

  @media (max-width: 640px) {
    .example-row {
      position: static;
      margin-top: 0.5rem;
    }
  }
</style>
