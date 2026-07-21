<script lang="ts">
  import { onMount } from 'svelte';
  import { Layer, Line, Stage } from 'svelte-konva';
  import { getAnnotationContext } from './context';
  import {
    annotationAnchorChainAtPoint,
    projectAnchoredPoint,
    resolveStrokeGeometry,
  } from './anchors';
  import type {
    AnnotationAnchor,
    AnnotationAnchorPoint,
    AnnotationPoint,
  } from '$lib/types/discoveryAnnotations';

  interface Props {
    surfaceKey: string;
    width: number;
    height: number;
  }

  let { surfaceKey, width, height }: Props = $props();
  const context = getAnnotationContext();

  let stage = $state<any>();
  let canvasEl = $state<HTMLDivElement>();
  let drawing = $state(false);
  let livePoints = $state<AnnotationPoint[]>([]);
  let liveAnchorChains = $state<PointerAnchorSample[][]>([]);
  let layoutVersion = $state(0);

  const strokes = $derived(context?.getStrokes(surfaceKey) ?? []);
  const capturesPointer = $derived(
    !!context?.editable &&
    context.active &&
    (context.tool === 'pen' || context.tool === 'eraser'),
  );

  interface PointerSample {
    point: AnnotationPoint;
    anchors: PointerAnchorSample[];
  }

  interface PointerAnchorSample extends AnnotationAnchorPoint {
    width: number;
    height: number;
  }

  function clamp(value: number): number {
    return Math.max(0, Math.min(1, value));
  }

  function surfaceElement(): HTMLElement | null {
    return canvasEl?.closest<HTMLElement>('[data-annotation-surface]') ?? null;
  }

  onMount(() => {
    const surface = surfaceElement();
    if (!surface) return;

    const refresh = () => { layoutVersion += 1; };
    const observer = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(refresh);
    observer?.observe(surface);
    for (const anchor of surface.querySelectorAll<HTMLElement>('[data-annotation-anchor]')) {
      observer?.observe(anchor);
    }

    window.addEventListener('resize', refresh, { passive: true });
    surface.addEventListener('scroll', refresh, { capture: true, passive: true });
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', refresh);
      surface.removeEventListener('scroll', refresh, { capture: true });
    };
  });

  function anchorsAt(point: { x: number; y: number }): PointerAnchorSample[] {
    const container = stage?.node?.container?.() as HTMLElement | undefined;
    const surface = surfaceElement();
    if (!container || !surface) return [];

    const containerRect = container.getBoundingClientRect();
    const clientX = containerRect.left + point.x;
    const clientY = containerRect.top + point.y;
    return annotationAnchorChainAtPoint(surface, { x: clientX, y: clientY }).flatMap((anchor) => {
      const key = anchor.dataset.annotationAnchor;
      const rect = anchor.getBoundingClientRect();
      if (!key || rect.width <= 0 || rect.height <= 0) return [];
      const contentWidth = Math.max(rect.width, anchor.scrollWidth);
      const contentHeight = Math.max(rect.height, anchor.scrollHeight);
      return [{
        key,
        // Do not clamp anchor-local coordinates: the annotation halo is
        // intentionally allowed to sit just outside the marked element.
        x: (clientX - rect.left + anchor.scrollLeft) / contentWidth,
        y: (clientY - rect.top + anchor.scrollTop) / contentHeight,
        width: contentWidth,
        height: contentHeight,
      }];
    });
  }

  function pointerSample(): PointerSample | null {
    const point = stage?.node?.getPointerPosition();
    if (!point || width <= 0 || height <= 0) return null;
    return {
      point: [clamp(point.x / width), clamp(point.y / height)],
      anchors: anchorsAt(point),
    };
  }

  function handlePointerDown() {
    if (!context || context.tool !== 'pen') return;
    const sample = pointerSample();
    if (!sample) return;
    drawing = true;
    livePoints = [sample.point];
    liveAnchorChains = [sample.anchors];
  }

  function handlePointerMove() {
    if (!drawing || !context || context.tool !== 'pen') return;
    const sample = pointerSample();
    if (!sample) return;
    const previous = livePoints[livePoints.length - 1];
    if (previous && Math.hypot(sample.point[0] - previous[0], sample.point[1] - previous[1]) < 0.0015) {
      return;
    }
    if (livePoints.length < 2_000) {
      livePoints = [...livePoints, sample.point];
      liveAnchorChains = [...liveAnchorChains, sample.anchors];
    }
  }

  function finishStroke() {
    if (!drawing || !context || context.tool !== 'pen') return;
    drawing = false;
    const surfacePoints = livePoints.length === 1
      ? [livePoints[0], livePoints[0]]
      : livePoints;
    const anchorChains = liveAnchorChains.length === 1
      ? [liveAnchorChains[0], liveAnchorChains[0]]
      : liveAnchorChains;
    const geometry = resolveStrokeGeometry(surfacePoints, anchorChains);
    livePoints = [];
    liveAnchorChains = [];
    if (!geometry.points.length) return;
    context.addStroke(surfaceKey, {
      id: crypto.randomUUID(),
      color: context.color,
      width: context.strokeWidth,
      createdAt: Date.now(),
      surfaceHeight: height,
      ...geometry,
    });
  }

  function denormalizeSegments(
    points: AnnotationPoint[],
    sourceHeight = height,
    anchor?: AnnotationAnchor,
    anchors?: Array<AnnotationAnchorPoint | null>,
  ): number[][] {
    // Re-run DOM projection when semantic regions reflow or an overlay scrolls.
    // Anchor-local points follow the destination region on both axes so marks
    // stay attached when text wraps or owner/shared chrome changes.
    void layoutVersion;
    const surface = surfaceElement();
    const surfaceRect = surface?.getBoundingClientRect();
    const elements = surface
      ? [
          ...(surface.matches('[data-annotation-anchor]') ? [surface] : []),
          ...Array.from(surface.querySelectorAll<HTMLElement>('[data-annotation-anchor]')),
        ]
      : [];
    const rects = new Map<string, DOMRect>();
    const anchorElements = new Map(
      elements.flatMap((element) => {
        const key = element.dataset.annotationAnchor;
        return key ? [[key, element] as const] : [];
      }),
    );

    if (anchor && surfaceRect) {
      const element = anchorElements.get(anchor.key);
      if (!element) return [];
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return [];
      const contentRect = {
        left: rect.left,
        top: rect.top,
        width: Math.max(rect.width, element.scrollWidth),
        height: Math.max(rect.height, element.scrollHeight),
      };
      return [points.flatMap((point) => projectAnchoredPoint(
          point,
          contentRect,
          surfaceRect,
          { left: element.scrollLeft, top: element.scrollTop },
          anchor,
        ))];
    }

    const segments: number[][] = [];
    let segment: number[] = [];
    const finishSegment = () => {
      if (segment.length === 2) segment = [...segment, ...segment];
      if (segment.length >= 4) segments.push(segment);
      segment = [];
    };

    points.forEach(([x, y], index) => {
      const anchorPoint = anchors?.[index];
      if (anchorPoint && surfaceRect) {
        let rect = rects.get(anchorPoint.key);
        if (!rect) {
          const element = anchorElements.get(anchorPoint.key);
          if (element) {
            rect = element.getBoundingClientRect();
            rects.set(anchorPoint.key, rect);
          }
        }
        if (rect && rect.width > 0 && rect.height > 0) {
          const element = anchorElements.get(anchorPoint.key);
          const contentWidth = Math.max(rect.width, element?.scrollWidth ?? 0);
          const contentHeight = Math.max(rect.height, element?.scrollHeight ?? 0);
          segment.push(...projectAnchoredPoint(
            [anchorPoint.x, anchorPoint.y],
            { left: rect.left, top: rect.top, width: contentWidth, height: contentHeight },
            surfaceRect,
            { left: element?.scrollLeft ?? 0, top: element?.scrollTop ?? 0 },
            anchorPoint.width && anchorPoint.height
              ? { width: anchorPoint.width, height: anchorPoint.height }
              : undefined,
          ));
          return;
        }
        // An anchored section may be collapsed or a pop-up may be closed.
        // Do not leak its mark into unrelated page coordinates.
        finishSegment();
        return;
      }
      segment.push(x * width, y * sourceHeight);
    });
    finishSegment();
    return segments;
  }
