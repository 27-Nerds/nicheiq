<script lang="ts">
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import {
    Check,
    Eraser,
    Loader2,
    MousePointer2,
    Pencil,
    RotateCcw,
    TriangleAlert,
  } from 'lucide-svelte';
  import {
    fetchSharedDiscoveryAnnotations,
    getDiscoveryAnnotations,
    saveDiscoveryAnnotations,
  } from '$lib/api';
  import {
    EMPTY_DISCOVERY_ANNOTATIONS,
    type AnnotationStroke,
    type DiscoveryAnnotationDocument,
    type DiscoveryAnnotationResponse,
  } from '$lib/types/discoveryAnnotations';
  import {
    provideAnnotationContext,
    type AnnotationContext,
    type AnnotationSaveStatus,
    type AnnotationTool,
  } from './context';
  import AnnotationSurface from './AnnotationSurface.svelte';
  import { portal } from '$lib/actions/portal';

  interface Props {
    mode: 'owner' | 'viewer';
    /** Loads and renders annotations when true. */
    enabled?: boolean;
    /** Owner mutation capability. Defaults to enabled for backward compatibility. */
    editable?: boolean;
    /** Keeps annotation support available without forcing the floating entry point onto every workspace. */
    showLauncher?: boolean;
    jobId?: string;
    shareToken?: string;
    surfaceKey?: string;
    /** SSR snapshot. When supplied, owner mode renders without a second client fetch. */
    initialDocument?: DiscoveryAnnotationResponse | null;
    children: Snippet;
  }

  let {
    mode,
    enabled = true,
    editable: editEnabled = true,
    showLauncher = true,
    jobId,
    shareToken,
    surfaceKey = 'research:page',
    initialDocument = null,
    children,
  }: Props = $props();

  let document = $state<DiscoveryAnnotationDocument>(
    structuredClone(EMPTY_DISCOVERY_ANNOTATIONS),
  );
  let revision = $state(0);
  let active = $state(false);
  let tool = $state<AnnotationTool>('pen');
  let color = $state('#dc2626');
  let strokeWidth = $state(4);
  let loadedOwnerJobId = $state<string | null>(null);
  let hydratedInitialKey = '';
  let saveStatus = $state<AnnotationSaveStatus>('idle');
  let saveTimer: ReturnType<typeof setTimeout> | undefined;
  let saveSequence = 0;

  const ownerReadable = $derived(mode === 'owner' && enabled && !!jobId);
  const editable = $derived(ownerReadable && editEnabled);

  $effect(() => {
    if (editable || !active) return;
    active = false;
    tool = 'navigate';
  });

  function getStrokes(surfaceKey: string): AnnotationStroke[] {
    return document?.surfaces?.[surfaceKey]?.strokes ?? [];
  }

  function scheduleSave() {
    if (!editable || !jobId) return;
    saveStatus = 'saving';
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => void persist(), 650);
  }

  async function persist() {
    if (!editable || !jobId) return;
    const sequence = ++saveSequence;
    try {
      const response = await saveDiscoveryAnnotations(jobId, document);
      if (sequence !== saveSequence) return;
      revision = response.revision;
      saveStatus = 'saved';
    } catch (error) {
      console.error('Failed to save discovery annotations:', error);
      if (sequence === saveSequence) saveStatus = 'error';
    }
  }

  function addStroke(surfaceKey: string, stroke: AnnotationStroke) {
    if (!editable) return;
    document.surfaces[surfaceKey] ??= { strokes: [] };
    document.surfaces[surfaceKey].strokes.push(stroke);
    scheduleSave();
  }

  function removeStroke(surfaceKey: string, strokeId: string) {
    if (!editable) return;
    const surface = document.surfaces[surfaceKey];
    if (!surface) return;
    const next = surface.strokes.filter((stroke) => stroke.id !== strokeId);
    if (next.length === surface.strokes.length) return;
    if (next.length) surface.strokes = next;
    else delete document.surfaces[surfaceKey];
    scheduleSave();
  }

  function undo() {
    if (!editable) return;
    let latest: { surfaceKey: string; stroke: AnnotationStroke } | null = null;
    for (const [surfaceKey, surface] of Object.entries(document.surfaces)) {
      for (const stroke of surface.strokes) {
        if (!latest || stroke.createdAt > latest.stroke.createdAt) {
          latest = { surfaceKey, stroke };
        }
      }
    }
    if (latest) removeStroke(latest.surfaceKey, latest.stroke.id);
  }

  const context: AnnotationContext = {
    get editable() { return editable; },
    get active() { return active; },
    get tool() { return tool; },
    get color() { return color; },
    get strokeWidth() { return strokeWidth; },
    get saveStatus() { return saveStatus; },
    getStrokes,
    addStroke,
    removeStroke,
    setActive(value) {
      active = value;
      tool = value ? 'pen' : 'navigate';
    },
    setTool(value) { tool = value; },
    setColor(value) { color = value; },
    undo,
  };
  provideAnnotationContext(context);

  async function loadOwnerDocument() {
    if (!ownerReadable || !jobId) return;
    saveStatus = 'loading';
    try {
      const response = await getDiscoveryAnnotations(jobId);
      revision = response.revision;
      document = response.document;
      saveStatus = 'idle';
    } catch (error) {
      console.error('Failed to load discovery annotations:', error);
      saveStatus = 'error';
    }
  }

  async function pollViewerDocument() {
    if (mode !== 'viewer' || !shareToken || globalThis.document.visibilityState === 'hidden') return;
    try {
      const response = await fetchSharedDiscoveryAnnotations(shareToken, revision);
      if (!response) return;
      revision = response.revision;
      document = response.document;
    } catch (error) {
      console.error('Failed to refresh shared annotations:', error);
    }
  }

  $effect(() => {
    if (!ownerReadable || !jobId || !initialDocument) return;
    const key = `${jobId}:${initialDocument.revision}`;
    if (hydratedInitialKey === key) return;
    hydratedInitialKey = key;
    revision = initialDocument.revision;
    document = structuredClone(initialDocument.document);
    loadedOwnerJobId = jobId;
  });

  $effect(() => {
    if (!ownerReadable || !jobId || loadedOwnerJobId === jobId) return;
    loadedOwnerJobId = jobId;
    void loadOwnerDocument();
  });

  onMount(() => {
    if (mode === 'owner') {
      return () => {
        if (saveTimer) clearTimeout(saveTimer);
      };
    }

    void pollViewerDocument();
    const interval = window.setInterval(() => void pollViewerDocument(), 4_000);
    return () => window.clearInterval(interval);
  });
