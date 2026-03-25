<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import {
    X,
    ArrowRight,
    Loader2,
    AlertCircle,
    Coins,
    Sparkles,
    PenLine,
  } from "lucide-svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import { DEFAULT_STAGE_COSTS } from "$lib/types/job";
  import type { StageCosts } from "$lib/types/job";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";

  const MAX_NICHE_LENGTH = 500;

  const PLACEHOLDER_EXAMPLES = [
    "Therapists who want to launch an online practice",
    "Freelance developers overwhelmed by admin work",
    "Solo entrepreneurs who want to start a digital agency",
    "Remote workers struggling with productivity and focus",
    "Parents looking for reliable after-school activities",
    "Small gym owners competing with big fitness chains",
    "Independent recruiters trying to scale without a team",
    "First-time managers learning to lead a team",
    "Real estate agents who want to automate lead gen",
    "Pet sitters looking to grow beyond word-of-mouth",
  ];

  function randomPlaceholder() {
    return PLACEHOLDER_EXAMPLES[
      Math.floor(Math.random() * PLACEHOLDER_EXAMPLES.length)
    ];
  }

  let { open = $bindable(false) } = $props();

  let placeholder = $state(randomPlaceholder());

  $effect(() => {
    if (open) {
      placeholder = randomPlaceholder();
    }
  });

  // Get credit balance and stage costs from page data
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  const stageCosts = $derived((page.data.stageCosts as StageCosts) ?? DEFAULT_STAGE_COSTS);
  const hasCredits = $derived(creditBalance >= stageCosts.discovery);

  const PROJECT_TYPES = [
    { value: "saas", label: "SaaS" },
    { value: "directory", label: "Directory" },
    { value: "aggregator", label: "Aggregator" },
    { value: "comparison-tool", label: "Comparison Tool" },
    { value: "marketplace", label: "Marketplace" },
  ] as const;

  let niche = $state("");
  let selectedProjectTypes = $state<string[]>(
    PROJECT_TYPES.map((t) => t.value),
  );
  let loading = $state(false);
  let error = $state("");

  function toggleProjectType(value: string) {
    if (selectedProjectTypes.includes(value)) {
      selectedProjectTypes = selectedProjectTypes.filter((t) => t !== value);
    } else {
      selectedProjectTypes = [...selectedProjectTypes, value];
    }
  }

  // Suggestion state
  let suggestLoading = $state(false);
  let suggestMode = $state<"lucky" | "complete" | null>(null);
  let suggestError = $state("");

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

      open = false;
      niche = "";
      selectedProjectTypes = PROJECT_TYPES.map((t) => t.value);
      // Navigate to job page (invalidateAll refreshes credit balance in header)
      goto(`/jobs/${data.id}`, { invalidateAll: true });
    } catch (err) {
      error = err instanceof Error ? err.message : "Something went wrong";
    } finally {
      loading = false;
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      open = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && open) {
      open = false;
    }
  }

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
      // Directly set textarea value
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
      // Directly replace textarea value
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
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- Modal -->
    <div
      class="bg-bg-surface border border-border rounded-xl shadow-2xl w-full max-w-lg"
    >
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-border">
        <h2 class="text-lg font-semibold text-text-primary">
          Start New Research
        </h2>
        <button
          onclick={() => (open = false)}
          aria-label="Close modal"
          class="p-1 rounded-lg hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <form onsubmit={handleSubmit} class="p-4 space-y-4">
        <!-- Credit Balance Indicator -->
        <div
          class="flex items-center justify-between p-3 rounded-lg {hasCredits
            ? 'bg-accent/5 border border-accent/20'
            : 'bg-warning/5 border border-warning/20'}"
        >
          <div class="flex items-center gap-2">
            <Coins
              class="w-4 h-4 {hasCredits ? 'text-accent' : 'text-warning'}"
            />
            <span
              class="text-sm font-medium {hasCredits
                ? 'text-text-primary'
                : 'text-warning'}"
            >
              {creditBalance}
              {creditBalance === 1 ? "credit" : "credits"} available
            </span>
          </div>
          {#if stageCosts.discovery > 0}
            <span class="text-xs text-text-muted">{stageCosts.discovery} credits for discovery</span>
          {/if}
        </div>

        {#if !hasCredits}
          <div
            class="flex items-start gap-3 p-3 bg-warning/5 border border-warning/20 rounded-lg"
          >
            <AlertCircle class="w-5 h-5 text-warning shrink-0 mt-0.5" />
            <div>
              <p class="text-sm font-medium text-text-primary">
                No credits available
              </p>
              <p class="text-xs text-text-muted mt-1">
                You need at least {stageCosts.discovery} credits to start a new research.
              </p>
              <button
                type="button"
                onclick={() => { open = false; creditTopUp.show({ balance: creditBalance, required: stageCosts.discovery, stageName: 'discovery' }); }}
                class="inline-flex items-center gap-1 text-xs text-accent hover:underline mt-2"
              >
                Get credits
                <ArrowRight class="w-3 h-3" />
              </button>
            </div>
          </div>
        {:else}
          <!-- Section 1: Research Input -->
          <div>
            <label
              for="niche"
              class="block text-sm font-medium text-text-primary mb-2"
            >
              What market should we research?
            </label>
            <textarea
              id="niche"
              bind:value={niche}
              rows={4}
              maxlength={MAX_NICHE_LENGTH}
              class="input resize-none w-full"
              placeholder="e.g., {placeholder}"
              disabled={loading}
            ></textarea>
            <div class="flex items-center justify-between mt-1.5">
              <p class="text-xs text-text-muted">
                Describe one niche or audience in a sentence or two. Don't worry
                about perfect phrasing — we'll refine it if needed.
              </p>
              <span
                class="text-xs {niche.length > MAX_NICHE_LENGTH * 0.9
                  ? 'text-warning'
                  : 'text-text-muted'}"
              >
                {niche.length}/{MAX_NICHE_LENGTH}
              </span>
            </div>

            <!-- Suggestion buttons -->
            <div class="flex items-center gap-2 mt-3">
              <button
                type="button"
                onclick={handleFeelingLucky}
                disabled={loading || suggestLoading}
                class="text-xs px-3 py-1.5 rounded-lg border border-border bg-bg-surface
                       hover:border-accent hover:bg-accent/5 text-text-secondary
                       transition-colors flex items-center gap-1.5
                       disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {#if suggestLoading && suggestMode === "lucky"}
                  <Loader2 class="w-3.5 h-3.5 animate-spin" />
                  Generating...
                {:else}
                  <Sparkles class="w-3.5 h-3.5 text-accent" />
                  Surprise me
                {/if}
              </button>

              <button
                type="button"
                onclick={handleExpandThis}
                disabled={loading || suggestLoading || !niche.trim()}
                class="text-xs px-3 py-1.5 rounded-lg border border-border bg-bg-surface
                       hover:border-accent hover:bg-accent/5 text-text-secondary
                       transition-colors flex items-center gap-1.5
                       disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {#if suggestLoading && suggestMode === "complete"}
                  <Loader2 class="w-3.5 h-3.5 animate-spin" />
                  Refining...
                {:else}
                  <PenLine class="w-3.5 h-3.5 text-accent" />
                  Refine my input
                {/if}
              </button>
            </div>

            <!-- Suggest error -->
            {#if suggestError}
              <p class="text-xs text-error mt-2">{suggestError}</p>
            {/if}
          </div>

          <!-- Section 2: Project Type Filter -->
          <div class="pt-3 border-t border-border/50">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-xs font-medium text-text-muted">
                Project types to focus on
              </span>
              <span class="text-xs text-text-muted">
                {selectedProjectTypes.length === PROJECT_TYPES.length
                  ? "All types"
                  : `${selectedProjectTypes.length} of ${PROJECT_TYPES.length}`}
              </span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              {#each PROJECT_TYPES as type}
                <button
                  type="button"
                  onclick={() => toggleProjectType(type.value)}
                  disabled={loading}
                  class="text-xs px-3 py-1.5 rounded-md border transition-colors
                         {selectedProjectTypes.includes(type.value)
                    ? 'bg-accent/10 border-accent/40 text-accent font-medium'
                    : 'bg-bg-surface border-border text-text-muted hover:border-border-emphasis hover:text-text-secondary'}
                         disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {type.label}
                </button>
              {/each}
            </div>
          </div>

        {/if}

        {#if error}
          <div
            class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm"
          >
            <AlertCircle class="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        {/if}

        {#if hasCredits}
          <p class="text-xs text-text-muted text-center">
            Phase 1 finds pain points and solution ideas (~15 min). You pick which to pursue, then Phase 2 validates with competitive analysis, SEO, and market sizing (~20 min).
          </p>
          <SubmitButton loading={loading} loadingText="Starting..." icon={ArrowRight} iconPosition="end" label="Start Research" disabled={!niche.trim()} class="btn-primary w-full justify-center" />
        {:else}
          <button type="button" onclick={() => { open = false; creditTopUp.show({ balance: creditBalance, required: stageCosts.discovery, stageName: 'discovery' }); }} class="btn-primary w-full justify-center flex items-center gap-2">
            <Coins class="w-4 h-4" />
            Get Credits to Start
          </button>
        {/if}
      </form>
    </div>
  </div>
{/if}

