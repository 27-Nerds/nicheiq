import { beforeEach, describe, expect, it, vi } from "vitest";
import { chapterIsSettled } from "$lib/types/tutorial";

describe("chapterIsSettled", () => {
  it("is false when nothing is recorded", () => {
    expect(chapterIsSettled(null, "compare")).toBe(false);
    expect(chapterIsSettled({ version: 1, chapters: {} }, "compare")).toBe(false);
  });

  it("treats completed and dismissed as settled, in_progress as not", () => {
    const at = "2026-07-25T00:00:00.000Z";
    expect(chapterIsSettled({ version: 1, chapters: { c: { status: "completed", at } } }, "c")).toBe(true);
    expect(chapterIsSettled({ version: 1, chapters: { c: { status: "dismissed", at } } }, "c")).toBe(true);
    // A chapter abandoned mid-run may offer itself again.
    expect(chapterIsSettled({ version: 1, chapters: { c: { status: "in_progress", at } } }, "c")).toBe(false);
  });

  it("does not confuse one chapter for another", () => {
    const progress = {
      version: 1,
      chapters: { compare: { status: "completed" as const, at: "x" } },
    };
    expect(chapterIsSettled(progress, "compare")).toBe(true);
    expect(chapterIsSettled(progress, "risks")).toBe(false);
  });
});

describe("tourProgress store", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  async function loadStore() {
    return (await import("../tourProgress.svelte")).tourProgress;
  }

  it("offers nothing before a successful load — an unknown user must not be re-taught", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const store = await loadStore();
    expect(store.loaded).toBe(false);
    expect(store.offersChapter("compare")).toBe(false);
  });

  it("offers an unseen chapter once loaded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 1, chapters: {} }),
    }));
    const store = await loadStore();
    await store.load();
    expect(store.offersChapter("compare")).toBe(true);
  });

  it("does not re-offer a chapter the user already declined", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        version: 1,
        chapters: { compare: { status: "dismissed", at: "x" } },
      }),
    }));
    const store = await loadStore();
    await store.load();
    expect(store.offersChapter("compare")).toBe(false);
    expect(store.offersChapter("risks")).toBe(true);
  });

  it("fails closed when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const store = await loadStore();
    await store.load();
    expect(store.loaded).toBe(true);
    // Loaded but with no data: showing a tutorial we can't confirm is unseen is worse
    // than showing none.
    expect(store.offersChapter("compare")).toBe(false);
  });

  it("fails closed on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    const store = await loadStore();
    await store.load();
    expect(store.offersChapter("compare")).toBe(false);
  });

  it("shares one request between concurrent callers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 1, chapters: {} }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const store = await loadStore();
    await Promise.all([store.load(), store.load(), store.load()]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("stops offering a chapter the moment it is recorded, before the write lands", async () => {
    let resolvePatch: (v: unknown) => void = () => {};
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") return new Promise((r) => { resolvePatch = r; });
      return Promise.resolve({ ok: true, json: async () => ({ version: 1, chapters: {} }) });
    });
    vi.stubGlobal("fetch", fetchMock);
    const store = await loadStore();
    await store.load();
    expect(store.offersChapter("compare")).toBe(true);

    const pending = store.record("compare", "dismissed");
    // Optimistic: the invitation must not flash back while the PATCH is in flight.
    expect(store.offersChapter("compare")).toBe(false);
    resolvePatch({ ok: true, json: async () => ({}) });
    await pending;
    expect(store.offersChapter("compare")).toBe(false);
  });

  it("keeps the optimistic state when the write fails", async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") return Promise.reject(new Error("offline"));
      return Promise.resolve({ ok: true, json: async () => ({ version: 1, chapters: {} }) });
    });
    vi.stubGlobal("fetch", fetchMock);
    const store = await loadStore();
    await store.load();
    await store.record("risks", "completed");
    expect(store.offersChapter("risks")).toBe(false);
  });

  it("sends the chapter, status and step the backend schema expects", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 1, chapters: {} }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const store = await loadStore();
    await store.load();
    await store.record("job-shortlist", "in_progress", 2);

    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toBe("/api/tutorial-progress");
    expect(JSON.parse(patch?.[1].body)).toEqual({
      chapter: "job-shortlist",
      status: "in_progress",
      step: 2,
    });
  });
});
