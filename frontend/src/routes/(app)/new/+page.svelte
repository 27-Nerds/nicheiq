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
    ClipboardCheck,
  } from "lucide-svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import EntryModeCards from "$lib/components/new-research/EntryModeCards.svelte";
  import CatalogTrendingGrid from "$lib/components/new-research/CatalogTrendingGrid.svelte";
  import ProcessTimeline from "$lib/components/new-research/ProcessTimeline.svelte";
  import StickyCtaBar from "$lib/components/new-research/StickyCtaBar.svelte";
  import InputQualityMeter from "$lib/components/new-research/InputQualityMeter.svelte";
  import IdeaClarifyCard, {
    flattenClarifyAnswers,
    type ClarifyAnswers,
    type ClarifyCardState,
    type ClarifyScanResult,
  } from "$lib/components/new-research/IdeaClarifyCard.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";
  import { DEFAULT_STAGE_COSTS } from "$lib/types/job";
  import type { StageCosts } from "$lib/types/job";
  import type { EntryMode } from "$lib/components/new-research/EntryModeCards.svelte";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import { normalizeIdeaText } from "$lib/utils/normalizeIdeaText";
  import { buildCoverageChecklist, detectIdeaCoverage } from "$lib/utils/ideaCoverage";

  let { data } = $props();

  const STANDARD_NICHE_MAX = 500;
  const STANDARD_NICHE_MIN = 10;
  // "Check my idea" pitches: the 2000-char backend cap minus a 300-char reserved
  // tail so clarify answers appended at submit can never overflow it.
  const VALIDATE_NICHE_MAX = 1700;
  const VALIDATE_NICHE_MIN = 40;

  // --- State ---
  let userEdited = $state(false);

  // --- Mode state ---
  let entryMode = $state<EntryMode>("idea");
  let chatMode = $state(false);
  const isValidateMode = $derived(entryMode === "validate_idea");
  const maxNicheLength = $derived(isValidateMode ? VALIDATE_NICHE_MAX : STANDARD_NICHE_MAX);
  const minNicheLength = $derived(isValidateMode ? VALIDATE_NICHE_MIN : STANDARD_NICHE_MIN);
  // Guided research is not available for idea checks (the backend rejects the combination).
  $effect(() => {
    if (isValidateMode && chatMode) chatMode = false;
  });

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
  let showResearchSetup = $state(false);
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
  // Mirrors the backend gate: < and > are rejected on every mode (they'd reach
  // email HTML templates), and the check mode has a higher minimum.
  const nicheHasAngleBrackets = $derived(/[<>]/.test(niche));
  const nicheIsValid = $derived(
    niche.trim().length >= minNicheLength && !nicheHasAngleBrackets,
  );
  let loading = $state(false);
  let error = $state("");

  // --- Clarify intake (validate mode only; P2) ---
  // "idle" = card not shown. The card's own ClarifyCardState covers every
  // other state - see IdeaClarifyCard.svelte for why "questions"/"answered"
  // collapse into "ready" and "submitting" is just this page's `loading`.
  let clarifyState = $state<ClarifyCardState | "idle">("idle");
  let clarifyScan = $state<ClarifyScanResult | null>(null);
  let clarifyAnswers = $state<ClarifyAnswers>({});
  // The normalized text the current scan (or the scan in flight) reflects -
  // used to detect edit-invalidation (stale) drift.
  let clarifyLastScannedText = $state("");
  // Plain (non-reactive) cache: scan results keyed by hash(normalizedText),
  // reused across 402 top-up / 409 price-change retries.
  const clarifyScanCache = new Map<string, ClarifyScanResult>();
  let clarifyAbort: AbortController | null = null;
  const clarifyCardActive = $derived(isValidateMode && clarifyState !== "idle");

  // Layer-1 coverage checklist (zero-LLM), wired into the meter only in
  // validate mode - other modes keep the tier-sentence rendering.
  const clarifyChecklist = $derived(
    isValidateMode ? buildCoverageChecklist(detectIdeaCoverage(niche)) : undefined,
  );

  // --- Retry-from-job (replaces deprecated NewResearchModal flow) ---
  const fromJobId = $derived(page.url.searchParams.get("fromJob") ?? "");
  const prefilledNiche = $derived(
    page.url.searchParams.get("prefilled") ??
      page.url.searchParams.get("niche") ??
      "",
  );
  const CARD_MODES = ["idea", "audience", "discovery", "validate_idea"] as const;
  const prefilledMode = $derived(page.url.searchParams.get("mode") ?? "");
  // Apply prefilled niche + mode on initial mount. A re-run URL carries ?mode= so a
  // validate-idea pitch round-trips as a validate run (forcing "idea" here used to
  // both lose the mode and 400 on >500-char pitches). A bare ?mode= (no prefill —
  // e.g. a shared/help link straight to "Check my idea") preselects the card too.
  // Untracked so later edits don't re-trigger.
  $effect(() => {
    if (userEdited) return;
    const validMode = (CARD_MODES as readonly string[]).includes(prefilledMode);
    if (prefilledNiche) {
      const mode: EntryMode = validMode ? (prefilledMode as EntryMode) : "idea";
      entryMode = mode;
      // Programmatic assignment bypasses the textarea maxlength attribute — clamp.
      niche = prefilledNiche.slice(
        0,
        mode === "validate_idea" ? VALIDATE_NICHE_MAX : STANDARD_NICHE_MAX,
      );
      userEdited = true;
    } else if (validMode) {
      entryMode = prefilledMode as EntryMode;
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

  // Show sticky bar only when CTA is scrolled past AND bottom of CTA block isn't
  // visible. Suppressed while the clarify card is active: its raw type=submit
  // button would bypass the gate below (StickyCtaBar.svelte:68).
  $effect(() => { ctaBarVisible = ctaAboveViewport && !ctaEndInView && !clarifyCardActive; });

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
      validate_idea: {
        label: "Describe your idea",
        icon: ClipboardCheck,
        colorClass: "text-accent",
        placeholders: [
          "e.g., A Chrome extension that drafts Reddit replies for community managers at small SaaS companies",
          "e.g., A dashboard for wedding photographers to track galleries, contracts, and payment reminders in one place",
          "e.g., A Slack bot that turns support tickets into a weekly product-gap digest for founders",
          "e.g., A web app for landlords that converts maintenance texts into tracked work orders",
          "e.g., An API that turns messy supplier spreadsheets into clean inventory data for small shops",
        ],
        helpText:
          "Say what it does, who it's for, and how they use it.",
        examples: [
          "A Chrome extension that drafts Reddit replies for community managers",
          "A dashboard where wedding photographers track galleries and payments",
          "A Slack bot that digests support tickets into product gaps",
          "A web app turning landlord maintenance texts into work orders",
          "An invoice chaser that follows up unpaid freelance invoices",
          "A tool that repurposes podcast episodes into short clips",
        ],
        qualityTiers: {
          bad: { label: "Too thin", example: "An AI tool for UX validation" },
          better: { label: "Getting there", example: "A Chrome extension that flags UX issues on web pages" },
          best: { label: "Ready to check", example: "A Chrome extension for solo product designers that flags UX issues on client sites before handoff" },
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

  // Programmatic niche assignments bypass the textarea maxlength attribute — clamp
  // to the current mode's cap at every non-typing write.
  function setNiche(text: string) {
    niche = text.slice(0, maxNicheLength);
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
        setNiche(data.suggestions[0].niche);
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
        setNiche(data.suggestions[0].niche);
      }
    } catch {
      suggestError = "Connection error. Please try again.";
    } finally {
      suggestLoading = false;
      suggestMode = null;
    }
  }

  // --- Clarify intake (validate mode only; P2) ---

  // Cheap synchronous cache key for the client-side scan cache - collisions
  // are low-stakes (memoization only, not an identity), so a full crypto
  // hash isn't warranted.
  function hashText(text: string): string {
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      hash = (Math.imul(31, hash) + text.charCodeAt(i)) | 0;
    }
    return hash.toString(36);
  }

  function resetClarify() {
    clarifyAbort?.abort();
    clarifyAbort = null;
    clarifyState = "idle";
    clarifyScan = null;
    clarifyAnswers = {};
  }

  // Card destroyed below the minimum length or on a mode change (P2 spec);
  // marked stale when the scanned text drifts while a scan is showing; an
  // in-flight scan is cancelled outright (nothing shown yet to mark stale).
  $effect(() => {
    if (clarifyState === "idle") return;
    if (!isValidateMode || niche.trim().length < VALIDATE_NICHE_MIN) {
      resetClarify();
      return;
    }
    const normalized = normalizeIdeaText(niche).trim();
    if (normalized === clarifyLastScannedText) return;
    if (clarifyState === "scanning") {
      clarifyAbort?.abort();
      clarifyState = "idle";
    } else if (clarifyState === "ready") {
      clarifyState = "stale";
    }
  });

  function applyClarifyScan(scanResult: ClarifyScanResult) {
    clarifyScan = scanResult;
    if (scanResult.questions.length === 0) {
      // Zero questions: the meter already said Ready - submit straight
      // through, no card flash.
      clarifyState = "idle";
      void submitJob();
      return;
    }
    clarifyState = "ready";
  }

  async function beginClarify() {
    const normalized = normalizeIdeaText(niche).trim();
    // Precheck: below the minimum, no LLM call - the existing inline error
    // already covers this case.
    if (normalized.length < VALIDATE_NICHE_MIN) return;

    const cacheKey = hashText(normalized);
    clarifyLastScannedText = normalized;

    const cached = clarifyScanCache.get(cacheKey);
    if (cached) {
      applyClarifyScan(cached);
      return;
    }

    clarifyState = "scanning";
    loading = true;

    clarifyAbort?.abort();
    const controller = new AbortController();
    clarifyAbort = controller;
    // 9s, not 5: the live scan p50 is ~5-8s (E2E-measured 2026-08-07) — at 5s users
    // mostly saw the fail-open card instead of the questions. The scanning skeleton
    // carries the perceived wait; the timeout only bounds the worst case.
    const timeoutId = setTimeout(() => controller.abort(), 9000);

    try {
      const res = await fetch("/api/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "clarify_idea", partial_input: normalized }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      loading = false;

      if (!res.ok) {
        // Includes 429 - fail-open, never a blocking error.
        clarifyState = "failopen";
        return;
      }
      const data = await res.json();
      const scanResult: ClarifyScanResult | undefined = data.clarify;
      if (!scanResult) {
        clarifyState = "failopen";
        return;
      }
      clarifyScanCache.set(cacheKey, scanResult);
      applyClarifyScan(scanResult);
    } catch {
      clearTimeout(timeoutId);
      loading = false;
      if (controller.signal.aborted && !document.hidden) {
        // Timeout with the tab visible: honor the click that already
        // happened rather than making the user click again.
        clarifyState = "idle";
        await submitJob();
        return;
      }
      // Tab hidden, or a genuine error: hold at failopen rather than
      // auto-charging while the user isn't looking.
      clarifyState = "failopen";
    }
  }

  // --- Submit ---
  async function submitJob() {
    loading = true;
    error = "";

    try {
      const pitch = niche.trim() + flattenClarifyAnswers(clarifyAnswers);
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          niche: pitch,
          ...(!isValidateMode
            && selectedProjectTypes.length > 0
            && selectedProjectTypes.length < PROJECT_TYPES.length && {
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

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!nicheIsValid || loading || entryPriceUnavailable || entryCost === null) return;

    if (isValidateMode) {
      if (clarifyState === "idle") {
        await beginClarify();
        return;
      }
      if (clarifyState === "scanning") return; // already in flight
      if (clarifyState === "stale") {
        await beginClarify(); // "Re-read and continue"
        return;
      }
      // "ready" or "failopen": submit with whatever answers/guesses we have.
    }

    await submitJob();
  }
</script>

<svelte:head>
  <title>New Research - NicheIQ</title>
  <meta
    name="description"
    content="Discover and check product ideas against real market discussions with NicheIQ research."
  />
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
        discussions — ready in under an hour. You pick which one is worth
        full validation.
      </p>
    </header>

    <!-- Mode cards -->
    <div class="mode-section max-w-3xl mx-auto mb-6 px-4 sm:px-6">
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
        <div class="input-shell mt-4" class:filled={inputFilled} class:validate-shell={isValidateMode}>
          <div class="input-shell-inner p-6 sm:p-8" class:validate-shell-inner={isValidateMode}>
            {#if isValidateMode}
              <div class="validate-brief-header">
                <span class="validate-brief-icon" aria-hidden="true">
                  <ModeIcon class="w-5 h-5 {modeConfig.colorClass}" />
                </span>
                <div>
                  <p class="validate-brief-kicker">Your idea brief</p>
                  <label for="niche" class="validate-brief-title">
                    Describe what you want to build
                  </label>
                  <p id="idea-brief-hint" class="validate-brief-hint">
                    One clear paragraph is enough. Include the product, who it serves, and the problem it solves.
                  </p>
                </div>
              </div>
            {:else}
              <label
                for="niche"
                class="flex items-center gap-2 text-sm font-medium text-text-primary mb-3"
              >
                <ModeIcon class="w-4 h-4 {modeConfig.colorClass}" />
                {modeConfig.label}
              </label>
            {/if}

            <!-- Textarea with pills overlay -->
            <div class="relative">
              <textarea
                id="niche"
                bind:value={niche}
                bind:this={textareaEl}
                rows={isValidateMode ? 5 : 3}
                maxlength={maxNicheLength}
                class="w-full resize-none text-lg sm:text-xl bg-transparent
                       px-0 py-4 min-h-[120px] placeholder:text-text-muted/50
                       focus:outline-none focus-visible:outline-none
                       transition-colors duration-200
                       disabled:opacity-50 disabled:cursor-not-allowed"
                class:validate-textarea={isValidateMode}
                style={niche.trim() ? 'padding-right: 4rem' : ''}
                placeholder={displayedPlaceholder}
                aria-describedby={isValidateMode ? "idea-brief-hint" : undefined}
                disabled={loading || showSuccess}
                onfocus={() => textareaFocused = true}
                onblur={() => textareaFocused = false}
                oninput={handleTextareaInput}
              ></textarea>

              {#if !niche.trim()}
                {#if isValidateMode}
                  <div class="validate-examples">
                    <p class="validate-examples-label">Start with an example</p>
                    <div class="validate-example-list">
                      {#each displayedExamples as example}
                        <button
                          type="button"
                          onclick={() => { setNiche(example); userEdited = true; }}
                          disabled={loading || showSuccess}
                          class="validate-example-button"
                        >
                          <span>{example}</span>
                          <span aria-hidden="true">&rarr;</span>
                        </button>
                      {/each}
                    </div>
                  </div>
                {:else}
                  <div class="example-row pointer-events-none">
                    <p class="text-xs text-text-secondary">
                      Try:
                      {#each displayedExamples as example, i}
                        {#if i > 0}<span class="mx-1 text-text-muted/40">·</span>{/if}
                        <button
                          type="button"
                          onclick={() => { setNiche(example); userEdited = true; }}
                          disabled={loading || showSuccess}
                          class="pointer-events-auto hover:text-text-primary underline underline-offset-2 decoration-border/50
                                 hover:decoration-text-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {example}
                        </button>
                      {/each}
                    </p>
                  </div>
                {/if}
              {:else if !isValidateMode}
                <!-- Floating text actions inside textarea. Hidden in check mode:
                     both actions REPLACE the text wholesale — one misclick would
                     destroy the user's pitch. -->
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
            <div class="quality-row flex items-center justify-between mt-1.5" class:validate-quality={isValidateMode}>
              {#if isValidateMode}
                <p class="validate-quality-label">A strong brief includes</p>
              {/if}
              <InputQualityMeter
                {niche}
                qualityTiers={modeConfig.qualityTiers}
                helpText={modeConfig.helpText}
                checklist={clarifyChecklist}
              />
              {#if niche.length > 0}
                <span
                  class="text-xs tabular-nums shrink-0 ml-2 {niche.length > maxNicheLength * 0.9
                    ? 'text-[color:var(--color-warning-text)]'
                    : 'text-text-muted'}"
                >
                  {niche.length}/{maxNicheLength}
                </span>
              {/if}
            </div>
            {#if niche.trim() && !nicheIsValid}
              <p class="text-xs text-[color:var(--color-error-text)] mt-1.5" role="alert">
                {#if nicheHasAngleBrackets}
                  The characters &lt; and &gt; aren't supported. Please remove them.
                {:else if isValidateMode}
                  Describe your idea in at least {VALIDATE_NICHE_MIN} characters. Say what it does and who it is for.
                {:else}
                  Add a little more detail — at least 10 characters are required.
                {/if}
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

        <!-- Clarify intake card - inline in the form, not an overlay; the
             pitch above stays visible/editable while it's active. -->
        {#if clarifyCardActive}
          <IdeaClarifyCard
            scan={clarifyScan}
            answers={clarifyAnswers}
            cardState={clarifyState === "idle" ? "scanning" : clarifyState}
            discoveryPrice={displayEntryCost}
            {loading}
            onanswer={(field, answer) => {
              clarifyAnswers = { ...clarifyAnswers, [field]: answer };
            }}
            onclear={(field) => {
              const next = { ...clarifyAnswers };
              delete next[field];
              clarifyAnswers = next;
            }}
            onstart={() => { void submitJob(); }}
            onrescan={() => { void beginClarify(); }}
            onswitchmode={() => { entryMode = "idea"; }}
          />
        {/if}

        <!-- Submit section (outside glow card) -->
        <div class="mt-5">
          <section class="research-setup" aria-labelledby="research-setup-heading">
            <button
              type="button"
              class="research-setup-header"
              onclick={() => showResearchSetup = !showResearchSetup}
              aria-expanded={showResearchSetup}
              aria-controls="research-setup-controls"
            >
              <span class="research-setup-copy">
                <span id="research-setup-heading" class="research-setup-title">Research setup</span>
                <span class="research-setup-description">Optional controls for how ideas are generated.</span>
              </span>
              <span class="research-setup-summary">
                <span class="research-setup-badge">Optional</span>
                <ChevronDown class="w-4 h-4 transition-transform duration-200 {showResearchSetup ? 'rotate-180' : ''}" />
              </span>
            </button>

          {#if showResearchSetup}
          <div id="research-setup-controls">
          {#if !isValidateMode}
          <div class="research-setup-row">
            <button
              type="button"
              onclick={() => showProjectTypes = !showProjectTypes}
              aria-expanded={showProjectTypes}
              aria-controls="product-shape-panel"
              class="research-setup-trigger"
            >
              <span class="font-medium">Product shape filter</span>
              <span>·</span>
              <span>{projectTypeCountLabel}</span>
              <ChevronDown class="w-3 h-3 transition-transform duration-200 {showProjectTypes ? 'rotate-180' : ''}" />
            </button>
            {#if showProjectTypes}
              <p class="text-[11px] text-text-muted mt-2">
                Leave all selected if you're exploring multiple approaches.
              </p>
              {@const allSelected = selectedProjectTypes.length === PROJECT_TYPES.length}
              <div id="product-shape-panel" class="flex flex-wrap gap-2 mt-2">
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
          {/if}

          <div class="research-setup-row">
            <button
              type="button"
              onclick={() => showFocus = !showFocus}
              aria-expanded={showFocus}
              aria-controls="idea-focus-panel"
              class="research-setup-trigger"
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

          {#if !isValidateMode}
          <div class="research-setup-row">
            <button
              type="button"
              onclick={() => (showGuided = !showGuided)}
              aria-expanded={showGuided}
              aria-controls="guided-research-panel"
              class="research-setup-trigger"
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
          {/if}
          </div>
          {/if}
          </section>

          <!-- Process timeline (contextual, near submit) -->
          <div class="process-summary">
            <p class="process-summary-label">What happens next</p>
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
              label={chatMode ? "Start guided research" : isValidateMode ? "Start the check" : "Discover ideas"}
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
            {:else if isValidateMode}
              {entryCreditLabel} &middot; a full check of your idea against real market evidence
            {:else}
              {entryCreditLabel} &middot; see every idea before paying for validation
            {/if}
          </p>
          <p class="text-[11px] text-text-muted text-center mt-1">
            Credits auto-refund if a run can't complete.
          </p>
          <p class="text-center mt-1 font-mono text-[11px] text-text-muted">
            {#if data.sampleReportAvailable}
              <a href="/sample-report" class="hover:text-text-secondary">See a sample report &rarr;</a>
            {:else}
              Sample report temporarily unavailable
            {/if}
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
            ctaLabel={chatMode ? "Start guided research" : isValidateMode ? "Start the check" : "Discover ideas"}
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
  .input-shell.validate-shell {
    border-color: var(--color-border-emphasis);
  }
  .input-shell:focus-within {
    border-color: var(--color-text-primary);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }
  .input-shell-inner :global(textarea:focus-visible) {
    outline: none;
  }

  .validate-brief-header {
    display: flex;
    align-items: flex-start;
    gap: 0.875rem;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid var(--color-border);
  }
  .validate-brief-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    flex-shrink: 0;
    border: 1px solid var(--color-border-accent);
    border-radius: 0.625rem;
    background: var(--color-accent-subtle);
  }
  .validate-brief-kicker,
  .validate-examples-label,
  .validate-quality-label,
  .process-summary-label {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .validate-brief-title {
    display: block;
    margin-top: 0.25rem;
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 600;
    line-height: 1.25;
    color: var(--color-text-primary);
  }
  .validate-brief-hint {
    max-width: 34rem;
    margin: 0.375rem 0 0;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }
  textarea.validate-textarea {
    min-height: 8.5rem;
    padding: 1.25rem 0 1rem;
    font-size: 1rem;
    line-height: 1.65;
  }
  .validate-examples {
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
  }
  .validate-example-list {
    display: grid;
    gap: 0.5rem;
    margin-top: 0.625rem;
  }
  .validate-example-button {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    width: 100%;
    min-height: 3.25rem;
    padding: 0.625rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.4;
    text-align: left;
    transition:
      border-color 0.15s ease,
      background-color 0.15s ease,
      color 0.15s ease,
      transform 0.15s ease;
  }
  .validate-example-button > span:last-child {
    flex-shrink: 0;
    color: var(--color-text-muted);
  }
  .validate-example-button:hover:not(:disabled) {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    transform: translateY(-1px);
  }
  .validate-example-button:active:not(:disabled) {
    transform: translateY(0);
  }
  .validate-example-button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .validate-example-button:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
  .quality-row.validate-quality {
    display: block;
    margin-top: 1.25rem;
    padding-top: 1.25rem;
    border-top: 1px solid var(--color-border);
  }
  .validate-quality-label {
    margin-bottom: 0.625rem;
  }
  .validate-quality > span:last-child {
    display: block;
    margin: 0.5rem 0 0;
    text-align: right;
  }

  .research-setup {
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
    background: var(--color-bg-surface);
  }
  .research-setup-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    width: 100%;
    padding: 0.875rem 1rem;
    text-align: left;
    transition: background-color 0.15s ease;
  }
  .research-setup-header:hover {
    background: var(--color-bg-elevated);
  }
  .research-setup-header:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -3px;
  }
  .research-setup-copy {
    display: flex;
    flex-direction: column;
  }
  .research-setup-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .research-setup-description {
    margin-top: 0.1875rem;
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
  }
  .research-setup-summary {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
    color: var(--color-text-muted);
  }
  .research-setup-badge {
    padding: 0.1875rem 0.375rem;
    border: 1px solid var(--color-border);
    border-radius: 0.25rem;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--color-text-secondary);
  }
  .research-setup-row {
    padding: 0.75rem 1rem;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
  }
  .research-setup-trigger {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    width: 100%;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    text-align: left;
    transition: color 0.15s ease;
  }
  .research-setup-trigger:hover {
    color: var(--color-text-secondary);
  }
  .research-setup-trigger:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
    border-radius: 0.25rem;
  }
  .research-setup-trigger :global(svg) {
    margin-left: auto;
  }
  .process-summary {
    margin: 1rem 0;
    padding: 0.875rem 1rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
    background: var(--color-bg-surface);
  }
  .process-summary-label {
    margin-bottom: 0.625rem;
    text-align: center;
    color: var(--color-text-secondary);
  }

  .example-row {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0.75rem;
    z-index: 10;
  }

  @media (max-width: 640px) {
    .new-hero {
      padding-top: 32px;
      padding-bottom: 12px;
    }
    .mode-section :global(.section-divider) {
      padding-top: 24px;
    }
    .validate-shell-inner {
      padding: 1.25rem;
    }
    .validate-brief-header {
      gap: 0.75rem;
    }
    .validate-brief-icon {
      width: 2.25rem;
      height: 2.25rem;
    }
    .example-row {
      position: static;
      margin-top: 0.5rem;
    }
  }
  @media (min-width: 640px) {
    .validate-example-list {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .validate-example-button {
      transition: none;
    }
    .validate-example-button:hover:not(:disabled),
    .validate-example-button:active:not(:disabled) {
      transform: none;
    }
  }
</style>
