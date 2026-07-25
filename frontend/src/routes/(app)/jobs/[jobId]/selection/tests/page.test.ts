import { describe, expect, it } from "vitest";
import { load } from "./+page";

describe("legacy test-planning route", () => {
  it("redirects into the evidence workspace and preserves exact URL state", () => {
    try {
      load({
        params: { jobId: "job 1" },
        url: new URL(
          "https://nicheiq.test/jobs/job%201/selection/tests?idea=idea-a%3A3&assumptionId=assumption-1",
        ),
      } as never);
      throw new Error("Expected the compatibility route to redirect.");
    } catch (error) {
      expect(error).toMatchObject({
        status: 307,
        location:
          "/jobs/job%201/selection/risks?idea=idea-a%3A3&assumptionId=assumption-1&tool=tests",
      });
    }
  });
});
