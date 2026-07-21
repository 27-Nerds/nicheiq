<script lang="ts">
  import { page } from "$app/state";
  import { invalidateAll, replaceState } from "$app/navigation";
  import type { Snippet } from "svelte";
  import type { LayoutData } from "./$types";
  import { MessageSquare, Plus, X } from "lucide-svelte";
  import AnnotationProvider from "$lib/components/annotations/AnnotationProvider.svelte";
  import ChatThread from "$lib/components/chat/ChatThread.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import PhaseNav from "$lib/components/nav/PhaseNav.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import { buildSelectionJourney } from "$lib/selection/decisionJourney";
  import DecisionCockpit from "$lib/components/selection/DecisionCockpit.svelte";
  import ExperimentWorkspace from "$lib/components/selection/ExperimentWorkspace.svelte";
  import ConceptForge from "$lib/components/selection/ConceptForge.svelte";
  import DecisionBrief from "$lib/components/selection/DecisionBrief.svelte";
  import { chatPanel } from "$lib/stores/chatPanel.svelte";
  import {
    getSelectionDecisionState,
    getStageCosts,
    saveSelectionDraft,
    seedIdea,
    ApiError,
    type SelectionWorkspaceContext,
    type IdeaSynthesisPatch,
  } from "$lib/api";
  import type { SelectionDraftItem, SolutionPreview } from "$lib/types/job";
  import type { SelectionExperimentPrefill } from "$lib/types/selectionExperiment";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import {
    setWorkspaceTools,
    workspaceIdeaKey,
    type WorkspaceChallengeFocus,
    type WorkspaceTestSeed,
  } from "$lib/selection/workspaceTools";
  import {
    START_DEEP_RESEARCH_LABEL,
    WORKSPACE_ROUTES,
    founderContextLabel,
  } from "$lib/selection/labels";
  import { formatBuildConstraints } from "$lib/selection/profileFormat";

  interface Props {
    data: LayoutData;
    children: Snippet;
  }

  let { data, children }: Props = $props();

  const MAX_SCOPE = 3;

  const activeSlug = $derived(page.url.pathname.split("/").at(-1) ?? "compare");
  const interactive = $derived(data.job.status === "AWAITING_SELECTION");

  // The active tool label drives the breadcrumb tail; the journey drives the
  // sidebar tool statuses — same source the job-page launchpad uses.
  const activeToolLabel = $derived(
    WORKSPACE_ROUTES.find((route) => route.slug === activeSlug)?.label ?? "Selection",
  );
  const journeyTasks = $derived(
    data.decisionState ? buildSelectionJourney(data.decisionState).tasks : undefined,
  );

  // ── Shortlist: the scope strip is the control, not a caption ──────────────
  // Hydrated from the server draft and re-hydrated whenever the server version
  // moves (our own save, or another tab). Local edits are optimistic; a failed
  // save rolls the strip back to the last known-good server state.
  let shortlistKeys = $state<string[]>([]);
  let shortlistVersion = $state(0);
  let shortlistBusy = $state(false);
  let shortlistError = $state("");
  let hydratedFrom = $state("");
  let addingScope = $state(false);

  const solutionsByKey = $derived(new Map(
    data.solutions.map((solution) => [workspaceIdeaKey(solution), solution]),
  ));

  $effect(() => {
    const serverItems = data.decisionState?.shortlist.items ?? [];
    const version = data.decisionState?.shortlist.version ?? 0;
    const signature = `${data.job.id}:${version}:${serverItems.map((i) => `${i.ideaId}@${i.ideaRevision}`).join(",")}`;
    if (hydratedFrom === signature) return;
    hydratedFrom = signature;
    shortlistVersion = version;
    shortlistKeys = serverItems
      .map((item) => data.solutions.find((solution) => (
        solution.idea_id === item.ideaId && (solution.idea_revision ?? 1) === item.ideaRevision
      )))
      .filter((solution): solution is SolutionPreview => Boolean(solution))
      .map(workspaceIdeaKey);
  });

  const scopeIdeas = $derived(
    shortlistKeys
      .map((key) => solutionsByKey.get(key))
      .filter((solution): solution is SolutionPreview => Boolean(solution)),
  );
  /** Scope falls back to the link-resolved ideas so a shared URL still shows
   *  something before any shortlist exists. */
  const activeIdeas = $derived(scopeIdeas.length > 0 ? scopeIdeas : data.workspace.ideas);
  const addableIdeas = $derived(
    data.solutions.filter((solution) => !shortlistKeys.includes(workspaceIdeaKey(solution))),
  );
  const shortlistFull = $derived(shortlistKeys.length >= MAX_SCOPE);

  async function persistShortlist(nextKeys: string[]): Promise<void> {
    const previous = shortlistKeys;
    const previousVersion = shortlistVersion;
    shortlistKeys = nextKeys;
    shortlistBusy = true;
    shortlistError = "";
    const items: SelectionDraftItem[] = nextKeys
      .map((key) => solutionsByKey.get(key))
      .filter((solution): solution is SolutionPreview => Boolean(solution?.idea_id))
      .map((solution) => ({
        ideaId: solution.idea_id as string,
        ideaRevision: solution.idea_revision ?? 1,
      }));
    try {
      const draft = await saveSelectionDraft(data.job.id, previousVersion, items);
      shortlistVersion = draft.version;
      hydratedFrom = "";
      await invalidateAll();
    } catch (error) {
      shortlistKeys = previous;
      shortlistError = error instanceof ApiError && error.status === 409
        ? "Your shortlist changed in another tab. Reload to continue."
        : error instanceof Error
          ? error.message
          : "We could not save your shortlist.";
    } finally {
      shortlistBusy = false;
    }
  }

  function toggleShortlist(idea: SolutionPreview): void {
    if (!interactive || shortlistBusy) return;
    const key = workspaceIdeaKey(idea);
    if (shortlistKeys.includes(key)) {
      void persistShortlist(shortlistKeys.filter((item) => item !== key));
      return;
    }
    if (shortlistKeys.length >= MAX_SCOPE) return;
    void persistShortlist([...shortlistKeys, key]);
  }

  // ── Tools, opened in place over the page that asked for them ──────────────
  let cockpitOpen = $state(false);
  let cockpitMode = $state<"market" | "fit" | "challenge" | "risk" | "assumptions">("challenge");
  let challengeFocus = $state<(WorkspaceChallengeFocus & { requestId: number }) | null>(null);
  let focusSequence = 0;
  let experimentOpen = $state(false);
  let experimentPrefill = $state<SelectionExperimentPrefill | null>(null);
  let forgeOpen = $state(false);
  let forgeError = $state("");
  let seedCost = $state<number | null>(null);
  let decisionBriefRef = $state<DecisionBrief | null>(null);
  let toolError = $state("");

  $effect(() => {
    void getStageCosts()
      .then((costs) => { seedCost = costs.seed_idea ?? null; })
      .catch(() => { seedCost = null; });
  });

  /** One tool at a time: two stacked aria-modal dialogs corrupt the AX tree. */
  function closeTools(): void {
    cockpitOpen = false;
    experimentOpen = false;
    forgeOpen = false;
    experimentPrefill = null;
    challengeFocus = null;
    forgeError = "";
    toolError = "";
    decisionBriefRef?.closeEditor?.();
  }

  function openCockpit(mode: typeof cockpitMode, focus?: WorkspaceChallengeFocus): void {
    if (activeIdeas.length === 0) {
      toolError = "Add a candidate to your shortlist before opening this tool.";
      return;
    }
    closeTools();
    cockpitMode = mode;
    if (focus) challengeFocus = { ...focus, requestId: ++focusSequence };
    cockpitOpen = true;
  }

  async function openTestPlanner(seed?: WorkspaceTestSeed): Promise<void> {
    if (activeIdeas.length === 0) {
      toolError = "Add a candidate to your shortlist before planning a test.";
      return;
    }
    closeTools();
    if (seed?.assumptionId) {
      try {
        const state = data.decisionState ?? await getSelectionDecisionState(data.job.id);
        const assumption = state.assumptions.find((item) => (
          item.id === seed.assumptionId
          && item.idea.ideaId === seed.ideaId
          && item.idea.ideaRevision === seed.ideaRevision
        ));
        if (assumption) {
          experimentPrefill = {
            requestId: crypto.randomUUID(),
            draft: {
              ideaId: seed.ideaId,
              ideaRevision: seed.ideaRevision,
              assumptionId: assumption.id,
              assumption: assumption.statement,
              whyCritical: assumption.impact,
              originChallengeId: assumption.originChallengeId,
              originQuestionId: assumption.originQuestionId,
            },
          };
        }
      } catch {
        toolError = "We could not load that assumption. The planner opened without it.";
      }
    } else if (seed) {
      experimentPrefill = {
        requestId: crypto.randomUUID(),
        draft: { ideaId: seed.ideaId, ideaRevision: seed.ideaRevision },
      };
    }
    experimentOpen = true;
  }

  async function handleForgeEvaluate(
    patch: IdeaSynthesisPatch,
    sourceMessageId: string,
  ): Promise<boolean> {
    forgeError = "";
    try {
      await seedIdea(data.job.id, {
        kind: "idea_synthesis",
        sourceMessageId,
        expectedCost: seedCost ?? 0,
      });
      await invalidateAll();
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const fresh = await getStageCosts().catch(() => null);
        seedCost = fresh?.seed_idea ?? seedCost;
        forgeError = "The price changed. Review the new cost and try again.";
      } else {
        forgeError = error instanceof Error ? error.message : "We could not evaluate that direction.";
      }
      return false;
    }
  }

  // ── Deep links ────────────────────────────────────────────────────────────
  // `?tool=` opens a tool on arrival, so the decision rail and the analyst can
  // link straight to a specific check. The param is stripped once handled: it
  // is a one-shot instruction, not overlay state, so closing the tool or
  // refreshing the page never silently re-opens it.
  // Plain variable, not $state: it is a write-only dedupe guard, and reading
  // and writing reactive state in the same effect re-triggers that effect.
  let handledToolQuery = "";

  $effect(() => {
    const tool = page.url.searchParams.get("tool");
    if (!tool || !interactive) return;
    const signature = `${page.url.pathname}${page.url.search}`;
    if (handledToolQuery === signature) return;
    handledToolQuery = signature;

    const ideaId = page.url.searchParams.get("ideaId");
    const ideaRevision = Number(page.url.searchParams.get("ideaRevision") ?? "1");
    const requestedLens = page.url.searchParams.get("lens");
    const lens = requestedLens === "demand"
      || requestedLens === "distribution"
      || requestedLens === "competition"
      || requestedLens === "dependencies"
      ? requestedLens
      : data.workspace.lens;
    const focus = ideaId && Number.isInteger(ideaRevision) && ideaRevision >= 1
      ? { ideaId, ideaRevision, lens }
      : undefined;
    // Read before stripping: `page.url` is live and the params are gone by the
    // time the microtask below runs.
    const assumptionId = page.url.searchParams.get("assumptionId") ?? undefined;

    queueMicrotask(() => {
      if (tool === "constraints") decisionBriefRef?.openEditor();
      else if (tool === "variants") { closeTools(); forgeOpen = true; }
      else if (tool === "fit") openCockpit("fit");
      else if (tool === "compare") openCockpit("market");
      else if (tool === "assumptions") openCockpit("assumptions", focus);
      else if (tool === "challenge") openCockpit("challenge", focus);
      else if (tool === "tests") {
        void openTestPlanner(focus
          ? { ideaId: focus.ideaId, ideaRevision: focus.ideaRevision, assumptionId }
          : undefined);
      }

      // Strip AFTER opening: a router that is not ready yet must never stop the
      // tool from opening. `lens` stays; it is real workspace state.
      stripToolQuery();
    });
  });

  /** Drops the one-shot tool params so closing the tool or refreshing never
   *  re-opens something the user already dismissed. On a cold load the router
   *  may not be ready on the first try, so this retries once. */
  function stripToolQuery(attempt = 0): void {
    const stripped = new URL(page.url);
    let changed = false;
    for (const key of ["tool", "ideaId", "ideaRevision", "assumptionId"]) {
      if (stripped.searchParams.has(key)) {
        stripped.searchParams.delete(key);
        changed = true;
      }
    }
    if (!changed) return;
    try {
      replaceState(`${stripped.pathname}${stripped.search}`, page.state);
    } catch {
      if (attempt < 1) setTimeout(() => stripToolQuery(attempt + 1), 250);
    }
  }

  setWorkspaceTools({
    openChallenge: (focus) => openCockpit("challenge", focus),
    openAssumptions: (focus) => openCockpit("assumptions", focus),
    openTestPlanner: (seed) => { void openTestPlanner(seed); },
    openVariants: () => { closeTools(); forgeOpen = true; },
    openConstraints: () => { closeTools(); decisionBriefRef?.openEditor(); },
    openFit: () => openCockpit("fit"),
    toggleShortlist,
    isShortlisted: (idea) => shortlistKeys.includes(workspaceIdeaKey(idea)),
    shortlistFull: () => shortlistFull,
    shortlistBusy: () => shortlistBusy,
  });

  // ── Header context and forward action ─────────────────────────────────────
  const profile = $derived(data.decisionState?.profile ?? null);
  const constraintsLine = $derived(profile ? formatBuildConstraints(profile) : null);
  const deepResearchReady = $derived(Boolean(data.decisionState?.deepResearch.eligible));

  const analystContext = $derived<SelectionWorkspaceContext>({
    workspace: activeSlug === "risks"
      ? "risks"
      : activeSlug === "tests"
        ? "tests"
        : activeSlug === "alternatives"
          ? "alternatives"
          : "compare",
    ideas: data.workspace.refs.map((idea) => ({ ...idea })),
    lens: activeSlug === "risks" ? data.workspace.lens : undefined,
  });
  const analystStarters = $derived([
    activeSlug === "compare"
      ? "Explain the most decision-relevant difference between these candidates."
      : activeSlug === "risks"
        ? "Which unresolved evidence gap is most likely to change my choice?"
        : activeSlug === "tests"
          ? "Help me turn the biggest open assumption into a small, decisive test."
          : "Suggest a meaningfully different direction without changing my current shortlist.",
  ]);
