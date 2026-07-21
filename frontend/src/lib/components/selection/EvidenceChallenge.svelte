<script lang="ts">
  import { tick } from "svelte";
  import { RefreshCw, ExternalLink, FlaskConical } from "lucide-svelte";
  import { getSelectionChallenges, runSelectionChallenge } from "$lib/api";
  import type { SolutionPreview } from "$lib/types/job";
  import type { SelectionExperimentDraftSeed } from "$lib/types/selectionExperiment";
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
  import OwnerEvidenceLedger from "./OwnerEvidenceLedger.svelte";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import { stressTestLabel } from "$lib/selection/labels";
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
    /** Candidate picked in the cockpit scope strip. Drives the internal
     *  selection; the strip is the only candidate-switching surface. */
    candidateId?: string | null;
    focus?: ChallengeFocus | null;
    onTestGap?: (draft: SelectionExperimentDraftSeed) => void;
    /** Captures the challenge finding as a tracked assumption (opens the
     *  assumption editor with a grounded draft; nothing is saved). */
    onTrackRisk?: (prefill: SelectionAssumptionPrefill) => void;
    /** Contextual Shape entry for open demand/competition gaps. Only passed
     *  when the forge is available. */
    onShapeAdjacent?: () => void;
    ownerEvidencePrefill?: SelectionOwnerEvidencePrefill | null;
  }

  let {
    jobId,
    ideas,
    candidateId = null,
    focus = null,
    onTestGap,
    onTrackRisk,
    onShapeAdjacent,
    ownerEvidencePrefill = null,
  }: Props = $props();
  let challenges = $state<SelectionChallenge[]>([]);
  let stale = $state<SelectionChallengeStaleReference[]>([]);
  let selectedIdeaId = $state("");
  let selectedLens = $state<SelectionChallengeLens>("demand");
  let loading = $state(false);
  let running = $state(false);
  let error = $state("");
  let runError = $state("");
  let runStatus = $state("");
  let lensRailOrientation = $state<"vertical" | "horizontal">("vertical");
  let loadedKey = "";
  let focusedRequestId = 0;
  const lensValues = SELECTION_CHALLENGE_LENSES.map((lens) => lens.value);
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
    selectedLens = lens;
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
    selectedLens = nextLens;
    queueMicrotask(() => document.getElementById(`evidence-lens-${nextLens}`)?.focus());
  }

  function ideaIdentity(idea: SolutionPreview): { id: string; revision: number } | null {
    if (!idea.idea_id || !Number.isInteger(idea.idea_revision) || Number(idea.idea_revision) < 1) return null;
    return { id: idea.idea_id, revision: Number(idea.idea_revision) };
  }

  function selectedIdea(): SolutionPreview | null {
    return ideas.find((idea) => idea.idea_id === selectedIdeaId) ?? ideas[0] ?? null;
  }

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


  function overallLabel(challenge: SelectionChallenge): string {
    return {
      withstands: "Evidence holds",
      weakened: "Case weakened",
      contradicted: "Contradiction found",
      disputed: "Assessments disagree",
      insufficient_evidence: "Evidence is insufficient",
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


  function experimentSeed(
    challenge: SelectionChallenge,
    question: SelectionChallengeQuestion,
  ): SelectionExperimentDraftSeed {
    const keys = [...new Set([...question.skeptic.evidenceKeys, ...question.auditor.evidenceKeys])];
    const cited = sourcesFor(challenge, keys);
    const evidenceText = cited.length
      ? cited.map((source) => source.title + ": " + source.excerpt).join("\n")
      : "The immutable challenge packet contains no source that answers this question.";
    const defaults = {
      demand: { assumptionType: "DESIRABILITY", method: "CUSTOMER_INTERVIEWS", evidenceSignal: "LANGUAGE" },
      competition: { assumptionType: "VIABILITY", method: "CUSTOMER_INTERVIEWS", evidenceSignal: "SMALL_COMMITMENT" },
      distribution: { assumptionType: "VIABILITY", method: "CTA_SMOKE_TEST", evidenceSignal: "CTA_INTEREST" },
      dependencies: { assumptionType: "FEASIBILITY", method: "TECHNICAL_SPIKE", evidenceSignal: "USAGE" },
    } as const;
    const method = question.questionId === "buyer_will_pay"
      ? { method: "PREORDER" as const, evidenceSignal: "PAYMENT_INTENT" as const }
      : defaults[challenge.lens];
    return {
      ideaId: challenge.ideaId,
      ideaRevision: challenge.ideaRevision,
      originChallengeId: challenge.id,
      originQuestionId: question.questionId,
      assumptionType: defaults[challenge.lens].assumptionType,
      assumption: SELECTION_CHALLENGE_ASSUMPTIONS[question.questionId]
        ?? (SELECTION_CHALLENGE_QUESTION_LABELS[question.questionId] ?? question.questionId),
      whyCritical: (
        (SELECTION_CHALLENGE_QUESTION_LABELS[question.questionId] ?? question.questionId)
        + " Current consensus: " + selectionChallengeConsensusLabel(question.consensus)
        + ". Skeptic: " + question.skeptic.summary
        + " Auditor: " + question.auditor.summary
      ).slice(0, 1500),
      currentEvidence: evidenceText.slice(0, 2000),
      method: method.method,
      evidenceSignal: method.evidenceSignal,
    };
  }

  /** Grounded assumption draft for the assumption-map editor. The drafted
   *  statement carries a challenge-question evidence reference, matching the
   *  copilot-prefill contract enforced by AssumptionMap. */
  function riskPrefill(
    challenge: SelectionChallenge,
    question: SelectionChallengeQuestion,
  ): SelectionAssumptionPrefill {
    const questionLabel = SELECTION_CHALLENGE_QUESTION_LABELS[question.questionId] ?? question.questionId;
    const lensName = SELECTION_CHALLENGE_LENSES.find((lens) => lens.value === challenge.lens)?.label ?? challenge.lens;
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
          label: `${lensName} evidence check · ${questionLabel} · ${consensusLabel}`,
          challengeId: challenge.id,
          questionId: question.questionId,
        }],
      },
      rationale: (
        `The ${lensName.toLowerCase()} check left this question at "${consensusLabel}". `
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
      error = cause instanceof Error ? cause.message : "Could not load evidence stress tests.";
    } finally {
      loading = false;
    }
  }

  async function run() {
    if (!jobId || running) return;
    const idea = selectedIdea();
    const identity = idea ? ideaIdentity(idea) : null;
    if (!identity) {
      runError = "This candidate is missing a stable reference. Reload the research before checking evidence.";
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
    } catch (cause) {
      runError = cause instanceof Error ? cause.message : "Evidence stress test failed.";
      runStatus = "";
    } finally {
      running = false;
    }
  }

  $effect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(max-width: 760px)");
    const update = () => { lensRailOrientation = query.matches ? "horizontal" : "vertical"; };
    update();
    if (typeof query.addEventListener !== "function") return;
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  });

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
      <p class="kicker">Independent evidence check</p>
      <div class="title-row">
        <h3 id="challenge-title">Try to break the case before you commit</h3>
        <DecisionHelp title="When to run a check" position="bottom">
          <p>Run a lens before you commit, and rerun whenever the candidate or its evidence changes. Results stay pinned to the exact inputs they saw. The packet spans saved research, your evidence ledger, and concluded experiments; an insufficient verdict means the packet can’t answer, not that the idea failed.</p>
        </DecisionHelp>
      </div>
      <p>Two isolated passes inspect the same captured research. Disagreement stays visible rather than averaged away.</p>
    </div>
  </header>

  {#if validatedOwnerEvidencePrefill.error}
    <p class="prefill-error" role="alert">{validatedOwnerEvidencePrefill.error}</p>
  {/if}

  <div class="sr-only" role="status" aria-live="polite">{runStatus}</div>

  <div class="challenge-layout">
    <nav class="lens-rail" aria-label="Evidence lenses">
      <div role="tablist" aria-orientation={lensRailOrientation}>
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
            <strong>{lens.label}</strong>
            <small>{lens.description}</small>
          </span>
          <span class="issue-badge" class:is-stale={stale}>
            {#if count !== null}{count}<span class="sr-only"> open issues</span>{:else if stale}Stale{:else}<span aria-hidden="true">·</span>{/if}
            {#if stale}<span class="sr-only"> (stale)</span>{/if}
          </span>
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
            <h4>{SELECTION_CHALLENGE_LENSES.find((lens) => lens.value === result.lens)?.label}</h4>
          </div>
          <div class="recheck-action">
            <SubmitButton
              type="button"
              class="run-action"
              label="Recheck"
              loadingText="Checking…"
              loading={running}
              icon={RefreshCw}
              minWidth="0"
              onclick={() => void run()}
            />
            {#if runError}<p class="run-error" role="alert">{runError}</p>{/if}
          </div>
        </header>

        {#if isStale(result.ideaId, result.lens)}
          <p class="stale-note">The research packet changed. This result remains visible for context, but it is not current.</p>
        {/if}

        <OwnerEvidenceLedger
          {jobId}
          ideaId={result.ideaId}
          ideaTitle={solutionDisplayTitle(selectedIdea()!)}
          ideaRevision={result.ideaRevision}
          lens={result.lens}
          prefill={validatedOwnerEvidencePrefill.prefill}
          onChanged={load}
        />

        {@const gap = actionableSelectionQuestion(result)}
        <div class="question-list">
          {#each result.questions as question}
            {@const citedKeys = [...new Set([...question.skeptic.evidenceKeys, ...question.auditor.evidenceKeys])]}
            {@const citedSources = sourcesFor(result, citedKeys)}
            <article class="question" class:is-disputed={question.consensus === "disputed"}>
              <header>
                <h5 id="challenge-question-{result.id}-{question.questionId}" tabindex="-1">{SELECTION_CHALLENGE_QUESTION_LABELS[question.questionId] ?? question.questionId}</h5>
                <span class="consensus consensus--{question.consensus}">{selectionChallengeConsensusLabel(question.consensus)}</span>
              </header>
              <div class="assessment-grid">
                <div>
                  <span>Falsification pass</span>
                  <strong>{question.skeptic.position}</strong>
                  <p>{question.skeptic.summary}</p>
                </div>
                <div>
                  <span>Evidence audit</span>
                  <strong>{question.auditor.position}</strong>
                  <p>{question.auditor.summary}</p>
                </div>
              </div>
              {#if question.consensus === "disputed"}
                <p class="disagreement">Conflict in the record: the two independent readings reached opposing conclusions. The evidence below is preserved instead of averaged away.</p>
              {/if}
              <details class="evidence">
                <summary>{citedSources.length} cited source{citedSources.length === 1 ? "" : "s"}</summary>
                {#if citedSources.length}
                  <ul>
                    {#each citedSources as source}
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
                        <p>{source.excerpt}</p>
                      </li>
                    {/each}
                  </ul>
                {:else}
                  <p class="no-evidence">No captured source answers this question. That is an evidence gap, not validation.</p>
                {/if}
              </details>
              {#if gap?.questionId === question.questionId && !isStale(result.ideaId, result.lens) && (onTestGap || onTrackRisk)}
                <div class="gap-actions">
                  {#if onTestGap}
                    <button type="button" class="test-gap" onclick={() => onTestGap?.(experimentSeed(result, question))}>
                      <FlaskConical aria-hidden="true" /> Plan a test
                    </button>
                  {/if}
                  {#if onTrackRisk}
                    <button type="button" class="test-gap" onclick={() => onTrackRisk?.(riskPrefill(result, question))}>
                      Track as risk
                    </button>
                  {/if}
                </div>
              {/if}
            </article>
          {/each}
        </div>

        {#if onShapeAdjacent && gap && !isStale(result.ideaId, result.lens) && (result.lens === "demand" || result.lens === "competition")}
          <button type="button" class="shape-adjacent" onclick={onShapeAdjacent}>
            Shape an adjacent direction <span aria-hidden="true">&rarr;</span>
          </button>
        {/if}

        <details class="run-details">
          <summary>Run details</summary>
          <p>Idea revision {result.ideaRevision} · {result.evidenceSnapshot.length} sources checked · {new Date(result.createdAt).toLocaleString()}</p>
        </details>
      {:else}
        {@const emptyIdea = selectedIdea()}
        {@const emptyIdentity = emptyIdea ? ideaIdentity(emptyIdea) : null}
        {#if emptyIdentity}
          <OwnerEvidenceLedger
            {jobId}
            ideaId={emptyIdentity.id}
            ideaTitle={solutionDisplayTitle(emptyIdea!)}
            ideaRevision={emptyIdentity.revision}
            lens={selectedLens}
            prefill={validatedOwnerEvidencePrefill.prefill}
            onChanged={load}
          />
        {/if}
        <div class="empty">
          <p class="empty-label">{isStale(selectedIdea()?.idea_id ?? "", selectedLens) ? "Previous result is stale" : "Not checked yet"}</p>
          <EmptyState
            title="Test the captured evidence, not the score"
            description="The two passes answer three fixed questions and can only cite sources already saved with this research."
          >
            <SubmitButton
              type="button"
              label={stressTestLabel(SELECTION_CHALLENGE_LENSES.find((item) => item.value === selectedLens)?.label)}
              loadingText="Checking…"
              loading={running}
              disabled={!jobId}
              minWidth="0"
              onclick={() => void run()}
            />
            {#if runError}<p class="run-error" role="alert">{runError}</p>{/if}
          </EmptyState>
        </div>
      {/if}
    </div>
  </div>

  <footer>Reviews and owner evidence never change scores or the shortlist. “Plan a test” opens an editable owner plan; it does not start a test.</footer>
</section>

<style>
  .challenge {
    padding: 1.1rem 1.5rem 1rem;
    background: var(--color-bg-surface);
  }
  .challenge-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.5rem;
    padding-bottom: 0.9rem;
  }
  .kicker {
    margin: 0 0 0.3rem;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  h3, h4, h5, p { margin: 0; }
  .challenge-head h3 { font-size: var(--text-md); line-height: 1.3; }
  .title-row { display: flex; align-items: center; gap: 0.5rem; }
  .title-row h3 { min-width: 0; }
  .challenge-head p:not(.kicker) {
    max-width: 43rem;
    margin-top: 0.35rem;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
  }
  .prefill-error {
    margin: 0 1.5rem 0.8rem;
    color: var(--color-error-text);
    font-size: var(--text-sm);
    line-height: 1.45;
  }
  .challenge-layout {
    display: grid;
    grid-template-columns: minmax(12rem, 0.24fr) minmax(0, 1fr);
    min-height: 19rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: var(--color-bg-elevated);
  }
  .lens-rail {
    padding: 0.4rem;
    border-right: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-elevated) 68%, var(--color-bg-surface));
  }
  .lens-rail > div { display: flex; flex-direction: column; }
  .lens-rail button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    width: 100%;
    min-height: 4.1rem;
    padding: 0.68rem 0.75rem;
    border: 0;
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    text-align: left;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default);
  }
  .lens-rail button:hover { background: color-mix(in srgb, var(--color-bg-surface) 82%, transparent); }
  .lens-rail button:active { transform: scale(0.98); }
  .lens-rail button.is-active {
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
    box-shadow: inset 2px 0 0 var(--color-accent);
  }
  .lens-rail span { display: grid; gap: 0.18rem; }
  .lens-rail strong { font-size: var(--text-sm); }
  .lens-rail small { color: var(--color-text-secondary); font-size: var(--text-xs); line-height: 1.35; }
  .lens-rail .issue-badge {
    min-width: 1.35rem;
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-style: normal;
    font-weight: 700;
    text-align: right;
  }
  .lens-rail .issue-badge.is-stale { color: var(--color-error-text); }
  .challenge-detail { min-width: 0; padding: 0.85rem 1.1rem 1rem; }
  .state-skeleton { display: grid; align-content: center; gap: 0.7rem; min-height: 16.5rem; }
  .state-skeleton span { height: 3.2rem; border-radius: var(--radius-md); background: var(--color-bg-surface); animation: challenge-pulse 1.2s ease-in-out infinite alternate; }
  .state-skeleton span:nth-child(2) { animation-delay: 120ms; }
  .state-skeleton span:nth-child(3) { animation-delay: 240ms; }
  @keyframes challenge-pulse { to { opacity: 0.48; } }
  .state, .empty {
    display: grid;
    place-items: center;
    align-content: center;
    min-height: 16.5rem;
    gap: 0.5rem;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    text-align: center;
  }
  .state-error { color: var(--color-error-text); }
  .empty-label { color: var(--color-text-secondary); font-size: var(--text-11); font-weight: 700; text-transform: uppercase; }
  .result-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding-bottom: 0.85rem; }
  .result-head h4 { margin-top: 0.35rem; font-size: var(--text-md); }
  .overall, .consensus, .evidence-class {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  .overall--contradicted, .consensus--contradicted { color: var(--color-error-text); }
  .overall--disputed, .consensus--disputed { color: var(--color-warning-text); }
  .overall--withstands, .consensus--supported { color: var(--color-success-text); }
  .recheck-action { display: grid; justify-items: end; gap: 0.35rem; }
  .run-error { margin: 0; color: var(--color-error-text); font-size: var(--text-11); text-align: right; }
  :global(.run-action) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-height: 2.3rem;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default);
  }
  :global(.run-action:hover:not(:disabled)) { background: var(--color-bg-hover); border-color: var(--color-text-secondary); }
  :global(.run-action:active:not(:disabled)) { transform: scale(0.98); }
  :global(.run-action:disabled) { opacity: 0.5; cursor: not-allowed; }
  :global(.run-action svg) { width: 0.9rem; height: 0.9rem; }
  .stale-note, .disagreement {
    margin-bottom: 0.7rem;
    padding: 0.65rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
    font-size: var(--text-11);
    line-height: 1.45;
  }
  .question-list { display: grid; }
  .question { padding: 0.9rem 0; border-top: 1px solid var(--color-border); }
  .question > header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
  .question h5 { font-size: var(--text-sm); line-height: 1.35; }
  .assessment-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.65rem; }
  .assessment-grid > div { min-width: 0; }
  .assessment-grid span { color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 700; }
  .assessment-grid strong { display: block; margin-top: 0.18rem; font-size: var(--text-11); text-transform: capitalize; }
  .assessment-grid p { margin-top: 0.3rem; color: var(--color-text-secondary); font-size: var(--text-11); line-height: 1.46; }
  .disagreement { margin: 0.7rem 0 0; }
  .evidence { margin-top: 0.65rem; }
  .evidence summary, .run-details summary {
    color: var(--color-text-secondary);
    font-size: var(--text-11);
    font-weight: 700;
    cursor: pointer;
  }
  .evidence ul { display: grid; gap: 0.65rem; margin: 0.65rem 0 0; padding: 0; list-style: none; }
  .evidence li { padding: 0.65rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .evidence li > div { display: flex; align-items: center; gap: 0.45rem; }
  .evidence li strong { min-width: 0; font-size: var(--text-11); overflow-wrap: anywhere; }
  .evidence li a { display: inline-flex; margin-left: auto; color: var(--color-text-muted); transition: color var(--duration-fast) var(--ease-default); }
  .evidence li a:hover { color: var(--color-text-primary); }
  .evidence li a :global(svg) { width: 0.78rem; height: 0.78rem; }
  .evidence li p, .no-evidence {
    margin-top: 0.35rem;
    color: var(--color-text-secondary);
    font-size: var(--text-11);
    line-height: 1.45;
  }
  .evidence-class { color: var(--color-text-secondary); }
  .gap-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
    margin-top: .65rem;
  }
  .test-gap {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-11);
    font-weight: 800;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .test-gap:hover { color: var(--color-accent-hover); text-decoration: underline; }
  .test-gap:active { transform: scale(0.98); }
  .test-gap :global(svg) { width: .85rem; height: .85rem; }
  /* Quiet ghost link: accent-dark text plus arrow, no aside chrome. */
  .shape-adjacent {
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    margin-top: .8rem;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-11);
    font-weight: 700;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .shape-adjacent:hover { color: var(--color-accent-hover); text-decoration: underline; }
  .shape-adjacent:active { transform: scale(0.98); }
  .run-details { margin-top: 0.8rem; padding-top: 0.75rem; border-top: 1px solid var(--color-border); }
  .run-details p { margin-top: 0.4rem; color: var(--color-text-secondary); font-size: var(--text-xs); }
  .challenge > footer { padding-top: 0.75rem; color: var(--color-text-secondary); font-size: var(--text-xs); }
  button:focus-visible, summary:focus-visible, a:focus-visible, [role="tabpanel"]:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  @media (max-width: 760px) {
    .challenge { padding: 1rem; }
    .challenge-head { align-items: stretch; flex-direction: column; gap: 0.8rem; }
    .challenge-layout { display: block; }
    .lens-rail {
      overflow-x: auto;
      border-right: 0;
      border-bottom: 1px solid var(--color-border);
    }
    .lens-rail > div { flex-direction: row; min-width: max-content; }
    .lens-rail button { flex: 0 0 10rem; min-height: 4rem; }
    .lens-rail button.is-active { box-shadow: inset 0 -2px 0 var(--color-accent); }
    .assessment-grid { grid-template-columns: 1fr; }
  }
</style>
