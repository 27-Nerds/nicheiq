<script lang="ts">
  import {
    PHASES,
    DEEP_RESEARCH_BLURRED_PREVIEW_IDS,
    DEEP_RESEARCH_PEEK_ITEMS,
    type PhaseConfig,
    type SectionConfig,
  } from "$lib/config/phase-sections";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";

  interface Props {
    jobStatus: string;
    activeSection?: string;
  }

  let { jobStatus, activeSection = "" }: Props = $props();

  let scrollProgress = $state(0);
  let trackedSection = $state("");
  let isOpen = $state(false);

  const currentSection = $derived(activeSection || trackedSection);

  // Phase badge states
  type BadgeState = "active" | "done" | "locked";

  interface PhaseBadge {
    label: string;
    state: BadgeState;
    variant: "success" | "secondary" | "muted";
  }

  const phaseBadges = $derived.by((): Record<string, PhaseBadge> => {
    switch (jobStatus) {
      case "RUNNING_PHASE2":
        return {
          discovery: { label: "WHAT", state: "done", variant: "success" },
          "deep-research": { label: "HOW", state: "active", variant: "secondary" },
          build: { label: "GO", state: "locked", variant: "muted" },
        };
      case "COMPLETED":
        return {
          discovery: { label: "WHAT", state: "done", variant: "success" },
          "deep-research": { label: "HOW", state: "done", variant: "secondary" },
          build: { label: "GO", state: "active", variant: "secondary" },
        };
      default:
        return {
          discovery: { label: "WHAT", state: "active", variant: "success" },
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

  function isPhaseUnlocked(phaseId: string): boolean {
    const badge = phaseBadges[phaseId];
    return badge?.state === "active" || badge?.state === "done";
  }

  const HEADER_OFFSET = 72; // 56px header + 16px breathing room
  const SCROLL_THRESHOLD = HEADER_OFFSET + 10; // small buffer above header for activation

  function scrollToElement(el: HTMLElement) {
    const y = el.getBoundingClientRect().top + window.scrollY - HEADER_OFFSET;
    window.scrollTo({ top: y, behavior: 'smooth' });
  }

  function handleSectionClick(phase: PhaseConfig, section: SectionConfig) {
    const el = document.getElementById(section.id);
    if (el) {
      trackedSection = section.id;
      scrollToElement(el);
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
    const allSections = PHASES.flatMap((p) => {
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
    for (let i = sectionElements.length - 1; i >= 0; i--) {
      const section = sectionElements[i];
      if (section.top - scrollY <= SCROLL_THRESHOLD) {
        trackedSection = section.id;
        break;
      }
    }
  }

  $effect(() => { handleScroll(); });
</script>

<svelte:window onscroll={handleScroll} />

<!-- ═══ DESKTOP SIDEBAR ═══ -->
<nav class="sidebar-desktop">
  <div class="sidebar-phases">
    {#each PHASES as phase, phaseIndex}
      {@const badge = phaseBadges[phase.id]}
      {@const unlocked = isPhaseUnlocked(phase.id)}

      {#if phaseIndex > 0}
        <div class="phase-divider"></div>
      {/if}

      <div class="phase-group">
        <div class="phase-header">
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

        <div class="phase-sections">
          {#if phase.id === 'deep-research' && !unlocked}
            <!-- Blurred preview items first (scrollable on page) -->
            {#each blurredPreviewSections as section}
              {@const isActive = currentSection === section.id}
              {@const Icon = section.icon}
              <button
                class="nav-item previewable"
                class:active={isActive}
                onclick={() => handleSectionClick(phase, section)}
              >
                {#if Icon}<Icon class="nav-icon" />{/if}
                <span class="nav-item-label">{section.label}</span>
                <span class="nav-preview-tag">Preview</span>
              </button>
            {/each}
            <!-- Peek items — locked, stacked label + value tagline -->
            {#each peekItems as item, idx (item.id)}
              {@const Icon = item.icon}
              <div
                class="nav-item locked nav-item-peek"
                class:nav-item-peek--first={idx === 0}
                aria-disabled="true"
              >
                {#if Icon}<Icon class="nav-icon" aria-hidden="true" />{/if}
                <div class="nav-item-peek-text">
                  <span class="nav-item-label">{item.label}</span>
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

              <button
                class="nav-item"
                class:active={isActive}
                class:done={isDone}
                class:locked={!unlocked}
                onclick={() => handleSectionClick(phase, section)}
                disabled={!unlocked}
              >
                {#if Icon}
                  <Icon class="nav-icon" />
                {/if}
                <span class="nav-item-label">{section.label}</span>
                {#if isDone}
                  <span class="nav-check">
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2.5 2.5L8 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </span>
                {:else if !unlocked}
                  <svg class="nav-lock-icon" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="5.5" width="8" height="6" rx="1.5"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/></svg>
                {/if}
              </button>
            {/each}
          {/if}
        </div>
      </div>
    {/each}
  </div>
</nav>

<!-- ═══ MOBILE BOTTOM BAR ═══ -->
<nav class="sidebar-mobile" class:open={isOpen}>
  <button class="mobile-toggle" onclick={() => (isOpen = !isOpen)}>
    <div class="mobile-progress-bar">
      <div class="mobile-progress-fill" style:width="{scrollProgress * 100}%"></div>
    </div>
    <span class="mobile-current">
      {PHASES.flatMap((p) => p.sections).find((s) => s.id === currentSection)?.label || "Navigate"}
    </span>
  </button>

  {#if isOpen}
    <div class="mobile-menu">
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
    </div>
  {/if}
</nav>

<style>
  /* ═══════════════════════════════════
     DESKTOP SIDEBAR
     ═══════════════════════════════════ */
  .sidebar-desktop {
    width: 240px;
    flex-shrink: 0;
    background: var(--color-bg-elevated);
    border-right: 1px solid var(--color-border);
    padding: 1.5rem 0;
    position: sticky;
    top: 3.5rem;
    height: calc(100vh - 3.5rem);
    overflow-y: auto;
    display: none;
  }

  @media (min-width: 1280px) {
    .sidebar-desktop { display: block; }
  }

  .sidebar-phases {
    display: flex;
    flex-direction: column;
  }

  /* ── Phase groups ── */
  .phase-group {
    display: flex;
    flex-direction: column;
  }

  .phase-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.375rem 1.5rem 0.5rem;
  }

  .phase-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .phase-badge {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 9999px;
    white-space: nowrap;
  }

  .phase-badge.badge-success {
    color: var(--color-success-dark);
    background: rgba(34, 197, 94, 0.1);
    border: 0.5px solid rgba(34, 197, 94, 0.3);
  }

  .phase-badge.badge-secondary {
    color: var(--color-secondary-dark, #4f46e5);
    background: var(--color-secondary-subtle, rgba(99, 102, 241, 0.08));
    border: 0.5px solid rgba(99, 102, 241, 0.2);
  }

  .phase-badge.badge-muted {
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border: 0.5px solid var(--color-border);
  }

  /* ── Phase dividers ── */
  .phase-divider {
    height: 0.5px;
    background: var(--color-border);
    margin: 0.75rem 1.5rem;
  }

  /* ── Section items ── */
  .phase-sections {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .nav-item {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.5rem 1.5rem;
    background: transparent;
    border: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    white-space: nowrap;
    transition: color 150ms ease, background-color 150ms ease;
  }

  .nav-item:hover:not(.locked):not(.active) {
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .nav-item:not(.locked):active {
    transform: scale(0.98);
  }

  .nav-item:focus-visible {
    transition: none;
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
  }

  /* Active indicator: text color + background fill */
  .nav-item.active,
  .nav-item.active.done {
    color: var(--color-accent);
    font-weight: 600;
    background: var(--color-accent-subtle);
  }

  /* Done tier */
  .nav-item.done {
    color: var(--color-text-primary);
  }

  .nav-check {
    margin-left: auto;
    width: 16px;
    height: 16px;
    background: var(--color-success);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
  }

  /* Preview-able tier */
  .nav-item.previewable {
    color: var(--color-text-secondary);
    opacity: 0.75;
    cursor: pointer;
  }

  .nav-item.previewable:hover {
    opacity: 1;
    background: var(--color-bg-surface);
  }

  /* Active state must win over .previewable color/opacity (source-order tie) */
  .nav-item.active.previewable {
    color: var(--color-accent);
    opacity: 1;
    font-weight: 600;
    background: var(--color-accent-subtle);
  }

  .nav-preview-tag {
    margin-left: auto;
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-accent);
    letter-spacing: 0.02em;
  }

  /* Locked tier */
  .nav-item.locked {
    color: var(--color-text-muted);
    opacity: 0.45;
    cursor: default;
    pointer-events: none;
  }

  /* Peek variant — locked, stacked label + value tagline */
  .nav-item-peek {
    align-items: flex-start;
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
  }
  .nav-item-peek--first {
    margin-top: 6px;
  }
  .nav-item-peek :global(.nav-icon) {
    margin-top: 1px;
  }
  .nav-item-peek-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    line-height: 1.2;
    min-width: 0;
  }
  .nav-item-peek .nav-item-label {
    color: var(--color-text-primary);
    font-weight: 500;
  }
  .nav-item-tagline {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  /* Override .nav-item.locked's 0.45 so the tagline is readable */
  .nav-item.locked.nav-item-peek {
    opacity: 0.75;
  }

  .nav-lock-trigger {
    margin-left: auto;
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

  .nav-item-label {
    line-height: 1.4;
  }

  /* "+N more" label */
  .nav-more {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.35rem 1.5rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    opacity: 0.4;
    letter-spacing: 0.03em;
  }

  /* ── Section icons ── */
  .nav-item :global(.nav-icon) {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    opacity: 0.5;
    transition: opacity 150ms ease;
  }

  .nav-item.active :global(.nav-icon) {
    opacity: 1;
  }

  .nav-item.done :global(.nav-icon) {
    opacity: 0.7;
  }

  /* ═══════════════════════════════════
     MOBILE BOTTOM BAR
     ═══════════════════════════════════ */
  .sidebar-mobile {
    position: fixed;
    bottom: calc(1rem + 60px);
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
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(12px);
    border: 1px solid var(--color-border);
    border-radius: 2rem;
    color: var(--color-text-primary);
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
  }

  .mobile-progress-bar {
    width: 60px;
    height: 3px;
    background: var(--color-bg-surface);
    border-radius: 2px;
    overflow: hidden;
  }

  .mobile-progress-fill {
    height: 100%;
    background: var(--color-accent);
    border-radius: 2px;
    transition: width 100ms linear;
  }

  .mobile-current {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
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
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(12px);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg, 0.75rem);
    min-width: 200px;
    max-height: 60vh;
    overflow-y: auto;
    animation: slideUp 200ms ease-out;
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
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    width: 100%;
    white-space: nowrap;
    transition: color 150ms ease, background-color 150ms ease;
  }

  .mobile-item:hover:not(.locked) {
    color: var(--color-text-primary);
    background: var(--color-bg-hover, var(--color-bg-surface));
  }

  .mobile-item.active {
    color: var(--color-accent);
    background: var(--color-accent-subtle, rgba(240, 96, 48, 0.06));
  }

  .mobile-item.done {
    color: var(--color-success-dark);
  }

  .mobile-item.locked {
    color: var(--color-text-muted);
    opacity: 0.5;
  }

  .mobile-item.previewable {
    color: var(--color-text-secondary);
    opacity: 0.75;
  }
</style>
