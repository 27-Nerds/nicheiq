<script lang="ts">
  import { onMount, type Component, type Snippet } from 'svelte';
  import type { HTMLAttributes } from 'svelte/elements';
  import { getAnnotationContext } from './context';

  interface CanvasProps {
    surfaceKey: string;
    width: number;
    height: number;
  }

  interface Props extends HTMLAttributes<HTMLDivElement> {
    surfaceKey: string;
    anchorKey?: string;
    children?: Snippet;
  }

  let { surfaceKey, anchorKey, class: className = '', children, ...rest }: Props = $props();
  const context = getAnnotationContext();

  let containerEl = $state<HTMLDivElement>();
  let width = $state(0);
  let height = $state(0);
  let Canvas = $state<Component<CanvasProps> | null>(null);

  onMount(() => {
    if (!context || !containerEl || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      width = entry.contentRect.width;
      height = entry.contentRect.height;
    });
    observer.observe(containerEl);
    return () => observer.disconnect();
  });

  // Defer the heavy Konva import + mount until this surface is actually used:
  // annotation mode turns on, or the surface already carries strokes. Loading it
  // eagerly on every mount froze screenshots and cost load on pages that never
  // annotate. The guard fires once; after the import there is nothing left to track.
  let canvasRequested = false;
  $effect(() => {
    if (!context || canvasRequested) return;
    if (!context.active && context.getStrokes(surfaceKey).length === 0) return;
    canvasRequested = true;
    void import('./KonvaAnnotationCanvas.svelte').then((module) => {
      Canvas = module.default;
    });
  });
</script>

<div
  {...rest}
  bind:this={containerEl}
  class="annotation-surface {className}"
  data-annotation-surface={surfaceKey}
  data-annotation-anchor={anchorKey ?? surfaceKey}
>
  {#if children}
    {@render children()}
  {/if}
  {#if context && Canvas && width > 0 && height > 0}
    <Canvas {surfaceKey} {width} {height} />
  {/if}
</div>

<style>
  .annotation-surface {
    position: relative;
    isolation: isolate;
    min-width: 0;
  }
</style>
