import { describe, expect, it } from "vitest";
import { bucketOf, statusMeta } from "$lib/config/jobStatus";

// The dashboard's default view renders every bucket, so a status mapping to
// 'review' is what keeps a paying decision (pick ideas / review a gate) visible.
describe("bucketOf", () => {
  it("maps AWAITING_SELECTION into the review (needs-action) bucket", () => {
    expect(bucketOf({ status: "AWAITING_SELECTION" })).toBe("review");
  });

  it("maps AWAITING_GATE into the review (needs-action) bucket", () => {
    expect(bucketOf({ status: "AWAITING_GATE" })).toBe("review");
  });

  it("is case-insensitive so wire-format drift cannot hide a review job", () => {
    expect(bucketOf({ status: "awaiting_selection" })).toBe("review");
    expect(bucketOf({ status: "awaiting_gate" })).toBe("review");
  });

  it("maps active statuses to progress", () => {
    for (const status of ["PENDING", "QUEUED", "RUNNING", "RUNNING_PHASE2", "REGENERATING"]) {
      expect(bucketOf({ status })).toBe("progress");
    }
  });

  it("maps COMPLETED to done", () => {
    expect(bucketOf({ status: "COMPLETED" })).toBe("done");
  });

  it("splits hard fails from quality-gate fails", () => {
    expect(bucketOf({ status: "FAILED", stopReason: null })).toBe("failed");
    expect(bucketOf({ status: "FAILED", stopReason: "INSUFFICIENT_DATA" })).toBe("archived");
  });

  it("maps CANCELLED to archived", () => {
    expect(bucketOf({ status: "CANCELLED" })).toBe("archived");
  });
});

describe("statusMeta", () => {
  it("gives the review statuses positive, actionable labels", () => {
    expect(statusMeta("AWAITING_SELECTION").label).toBe("Ideas ready");
    expect(statusMeta("AWAITING_GATE").label).toBe("Checkpoint reached");
  });
});