</script>

<AnnotationSurface {surfaceKey}>
  {@render children()}
</AnnotationSurface>

{#if editable && (showLauncher || active)}
  <!-- Portaled to <body> and marked data-modal-exempt: the toolbar is designed to
       work ABOVE modals (see the z-index comment below), but isolateModalBackground
       inertifies every body child while a FormOverlay/WorkspaceOverlay is open —
       rendered in the app root it was a dead strip of buttons under every modal. -->
  <div
    use:portal
    data-modal-exempt
    class="annotation-toolbar"
    role="toolbar"
    aria-label="Page annotation controls"
  >
    {#if !active}
      <button
        type="button"
        class="annotation-primary"
        onclick={() => context.setActive(true)}
      >
        <Pencil aria-hidden="true" />
        Annotate
      </button>
    {:else}
      <button
        type="button"
        class:active={tool === 'navigate'}
        aria-pressed={tool === 'navigate'}
        title="Navigate and open page controls"
        onclick={() => context.setTool('navigate')}
      >
        <MousePointer2 aria-hidden="true" />
        <span>Navigate</span>
      </button>
      <button
        type="button"
        class:active={tool === 'pen'}
        aria-pressed={tool === 'pen'}
        onclick={() => context.setTool('pen')}
      >
        <Pencil aria-hidden="true" />
        <span>Draw</span>
      </button>
      <button
        type="button"
        class:active={tool === 'eraser'}
        aria-pressed={tool === 'eraser'}
        onclick={() => context.setTool('eraser')}
      >
        <Eraser aria-hidden="true" />
        <span>Erase</span>
      </button>
      <label class="annotation-color" title="Drawing color">
        <span class="sr-only">Drawing color</span>
        <input
          type="color"
          value={color}
          oninput={(event) => context.setColor(event.currentTarget.value)}
        />
      </label>
      <button type="button" title="Undo last stroke" onclick={() => context.undo()}>
        <RotateCcw aria-hidden="true" />
        <span class="sr-only">Undo last stroke</span>
      </button>
      <span class="annotation-status" aria-live="polite">
        {#if saveStatus === 'loading' || saveStatus === 'saving'}
          <Loader2 class="spin" aria-hidden="true" />
          {saveStatus === 'loading' ? 'Loading' : 'Saving'}
        {:else if saveStatus === 'saved'}
          <Check aria-hidden="true" />
          Saved
        {:else if saveStatus === 'error'}
          <TriangleAlert aria-hidden="true" />
          Save failed
        {/if}
      </span>
      <button
        type="button"
        class="annotation-done"
        onclick={() => context.setActive(false)}
      >
        Done
      </button>
    {/if}
  </div>
{/if}

<style>
  /* Bottom-anchored on purpose: the toolbar sits above modals so annotating
     works inside an overlay, and the top-right corner is where every overlay
     puts its close button. Anchoring top-right had it covering the control
     users reach for most. */
  .annotation-toolbar {
    position: fixed;
    bottom: max(0.75rem, calc(env(safe-area-inset-bottom) + 0.75rem));
    right: max(0.75rem, env(safe-area-inset-right));
    z-index: var(--z-annotation-toolbar, 90);
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.35rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 0.75rem;
    background: var(--color-bg-elevated);
    box-shadow: 0 0.75rem 2rem rgb(0 0 0 / 14%);
  }

  .annotation-toolbar button,
  .annotation-color {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
    min-height: 2.5rem;
    padding: 0.5rem 0.65rem;
    border: 0;
    border-radius: 0.5rem;
    background: transparent;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 650;
    cursor: pointer;
    transition:
      background-color 180ms ease,
      color 180ms ease,
      transform 120ms ease;
  }

  .annotation-toolbar button:hover,
  .annotation-toolbar button.active {
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .annotation-toolbar button:active {
    transform: translateY(1px) scale(0.98);
  }

  .annotation-toolbar button:focus-visible,
  .annotation-color:focus-within {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .annotation-toolbar .annotation-primary,
  .annotation-toolbar .annotation-done {
    background: var(--color-text-primary);
    color: var(--color-bg-surface);
  }

  .annotation-toolbar :global(svg) {
    width: 1rem;
    height: 1rem;
  }

  .annotation-color input {
    width: 1.35rem;
    height: 1.35rem;
    padding: 0;
    border: 0;
    border-radius: 999px;
    background: transparent;
    cursor: pointer;
  }

  .annotation-status {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    min-width: 4.5rem;
    color: var(--color-text-muted);
    font-size: 0.6875rem;
  }

  :global(.spin) {
    animation: annotation-spin 800ms linear infinite;
  }

  @keyframes annotation-spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 640px) {
    .annotation-toolbar {
      top: auto;
      right: 0.5rem;
      bottom: max(0.5rem, env(safe-area-inset-bottom));
      left: 0.5rem;
      justify-content: center;
      overflow-x: auto;
    }

    .annotation-toolbar button,
    .annotation-color {
      min-width: 2.75rem;
      min-height: 2.75rem;
    }

    .annotation-toolbar button span:not(.sr-only),
    .annotation-status {
      display: none;
    }
  }
</style>
