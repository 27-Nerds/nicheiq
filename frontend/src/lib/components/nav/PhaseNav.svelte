<script lang="ts">
  import { onMount } from "svelte";
  import {
    FileText,
    FlaskConical,
    LayoutDashboard,
    ListChecks,
    Package,
  } from "lucide-svelte";
  import {
    PHASES,
    DEEP_RESEARCH_BLURRED_PREVIEW_IDS,
    DEEP_RESEARCH_PEEK_ITEMS,
    type PhaseConfig,
    type SectionConfig,
  } from "$lib/config/phase-sections";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import SidebarNav from "$lib/components/nav/SidebarNav.svelte";
  import SidebarGroup from "$lib/components/nav/SidebarGroup.svelte";
  import SidebarDivider from "$lib/components/nav/SidebarDivider.svelte";
  import SidebarNavItem from "$lib/components/nav/SidebarNavItem.svelte";
  import {
    WORKSPACE_ROUTES,
    PRIMARY_TOOL_SLUGS,
    CHOOSE_IDEAS_LABEL,
    REVIEW_AND_START_LABEL,
  } from "$lib/selection/labels";
  import type { SelectionJourneyTask } from "$lib/selection/decisionJourney";
  import { rankedIdeasHref } from "$lib/selection/rankedIdeas";

  interface Props {
    jobStatus: string;
    activeSection?: string;
    /** Job id — required to build Decision-tools links and, on nested workspace
     *  routes, the back-to-section links. */
    jobId?: string;
    /** Selection flows only: the decision tools become one persistent sidebar
     *  group present on BOTH the job page and every /selection route, so the
     *  navigation map never reshuffles as the user drills in. */
    toolTasks?: SelectionJourneyTask[];
    /** Stable journey destination (choose|compare|risks|review),
     *  or null on the job page itself. */
    activeTool?: string | null;
    /** True on a /selection route: content sections are not on this page, so
     *  they link back to the job page instead of scroll-jumping. */
    nested?: boolean;
    /** Seeded-flow mode. 'deep_idea' skips discovery (stages 1-5) and runs deep-research
     *  immediately, so its discovery phase shows as seeded/done while deep-research is active. */
    entryMode?: string | null;
    /** 'gate' = guided-mode checkpoint (AWAITING_GATE): the page is a single
     *  checkpoint ledger with no scrollable sections, so the sidebar orients
     *  (gate rail + what-runs-next) instead of navigating. */
    /** 'stopped' = a FAILED/CANCELLED run that still completed discovery. It keeps the
     *  workbench shell (the discovery context is real and paid for) but swaps the idea
     *  tools — none of which can be acted on — for the one recovery step. */
    mode?: "default" | "selection" | "selection-record" | "gate" | "stopped";
    /** 'stopped' mode: label + href for the single recovery action, mirroring the
     *  handoff card's primary button so the sidebar never offers a different next step. */
    recoverLabel?: string;
    recoverHref?: string;
    recoverOnclick?: () => void;
    recoverDisabled?: boolean;
    selectedCount?: number;
    /** Exact candidate-revision query carried between selection routes. */
    selectionQuery?: string;
    /** Discovery sections actually present on the current job page. When supplied,
     * unavailable legacy/partial sections are omitted instead of linking to nowhere. */
    availableSectionIds?: string[];
    /** Guided mode (Phase B) — chatMode opts a job into the G1/G2 stage gates.
     *  gateStage (1|4) is only set while jobStatus=AWAITING_GATE. When both are
     *  present, the Discovery group shows a compact gate rail (diamond markers =
     *  decision points, circle = passive progress) so the sidebar orients the user
     *  at a checkpoint instead of just showing "WHAT · active" (scope-capped to
     *  markers in this existing nav — no new nav component, SC2). */
    chatMode?: boolean;
    gateStage?: 1 | 4 | null;
    /** Admin-granted optional decision tools. Fails CLOSED: without it the sidebar
     *  shows Choose ideas → Compare trade-offs → Review and start, and the
     *  "Check the evidence" row is omitted rather than linking into a 403. */
    decisionTools?: boolean;
    /** "Check my idea" runs whose pipeline refused to grade the idea
     *  (`idea_validation.outcome === 'not_evaluated'`). There is no verdict on such a run,
     *  so the journey step cannot be named for one. Defaults false: a surface that cannot
     *  see the outcome keeps the graded-run label rather than inventing a refusal. */
    validationNotEvaluated?: boolean;
    /** Status of the completed run's optional landing-page deliverable. */
    landingPageStatus?: "pending" | "running" | "completed" | "failed" | "locked";
    /** Asset-backed report availability. COMPLETED alone does not make report routes valid. */
    reportAvailable?: boolean;
  }

  let {
    jobStatus,
    activeSection = "",
    jobId,
    toolTasks,
    activeTool = null,
    nested = false,
    entryMode = null,
    mode = "default",
    selectedCount = 0,
    selectionQuery = "",
    availableSectionIds,
    chatMode = false,
    gateStage = null,
    decisionTools = false,
    validationNotEvaluated = false,
    landingPageStatus = "pending",
    reportAvailable = false,
    recoverLabel = "Next step",
    recoverHref,
    recoverOnclick,
    recoverDisabled = false,
  }: Props = $props();

  // Research shortlist: one shared nav group of the TWO primary tools (Compare,
  // Check the evidence). Plan-a-test and Branch-a-direction are reached
  // contextually, not as co-equal nav. Same status source as the launchpad.
  const toolItems = $derived(
    WORKSPACE_ROUTES
      .filter((route) => PRIMARY_TOOL_SLUGS.includes(route.slug))
      // "Check the evidence" (/selection/risks) is a decision tool; compare is not.
      .filter((route) => decisionTools || route.slug === "compare")
      .map((route) => ({
        slug: route.slug,
        label: route.label,
        href: jobId ? `/jobs/${jobId}/selection/${route.slug}${selectionQuery}` : undefined,
        task: toolTasks?.find((task) => task.key === route.slug),
      })),
  );
  const reviewHref = $derived(
    jobId ? `/jobs/${jobId}/selection/review` : undefined,
  );
  const compareRecordHref = $derived(
    jobId ? `/jobs/${jobId}/selection/compare${selectionQuery}` : undefined,
  );
  const evidenceRecordHref = $derived(
    jobId ? `/jobs/${jobId}/selection/risks${selectionQuery}` : undefined,
  );
  const runRecordHref = $derived(
    jobId
      ? jobStatus === "COMPLETED" && reportAvailable
        ? `/jobs/${jobId}/report`
        : `/jobs/${jobId}`
      : undefined,
  );
  const hubSectionHref = (sectionId: string): string | undefined => {
    if (!nested || !jobId) return undefined;
    return sectionId === "opportunities"
      ? rankedIdeasHref(jobId)
      : `/jobs/${jobId}#${sectionId}`;
  };

  // Gate-rail step states, derived purely from which gate the job is CURRENTLY
  // sitting at (gateStage is only non-null while AWAITING_GATE) — Niche precedes
  // Evidence precedes Audience, so a later gate implies the earlier ones are done.
  const gateRailSteps = $derived.by(() => {
    if (!chatMode || !gateStage) return null;
    return {
      niche: gateStage === 1 ? "active" : "done",
      evidence: gateStage === 4 ? "done" : "upcoming",
      audience: gateStage === 4 ? "active" : "upcoming",
    } as const;
  });

  let scrollProgress = $state(0);
  let trackedSection = $state("");
  let isOpen = $state(false);

  const isSelectionMode = $derived(mode === "selection");
  const isSelectionRecordMode = $derived(mode === "selection-record");
  const isGateMode = $derived(mode === "gate");
  const isStoppedMode = $derived(mode === "stopped");
  // Both shells are the full-width, aside-less workbench treatment; they differ only in
  // which group sits above the discovery context.
  const isWorkbenchMode = $derived(isSelectionMode || isSelectionRecordMode || isStoppedMode);
  const isCompletedMode = $derived(jobStatus === "COMPLETED" && Boolean(jobId));
  const currentSection = $derived(activeSection || trackedSection || (isWorkbenchMode ? "opportunities" : ""));

  const deliverableStatus = $derived.by(() => {
    switch (landingPageStatus) {
      case "completed":
        return { label: "Ready", variant: "ready" };
      case "running":
        return { label: "Generating", variant: "running" };
      case "failed":
        return { label: "Needs attention", variant: "attention" };
      case "locked":
        return { label: "Unavailable", variant: "muted" };
      default:
        return { label: "Available", variant: "available" };
    }
  });

  // Phase badge states
  type BadgeState = "active" | "done" | "locked";

  interface PhaseBadge {
    label: string;
    state: BadgeState;
    variant: "success" | "secondary" | "muted";
  }

  // Catalog-seeded flows replace discovery's "WHAT" journey tag with "SEEDED":
  // deep_idea never ran discovery at all (muted); pain_research/pain_remix ran an
  // abbreviated discovery (stages 1-4 seeded, stage 5 real), so the badge keeps
  // the success treatment but tells the user where the inputs came from.
  const isSeeded = $derived(
    entryMode === "deep_idea" || entryMode === "pain_research" || entryMode === "pain_remix",
  );
  const discoveryLabel = $derived(isSeeded ? "SEEDED" : "WHAT");
  // "Check my idea" runs land on a verdict about ONE idea — "Choose ideas" is
  // discovery vocabulary and reads wrong beside it. Same journey, mode-true name
  // (matches the progress screen's "Your verdict" phase label).
  //
  // Unless there is no verdict. A run that refused to grade the idea has an outcome, not a
  // verdict, and the label was derived from the ENTRY MODE alone — so the sidebar read
  // "Selection step · Your verdict" beside a card reading "Not evaluated". Falls back to
  // the breadcrumb's word for the same step, which names the step without claiming a
  // result.
  const chooseIdeasLabel = $derived(
    entryMode === "validate_idea"
      ? (validationNotEvaluated ? "Idea check" : "Your verdict")
      : CHOOSE_IDEAS_LABEL,
  );

  const phaseBadges = $derived.by((): Record<string, PhaseBadge> => {
    // deep_idea jobs skip discovery (stages 1-5) and run deep-research straight away —
    // they never enter RUNNING_PHASE2, so without this the default case would wrongly show
    // discovery "active" / deep-research "locked". Mark discovery SEEDED and deep-research active.
    if (entryMode === "deep_idea" && jobStatus !== "COMPLETED") {
      return {
        discovery: { label: "SEEDED", state: "done", variant: "muted" },
        "deep-research": { label: "HOW", state: "active", variant: "secondary" },
        build: { label: "GO", state: "locked", variant: "muted" },
      };
    }
    switch (jobStatus) {
      case "RUNNING_PHASE2":
        return {
          discovery: { label: discoveryLabel, state: "done", variant: "success" },
          "deep-research": { label: "HOW", state: "active", variant: "secondary" },
          build: { label: "GO", state: "locked", variant: "muted" },
        };
      case "COMPLETED":
        return {
          discovery: { label: discoveryLabel, state: "done", variant: entryMode === "deep_idea" ? "muted" : "success" },
          "deep-research": { label: "HOW", state: "done", variant: "secondary" },
          build: { label: "GO", state: "active", variant: "secondary" },
        };
      default:
        return {
          discovery: { label: discoveryLabel, state: "active", variant: "success" },
          "deep-research": { label: "HOW", state: "locked", variant: "muted" },
          build: { label: "GO", state: "locked", variant: "muted" },
        };
    }
  });

  // Deep research: blurred previews (scrollable) vs peek (sidebar-only) vs rolled-up
  const deepResearchPhase = PHASES.find(p => p.id === 'deep-research')!;
  // Preserve the order declared in DEEP_RESEARCH_BLURRED_PREVIEW_IDS (matches on-page order),
  // not the canonical DEEP_RESEARCH_SECTIONS order (which is the unlocked-state order).
  const blurredPreviewSections: SectionConfig[] = DEEP_RESEARCH_BLURRED_PREVIEW_IDS
    .map(id => deepResearchPhase.sections.find(s => s.id === id))
    .filter((s): s is SectionConfig => s !== undefined);
  // Peek items — join ids with section configs (icon/label) and attach tagline.
  const peekItems = DEEP_RESEARCH_PEEK_ITEMS
    .map(p => {
      const section = deepResearchPhase.sections.find(s => s.id === p.id);
      return section ? { ...section, tagline: p.tagline } : null;
    })
    .filter((x): x is SectionConfig & { tagline: string } => x !== null);
  const peekIds = DEEP_RESEARCH_PEEK_ITEMS.map(p => p.id);
  const rolledUpLocked = $derived(
    deepResearchPhase.sections.filter(
      s => !DEEP_RESEARCH_BLURRED_PREVIEW_IDS.includes(s.id) && !peekIds.includes(s.id)
    )
  );
  const moreItemsTooltip = $derived(rolledUpLocked.map(s => s.label).join(' · '));
  const discoveryPhase = PHASES.find(p => p.id === 'discovery')!;
  const opportunitySection = discoveryPhase.sections.find(s => s.id === 'opportunities');
  const marketReadSection: SectionConfig = { id: 'market-read', label: 'Market Read', icon: FileText };
  const availableSectionSet = $derived(
    availableSectionIds ? new Set(availableSectionIds) : null,
  );
  const contextSections = $derived(
    [
      ...(availableSectionSet?.has('market-read') ? [marketReadSection] : []),
      ...discoveryPhase.sections.filter(
        s => s.id !== 'opportunities'
          && (!availableSectionSet || availableSectionSet.has(s.id))
      ),
    ]
  );
  const selectionTrackedSections = $derived.by(() => [
    opportunitySection,
    ...contextSections,
    ...blurredPreviewSections,
  ].filter((s): s is SectionConfig => s !== undefined));

  function isPhaseUnlocked(phaseId: string): boolean {
    const badge = phaseBadges[phaseId];
    return badge?.state === "active" || badge?.state === "done";
  }

  const HEADER_OFFSET = 24; // static app header; keep a small breathing offset for anchors
  const SCROLL_THRESHOLD = HEADER_OFFSET + 10; // small buffer above header for activation

  const completedReportItems = [
    {
      id: "report-brief",
      label: "Brief",
      description: "Understand the recommendation",
      view: "brief",
      icon: FileText,
    },
    {
      id: "report-evidence",
      label: "Evidence",
      description: "Verify the case",
      view: "evidence",
      icon: FlaskConical,
    },
    {
      id: "report-plan",
      label: "Plan",
      description: "Decide what to do next",
      view: "plan",
      icon: ListChecks,
    },
  ] as const;

  function scrollToElement(el: HTMLElement) {
    const y = el.getBoundingClientRect().top + window.scrollY - HEADER_OFFSET;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: y, behavior: reduce ? 'auto' : 'smooth' });
  }

  function handleSectionClick(phase: PhaseConfig, section: SectionConfig) {
    const el = document.getElementById(section.id);
    if (el) {
      trackedSection = section.id;
      // Ask a collapsed dossier accordion to open, then scroll next frame so the
      // jump measures the expanded height and lands on content, not a closed row.
      window.dispatchEvent(
        new CustomEvent("nicheiq:reveal-section", { detail: { id: section.id } }),
      );
      requestAnimationFrame(() => scrollToElement(el));
      isOpen = false;
    } else {
      const cta = document.getElementById("solution-selector");
      if (cta) {
        scrollToElement(cta);
        isOpen = false;
      }
    }
  }

  function handleScroll() {
    const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
    scrollProgress = scrollHeight > 0 ? Math.min(window.scrollY / scrollHeight, 1) : 0;

    // Only track sections that correspond to visible/interactive sidebar items.
    // For locked deep-research, only the blurred-preview items appear in the sidebar.
    const allSections = isWorkbenchMode
      ? selectionTrackedSections
      : PHASES.flatMap((p) => {
          if (isPhaseUnlocked(p.id)) return p.sections;
          if (p.id === 'deep-research') {
            return blurredPreviewSections;
          }
          return [];
        });
    // Resolve to elements, then sort by actual DOM position — the allSections order
    // does not always match the rendered page order (e.g., Phase 2 previews are rendered
    // unified-hero → seo → competitors on the page).
    const sectionElements = allSections
      .map((s) => ({ id: s.id, el: document.getElementById(s.id) }))
      .filter((s): s is { id: string; el: HTMLElement } => s.el !== null)
      .map((s) => ({ id: s.id, el: s.el, top: s.el.getBoundingClientRect().top + window.scrollY }))
      .sort((a, b) => a.top - b.top);

    const scrollY = window.scrollY;
    let nextSection = isWorkbenchMode ? "opportunities" : trackedSection;
    for (let i = sectionElements.length - 1; i >= 0; i--) {
      const section = sectionElements[i];
      if (section.top - scrollY <= SCROLL_THRESHOLD) {
        nextSection = section.id;
        break;
      }
    }
    trackedSection = nextSection;
  }

  $effect(() => { handleScroll(); });

  onMount(() => {
    if (nested || !window.location.hash) return;
    const sectionId = decodeURIComponent(window.location.hash.slice(1));
    if (!sectionId || (availableSectionSet && !availableSectionSet.has(sectionId))) return;
    const section = discoveryPhase.sections.find((candidate) => candidate.id === sectionId);
    if (!section) return;

    window.dispatchEvent(
      new CustomEvent("nicheiq:reveal-section", { detail: { id: sectionId } }),
    );
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const element = document.getElementById(sectionId);
        if (element) {
          trackedSection = sectionId;
          scrollToElement(element);
        }
      });
    });
  });
