import { describe, expect, it } from "vitest";
import { load } from "./+page";

describe("legacy alternatives route", () => {
  it("redirects exact candidate revisions to the contextual direction form", () => {
    try {
      load({
        params: { jobId: "job 1" },
        url: new URL(
          "https://nicheiq.test/jobs/job%201/selection/alternatives?idea=idea-a%3A3&mode=reshape",
        ),
      } as never);
      throw new Error("Expected the compatibility route to redirect.");
    } catch (error) {
      expect(error).toMatchObject({
        status: 307,
        location:
          "/jobs/job%201/selection/compare?idea=idea-a%3A3&mode=reshape&tool=variants",
      });
    }
  });
});