</script>

<svelte:head>
  <title>Selection workspace · {data.job.niche} · NicheIQ</title>
</svelte:head>

<AnnotationProvider
  mode="owner"
  enabled={data.job.status === "AWAITING_SELECTION" || data.job.status === "REGENERATING"}
  jobId={data.job.id}
  surfaceKey={`selection:workspace:${activeSlug}`}
>
<div class="job-page-shell">
  <PhaseNav
    jobStatus={data.job.status}
    entryMode={data.job.entryMode}
    mode="selection"
    nested
    jobId={data.job.id}
    activeTool={activeSlug}
    toolTasks={journeyTasks}
    selectionCount={data.solutions.length}
    selectedCount={shortlistKeys.length}
  />
  <main class="job-page-content job-page-content--selection">
  <PageHeader
    class="ws-header"
    breadcrumbItems={[
      { label: "Dashboard", href: "/dashboard" },
      { label: "Selection", href: `/jobs/${data.job.id}` },
    ]}
    breadcrumbCurrent={activeToolLabel}
    title={data.job.niche}
    titleVariant="research-topic"
  >
    {#snippet actions()}
      <button type="button" class="ask-analyst" onclick={() => chatPanel.open()}>
        <MessageSquare aria-hidden="true" />
        Ask analyst
      </button>
    {/snippet}
    {#snippet below()}
      <button type="button" class="constraints-line" onclick={() => decisionBriefRef?.openEditor()}>
        <span class="constraints-key">Your constraints</span>
        <span class="constraints-value">{constraintsLine ?? "Not saved yet"}</span>
        <span class="constraints-edit">{founderContextLabel(Boolean(profile))}</span>
      </button>
    {/snippet}
  </PageHeader>

  <section class="scope-strip" aria-labelledby="scope-title">
    <div class="scope-heading">
      <p id="scope-title">Shortlist</p>
      <span class="scope-count" aria-label={`${shortlistKeys.length} of ${MAX_SCOPE} shortlisted`}>
        {shortlistKeys.length}<span aria-hidden="true">/{MAX_SCOPE}</span>
      </span>
    </div>
    <div class="candidate-pills">
      {#each activeIdeas as idea (workspaceIdeaKey(idea))}
        {@const shortlisted = shortlistKeys.includes(workspaceIdeaKey(idea))}
        <span class="candidate-pill" class:preview={!shortlisted}>
          <span class="pill-title">{solutionDisplayTitle(idea)}</span>
          {#if (idea.idea_revision ?? 1) > 1}
            <small>rev {idea.idea_revision}</small>
          {/if}
          {#if interactive && shortlisted}
            <button
              type="button"
              class="pill-remove"
              disabled={shortlistBusy}
              aria-label={`Remove ${solutionDisplayTitle(idea)} from shortlist`}
              onclick={() => toggleShortlist(idea)}
            >
              <X aria-hidden="true" />
            </button>
          {/if}
        </span>
      {:else}
        <span class="empty-scope">No candidates are available for this research yet.</span>
      {/each}

      {#if interactive && !shortlistFull && addableIdeas.length > 0}
        <div class="scope-add">
          <button
            type="button"
            class="add-trigger"
            aria-expanded={addingScope}
            disabled={shortlistBusy}
            onclick={() => (addingScope = !addingScope)}
          >
            <Plus aria-hidden="true" />
            Add candidate
          </button>
          {#if addingScope}
            <ul class="add-menu">
              {#each addableIdeas.slice(0, 12) as idea (workspaceIdeaKey(idea))}
                <li>
                  <button
                    type="button"
                    onclick={() => { toggleShortlist(idea); addingScope = false; }}
                  >{solutionDisplayTitle(idea)}</button>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    </div>
    {#if shortlistError}
      <p class="scope-error" role="alert">{shortlistError}</p>
    {/if}
  </section>

  {#if data.workspace.notices.length > 0}
    <aside class="scope-notice" aria-live="polite">
      <span class="notice-icon" aria-hidden="true">i</span>
      <div>
        <strong>We adjusted this link safely</strong>
        {#each data.workspace.notices as notice}<p>{notice}</p>{/each}
      </div>
    </aside>
  {/if}

  {#if toolError}
    <p class="tool-error" role="alert">{toolError}</p>
  {/if}

  <main class="workspace-content">
    {@render children()}
  </main>

  {#if interactive}
    <div class="workspace-commit">
      <p>
        {deepResearchReady
          ? "Your shortlist is saved. Every step here is optional."
          : "Shortlist at least one candidate to continue."}
      </p>
      <a class="commit-cta" class:ready={deepResearchReady} href={`/jobs/${data.job.id}#deep-research`}>
        {START_DEEP_RESEARCH_LABEL}
        <span aria-hidden="true">→</span>
      </a>
    </div>
  {/if}
  </main>
</div>

<DecisionBrief
  bind:this={decisionBriefRef}
  jobId={data.job.id}
  profile={profile}
  variant="summary"
  hideSummary
  onSaved={() => { hydratedFrom = ""; void invalidateAll(); }}
/>

<DecisionCockpit
  open={cockpitOpen}
  jobId={data.job.id}
  ideas={activeIdeas}
  profile={profile}
  initialMode={cockpitMode}
  tabGroup={cockpitMode === "market" || cockpitMode === "fit" ? "compare" : "pressure"}
  initialChallengeFocus={challengeFocus}
  shortlistedIdeaKeys={shortlistKeys}
  shortlistAtCapacity={shortlistFull}
  shortlistDisabled={!interactive || shortlistBusy}
  onToggleShortlist={toggleShortlist}
  onOpenFounderContext={() => { closeTools(); decisionBriefRef?.openEditor(); }}
  onAskAnalyst={() => chatPanel.open()}
  onTestUnknown={(draft) => {
    closeTools();
    experimentPrefill = { requestId: crypto.randomUUID(), draft };
    experimentOpen = true;
  }}
  onShapeAdjacent={() => { closeTools(); forgeOpen = true; }}
  {seedCost}
  onClose={() => { cockpitOpen = false; challengeFocus = null; void invalidateAll(); }}
/>

<ExperimentWorkspace
  open={experimentOpen}
  jobId={data.job.id}
  ideas={activeIdeas}
  prefill={experimentPrefill}
  {seedCost}
  onOpenChallenge={() => openCockpit("challenge")}
  onChanged={() => { void invalidateAll(); }}
  onClose={() => { experimentOpen = false; experimentPrefill = null; void invalidateAll(); }}
/>

<ConceptForge
  open={forgeOpen}
  jobId={data.job.id}
  parents={activeIdeas}
  {seedCost}
  disabled={!interactive}
  evaluateError={forgeError}
  onEvaluate={handleForgeEvaluate}
  onClose={() => { forgeOpen = false; forgeError = ""; }}
/>

<WorkspaceOverlay
  open={chatPanel.isOpen}
  modal={chatPanel.isExpanded}
  label="Analyst conversation"
  onClose={() => chatPanel.close()}
>
  <ChatThread
    jobId={data.job.id}
    dock="rail"
    selectionContext={analystContext}
    starters={analystStarters}
    focused={chatPanel.isExpanded}
    onToggleFocus={() => chatPanel.toggleExpanded()}
    onCollapse={() => chatPanel.close()}
  />
</WorkspaceOverlay>

</AnnotationProvider>

<style>
  /* Same shell as the job page: sidebar + content, full-bleed, matched width.
     The workspace is a drill-down of the decision, not a different app. */
  .job-page-shell { display: flex; align-items: flex-start; }
  .job-page-content {
    --workspace-ink: var(--color-text-primary);
    --workspace-muted: var(--color-text-secondary);
    --workspace-line: var(--color-border);
    --workspace-accent: var(--color-accent-hover);
    flex: 1;
    min-width: 0;
    width: min(76rem, 100%);
    margin: 0 auto;
    padding: 2rem 2.5rem 4rem;
    color: var(--workspace-ink);
  }

  /* The niche is CONTEXT on a tool page, not the hero — it rides just under the
     breadcrumb, quieter than the tool's own H2. The loudest heading above the
     fold is the tool heading, not the repeated niche name. Scoped via .ws-header
     so the job page's title is untouched. */
  :global(.ws-header .page-header-title--research-topic) { font-size: var(--text-md); line-height: 1.2; color: var(--color-text-secondary); }
  :global(.ws-header) { margin-bottom: var(--space-6); }

  .ask-analyst { display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem; min-height: 2.25rem; padding: 0.5rem 0.85rem; border: 1px solid var(--workspace-line); border-radius: 999px; color: var(--workspace-ink); background: var(--color-bg-elevated); box-shadow: var(--shadow-sm); font: inherit; font-size: var(--text-13); font-weight: 700; cursor: pointer; transition: border-color 220ms cubic-bezier(0.32, 0.72, 0, 1), box-shadow 220ms cubic-bezier(0.32, 0.72, 0, 1); }
  .ask-analyst:hover { border-color: var(--color-border-emphasis); box-shadow: var(--shadow-md); }
  .ask-analyst:active { transform: scale(0.98); }
  .ask-analyst :global(svg) { width: 1rem; height: 1rem; }

  /* The constraints that govern every "fit" number on these pages, stated
     once in the shell instead of only inside the evidence dialog. */
  .constraints-line { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: baseline; margin-top: var(--space-3); padding: 0.5rem 0.75rem; border: 1px solid var(--workspace-line); border-radius: var(--radius-md); background: var(--color-bg-surface); font: inherit; text-align: left; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default); }
  .constraints-line:hover { border-color: var(--color-border-emphasis); }
  .constraints-key { color: var(--workspace-muted); font: 700 var(--text-11)/1.3 var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase; }
  .constraints-value { color: var(--workspace-ink); font: 600 var(--text-13)/1.4 var(--font-mono); }
  .constraints-edit { margin-left: auto; color: var(--color-accent-dark); font-size: var(--text-sm); font-weight: 700; }

  .scope-strip { display: flex; gap: 0.75rem; align-items: center; padding: var(--space-3) 0; border-bottom: 1px solid var(--workspace-line); }
  .scope-heading { display: flex; flex: 0 0 auto; gap: 0.375rem; align-items: baseline; }
  .scope-heading > p { margin: 0; color: var(--workspace-muted); font: 700 var(--text-xs)/1.2 var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase; }
  .scope-count { color: var(--workspace-ink); font: 700 var(--text-13)/1 var(--font-mono); font-variant-numeric: tabular-nums; }
  .scope-count span { color: var(--workspace-muted); }
  .candidate-pills { display: flex; flex-wrap: wrap; gap: 0.4rem; min-width: 0; }
  .candidate-pill { display: inline-flex; max-width: min(22rem, 100%); gap: 0.4rem; align-items: center; padding: 0.25rem 0.25rem 0.25rem 0.6rem; border-radius: var(--radius-md); background: color-mix(in srgb, var(--color-accent) 6%, var(--color-bg-elevated)); box-shadow: inset 0 0 0 1px var(--color-border-accent); }
  .candidate-pill.preview { background: var(--color-bg-surface); box-shadow: inset 0 0 0 1px var(--workspace-line); }
  .pill-title { overflow: hidden; font-size: var(--text-13); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
  .candidate-pill small { flex: 0 0 auto; color: var(--workspace-muted); font: 600 0.6rem/1 var(--font-mono); }
  .pill-remove { display: grid; flex: 0 0 auto; width: 1.5rem; height: 1.5rem; padding: 0; place-items: center; border: 0; border-radius: 50%; color: var(--workspace-muted); background: transparent; cursor: pointer; transition: color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .pill-remove:hover:not(:disabled) { color: var(--color-error-text); background: color-mix(in srgb, currentcolor 10%, transparent); }
  .pill-remove:active:not(:disabled) { transform: scale(0.92); }
  .pill-remove:disabled { cursor: not-allowed; opacity: var(--opacity-disabled); }
  .pill-remove :global(svg) { width: 0.75rem; height: 0.75rem; }

  .scope-add { position: relative; }
  .add-trigger { display: inline-flex; gap: 0.375rem; align-items: center; min-height: 1.75rem; padding: 0.375rem 0.65rem; border: 1px dashed var(--color-border-emphasis); border-radius: var(--radius-md); color: var(--workspace-muted); background: transparent; font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; transition: color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default); }
  .add-trigger:hover:not(:disabled) { color: var(--workspace-ink); border-style: solid; }
  .add-trigger:active:not(:disabled) { transform: scale(0.98); }
  .add-trigger:disabled { cursor: not-allowed; opacity: var(--opacity-disabled); }
  .add-trigger :global(svg) { width: 0.85rem; height: 0.85rem; }
  .add-menu { position: absolute; z-index: 20; top: calc(100% + 0.35rem); left: 0; width: max(18rem, 100%); max-height: 17rem; overflow-y: auto; margin: 0; padding: 0.3rem; border: 1px solid var(--workspace-line); border-radius: var(--radius-md); background: var(--color-bg-elevated); box-shadow: var(--shadow-lg); list-style: none; }
  .add-menu button { display: block; width: 100%; padding: 0.5rem 0.6rem; border: 0; border-radius: var(--radius-sm); color: var(--workspace-ink); background: transparent; font: inherit; font-size: var(--text-base); text-align: left; cursor: pointer; transition: background var(--duration-fast) var(--ease-default); }
  .add-menu button:hover { background: var(--color-bg-surface); }
  .add-menu button:active { background: var(--color-accent-subtle); }

  .empty-scope { color: var(--workspace-muted); font-size: var(--text-base); }
  .scope-error, .tool-error { margin: 0.75rem 0 0; color: var(--color-error-text); font-size: var(--text-base); }
  .scope-notice { display: flex; gap: 0.75rem; margin-top: 1rem; padding: 0.75rem 1rem; border: 1px solid var(--color-border-warning); border-radius: var(--radius-lg); background: var(--color-warning-subtle); color: var(--color-warning-text); }
  .notice-icon { display: grid; flex: 0 0 auto; width: 1.35rem; height: 1.35rem; place-items: center; border-radius: 50%; background: color-mix(in srgb, var(--color-warning) 22%, var(--color-bg-elevated)); color: var(--color-warning-text); font-weight: 800; }
  .scope-notice strong, .scope-notice p { display: block; margin: 0; font-size: var(--text-base); line-height: 1.45; }
  .workspace-content { min-height: 24rem; padding: var(--space-8) 0 2.5rem; }

  /* No page in this workspace ends in a dead end. */
  .workspace-commit { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1rem; align-items: center; margin-bottom: 3rem; padding: 1rem 1.25rem; border: 1px solid var(--workspace-line); border-radius: var(--radius-lg); background: var(--color-bg-elevated); }
  .workspace-commit p { margin: 0; color: var(--workspace-muted); font-size: var(--text-base); }
  .commit-cta { display: inline-flex; gap: 0.5rem; align-items: center; padding: 0.6rem 1.1rem; border: 1px solid var(--workspace-line); border-radius: var(--radius-md); color: var(--workspace-muted); font-size: var(--text-base); font-weight: 700; text-decoration: none; transition: background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .commit-cta.ready { border-color: transparent; color: var(--color-text-on-accent); background: var(--color-accent-hover); }
  .commit-cta:hover { border-color: var(--color-border-emphasis); }
  .commit-cta.ready:hover { background: var(--color-accent-dark); border-color: transparent; }
  .commit-cta:active { transform: scale(0.98); }

  :global(.selection-page) { animation: workspace-enter 420ms cubic-bezier(0.32, 0.72, 0, 1) both; }
  :global(.selection-page__header) { display: flex; justify-content: space-between; gap: 2rem; align-items: end; margin-bottom: var(--space-4); }
  /* Calm section heading: this is the loudest thing above the fold — louder than
     the muted niche label — because the tool is the content, the niche is context. */
  :global(.selection-page h2) { margin: 0; font-family: var(--font-display); font-size: 1.1rem; font-weight: 700; line-height: 1.25; letter-spacing: -0.01em; }
  :global(.selection-page__lead) { max-width: 62ch; margin: 0.35rem 0 0; color: var(--workspace-muted); font-size: var(--text-13); line-height: 1.5; }
  :global(.selection-page__switcher) { display: inline-flex; gap: 0.25rem; padding: 0.25rem; border-radius: var(--radius-md); background: var(--color-bg-surface); }
  :global(.selection-page__switcher a) { min-height: 1.75rem; display: inline-flex; align-items: center; padding: 0.375rem 0.75rem; border-radius: var(--radius-sm); color: var(--workspace-muted); font-size: var(--text-13); font-weight: 700; text-decoration: none; transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  :global(.selection-page__switcher a:hover:not(.active)) { color: var(--workspace-ink); }
  :global(.selection-page__switcher a.active) { background: var(--color-bg-elevated); color: var(--workspace-ink); box-shadow: var(--shadow-sm); }
  :global(.selection-page__panel) { border: 1px solid var(--workspace-line); border-radius: var(--radius-lg); background: var(--color-bg-elevated); box-shadow: var(--shadow-sm); }
  :global(.selection-page__empty) { display: grid; min-height: 18rem; padding: 3rem 1.5rem; place-items: center; text-align: center; }
  :global(.selection-page__empty > div) { max-width: 32rem; }
  :global(.selection-page__empty h3) { margin: 0; font-size: var(--text-xl); }
  :global(.selection-page__empty p) { margin: 0.65rem 0 0; color: var(--workspace-muted); line-height: 1.55; }
  :global(.selection-page__action) { display: inline-flex; align-items: center; gap: 0.5rem; margin-top: 1rem; min-height: 2.25rem; padding: 0.5rem 1rem; border: 0; border-radius: var(--radius-md); color: var(--color-text-on-accent); background: var(--color-accent-hover); font: inherit; font-size: var(--text-base); font-weight: 700; cursor: pointer; transition: background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  :global(.selection-page__action:hover) { background: var(--color-accent-dark); }
  :global(.selection-page__action:active) { transform: scale(0.98); }
  :global(.selection-page__action:disabled) { cursor: not-allowed; opacity: var(--opacity-disabled); }
  :global(.selection-page__link) { display: inline-flex; align-items: center; gap: 0.5rem; margin-top: 1rem; min-height: 1.75rem; border: 0; background: transparent; color: var(--color-accent-dark); font: inherit; font-weight: 700; text-decoration: none; cursor: pointer; }
  :global(.selection-page__link:hover:not(:disabled)) { text-decoration: underline; text-underline-offset: 0.2rem; }
  :global(.selection-page__link:disabled) { color: var(--workspace-muted); cursor: not-allowed; opacity: var(--opacity-disabled); }
  @keyframes workspace-enter { from { opacity: 0; transform: translateY(0.35rem); } to { opacity: 1; transform: translateY(0); } }

  @media (max-width: 1279px) {
    .job-page-content { padding: 1.5rem 1.25rem 3rem; }
  }

  @media (max-width: 767px) {
    .constraints-line { flex-direction: column; align-items: flex-start; }
    .constraints-edit { margin-left: 0; }
    .scope-strip { align-items: flex-start; flex-direction: column; }
    .candidate-pills { width: 100%; }
    .candidate-pill { width: 100%; justify-content: space-between; }
    .add-menu { width: 100%; }
    :global(.selection-page__header) { display: block; }
    :global(.selection-page__switcher) { margin-top: 1rem; }
  }

  @media (prefers-reduced-motion: reduce) {
    :global(.selection-page) { animation: none; }
    .ask-analyst, .constraints-line, .pill-remove, .add-trigger, .commit-cta { transition: none; }
    .pill-remove:active, .add-trigger:active, .commit-cta:active { transform: none; }
    :global(.selection-page__action), :global(.selection-page__action:active) { transition: none; transform: none; }
  }
</style>
