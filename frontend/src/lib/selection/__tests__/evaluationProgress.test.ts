import { describe, expect, it } from "vitest";
import {
  EVALUATION_OVERDUE_MS,
  evaluationProgress,
  formatElapsed,
  phaseNote,
} from "../evaluationProgress.svelte";

const CREATED = "2026-07-27T12:00:00.000Z";
const CREATED_MS = Date.parse(CREATED);

describe("evaluationProgress", () => {
  it("reports queued while no worker has claimed the dispatch", () => {
    // claimedAt === null is the ONLY signal separating "sitting in the Redis queue"
    // from "a worker is scoring it". Both used to render identically as "pending".
    const progress = evaluationProgress(
      { createdAt: CREATED, claimedAt: null },
      CREATED_MS + 42_000,
    );

    expect(progress.phase).toBe("queued");
    expect(progress.elapsedLabel).toBe("0:42");
  });

  it("reports running once a worker has claimed it", () => {
    const progress = evaluationProgress(
      { createdAt: CREATED, claimedAt: "2026-07-27T12:00:30.000Z" },
      CREATED_MS + 75_000,
    );

    expect(progress.phase).toBe("running");
    expect(progress.elapsedLabel).toBe("1:15");
  });

  it("reports overdue past the threshold even while running", () => {
    const progress = evaluationProgress(
      { createdAt: CREATED, claimedAt: "2026-07-27T12:00:30.000Z" },
      CREATED_MS + EVALUATION_OVERDUE_MS + 1000,
    );

    expect(progress.phase).toBe("overdue");
  });

  it("reports overdue for a request still stuck in the queue", () => {
    const progress = evaluationProgress(
      { createdAt: CREATED, claimedAt: null },
      CREATED_MS + EVALUATION_OVERDUE_MS,
    );

    expect(progress.phase).toBe("overdue");
  });

  it("falls back to queued with a zero timer when the operation is absent", () => {
    // /chat/history returns activeOperation: null between the POST and the next
    // reload; the wait must render rather than crash or show a negative timer.
    const progress = evaluationProgress(null, CREATED_MS);

    expect(progress.phase).toBe("queued");
    expect(progress.elapsedMs).toBe(0);
    expect(progress.elapsedLabel).toBe("0:00");
  });

  it("never reports a negative elapsed time when clocks disagree", () => {
    const progress = evaluationProgress({ createdAt: CREATED }, CREATED_MS - 30_000);

    expect(progress.elapsedMs).toBe(0);
  });

  it("ignores an unparseable timestamp instead of producing NaN", () => {
    const progress = evaluationProgress({ createdAt: "not-a-date" }, CREATED_MS);

    expect(progress.elapsedLabel).toBe("0:00");
  });
});

describe("formatElapsed", () => {
  it.each([
    [0, "0:00"],
    [9_000, "0:09"],
    [61_000, "1:01"],
    [599_000, "9:59"],
    [3_600_000, "1:00:00"],
    [3_661_000, "1:01:01"],
  ])("formats %ims as %s", (ms, expected) => {
    expect(formatElapsed(ms)).toBe(expected);
  });
});

describe("phaseNote", () => {
  it("never asserts a duration, since the overdue threshold is not yet calibrated", () => {
    for (const phase of ["queued", "running", "overdue"] as const) {
      expect(phaseNote(phase)).not.toMatch(/\d/);
    }
  });

  it("tells an overdue waiter the operation still settles or refunds on its own", () => {
    expect(phaseNote("overdue")).toMatch(/finish or refund/);
    expect(phaseNote("overdue")).toMatch(/leave this page/);
  });
});
