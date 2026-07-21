import type {
  AnnotationAnchor,
  AnnotationAnchorPoint,
  AnnotationPoint,
} from '$lib/types/discoveryAnnotations';

interface CapturedAnnotationAnchor extends AnnotationAnchorPoint {
  width: number;
  height: number;
}

export interface ResolvedStrokeGeometry {
  points: AnnotationPoint[];
  anchor?: AnnotationAnchor;
  anchors?: Array<CapturedAnnotationAnchor | null>;
}

export function outermostAnnotationAnchor(
  element: Element,
  surface: HTMLElement,
): HTMLElement | null {
  return annotationAnchorChain(element, surface)[0] ?? null;
}

/** Returns semantic anchors from the most specific region to the surface root. */
export function annotationAnchorChain(
  element: Element,
  surface: HTMLElement,
): HTMLElement[] {
  // Ignore the annotation canvas itself so elementsFromPoint can reach the
  // semantic content underneath it.
  if (element.closest('.annotation-canvas')) return [];

  const anchors: HTMLElement[] = [];
  let anchor = element.closest<HTMLElement>('[data-annotation-anchor]');
  while (anchor && surface.contains(anchor)) {
    anchors.push(anchor);
    if (anchor === surface) break;
    anchor = anchor.parentElement?.closest<HTMLElement>('[data-annotation-anchor]') ?? null;
  }
  return anchors;
}

interface ClientPoint {
  x: number;
  y: number;
}

function distanceFromRect(point: ClientPoint, rect: DOMRect): number {
  const dx = Math.max(rect.left - point.x, 0, point.x - rect.right);
  const dy = Math.max(rect.top - point.y, 0, point.y - rect.bottom);
  return Math.hypot(dx, dy);
}

/**
 * Finds the most specific semantic region at, or just beside, a pointer.
 *
 * People naturally draw circles and arrows slightly outside the element they
 * are marking. Treating those pixels as page-level coordinates makes the mark
 * drift when the sidebar collapses or the shared report uses different chrome.
 * A small halo keeps that whitespace attached to the nearby content region.
 */
export function annotationAnchorChainAtPoint(
  surface: HTMLElement,
  clientPoint: ClientPoint,
  halo = 40,
): HTMLElement[] {
  const elements = [
    ...(surface.matches('[data-annotation-anchor]') ? [surface] : []),
    ...Array.from(surface.querySelectorAll<HTMLElement>('[data-annotation-anchor]')),
  ];

  const candidates = elements.flatMap((element) => {
    const rect = element.getBoundingClientRect();
    if (!element.dataset.annotationAnchor || rect.width <= 0 || rect.height <= 0) return [];
    const distance = distanceFromRect(clientPoint, rect);
    if (distance > halo) return [];
    return [{ element, distance, area: rect.width * rect.height }];
  });

  // Semantic anchors are deliberately sparse. Prefer the tightest eligible
  // region so a title's annotation halo wins over a containing page or panel.
  candidates.sort((a, b) => a.area - b.area || a.distance - b.distance);
  const nearest = candidates[0]?.element;
  return nearest ? annotationAnchorChain(nearest, surface) : [];
}

/** Picks the deepest semantic region shared by every point in a gesture. */
export function deepestCommonAnnotationAnchorKey(
  chains: ReadonlyArray<ReadonlyArray<string>>,
): string | null {
  if (!chains.length) return null;
  return chains[0].find((key) => chains.every((chain) => chain.includes(key))) ?? null;
}

/**
 * Stores a gesture in the deepest semantic region shared by every sampled point.
 * A single coordinate frame keeps the stroke coherent while still letting the
 * whole gesture follow a header, candidate list, or overlay after reflow.
 */
export function resolveStrokeGeometry(
  surfacePoints: AnnotationPoint[],
  anchorChains: ReadonlyArray<ReadonlyArray<CapturedAnnotationAnchor>>,
): ResolvedStrokeGeometry {
  const commonKey = deepestCommonAnnotationAnchorKey(
    anchorChains.map((chain) => chain.map((anchor) => anchor.key)),
  );
  const commonAnchors = commonKey
    ? anchorChains.map((chain) => chain.find((anchor) => anchor.key === commonKey) ?? null)
    : [];
  const everyPointAnchored = commonAnchors.length === surfacePoints.length
    && commonAnchors.every(Boolean);

  if (commonKey && everyPointAnchored) {
    const first = commonAnchors[0]!;
    return {
      points: commonAnchors.map((anchor) => [anchor!.x, anchor!.y]),
      anchor: { key: first.key, width: first.width, height: first.height },
    };
  }

  const nearest = anchorChains.map((chain) => chain[0] ?? null);
  if (nearest.some(Boolean)) {
    return {
      points: surfacePoints,
      anchors: nearest.map((anchor) => anchor ? { ...anchor } : null),
    };
  }

  return { points: surfacePoints };
}

interface RectOrigin {
  left: number;
  top: number;
}

interface RectSize extends RectOrigin {
  width: number;
  height: number;
}

/**
 * Replays a point at the same relative position inside a semantic region.
 * The axes scale independently because responsive layouts can change an
 * anchor's aspect ratio when navigation collapses or text wraps.
 */
export function projectAnchoredPoint(
  point: readonly [number, number],
  anchorRect: RectSize,
  surfaceRect: RectOrigin,
  scroll = { left: 0, top: 0 },
  _sourceSize?: Pick<RectSize, 'width' | 'height'>,
): [number, number] {
  // A stroke belongs to the semantic region, not to its original pixel box.
  // Reproject each axis against the rendered destination so the drawing follows
  // text wrapping, collapsed navigation, shared-view chrome, and modal reflow.
  return [
    anchorRect.left - surfaceRect.left - scroll.left + point[0] * anchorRect.width,
    anchorRect.top - surfaceRect.top - scroll.top + point[1] * anchorRect.height,
  ];
}