</script>

<div
  bind:this={canvasEl}
  class="annotation-canvas"
  class:annotation-canvas--interactive={capturesPointer}
  aria-hidden="true"
>
  <Stage
    bind:this={stage}
    {width}
    {height}
    onpointerdown={handlePointerDown}
    onpointermove={handlePointerMove}
    onpointerup={finishStroke}
    onpointercancel={finishStroke}
    onpointerleave={finishStroke}
  >
    <Layer>
      {#each strokes as stroke (stroke.id)}
        {@const segments = denormalizeSegments(stroke.points, stroke.surfaceHeight, stroke.anchor, stroke.anchors)}
        {#each segments as segment, segmentIndex (`${stroke.id}:${segmentIndex}`)}
          <Line
            points={segment}
            stroke={stroke.color}
            strokeWidth={stroke.width}
            lineCap="round"
            lineJoin="round"
            tension={0.35}
            hitStrokeWidth={Math.max(14, stroke.width + 8)}
            listening={!!context?.editable && context.active && context.tool === 'eraser'}
            onpointerdown={() => context?.removeStroke(surfaceKey, stroke.id)}
          />
        {/each}
      {/each}
      {#if livePoints.length}
        {#each denormalizeSegments(livePoints, height) as segment}
          <Line
            points={segment}
            stroke={context?.color ?? '#dc2626'}
            strokeWidth={context?.strokeWidth ?? 4}
            lineCap="round"
            lineJoin="round"
            tension={0.35}
            listening={false}
          />
        {/each}
      {/if}
    </Layer>
  </Stage>
</div>

<style>
  .annotation-canvas {
    position: absolute;
    inset: 0;
    z-index: var(--z-annotation-canvas, var(--z-annotation-page, 35));
    overflow: hidden;
    pointer-events: none;
  }

  .annotation-canvas--interactive {
    pointer-events: auto;
    touch-action: none;
    user-select: none;
    cursor: crosshair;
  }
</style>
