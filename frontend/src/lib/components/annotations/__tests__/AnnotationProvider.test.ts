import { cleanup, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Harness from "./AnnotationProviderReadonlyHarness.test.svelte";

const apiMocks = vi.hoisted(() => ({
  getDiscoveryAnnotations: vi.fn(),
  saveDiscoveryAnnotations: vi.fn(),
  fetchSharedDiscoveryAnnotations: vi.fn(),
}));

vi.mock("$lib/api", () => apiMocks);
vi.mock("../KonvaAnnotationCanvas.svelte", async () => {
  const { default: Stub } = await import("./KonvaCanvasStub.test.svelte");
  return { default: Stub };
});

class ImmediateResizeObserver {
  constructor(private cb: ResizeObserverCallback) {}
  observe() {
    this.cb(
      [{ contentRect: { width: 240, height: 120 } } as ResizeObserverEntry],
      this as unknown as ResizeObserver,
    );
  }
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("ResizeObserver", ImmediateResizeObserver);
  apiMocks.getDiscoveryAnnotations.mockResolvedValue({
    revision: 4,
    updatedAt: "2026-08-02T00:00:00.000Z",
    document: {
      version: 1,
      surfaces: {
        "selection:workspace:compare": {
          strokes: [{
            id: "stroke-1",
            color: "#dc2626",
            width: 4,
            points: [[0, 0], [10, 10]],
            createdAt: 1,
          }],
        },
      },
    },
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AnnotationProvider read-only owner mode", () => {
  it("loads and renders saved strokes without exposing mutation controls", async () => {
    const view = render(Harness);

    await waitFor(() => expect(apiMocks.getDiscoveryAnnotations).toHaveBeenCalledWith("job-1"));
    await waitFor(() => expect(view.getByTestId("konva-stub")).toBeInTheDocument());
    expect(view.getByText("Saved decision content")).toBeInTheDocument();
    expect(view.queryByRole("toolbar", { name: "Page annotation controls" })).not.toBeInTheDocument();
    expect(apiMocks.saveDiscoveryAnnotations).not.toHaveBeenCalled();
  });
});