</script>

<svelte:window onscroll={handleScroll} />

<!-- ═══ DESKTOP SIDEBAR ═══ -->
<SidebarNav
  class={isWorkbenchMode ? "phase-side phase-side--selection" : "phase-side"}
  desktopOnly
  width="300px"
  background={isWorkbenchMode ? "var(--color-bg-base)" : "var(--color-bg-elevated)"}
  label={isSelectionRecordMode ? "Decision record navigation" : "Research phases"}
>
  {#if isGateMode}
    <!-- Checkpoint page: nothing to scroll to — orient instead of navigate.
         No done-checkmarks (nothing has run yet) and no Preview links (the
         phase-2 preview scaffold is suppressed at gates). -->
    <SidebarGroup label="Discovery">
      {#snippet trailing()}
        <span class="phase-badge badge-success">{discoveryLabel}</span>
      {/snippet}
      {#if gateRailSteps}
        <div class="gate-rail" aria-label="Guided research checkpoints">
          <span class="gate-rail-step" class:is-active={gateRailSteps.niche === "active"} class:is-done={gateRailSteps.niche === "done"}>
            <span class="gate-rail-marker gate-rail-marker--diamond" aria-hidden="true"></span>
            Niche
          </span>
          <span class="gate-rail-arrow" aria-hidden="true">&rarr;</span>
          <span class="gate-rail-step" class:is-done={gateRailSteps.evidence === "done"}>
            <span class="gate-rail-marker gate-rail-marker--circle" aria-hidden="true"></span>
            Evidence
          </span>
          <span class="gate-rail-arrow" aria-hidden="true">&rarr;</span>
          <span class="gate-rail-step" class:is-active={gateRailSteps.audience === "active"} class:is-upcoming={gateRailSteps.audience === "upcoming"}>
            <span class="gate-rail-marker gate-rail-marker--diamond" aria-hidden="true"></span>
            Audience
          </span>
        </div>
      {/if}
      <div class="next-card" aria-label="What runs after this checkpoint">
        <span class="next-card-title">{gateStage === 1 ? "Next: evidence search" : "Next: idea generation"}</span>
        <span class="next-card-text">
          {gateStage === 1
            ? "Scans community discussions in this niche for pain signals."
            : "Generates solution candidates from the scoped pains and segments."}
        </span>
      </div>
    </SidebarGroup>

    <SidebarDivider />
    <SidebarGroup label="Deep Research">
      <div class="next-card" aria-label="Deep Research unlocks later">
        <span class="next-card-title">Validation</span>
        <span class="next-card-text">Validates the ideas you shortlist after discovery.</span>
      </div>
    </SidebarGroup>
  {:else if isSelectionMode}
    <SidebarGroup label="Ideas for Deep Research">
      {#if opportunitySection}
        {@const isActive = activeTool === "choose" || (!nested && currentSection === opportunitySection.id)}
        {@const Icon = opportunitySection.icon}
        <SidebarNavItem
          active={isActive}
          href={hubSectionHref(opportunitySection.id)}
          onclick={nested ? undefined : () => handleSectionClick(discoveryPhase, opportunitySection)}
        >
          {#snippet leading()}{#if Icon}<Icon class="sidebar-nav-ic" />{/if}{/snippet}
          {chooseIdeasLabel}
        </SidebarNavItem>
      {/if}
      {#if toolItems.some((item) => item.href)}
        {#each toolItems as item (item.slug)}
          {@const locked = item.task?.status === "not_ready"}
          <SidebarNavItem
            active={activeTool === item.slug}
            href={locked ? undefined : item.href}
            aria-current={activeTool === item.slug ? "page" : undefined}
            disabled={locked}
            class={locked ? "tool-locked" : ""}
            title={locked ? item.task?.statusLabel : undefined}
          >
            {item.label}
          </SidebarNavItem>
        {/each}
      {/if}
      <SidebarNavItem
        active={activeTool === "review"}
        href={reviewHref}
        aria-current={activeTool === "review" ? "page" : undefined}
      >
        {REVIEW_AND_START_LABEL}
      </SidebarNavItem>
    </SidebarGroup>

    <SidebarDivider />
    <SidebarGroup label="Discovery context">
      {#each contextSections as section}
        {@const isActive = !nested && currentSection === section.id}
        {@const Icon = section.icon}
        <SidebarNavItem
          active={isActive}
          href={hubSectionHref(section.id)}
          onclick={nested ? undefined : () => handleSectionClick(discoveryPhase, section)}
        >
          {#snippet leading()}{#if Icon}<Icon class="sidebar-nav-ic" />{/if}{/snippet}
          {section.label}
        </SidebarNavItem>
      {/each}
    </SidebarGroup>
  {:else if isSelectionRecordMode}
    <SidebarGroup label="Decision record">
      <SidebarNavItem
        active={activeTool === "compare"}
        href={compareRecordHref}
        aria-current={activeTool === "compare" ? "page" : undefined}
      >
        Comparison record
      </SidebarNavItem>
      {#if decisionTools}
        <SidebarNavItem
          active={activeTool === "risks"}
          href={evidenceRecordHref}
          aria-current={activeTool === "risks" ? "page" : undefined}
        >
          Evidence &amp; risk record
        </SidebarNavItem>
      {/if}
      <SidebarNavItem
        active={activeTool === "review"}
        href={reviewHref}
        aria-current={activeTool === "review" ? "page" : undefined}
      >
        Saved research scope
      </SidebarNavItem>
    </SidebarGroup>

    <SidebarDivider />
    <SidebarGroup label="Research run">
      <SidebarNavItem href={runRecordHref}>
        {jobStatus === "COMPLETED" && reportAvailable ? "Open report" : "View run"}
      </SidebarNavItem>
    </SidebarGroup>
  {:else if isStoppedMode}
    <SidebarGroup label="Recover run">
      <SidebarNavItem
        active
        href={recoverOnclick ? undefined : (recoverHref ?? "#recover-run")}
        onclick={recoverOnclick}
        disabled={recoverDisabled}
        aria-current="page"
      >
        {#snippet leading()}<ListChecks class="sidebar-nav-ic" />{/snippet}
        {recoverLabel}
      </SidebarNavItem>
    </SidebarGroup>

    {#if contextSections.length > 0}
      <SidebarDivider />
      <SidebarGroup label="Discovery context">
        <!-- Opportunities stays in this group rather than being promoted to its own
             "Choose ideas" row: on a stopped run it is evidence to read, not a task to do. -->
        {#each [opportunitySection, ...contextSections].filter(Boolean) as section}
          {@const isActive = !nested && currentSection === section!.id}
          {@const Icon = section!.icon}
          <SidebarNavItem
            active={isActive}
            href={hubSectionHref(section!.id)}
            onclick={nested ? undefined : () => handleSectionClick(discoveryPhase, section!)}
          >
            {#snippet leading()}{#if Icon}<Icon class="sidebar-nav-ic" />{/if}{/snippet}
            {section!.label}
          </SidebarNavItem>
        {/each}
      </SidebarGroup>
    {/if}
  {:else if isCompletedMode}
    <SidebarGroup label="Completed run">
      <SidebarNavItem
        active
        href={jobId ? `/jobs/${jobId}` : undefined}
        aria-current="page"
      >
        {#snippet leading()}<LayoutDashboard class="sidebar-nav-ic" />{/snippet}
        Run overview
      </SidebarNavItem>
      <SidebarNavItem href={compareRecordHref}>
        Decision record
      </SidebarNavItem>
      <span class="report-nav-description">
        {reportAvailable ? "Report and deliverables" : "Report unavailable"}
      </span>
    </SidebarGroup>

    <SidebarDivider />
    <SidebarGroup label="Research report">
      {#if reportAvailable}
        {#each completedReportItems as item}
          {@const Icon = item.icon}
          <SidebarNavItem href={jobId ? `/jobs/${jobId}/report?view=${item.view}` : undefined}>
            {#snippet leading()}<Icon class="sidebar-nav-ic" />{/snippet}
            {item.label}
          </SidebarNavItem>
          <span class="report-nav-description">{item.description}</span>
        {/each}
      {:else}
        <SidebarNavItem disabled>
          {#snippet leading()}<FileText class="sidebar-nav-ic" />{/snippet}
          Report unavailable
        </SidebarNavItem>
        <span class="report-nav-description">Refresh the run overview to check again.</span>
      {/if}
    </SidebarGroup>

    <SidebarDivider />
    <SidebarGroup label="Optional deliverables">
      <SidebarNavItem href={jobId ? `/jobs/${jobId}#optional-deliverables` : undefined}>
        {#snippet leading()}<Package class="sidebar-nav-ic" />{/snippet}
        Landing page
        {#snippet trailing()}
          <span
            class="deliverable-status"
            class:deliverable-status--ready={deliverableStatus.variant === "ready"}
            class:deliverable-status--running={deliverableStatus.variant === "running"}
            class:deliverable-status--attention={deliverableStatus.variant === "attention"}
          >
            {deliverableStatus.label}
          </span>
        {/snippet}
      </SidebarNavItem>
    </SidebarGroup>
  {:else}
    {#each PHASES as phase, phaseIndex}
      {@const badge = phaseBadges[phase.id]}
      {@const unlocked = isPhaseUnlocked(phase.id)}

      {#if phaseIndex > 0}
        <SidebarDivider />
      {/if}

      <SidebarGroup label={phase.label}>
        {#snippet trailing()}
          <span
            class="phase-badge"
            class:badge-success={badge?.variant === "success"}
            class:badge-secondary={badge?.variant === "secondary"}
            class:badge-muted={badge?.variant === "muted"}
          >
            {badge?.label}
          </span>
        {/snippet}

        {#if phase.id === 'discovery' && gateRailSteps}
          <div class="gate-rail" aria-label="Guided research checkpoints">
            <span class="gate-rail-step" class:is-active={gateRailSteps.niche === "active"} class:is-done={gateRailSteps.niche === "done"}>
              <span class="gate-rail-marker gate-rail-marker--diamond" aria-hidden="true"></span>
              Niche
            </span>
            <span class="gate-rail-arrow" aria-hidden="true">&rarr;</span>
            <span class="gate-rail-step" class:is-done={gateRailSteps.evidence === "done"}>
              <span class="gate-rail-marker gate-rail-marker--circle" aria-hidden="true"></span>
              Evidence
            </span>
            <span class="gate-rail-arrow" aria-hidden="true">&rarr;</span>
            <span class="gate-rail-step" class:is-active={gateRailSteps.audience === "active"} class:is-upcoming={gateRailSteps.audience === "upcoming"}>
              <span class="gate-rail-marker gate-rail-marker--diamond" aria-hidden="true"></span>
              Audience
            </span>
          </div>
        {/if}

        {#if phase.id === 'deep-research' && !unlocked}
          <!-- Blurred preview items first (scrollable on page) -->
          {#each blurredPreviewSections as section}
            {@const isActive = currentSection === section.id}
            {@const Icon = section.icon}
            <SidebarNavItem
              preview
              active={isActive}
              onclick={() => handleSectionClick(phase, section)}
            >
              {#snippet leading()}{#if Icon}<Icon class="sidebar-nav-ic" />{/if}{/snippet}
              {section.label}
              {#snippet trailing()}<span class="nav-preview-tag">Preview</span>{/snippet}
            </SidebarNavItem>
          {/each}
          <!-- Peek items — locked, stacked label + value tagline -->
          {#each peekItems as item, idx (item.id)}
            {@const Icon = item.icon}
            <div
              class="peek-item"
              class:peek-item--first={idx === 0}
              aria-disabled="true"
            >
              {#if Icon}<Icon class="peek-icon" aria-hidden="true" />{/if}
              <div class="nav-item-peek-text">
                <span class="peek-label">{item.label}</span>
                <span class="nav-item-tagline">{item.tagline}</span>
              </div>
              <Tooltip content="Unlocks with Deep Research" position="right">
                {#snippet children()}
                  <span class="nav-lock-trigger" aria-label="Locked - unlocks with Deep Research">
                    <svg class="nav-lock-icon" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" aria-hidden="true"><rect x="2" y="5.5" width="8" height="6" rx="1.5"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/></svg>
                  </span>
                {/snippet}
              </Tooltip>
            </div>
          {/each}
          {#if rolledUpLocked.length > 0}
            <span class="nav-more" title={moreItemsTooltip}>
              +{rolledUpLocked.length} more
            </span>
          {/if}
        {:else}
          <!-- Normal rendering (unlocked phases) -->
          {#each phase.sections as section}
            {@const isActive = currentSection === section.id}
            {@const isDone = unlocked && (badge?.state === 'done' || badge?.state === 'active')}
            {@const Icon = section.icon}

            <SidebarNavItem
              class={isDone ? "is-done" : ""}
              active={isActive}
              onclick={() => handleSectionClick(phase, section)}
              disabled={!unlocked}
            >
              {#snippet leading()}{#if Icon}<Icon class="sidebar-nav-ic" />{/if}{/snippet}
              {section.label}
              {#snippet trailing()}
                {#if isDone}
                  <span class="nav-check">
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2.5 2.5L8 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </span>
                {:else if !unlocked}
                  <svg class="nav-lock-icon" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="5.5" width="8" height="6" rx="1.5"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/></svg>
                {/if}
              {/snippet}
            </SidebarNavItem>
          {/each}
        {/if}
      </SidebarGroup>
    {/each}
  {/if}
</SidebarNav>

{#if isSelectionRecordMode}
<div class="selection-mobile-navigation">
  <nav class="selection-mobile-nav selection-mobile-nav--record" aria-label="Saved decision record">
    {#if compareRecordHref}
      <a
        class="selection-mobile-item tool"
        class:active={activeTool === "compare"}
        href={compareRecordHref}
        aria-current={activeTool === "compare" ? "page" : undefined}
      >Comparison record</a>
    {/if}
    {#if decisionTools && evidenceRecordHref}
      <a
        class="selection-mobile-item tool"
        class:active={activeTool === "risks"}
        href={evidenceRecordHref}
        aria-current={activeTool === "risks" ? "page" : undefined}
      >Evidence &amp; risk record</a>
    {/if}
    {#if reviewHref}
      <a
        class="selection-mobile-item tool"
        class:active={activeTool === "review"}
        href={reviewHref}
        aria-current={activeTool === "review" ? "page" : undefined}
      >Saved research scope</a>
    {/if}
    {#if runRecordHref}
      <a class="selection-mobile-item tool" href={runRecordHref}>
        {jobStatus === "COMPLETED" && reportAvailable ? "Open report" : "View run"}
      </a>
    {/if}
  </nav>
</div>
{:else if isSelectionMode}
<div class="selection-mobile-navigation">
<button
  type="button"
  class="selection-step-toggle"
  aria-expanded={isOpen}
  aria-controls="selection-step-menu"
  onclick={() => (isOpen = !isOpen)}
>
  <span>Selection step</span>
  <strong>
    {activeTool === "choose"
      ? chooseIdeasLabel
      : activeTool === "review"
        ? REVIEW_AND_START_LABEL
        : toolItems.find((item) => item.slug === activeTool)?.label ?? chooseIdeasLabel}
  </strong>
</button>
<nav class="selection-mobile-nav selection-mobile-nav--journey" aria-label="Research shortlist journey">
  {#if opportunitySection}
    {#if nested}
      <a
        class="selection-mobile-item"
        class:active={activeTool === "choose"}
        aria-current={activeTool === "choose" ? "page" : undefined}
        href={hubSectionHref(opportunitySection.id)}
      >{chooseIdeasLabel}</a>
    {:else}
      <button
        class="selection-mobile-item"
        class:active={currentSection === opportunitySection.id}
        type="button"
        aria-current={currentSection === opportunitySection.id ? "location" : undefined}
        onclick={() => handleSectionClick(discoveryPhase, opportunitySection)}
      >
        {chooseIdeasLabel}
      </button>
    {/if}
  {/if}
  {#each toolItems as item (item.slug)}
    {#if item.href}
      {@const locked = item.task?.status === "not_ready"}
      {#if locked}
        <span class="selection-mobile-item tool locked" aria-disabled="true">
          <span>{item.label}</span>
          <small>{item.task?.statusLabel}</small>
        </span>
      {:else}
        <a
          class="selection-mobile-item tool"
          class:active={activeTool === item.slug}
          href={item.href}
          aria-current={activeTool === item.slug ? "page" : undefined}
        >{item.label}</a>
      {/if}
    {/if}
  {/each}
  {#if reviewHref}
    <a
      class="selection-mobile-item tool"
      class:active={activeTool === "review"}
      href={reviewHref}
      aria-current={activeTool === "review" ? "page" : undefined}
    >{REVIEW_AND_START_LABEL}</a>
  {/if}
</nav>
<details class="selection-context-menu">
  <summary>Research context</summary>
  <nav aria-label="Discovery context">
    {#each contextSections as section}
      {#if nested}
        <a href={hubSectionHref(section.id)}>{section.label}</a>
      {:else}
        <button
          class:active={currentSection === section.id}
          type="button"
          aria-current={currentSection === section.id ? "location" : undefined}
          onclick={() => handleSectionClick(discoveryPhase, section)}
        >{section.label}</button>
      {/if}
    {/each}
  </nav>
</details>
{#if isOpen}
  <nav class="selection-step-menu" id="selection-step-menu" aria-label="Selection steps">
    {#if opportunitySection}
      {#if nested}
        <a href={hubSectionHref(opportunitySection.id)} onclick={() => (isOpen = false)}>{CHOOSE_IDEAS_LABEL}</a>
      {:else}
        <button type="button" onclick={() => { isOpen = false; handleSectionClick(discoveryPhase, opportunitySection); }}>{CHOOSE_IDEAS_LABEL}</button>
      {/if}
    {/if}
    {#each toolItems as item (item.slug)}
      {#if item.href && item.task?.status !== "not_ready"}
        <a href={item.href} aria-current={activeTool === item.slug ? "page" : undefined} onclick={() => (isOpen = false)}>{item.label}</a>
      {:else if item.href}
        <span aria-disabled="true">{item.label} · {item.task?.statusLabel}</span>
      {/if}
    {/each}
    {#if reviewHref}
      <a href={reviewHref} aria-current={activeTool === "review" ? "page" : undefined} onclick={() => (isOpen = false)}>{REVIEW_AND_START_LABEL}</a>
    {/if}
    <details>
      <summary>Research context</summary>
      {#each contextSections as section}
        {#if nested}
          <a href={hubSectionHref(section.id)} onclick={() => (isOpen = false)}>{section.label}</a>
        {:else}
          <button type="button" onclick={() => { isOpen = false; handleSectionClick(discoveryPhase, section); }}>{section.label}</button>
        {/if}
      {/each}
    </details>
  </nav>
{/if}
</div>
{/if}

<!-- ═══ MOBILE BOTTOM BAR ═══ -->
<!-- Suppressed in gate mode: a checkpoint page has no sections to jump between. -->
{#if !isSelectionMode && !isSelectionRecordMode && !isGateMode}
<nav class="sidebar-mobile" class:open={isOpen}>
  <button
    class="mobile-toggle"
    onclick={() => (isOpen = !isOpen)}
    aria-expanded={isOpen}
    aria-controls="phase-nav-mobile-menu"
    aria-label="Section navigation"
  >
    <div class="mobile-progress-bar">
      <div class="mobile-progress-fill" style:width="{scrollProgress * 100}%"></div>
    </div>
    <span class="mobile-current">
      {isCompletedMode
        ? "Run overview"
        : PHASES.flatMap((p) => p.sections).find((s) => s.id === currentSection)?.label || "Navigate"}
    </span>
  </button>

  {#if isOpen}
    <div class="mobile-menu" id="phase-nav-mobile-menu">
      {#if isCompletedMode}
        <div class="mobile-phase-header">
          <span class="phase-label">Completed run</span>
        </div>
        <a
          class="mobile-item active"
          href={jobId ? `/jobs/${jobId}` : undefined}
          aria-current="page"
          onclick={() => (isOpen = false)}
        >
          <span>Run overview</span>
        </a>
        <a
          class="mobile-item"
          href={compareRecordHref}
          onclick={() => (isOpen = false)}
        >
          <span>Decision record</span>
        </a>

        <div class="mobile-divider"></div>
        <div class="mobile-phase-header">
          <span class="phase-label">Research report</span>
        </div>
        {#if reportAvailable}
          {#each completedReportItems as item}
            <a
              class="mobile-item"
              href={jobId ? `/jobs/${jobId}/report?view=${item.view}` : undefined}
              onclick={() => (isOpen = false)}
            >
              <span>{item.label}</span>
            </a>
          {/each}
        {:else}
          <span class="mobile-item mobile-item--disabled" aria-disabled="true">
            <span>Report unavailable</span>
          </span>
        {/if}

        <div class="mobile-divider"></div>
        <div class="mobile-phase-header">
          <span class="phase-label">Optional deliverables</span>
        </div>
        <a
          class="mobile-item"
          href={jobId ? `/jobs/${jobId}#optional-deliverables` : undefined}
          onclick={() => (isOpen = false)}
        >
          <span>Landing page</span>
          <span
            class="deliverable-status"
            class:deliverable-status--ready={deliverableStatus.variant === "ready"}
            class:deliverable-status--running={deliverableStatus.variant === "running"}
            class:deliverable-status--attention={deliverableStatus.variant === "attention"}
          >
            {deliverableStatus.label}
          </span>
        </a>
      {:else}
      {#each PHASES as phase, phaseIndex}
        {@const badge = phaseBadges[phase.id]}
        {@const unlocked = isPhaseUnlocked(phase.id)}

        {#if phaseIndex > 0}
          <div class="mobile-divider"></div>
        {/if}

        <div class="mobile-phase-header">
          <span class="phase-label">{phase.label}</span>
          <span
            class="phase-badge"
            class:badge-success={badge?.variant === "success"}
            class:badge-secondary={badge?.variant === "secondary"}
            class:badge-muted={badge?.variant === "muted"}
          >
            {badge?.label}
          </span>
        </div>

        {#if phase.id === 'deep-research' && !unlocked}
          {#each blurredPreviewSections as section}
            <button class="mobile-item previewable" onclick={() => handleSectionClick(phase, section)}>
              <span>{section.label}</span>
              <span class="nav-preview-tag">Preview</span>
            </button>
          {/each}
          <span class="mobile-item locked nav-more" title={moreItemsTooltip}>
            +{rolledUpLocked.length + peekItems.length} more
          </span>
        {:else}
          {#each phase.sections as section}
            {@const isActive = currentSection === section.id}
            <button
              class="mobile-item"
              class:active={isActive}
              class:done={unlocked}
              class:locked={!unlocked}
              onclick={() => handleSectionClick(phase, section)}
              disabled={!unlocked}
            >
              {#if unlocked}
                <span class="nav-check"><svg width="8" height="8" viewBox="0 0 8 8" fill="none"><path d="M1 4l2 2 4-4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
              {/if}
              <span>{section.label}</span>
            </button>
          {/each}
        {/if}
      {/each}
      {/if}
    </div>
  {/if}
</nav>
{/if}

<style>
  /* ═══════════════════════════════════
     DESKTOP SIDEBAR
     Shell + rows come from the shared sidebar primitives
     (SidebarNav / SidebarGroup / SidebarNavItem). Only the
     phase-specific decorations live here.
     ═══════════════════════════════════ */

  /* Selection sidebar: calmer phase badge + muted preview tags. */
  :global(.phase-side--selection .phase-badge) {
    background: transparent;
    border-color: var(--color-border);
  }

  /* A locked decision tool: readable, clearly not-yet-available. */
  :global(.phase-side .sidebar-nav-item.tool-locked) {
    cursor: default;
  }
  :global(.phase-side--selection .nav-preview-tag) {
    color: var(--color-text-muted);
  }
  :global(.phase-side--selection .sidebar-nav-item.active .nav-preview-tag) {
    color: var(--color-text-secondary);
  }

  /* Done tier — completed sections read at full strength (base rows are
     secondary); the check + brighter text mark them without a fill. */
  :global(.phase-side .sidebar-nav-item.is-done) {
    color: var(--color-text-primary);
  }
  :global(.phase-side .sidebar-nav-item.is-done .sidebar-nav-ic) {
    opacity: 0.7;
  }

  .report-nav-description {
    display: block;
    margin: calc(-1 * var(--space-2)) var(--space-3) var(--space-2);
    padding-left: var(--space-8);
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    line-height: 1.4;
  }

  .deliverable-status {
    margin-left: auto;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }
  .deliverable-status--ready {
    color: var(--color-success-text);
  }
  .deliverable-status--running {
    color: var(--color-info-dark);
  }
  .deliverable-status--attention {
    color: var(--color-error-dark);
  }

  /* ── Phase badge (SidebarGroup trailing) ── */
  .phase-badge {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
    white-space: nowrap;
  }

  .phase-badge.badge-success {
    color: var(--color-success-text);
    background: var(--color-success-subtle);
    border: 1px solid var(--color-border-success);
  }

  .phase-badge.badge-secondary {
    color: var(--color-info-dark);
    background: var(--color-info-subtle);
    border: 1px solid var(--color-border-info);
  }

  .phase-badge.badge-muted {
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
  }

  /* ── "Done" check (SidebarNavItem trailing) ── */
  .nav-check {
    margin-left: auto;
    width: 16px;
    height: 16px;
    /* -dark for 3:1 non-text contrast of the white glyph (1.4.11). */
    background: var(--color-success-dark);
    border-radius: var(--radius-full);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-bg-elevated);
    flex-shrink: 0;
  }

  /* ── Preview tag (SidebarNavItem trailing) ── */
  .nav-preview-tag {
    margin-left: auto;
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-accent-dark);
    letter-spacing: 0.02em;
  }

  /* ── Gate rail (guided mode — Discovery group) ──
     Diamonds = decision points (gates), circle = passive progress. Orange marks
     the CURRENT checkpoint (the one legitimate accent use per the review/pending
     semantic); done steps read muted-filled, upcoming steps read hollow/faint. */
  .gate-rail {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin: 0.15rem 1.5rem 0.6rem;
    padding: 0.5rem 0.65rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }
  .gate-rail-step {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
  }
  .gate-rail-step.is-done {
    color: var(--color-text-secondary);
  }
  .gate-rail-step.is-active {
    color: var(--color-accent-dark);
  }
  .gate-rail-arrow {
    color: var(--color-text-muted);
    opacity: 0.5;
    font-size: var(--text-xs);
  }
  .gate-rail-marker {
    flex-shrink: 0;
    width: 6px;
    height: 6px;
    background: var(--color-text-muted);
    opacity: 0.45;
  }
  .gate-rail-marker--diamond {
    transform: rotate(45deg);
    border-radius: var(--radius-sm);
  }
  .gate-rail-marker--circle {
    border-radius: var(--radius-full);
  }
  .gate-rail-step.is-done .gate-rail-marker {
    background: var(--color-text-secondary);
    opacity: 0.8;
  }
  .gate-rail-step.is-active .gate-rail-marker {
    background: var(--color-accent);
    opacity: 1;
  }

  /* ── Deep-research "next" card (selection sidebar) ── */
  .next-card {
    display: grid;
    gap: var(--space-1);
    margin: var(--space-1) var(--space-6) 0;
    padding: var(--space-3);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    color: var(--color-text-muted);
  }

  .next-card-title {
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 700;
  }

  .next-card-text {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.35;
  }

  /* ── Peek items — locked, stacked label + value tagline. Standalone (not a
       SidebarNavItem): two-line, non-interactive teaser. ── */
  .peek-item {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    padding: 0.5rem 1.5rem;
    opacity: 0.75;
    pointer-events: none;
  }
  .peek-item--first {
    margin-top: 6px;
  }
  .peek-item :global(.peek-icon) {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    opacity: 0.5;
    margin-top: 1px;
  }
  .nav-item-peek-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    line-height: 1.2;
    min-width: 0;
  }
  .peek-label {
    line-height: 1.4;
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: var(--text-13);
    font-weight: 500;
  }
  .nav-item-tagline {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  /* Push the Tooltip's outer wrapper (the actual flex child) to the right */
  .peek-item :global(.tooltip-wrapper) {
    margin-left: auto;
  }

  .nav-lock-trigger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    pointer-events: auto;
    cursor: help;
    flex-shrink: 0;
  }

  .nav-lock-icon {
    width: 12px;
    height: 12px;
    flex-shrink: 0;
    opacity: 0.35;
  }

  /* "+N more" label */
  .nav-more {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.35rem 1.5rem;
    font-family: var(--font-mono);
    font-size: var(--text-11);
    /* Was opacity:0.4 (~1.9:1) — the "+N more" count is information, not
       decoration, so it must be legible. Full-strength muted = 4.4:1. */
    color: var(--color-text-muted);
    letter-spacing: 0.03em;
  }

  /* Width clamp: this wrapper is a direct flex item of .job-page-shell. Without
     min-width:0 its min-content (the sum of the nowrap chips, ~700px) propagates
     into the shell and inflates the page at narrow viewports, pushing the commit
     CTA off-screen. The inner navs stay the scrollers (overflow-x:auto). */
  .selection-mobile-navigation {
    position: relative;
    min-width: 0;
    max-width: 100%;
    overflow-x: clip;
  }

  .selection-step-toggle,
  .selection-step-menu {
    display: none;
  }

  .selection-mobile-nav {
    display: flex;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    overflow-x: auto;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-base);
  }

  .selection-context-menu {
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }
  .selection-context-menu > summary {
    width: fit-content;
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-4);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
  }
  .selection-context-menu nav {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    padding: 0 var(--space-4) var(--space-3);
  }
  .selection-context-menu a,
  .selection-context-menu button {
    min-height: var(--space-9);
    padding: var(--space-2);
    border: 0;
    background: transparent;
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-13);
    text-decoration: none;
    cursor: pointer;
  }

  .selection-mobile-item {
    flex: 0 0 auto;
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 600;
    white-space: nowrap;
    text-decoration: none;
    transition: background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }

  .selection-mobile-item:hover:not(.locked):not(.active) { border-color: var(--color-border-emphasis); color: var(--color-text-primary); }
  .selection-mobile-item:active:not(.locked) { transform: scale(0.98); }
  .selection-mobile-item.locked { display: grid; gap: var(--space-1); color: var(--color-text-muted); background: var(--color-bg-surface); }
  .selection-mobile-item.locked small { font-size: var(--text-xs); line-height: 1.2; }

  .selection-mobile-item.active {
    border-color: var(--color-border-accent);
    background: var(--color-accent-subtle);
    color: var(--color-accent-dark);
  }

  .selection-mobile-item:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  @media (min-width: 1280px) {
    .selection-mobile-navigation { display: none; }
  }

  @media (max-width: 40rem) {
    .selection-mobile-nav--journey,
    .selection-context-menu {
      display: none;
    }
    .selection-step-toggle {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: var(--space-2);
      align-items: baseline;
      width: 100%;
      min-height: var(--space-12);
      padding: var(--space-2) var(--space-4);
      border: 0;
      border-bottom: 1px solid var(--color-border);
      background: var(--color-bg-base);
      color: var(--color-text-secondary);
      text-align: left;
    }
    .selection-step-toggle span {
      font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono);
      letter-spacing: var(--tracking-wide);
      text-transform: uppercase;
    }
    .selection-step-toggle strong {
      overflow: hidden;
      color: var(--color-text-primary);
      font-size: var(--text-sm);
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .selection-step-menu {
      display: grid;
      position: absolute;
      z-index: var(--z-dropdown);
      top: 100%;
      right: var(--space-3);
      left: var(--space-3);
      padding: var(--space-2);
      border: 1px solid var(--color-border-emphasis);
      border-radius: var(--radius-md);
      background: var(--color-bg-elevated);
      box-shadow: var(--shadow-md);
    }
    .selection-step-menu > a,
    .selection-step-menu > button,
    .selection-step-menu > span,
    .selection-step-menu details > a,
    .selection-step-menu details > button {
      display: block;
      width: 100%;
      min-height: var(--space-10);
      padding: var(--space-2) var(--space-3);
      border: 0;
      border-radius: var(--radius-sm);
      background: transparent;
      color: var(--color-text-primary);
      font: inherit;
      font-size: var(--text-sm);
      line-height: var(--space-6);
      text-align: left;
      text-decoration: none;
      cursor: pointer;
    }
    .selection-step-menu > span { color: var(--color-text-muted); }
    .selection-step-menu a[aria-current="page"] { background: var(--color-accent-subtle); color: var(--color-accent-dark); }
    .selection-step-menu details { border-top: 1px solid var(--color-border); }
    .selection-step-menu details > summary {
      min-height: var(--space-10);
      padding: var(--space-2) var(--space-3);
      color: var(--color-text-secondary);
      font-size: var(--text-sm);
      font-weight: 700;
      cursor: pointer;
    }
  }

  /* ═══════════════════════════════════
     MOBILE BOTTOM BAR
     ═══════════════════════════════════ */
  .sidebar-mobile {
    position: fixed;
    bottom: max(var(--space-4), env(safe-area-inset-bottom));
    left: 50%;
    transform: translateX(-50%);
    z-index: var(--z-overlay, 50);
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  @media (min-width: 1280px) {
    .sidebar-mobile { display: none; }
  }

  .mobile-toggle {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    padding: 0.75rem 1.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 600;
    cursor: pointer;
  }

  .mobile-progress-bar {
    width: 60px;
    height: 3px;
    background: var(--color-bg-surface);
    border-radius: var(--radius-full);
    overflow: hidden;
  }

  .mobile-progress-fill {
    height: 100%;
    background: var(--color-accent);
    border-radius: var(--radius-full);
    transition: width var(--duration-fast) linear;
  }

  .mobile-current {
    font-family: var(--font-mono);
    font-size: var(--text-11);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .mobile-menu {
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    margin-bottom: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 0.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg, 0.75rem);
    min-width: 200px;
    max-height: 60vh;
    overflow-y: auto;
    animation: slideUp var(--duration-normal) var(--ease-out);
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateX(-50%) translateY(10px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
  }

  .mobile-phase-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
  }

  .mobile-divider {
    height: 1px;
    background: var(--color-border);
    margin: 0.5rem 0;
  }

  .mobile-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: transparent;
    border: none;
    border-radius: var(--radius-md, 0.375rem);
    color: var(--color-text-muted);
    font-size: var(--text-base);
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    width: 100%;
    white-space: nowrap;
    transition: color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default);
  }

  .mobile-item:hover:not(.locked):not(.mobile-item--disabled) {
    color: var(--color-text-primary);
    background: var(--color-bg-hover, var(--color-bg-surface));
  }

  .mobile-item.active {
    /* -dark so orange-on-accent-subtle clears AA (4.5:1), not 3.4:1. */
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
  }

  .mobile-item.done {
    color: var(--color-success-text);
  }

  .mobile-item.locked {
    color: var(--color-text-muted);
    opacity: 0.5;
  }
  .mobile-item--disabled {
    cursor: default;
    opacity: 0.6;
  }

  .mobile-item.previewable {
    color: var(--color-text-secondary);
    opacity: 0.75;
  }

  @media (prefers-reduced-motion: reduce) {
    .mobile-menu { animation: none; }
    .mobile-progress-fill { transition: none; }
    .selection-mobile-item { transition: none; }
    .selection-mobile-item:active { transform: none; }
  }
</style>
