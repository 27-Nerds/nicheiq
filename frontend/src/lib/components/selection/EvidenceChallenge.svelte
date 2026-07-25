<script lang="ts">
  import { tick } from "svelte";
  import { RefreshCw, ExternalLink } from "lucide-svelte";
  import { getSelectionChallenges, runSelectionChallenge } from "$lib/api";
  import type { SolutionPreview } from "$lib/types/job";
  import type {
    SelectionAssumptionPrefill,
    SelectionOwnerEvidencePrefill,
  } from "$lib/types/selectionCopilot";
  import type {
    SelectionChallenge,
    SelectionChallengeLens,
    SelectionChallengeQuestion,
    SelectionChallengeSource,
    SelectionChallengeStaleReference,
  } from "$lib/types/selectionChallenge";
  import {
    actionableSelectionQuestion,
    SELECTION_CHALLENGE_ASSUMPTIONS,
    SELECTION_CHALLENGE_LENSES,
    SELECTION_CHALLENGE_QUESTION_LABELS,
    selectionChallengeConsensusLabel,
  } from "$lib/utils/selectionRisk";
  import OwnerEvidenceLedger, {
    discardOwnerEvidenceDraft,
    ownerEvidenceDraftIsDirty,
  } from "./OwnerEvidenceLedger.svelte";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import { BRANCH_DIRECTION_LABEL } from "$lib/selection/labels";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface ChallengeFocus {
    requestId: number;
    ideaId: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
    challengeId?: string;
    questionId?: string;
  }

  interface Props {
    jobId?: string;
    ideas: SolutionPreview[];
    /** Candidate picked in the page scope strip. Drives the internal
     *  selection; the strip is the only candidate-switching surface. */
    candidateId?: string | null;
    focus?: ChallengeFocus | null;
    /** Captures the challenge finding as a tracked assumption (opens the
     *  assumption editor with a grounded draft; nothing is saved). */
    onTrackRisk?: (prefill: SelectionAssumptionPrefill) => void;
    /** Contextual branch entry for open demand/competition gaps. Only passed
     *  when the branch form is available. */
    onBranchDirection?: () => void;
    ownerEvidencePrefill?: SelectionOwnerEvidencePrefill | null;
    onLensChange?: (lens: SelectionChallengeLens) => void;
    onChanged?: () => void;
    onReturnToEvidenceDraft?: (target: {
      jobId: string;
      ideaId: string;
      ideaRevision: number;
      lens: SelectionChallengeLens;
    }) => void | Promise<void>;
  }

  let {
    jobId,
    ideas,
    candidateId = null,
    focus = null,
    onTrackRisk,
    onBranchDirection,
    ownerEvidencePrefill = null,
    onLensChange,
    onChanged,
    onReturnToEvidenceDraft,
  }: Props = $props();
  let challenges = $state<SelectionChallenge[]>([]);
  let stale = $state<SelectionChallengeStaleReference[]>([]);
  let evidenceLedger = $state<ReturnType<typeof OwnerEvidenceLedger>>();
  let selectedIdeaId = $state("");
  let selectedLens = $state<SelectionChallengeLens>("demand");
  let loading = $state(false);
  let running = $state(false);
  let error = $state("");
  let runError = $state("");
  let runStatus = $state("");
  let loadedKey = "";
  let focusedRequestId = 0;
  const lensValues = SELECTION_CHALLENGE_LENSES.map((lens) => lens.value);
  const LENS_COPY: Record<SelectionChallengeLens, { label: string; description: string; action: string; empty: string }> = {
    demand: {
      label: "Do people want it?",
      description: "Pain, urgency, and willingness to pay",
      action: "Check demand",
      empty: "See what your saved evidence says about demand",
    },
    distribution: {
      label: "Can you reach buyers?",
      description: "Audience access and acquisition friction",
      action: "Check buyer reach",
      empty: "See what your saved evidence says about reaching buyers",
    },
    competition: {
      label: "Can it stand out?",
      description: "Alternatives, switching, and differentiation",
      action: "Check differentiation",
      empty: "See what your saved evidence says about standing out",
    },
    dependencies: {
      label: "Can you build it?",
      description: "Data, integrations, platforms, and compliance",
      action: "Check build limits",
      empty: "See what your saved evidence says about building it",
    },
  };
  const STALE_TAB_MESSAGE = "Needs recheck — the evidence used by this review changed.";
  const validatedOwnerEvidencePrefill = $derived.by(() => {
    const request = ownerEvidencePrefill;
    if (!request) return { prefill: null, error: "" };
    const exactIdea = ideas.some((idea) => (
      idea.idea_id === request.ideaId
      && Number(idea.idea_revision) === request.ideaRevision
    ));
    if (!exactIdea) {
      return { prefill: null, error: "This evidence draft references an older candidate revision." };
    }
    if (request.origin) {
      const exactChallenge = challenges.find((challenge) => (
        challenge.id === request.origin?.challengeId
        && challenge.ideaId === request.ideaId
        && challenge.ideaRevision === request.ideaRevision
        && challenge.lens === request.lens
      ));
      if (!loading && (
        !exactChallenge
        || !exactChallenge.questions.some((question) => question.questionId === request.origin?.questionId)
      )) {
        return { prefill: null, error: "The evidence-check question behind this draft is missing or no longer current." };
      }
      if (!exactChallenge) return { prefill: null, error: "" };
    }
    return { prefill: request, error: "" };
  });

  function selectLens(lens: SelectionChallengeLens) {
    if (!ownerEvidenceDraftIsDirty()) discardOwnerEvidenceDraft();
    selectedLens = lens;
    onLensChange?.(lens);
  }

  function handleLensKeydown(event: KeyboardEvent, currentLens: SelectionChallengeLens) {
    const currentIndex = lensValues.indexOf(currentLens);
    let nextIndex = currentIndex;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") nextIndex = (currentIndex + 1) % lensValues.length;
    else if (event.key === "ArrowUp" || event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + lensValues.length) % lensValues.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = lensValues.length - 1;
    else return;
    event.preventDefault();
    const nextLens = lensValues[nextIndex];
    if (!ownerEvidenceDraftIsDirty()) discardOwnerEvidenceDraft();
    selectedLens = nextLens;
    onLensChange?.(nextLens);
    queueMicrotask(() => document.getElementById(`evidence-lens-${nextLens}`)?.focus());
  }

  function ideaIdentity(idea: SolutionPreview): { id: string; revision: number } | null {
    if (!idea.idea_id || !Number.isInteger(idea.idea_revision) || Number(idea.idea_revision) < 1) return null;
    return { id: idea.idea_id, revision: Number(idea.idea_revision) };
  }

  function selectedIdea(): SolutionPreview | null {
    return ideas.find((idea) => idea.idea_id === selectedIdeaId) ?? ideas[0] ?? null;
  }

  const focusedIdea = $derived(selectedIdea());
  const focusedIdentity = $derived(focusedIdea ? ideaIdentity(focusedIdea) : null);

  function challengeFor(ideaId: string, lens: SelectionChallengeLens): SelectionChallenge | null {
    const idea = ideas.find((candidate) => candidate.idea_id === ideaId);
    return challenges.find((challenge) =>
      challenge.ideaId === ideaId
      && challenge.ideaRevision === Number(idea?.idea_revision)
      && challenge.lens === lens
    ) ?? null;
  }

  function currentChallenge(): SelectionChallenge | null {
    return challengeFor(selectedIdea()?.idea_id ?? "", selectedLens);
  }

  function isStale(ideaId: string, lens: SelectionChallengeLens): boolean {
    const idea = ideas.find((candidate) => candidate.idea_id === ideaId);
    return stale.some((reference) =>
      reference.ideaId === ideaId
      && reference.ideaRevision === Number(idea?.idea_revision)
      && reference.lens === lens
    );
  }

  function issueCount(challenge: SelectionChallenge | null): number | null {
    if (!challenge) return null;
    return challenge.questions.filter((question) => question.consensus !== "supported").length;
  }

  function reviewItems(
    question: SelectionChallengeQuestion,
    positions: Array<SelectionChallengeQuestion["skeptic"]["position"]>,
  ) {
    return [
      { label: "Challenge perspective", assessment: question.skeptic },
      { label: "Evidence perspective", assessment: question.auditor },
    ].filter((item) => positions.includes(item.assessment.position));
  }

  function impactCopy(question: SelectionChallengeQuestion): string {
    return {
      supported: "The reviewed evidence supports this part of the case.",
      contradicted: "The reviewed evidence weakens this part of the case.",
      mixed: "The reviewed evidence points in more than one direction.",
      disputed: "The two review perspectives reached different conclusions from the same evidence.",
      insufficient: "The reviewed evidence does not answer this question yet.",
    }[question.consensus];
  }

  function nextActionCopy(question: SelectionChallengeQuestion): string {
    return {
      supported: "Keep this point, and check it again if the idea or its evidence changes.",
      contradicted: "Resolve this concern before relying on this part of the idea.",
      mixed: "Review the cited sources and collect evidence that separates the competing signals.",
      disputed: "Review the cited sources and collect evidence that can resolve the disagreement.",
      insufficient: "Add direct evidence or plan a test before relying on this point.",
    }[question.consensus];
  }


  function overallLabel(challenge: SelectionChallenge): string {
    return {
      withstands: "Saved evidence supports this",
      weakened: "Saved evidence raises concerns",
      contradicted: "Saved evidence contradicts this",
      disputed: "Review perspectives disagree",
      insufficient_evidence: "Saved evidence cannot answer this",
    }[challenge.overall];
  }

  function sourcesFor(challenge: SelectionChallenge, keys: string[]): SelectionChallengeSource[] {
    const wanted = new Set(keys);
    return challenge.evidenceSnapshot.filter((source) => wanted.has(source.key));
  }

  function evidenceLabel(source: SelectionChallengeSource): string {
    if (source.kind === "customer_quote") return "Observed";
    if (source.kind === "owner_evidence") return "Owner-provided";
    if (source.kind === "experiment_result" && source.provenance.assetType === "EXPERIMENT_RESULT") {
      return source.provenance.sourceType === "FIRST_PARTY"
        ? "Observed hosted test"
        : "Owner-recorded external result";
    }
    return "Proxy";
  }

  function readableEvidenceExcerpt(excerpt: string): { text: string; raw: string | null } {
    const trimmed = excerpt.trim();
    if (!(trimmed.startsWith("{") || trimmed.startsWith("["))) {
      return { text: excerpt, raw: null };
    }

    try {
      const formatValue = (value: unknown): string => {
        if (typeof value === "string") return value.trim();
        if (typeof value === "number" || typeof value === "boolean") return String(value);
        if (Array.isArray(value)) return value.map(formatValue).filter(Boolean).join(", ");
        if (!value || typeof value !== "object") return "";

        return Object.entries(value)
          .flatMap(([key, entry]) => {
            const readableValue = formatValue(entry);
            if (!readableValue) return [];
            const label = key
              .replace(/[_-]+/g, " ")
              .replace(/^\w/, (character) => character.toUpperCase());
            return [`${label}: ${readableValue}`];
          })
          .join(" · ");
      };

      return { text: formatValue(JSON.parse(trimmed)) || excerpt, raw: null };
    } catch {
      return {
        text: "This captured source excerpt could not be formatted.",
        raw: excerpt,
      };
    }
  }


  /** Grounded assumption draft for the assumption-map editor. The drafted
   *  statement carries a challenge-question evidence reference, matching the
   *  copilot-prefill contract enforced by AssumptionMap. */
  function riskPrefill(
    challenge: SelectionChallenge,
    question: SelectionChallengeQuestion,
  ): SelectionAssumptionPrefill {
    const questionLabel = SELECTION_CHALLENGE_QUESTION_LABELS[question.questionId] ?? question.questionId;
    const lensName = LENS_COPY[challenge.lens].label;
    const consensusLabel = selectionChallengeConsensusLabel(question.consensus);
    return {
      requestId: crypto.randomUUID(),
      ideaId: challenge.ideaId,
      ideaRevision: challenge.ideaRevision,
      lens: challenge.lens,
      origin: { challengeId: challenge.id, questionId: question.questionId },
      grounding: {
        statement: [{
          ref: `${challenge.id}:${question.questionId}`,
          kind: "challenge_question",
          label: `${lensName} · ${questionLabel} · ${consensusLabel}`,
          challengeId: challenge.id,
          questionId: question.questionId,
        }],
      },
      rationale: (
        `The saved-evidence review for “${lensName}” left this question at "${consensusLabel}". `
        + `Skeptic: ${question.skeptic.summary} Auditor: ${question.auditor.summary}`
      ).slice(0, 1500),
      caveats: [],
      values: {
        statement: SELECTION_CHALLENGE_ASSUMPTIONS[question.questionId] ?? questionLabel,
      },
    };
  }

  async function load() {
    if (!jobId) return;
    loading = true;
    error = "";
    try {
      const response = await getSelectionChallenges(jobId);
      challenges = response.challenges;
      stale = response.stale;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not load saved risk checks.";
    } finally {
      loading = false;
    }
  }

  async function run() {
    if (!jobId || running) return;
    const idea = selectedIdea();
    const identity = idea ? ideaIdentity(idea) : null;
    if (!identity) {
      runError = "This idea is missing a stable reference. Reload the research before checking its evidence.";
      return;
    }
    running = true;
    runError = "";
    runStatus = "Check running…";
    try {
      const response = await runSelectionChallenge(jobId, {
        ideaId: identity.id,
        ideaRevision: identity.revision,
        lens: selectedLens,
      });
      challenges = [
        response.challenge,
        ...challenges.filter((challenge) =>
          !(challenge.ideaId === identity.id && challenge.lens === selectedLens)
        ),
      ];
      stale = stale.filter((reference) =>
        !(reference.ideaId === identity.id && reference.lens === selectedLens)
      );
      runStatus = `Check complete: ${overallLabel(response.challenge)}`;
      onChanged?.();
    } catch (cause) {
      runError = cause instanceof Error ? cause.message : "Could not check the saved evidence.";
      runStatus = "";
    } finally {
      running = false;
    }
  }

  $effect(() => {
    if (focus) {
      const match = ideas.find((idea) => (
        idea.idea_id === focus.ideaId && Number(idea.idea_revision) === focus.ideaRevision
      ));
      if (match) {
        selectedIdeaId = focus.ideaId;
        selectedLens = focus.lens;
      }
    }
    // The cockpit scope strip drives the candidate; it stays consistent with a
    // deep-link focus because the cockpit syncs its scope to the focus idea.
    if (candidateId && ideas.some((idea) => idea.idea_id === candidateId)) {
      selectedIdeaId = candidateId;
    }
    const identities = ideas.map((idea) => `${idea.idea_id ?? ""}:${idea.idea_revision ?? ""}`).join("|");
    const key = `${jobId ?? ""}:${identities}`;
    if (!selectedIdeaId || !ideas.some((idea) => idea.idea_id === selectedIdeaId)) {
      selectedIdeaId = ideas[0]?.idea_id ?? "";
    }
    if (!jobId || key === loadedKey) return;
    loadedKey = key;
    void load();
  });

  $effect(() => {
    if (
      !focus?.challengeId
      || !focus.questionId
      || focusedRequestId === focus.requestId
      || !challenges.some((challenge) => challenge.id === focus.challengeId)
    ) return;
    focusedRequestId = focus.requestId;
    void tick().then(() => {
      const target = document.getElementById(`challenge-question-${focus.challengeId}-${focus.questionId}`);
      target?.focus({ preventScroll: true });
      target?.scrollIntoView({
        block: "nearest",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      });
    });
  });
