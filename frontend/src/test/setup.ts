import '@testing-library/jest-dom/vitest';

// Mock IntersectionObserver (not available in jsdom)
class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | null = null;
  readonly rootMargin: string = '';
  readonly thresholds: ReadonlyArray<number> = [];

  constructor(
    private callback: IntersectionObserverCallback,
    options?: IntersectionObserverInit
  ) {}

  observe(target: Element): void {
    // Immediately trigger as if element is visible
    this.callback(
      [
        {
          target,
          isIntersecting: true,
          intersectionRatio: 1,
          boundingClientRect: target.getBoundingClientRect(),
          intersectionRect: target.getBoundingClientRect(),
          rootBounds: null,
          time: Date.now(),
        },
      ],
      this
    );
  }

  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

global.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver;

/**
 * jsdom implements no ResizeObserver. Svelte 5 compiles `bind:clientWidth/clientHeight`
 * into one *unguarded*, so any component using those bindings throws on mount and every
 * test rendering it fails — which is exactly what happened when DecisionRail started
 * measuring its own height (3 failures -> 47).
 *
 * Product code that constructs a ResizeObserver directly still guards with
 * `typeof ResizeObserver === 'undefined'` (see AnnotationSurface, KonvaAnnotationCanvas);
 * this stub exists for the compiler-generated case, which cannot be guarded.
 *
 * Sizes are always 0 under jsdom, so this makes bindings inert rather than accurate —
 * enough to let components mount. Assert on layout in a real browser, not here.
 */
class MockResizeObserver {
  constructor(private callback: ResizeObserverCallback) {}

  observe(target: Element): void {
    this.callback(
      [
        {
          target,
          contentRect: target.getBoundingClientRect(),
          borderBoxSize: [{ blockSize: 0, inlineSize: 0 }],
          contentBoxSize: [{ blockSize: 0, inlineSize: 0 }],
          devicePixelContentBoxSize: [{ blockSize: 0, inlineSize: 0 }],
        } as unknown as ResizeObserverEntry,
      ],
      this as unknown as ResizeObserver
    );
  }

  unobserve(): void {}
  disconnect(): void {}
}

global.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
