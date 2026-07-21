import { cleanup, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AnnotationStroke } from "$lib/types/discoveryAnnotations";
import Harness from "./AnnotationSurfaceHarness.test.svelte";

// Swap the heavy Konva canvas for a trivial stub so this test never loads the
// real Konva runtime — the whole point of the deferral is to avoid that import
// until a surface is actually used.
vi.mock("../KonvaAnnotationCanvas.svelte", async () => {
  const { default: Stub } = await import("./KonvaCanvasStub.test.svelte");
  return { default: Stub };
});

// The surface only mounts the canvas once it has a measured size; jsdom never
// fires layout, so feed a fixed size synchronously on observe().
class ImmediateResizeObserver {
  private cb: ResizeObserverCallback;
  constructor(cb: ResizeObserverCallback) {
    this.cb = cb;
  }
  observe(target: Element) {
    this.cb(
      [{ contentRect: { width: 240, height: 120 } } as ResizeObserverEntry],
      this as unknown as ResizeObserver,
    );
  }
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ImmediateResizeObserver);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const stroke: AnnotationStroke = {
  id: "s-1",
  color: "#dc2626",
  width: 4,
  points: [
    [0, 0],
    [10, 10],
  ],
  createdAt: 1,
};

describe("AnnotationSurface Konva deferral", () => {
  it("does not load the canvas while the surface is idle (inactive, no strokes)", async () => {
    const view = render(Harness, { props: { active: false, strokes: [] } });

    // Give any pending microtask-scheduled dynamic import a chance to resolve.
    await Promise.resolve();
    await Promise.resolve();

    expect(view.queryByTestId("konva-stub")).toBeNull();
  });

  it("loads the canvas once the surface becomes active", async () => {
    const view = render(Harness, { props: { active: false, strokes: [] } });
    expect(view.queryByTestId("konva-stub")).toBeNull();

    await view.rerender({ active: true, strokes: [] });

    await waitFor(() => expect(view.getByTestId("konva-stub")).toBeInTheDocument());
  });

  it("loads the canvas when the surface already carries strokes", async () => {
    const view = render(Harness, { props: { active: false, strokes: [stroke] } });

    await waitFor(() => expect(view.getByTestId("konva-stub")).toBeInTheDocument());
  });
});