</script>

<section class="challenge" aria-labelledby="challenge-title">
  <header class="challenge-head">
    <div>
      <div class="title-row">
        <h3 id="challenge-title">Choose a risk area</h3>
        <DecisionHelp title="What this review does" position="bottom">
          <p>Each check reviews Discovery sources, evidence you add, and completed test results saved for this exact idea revision. Run it again when that evidence changes. “Cannot answer” means the saved record has a gap; it does not mean the idea failed.</p>
        </DecisionHelp>
      </div>
      <p>Two review perspectives reread the evidence saved for this idea. They do not search for new sources.</p>
    </div>
  </header>

  {#if validatedOwnerEvidencePrefill.error}
    <p class="prefill-error" role="alert">{validatedOwnerEvidencePrefill.error}</p>
  {/if}

  <div class="sr-only" role="status" aria-live="polite">{runStatus}</div>

  <div class="challenge-layout">
    <nav class="lens-rail" aria-label="Risk areas">
      <div role="tablist" aria-orientation="horizontal">
      {#each SELECTION_CHALLENGE_LENSES as lens}
        {@const saved = challengeFor(selectedIdea()?.idea_id ?? "", lens.value)}
        {@const count = issueCount(saved)}
        {@const stale = isStale(selectedIdea()?.idea_id ?? "", lens.value)}
        <button
          id={`evidence-lens-${lens.value}`}
          type="button"
          role="tab"
          class:is-active={selectedLens === lens.value}
          aria-selected={selectedLens === lens.value}
          aria-controls="evidence-lens-panel"
          tabindex={selectedLens === lens.value ? 0 : -1}
          onclick={() => selectLens(lens.value)}
          onkeydown={(event) => handleLensKeydown(event, lens.value)}
        >
          <span>
            <strong>{LENS_COPY[lens.value].label}</strong>
            <small>{LENS_COPY[lens.value].description}</small>
          </span>
          {#if count !== null || stale}
          <span class="badge-col">
            <span class="issue-badge" class:is-stale={stale} title={stale ? STALE_TAB_MESSAGE : undefined}>
              {#if count !== null}{count}<span class="sr-only"> open issues</span>{:else}Recheck{/if}
              {#if stale}<span class="sr-only"> ({STALE_TAB_MESSAGE})</span>{/if}
            </span>
          </span>
          {/if}
        </button>
      {/each}
      </div>
    </nav>

    <div class="challenge-detail" id="evidence-lens-panel" role="tabpanel" aria-labelledby={`evidence-lens-${selectedLens}`} tabindex="0">
      {#if loading}
        <div class="state-skeleton" role="status" aria-busy="true">
          <span aria-hidden="true"></span><span aria-hidden="true"></span><span aria-hidden="true"></span>
          <span class="sr-only">Loading saved checks…</span>
        </div>
      {:else if error}
        <div class="state state-error" role="alert">
          <p>{error}</p>
          <button type="button" class="run-action" onclick={() => void load()}>
            <RefreshCw aria-hidden="true" /> Reload saved checks
          </button>
        </div>
      {:else if currentChallenge()}
        {@const result = currentChallenge()!}
        <header class="result-head">
          <div>
            <span class="overall overall--{result.overall}">{overallLabel(result)}</span>
            <h4>{LENS_COPY[result.lens].label}</h4>
          </div>
          <div class="recheck-action">
            <button type="button" class="add-evidence-action" data-tour="add-evidence" onclick={() => evidenceLedger?.openAddEvidence()}>
              Add your evidence
            </button>
            <SubmitButton
              type="button"
              class="run-action"
              label="Check again"
              loadingText="Checking…"
              loading={running}
              icon={RefreshCw}
              minWidth="0"
              onclick={() => void run()}
            />
            {#if runError}<p class="run-error" role="alert">{runError}</p>{/if}
          </div>
        </header>

        {@const gap = actionableSelectionQuestion(result)}
        <div class="question-list">
          {#each result.questions as question}
            {@const citedKeys = [...new Set([...question.skeptic.evidenceKeys, ...question.auditor.evidenceKeys])]}
            {@const citedSources = sourcesFor(result, citedKeys)}
            {@const supports = reviewItems(question, ["supports"])}
            {@const concerns = reviewItems(question, ["contradicts", "mixed"])}
            {@const unknowns = reviewItems(question, ["insufficient"])}
            <article class="question" class:is-disputed={question.consensus === "disputed"}>
              <header>
                <h5 id="challenge-question-{result.id}-{question.questionId}" tabindex="-1">{SELECTION_CHALLENGE_QUESTION_LABELS[question.questionId] ?? question.questionId}</h5>
                <span class="consensus consensus--{question.consensus}">{selectionChallengeConsensusLabel(question.consensus)}</span>
              </header>
              <div class="finding-grid">
                <section class="finding finding--supports">
                  <h6>Supports</h6>
                  {#if supports.length}
                    {#each supports as item}
                      <p><strong>{item.label}</strong>{item.assessment.summary}</p>
                    {/each}
                  {:else}
                    <p>Neither review perspective found support in the reviewed evidence.</p>
                  {/if}
                </section>
                <section class="finding finding--concern">
                  <h6>Raises concern</h6>
                  {#if concerns.length}
                    {#each concerns as item}
                      <p><strong>{item.label}</strong>{item.assessment.summary}</p>
                    {/each}
                  {:else}
                    <p>Neither review perspective raised a concern from the reviewed evidence.</p>
                  {/if}
                </section>
                <section class="finding finding--unknown">
                  <h6>Still unknown</h6>
                  {#if unknowns.length}
                    {#each unknowns as item}
                      <p><strong>{item.label}</strong>{item.assessment.summary}</p>
                    {/each}
                  {:else}
                    <p>Neither review perspective marked this question unanswered.</p>
                  {/if}
                </section>
                <section class="finding finding--impact">
                  <h6>Impact</h6>
                  <p>{impactCopy(question)}</p>
                </section>
                <section class="finding finding--next">
                  <h6>Next action</h6>
                  <p>{nextActionCopy(question)}</p>
                  {#if gap?.questionId === question.questionId && !isStale(result.ideaId, result.lens) && onTrackRisk}
                    <div class="gap-actions">
                      <button type="button" class="gap-action" onclick={() => onTrackRisk?.(riskPrefill(result, question))}>
                        Save as a question to resolve
                      </button>
                    </div>
                  {/if}
                </section>
              </div>
              {#if question.consensus === "disputed"}
                <p class="disagreement">The two review perspectives read the same evidence differently. Both conclusions remain visible; neither is averaged away.</p>
              {/if}
              <details class="evidence">
                <summary>{citedSources.length} cited source{citedSources.length === 1 ? "" : "s"}</summary>
                {#if citedSources.length}
                  <ul>
                    {#each citedSources as source}
                      {@const readableExcerpt = readableEvidenceExcerpt(source.excerpt)}
                      <li>
                        <div>
                          <span class="evidence-class">{evidenceLabel(source)}</span>
                          <strong>{source.title}</strong>
                          {#if source.url}
                            <a href={source.url} target="_blank" rel="noreferrer" aria-label="Open source for {source.title} (opens in new tab)">
                              <ExternalLink aria-hidden="true" />
                            </a>
                          {/if}
                        </div>
                        <p>{readableExcerpt.text}</p>
                        {#if readableExcerpt.raw}
                          <details class="raw-excerpt">
                            <summary>View captured text</summary>
                            <pre>{readableExcerpt.raw}</pre>
                          </details>
                        {/if}
                      </li>
                    {/each}
                  </ul>
                {:else}
                  <p class="no-evidence">No captured source answers this question. That is an evidence gap, not validation.</p>
                {/if}
              </details>
            </article>
          {/each}
        </div>

        {#if onBranchDirection && gap && !isStale(result.ideaId, result.lens) && (result.lens === "demand" || result.lens === "competition")}
          <button type="button" class="shape-adjacent" onclick={onBranchDirection}>
            {BRANCH_DIRECTION_LABEL} <span aria-hidden="true">&rarr;</span>
          </button>
        {/if}

        <details class="run-details">
          <summary>Run details</summary>
          <p>Idea revision {result.ideaRevision} · {result.evidenceSnapshot.length} evidence items reviewed · {new Date(result.createdAt).toLocaleString()}</p>
        </details>
      {:else}
        {@const staleReview = isStale(focusedIdea?.idea_id ?? "", selectedLens)}
        <div class="empty">
          <p class="empty-label">{staleReview ? "Needs recheck" : "Not checked yet"}</p>
          <EmptyState
            title={staleReview ? "The evidence changed since this review" : LENS_COPY[selectedLens].empty}
            description={staleReview
              ? "Run this risk area again to include the current Discovery sources, evidence you added, and completed test results."
              : "Run this check to separate what the saved evidence supports, contradicts, or leaves unanswered."}
          >
            <SubmitButton
              type="button"
              label={staleReview ? LENS_COPY[selectedLens].action.replace("Check", "Recheck") : LENS_COPY[selectedLens].action}
              loadingText="Checking…"
              loading={running}
              disabled={!jobId}
              minWidth="0"
              onclick={() => void run()}
            />
            <div class="empty-supporting-actions">
              <p class="run-cost-note">Free · reviews saved evidence only</p>
              {#if focusedIdentity}
                <button type="button" class="add-evidence-action" data-tour="add-evidence" onclick={() => evidenceLedger?.openAddEvidence()}>
                  Add your evidence
                </button>
              {/if}
            </div>
            {#if runError}<p class="run-error" role="alert">{runError}</p>{/if}
          </EmptyState>
        </div>
      {/if}

      {#if focusedIdentity}
        <OwnerEvidenceLedger
          bind:this={evidenceLedger}
          {jobId}
          ideaId={focusedIdentity.id}
          ideaTitle={solutionDisplayTitle(focusedIdea!)}
          ideaRevision={focusedIdentity.revision}
          lens={selectedLens}
          prefill={validatedOwnerEvidencePrefill.prefill}
          showAddAction={false}
          onReturnToDraft={onReturnToEvidenceDraft}
          onChanged={() => { void load(); onChanged?.(); }}
        />
      {/if}
    </div>
  </div>

  <footer>
    Uses saved evidence only. Results never change scores or your shortlist.
  </footer>
</section>

<style>
  .challenge {
    padding: 0;
    background: transparent;
  }
  .challenge-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-6);
    padding-bottom: var(--space-3);
  }
  h3, h4, h5, p { margin: 0; }
  .challenge-head h3 { max-width: 38ch; font-size: var(--text-xl); line-height: var(--leading-tight); letter-spacing: var(--tracking-tight); text-wrap: balance; }
  .title-row { display: flex; align-items: flex-start; gap: var(--space-2); }
  .title-row h3 { min-width: 0; }
  .challenge-head p:not(.kicker) {
    max-width: 65ch;
    margin-top: var(--space-2);
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }
  .prefill-error {
    margin: 0 var(--space-6) var(--space-3);
    color: var(--color-error-text);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }
  .challenge-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    min-height: calc(var(--space-30) + var(--space-20) + var(--space-4));
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
    overflow: clip;
  }
  .lens-rail {
    overflow-x: auto;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }
  .lens-rail > div {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    min-width: 0;
  }
  .lens-rail button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    width: 100%;
    min-height: var(--space-16);
    padding: var(--space-2) var(--space-3);
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--color-text-secondary);
    text-align: left;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default);
  }
  .lens-rail button:hover { background: var(--color-bg-elevated); color: var(--color-text-primary); }
  .lens-rail button:active { transform: scale(0.98); }
  .lens-rail button.is-active {
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    box-shadow: inset 0 -2px 0 var(--color-accent);
  }
  .lens-rail span { display: grid; gap: var(--space-1); }
  .lens-rail strong { font-size: var(--text-13); line-height: var(--leading-snug); }
  .lens-rail small { max-width: 25ch; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-snug); text-wrap: pretty; }
  .lens-rail .badge-col { display: grid; gap: var(--space-1); justify-items: end; }
  .lens-rail .issue-badge {
    min-width: var(--space-5);
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-style: normal;
    font-weight: 700;
    text-align: right;
  }
  .lens-rail .issue-badge.is-stale { color: var(--color-warning-text); }
  .challenge-detail { min-width: 0; padding: var(--space-3) var(--space-4) var(--space-4); }
  .state-skeleton { display: grid; align-content: center; gap: var(--space-3); min-height: calc((var(--space-30) * 2) + var(--space-6)); }
  .state-skeleton span { height: var(--space-12); border-radius: var(--radius-md); background: var(--color-bg-surface); animation: challenge-pulse var(--duration-slowest) var(--ease-in-out) infinite alternate; }
  .state-skeleton span:nth-child(2) { animation-delay: var(--duration-fast); }
  .state-skeleton span:nth-child(3) { animation-delay: var(--duration-slow); }
  @keyframes challenge-pulse { to { opacity: 0.48; } }
  .state, .empty {
    display: grid;
    place-items: center;
    align-content: center;
    min-height: calc(var(--space-35) + var(--space-8));
    gap: var(--space-2);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    text-align: center;
  }
  .state-error { color: var(--color-error-text); }
  .empty-label { color: var(--color-text-secondary); font-size: var(--text-11); font-weight: 700; text-transform: uppercase; }
  .result-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-5); padding-bottom: var(--space-4); }
  .result-head h4 { max-width: 38ch; margin-top: var(--space-2); font-size: var(--text-lg); line-height: var(--leading-tight); text-wrap: balance; }
  .overall, .consensus, .evidence-class {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }
  .overall--contradicted, .consensus--contradicted { color: var(--color-error-text); }
  .overall--disputed, .consensus--disputed { color: var(--color-warning-text); }
  .overall--withstands, .consensus--supported { color: var(--color-success-text); }
  .recheck-action { display: grid; justify-items: end; gap: var(--space-1-5); }
  .run-error { margin: 0; color: var(--color-error-text); font-size: var(--text-11); text-align: right; }
  :global(.run-action) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-1-5);
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    white-space: nowrap;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default);
  }
  :global(.run-action:hover:not(:disabled)) { background: var(--color-bg-hover); border-color: var(--color-text-secondary); }
  :global(.run-action:active:not(:disabled)) { transform: scale(0.98); }
  :global(.run-action:disabled) { opacity: 0.5; cursor: not-allowed; }
  :global(.run-action svg) { width: var(--text-base); height: var(--text-base); }
  .disagreement {
    margin-bottom: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }
  .question-list { display: grid; }
  .question { padding: var(--space-5) 0; border-top: 1px solid var(--color-border); }
  .question > header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
  .question h5 { max-width: 48ch; font-size: var(--text-base); line-height: var(--leading-snug); text-wrap: balance; }
  .finding-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0;
    margin-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }
  .finding {
    min-width: 0;
    padding: var(--space-4) var(--space-4) var(--space-4) 0;
    border-bottom: 1px solid var(--color-border);
  }
  .finding:nth-child(even) {
    padding-right: 0;
    padding-left: var(--space-4);
    border-left: 1px solid var(--color-border);
  }
  .finding--unknown,
  .finding--next { grid-column: 1 / -1; padding-right: 0; }
  .finding--next { border-bottom: 0; }
  .finding h6 {
    margin: 0 0 var(--space-1);
    color: var(--color-text-primary);
    font-size: var(--text-13);
    font-weight: 800;
  }
  .finding > p {
    max-width: 65ch;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }
  .finding > p + p { margin-top: var(--space-2); }
  .finding > p strong {
    display: block;
    margin-bottom: var(--space-1);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
  }
  .disagreement { margin: var(--space-3) 0 0; }
  .evidence { margin-top: var(--space-3); }
  .evidence summary, .run-details summary {
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
  }
  .evidence ul { display: grid; gap: var(--space-3); margin: var(--space-3) 0 0; padding: 0; list-style: none; }
  .evidence li { padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .evidence li > div { display: flex; align-items: center; gap: var(--space-2); }
  .evidence li strong { min-width: 0; font-size: var(--text-13); line-height: var(--leading-snug); overflow-wrap: anywhere; }
  .evidence li a { display: inline-flex; margin-left: auto; color: var(--color-text-muted); transition: color var(--duration-fast) var(--ease-default); }
  .evidence li a:hover { color: var(--color-text-primary); }
  .evidence li a :global(svg) { width: var(--text-13); height: var(--text-13); }
  .evidence li p, .no-evidence {
    max-width: 65ch;
    margin-top: var(--space-2);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }
  .raw-excerpt { margin-top: var(--space-2); }
  .raw-excerpt summary {
    min-height: var(--space-6);
    color: var(--color-text-muted);
    font-size: var(--text-xs);
  }
  .raw-excerpt pre {
    max-width: 100%;
    margin: var(--space-2) 0 0;
    padding: var(--space-2);
    overflow: auto;
    border-radius: var(--radius-sm);
    background: var(--color-bg-subtle);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    line-height: var(--leading-normal);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .evidence-class { color: var(--color-text-secondary); }
  .gap-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-4);
    margin-top: var(--space-3);
  }
  .gap-action {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1-5);
    min-height: var(--space-8);
    padding: var(--space-1) 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 800;
    white-space: nowrap;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .gap-action:hover { color: var(--color-accent-hover); text-decoration: underline; }
  .gap-action:active { transform: scale(0.98); }
  /* Quiet ghost link: accent-dark text plus arrow, no aside chrome. */
  .shape-adjacent {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    margin-top: var(--space-3);
    min-height: var(--space-8);
    padding: var(--space-1) 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    white-space: nowrap;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .shape-adjacent:hover { color: var(--color-accent-hover); text-decoration: underline; }
  .shape-adjacent:active { transform: scale(0.98); }
  .run-details { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--color-border); }
  .run-details p { max-width: 65ch; margin-top: var(--space-2); color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); }
  .challenge > footer { max-width: 65ch; padding-top: var(--space-3); color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); text-wrap: pretty; }
  :global(.empty .empty-state) { padding: var(--space-4); }
  .empty-supporting-actions {
    display: grid;
    width: 100%;
    justify-items: center;
    gap: var(--space-1);
  }
  .run-cost-note { margin: 0; color: var(--color-text-muted); font-size: var(--text-xs); }
  .add-evidence-action {
    min-height: var(--space-8);
    padding: var(--space-1) 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    white-space: nowrap;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .add-evidence-action:hover { color: var(--color-accent-hover); text-decoration: underline; }
  .add-evidence-action:active { transform: scale(0.98); }
  button:focus-visible, summary:focus-visible, a:focus-visible, [role="tabpanel"]:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  @media (max-width: 760px) {
    .challenge { padding: var(--space-4); }
    .challenge-head { align-items: stretch; flex-direction: column; gap: var(--space-3); }
    .lens-rail > div { grid-template-columns: repeat(4, minmax(10rem, 1fr)); min-width: max-content; }
    .lens-rail button { min-height: var(--space-16); }
    .finding-grid { grid-template-columns: 1fr; }
    .finding,
    .finding:nth-child(even),
    .finding--unknown,
    .finding--next {
      grid-column: 1;
      padding: var(--space-3) 0;
      border-left: 0;
    }
  }
  @media (max-width: 520px) {
    .result-head { align-items: flex-start; flex-direction: column; }
    .recheck-action { width: 100%; justify-items: stretch; }
    :global(.run-action) { width: 100%; }
    .question > header { align-items: flex-start; flex-direction: column; gap: var(--space-2); }
    .gap-actions { align-items: flex-start; flex-direction: column; gap: var(--space-1); }
  }
  @media (prefers-reduced-motion: reduce) {
    .challenge *,
    .challenge *::before,
    .challenge *::after {
      scroll-behavior: auto !important;
      transition: none !important;
      animation: none !important;
    }
    .lens-rail button:active,
    :global(.run-action:hover:not(:disabled)),
    :global(.run-action:active:not(:disabled)),
    .gap-action:active,
    .add-evidence-action:active,
    .shape-adjacent:active { transform: none; }
  }
</style>
