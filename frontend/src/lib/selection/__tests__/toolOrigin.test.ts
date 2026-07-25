import { describe, expect, it } from "vitest";
import {
  createSelectionToolOrigin,
  trustedSelectionToolOrigin,
} from "../toolOrigin";

describe("selection tool origin", () => {
  it("preserves the exact job-page query and hash", () => {
    expect(createSelectionToolOrigin(
      new URL("https://app.example/jobs/job-1?source=shortlist#ideas"),
      "job-1",
    )).toEqual({
      tool: "variants",
      jobId: "job-1",
      returnHref: "/jobs/job-1?source=shortlist#ideas",
      historyOwned: true,
    });
  });

  it("accepts only the exact current job page on the current origin", () => {
    const valid = {
      tool: "variants",
      jobId: "job-1",
      returnHref: "/jobs/job-1?source=shortlist#ideas",
      historyOwned: true,
    };

    expect(trustedSelectionToolOrigin(valid, "https://app.example", "job-1")).toEqual(valid);
    expect(trustedSelectionToolOrigin(
      { ...valid, returnHref: "/jobs/job-2" },
      "https://app.example",
      "job-1",
    )).toBeNull();
    expect(trustedSelectionToolOrigin(
      { ...valid, returnHref: "//evil.example/jobs/job-1" },
      "https://app.example",
      "job-1",
    )).toBeNull();
    expect(trustedSelectionToolOrigin(
      { ...valid, historyOwned: false },
      "https://app.example",
      "job-1",
    )).toBeNull();
  });
});
