import { describe, expect, it } from "vitest";
import {
  stateAfterToolQueryStrip,
  TOOL_QUERY_KEYS,
  strippedToolSignature,
  toolQuerySignature,
} from "../toolQuery";

const BASE = "https://app.test/jobs/j1/selection/compare";

describe("selection tool-query guard helpers (P0-E)", () => {
  it("signature is pathname plus search", () => {
    const url = new URL(`${BASE}?tool=tests&lens=demand`);
    expect(toolQuerySignature(url)).toBe("/jobs/j1/selection/compare?tool=tests&lens=demand");
  });

  it("strips exactly the one-shot keys and keeps workspace state", () => {
    const url = new URL(`${BASE}?tool=assumptions&assumptionId=a1&lens=demand&ideaId=idea-1`);
    expect(TOOL_QUERY_KEYS).toEqual(["tool", "assumptionId"]);
    expect(strippedToolSignature(url)).toBe(
      "/jobs/j1/selection/compare?lens=demand&ideaId=idea-1",
    );
  });

  it("is a no-op signature for URLs without one-shot params", () => {
    const url = new URL(`${BASE}?lens=demand`);
    expect(strippedToolSignature(url)).toBe(toolQuerySignature(url));
  });

  it("re-arms the guard: the post-strip signature never matches the with-tool URL", () => {
    // The layout effect stores the handled signature; after the strip it must
    // store this value instead, so a REPEAT navigation to the identical
    // ?tool= deep link reads as new and reopens the tool.
    const deepLink = new URL(`${BASE}?tool=variants&mode=explore_direction`);
    const handledAfterStrip = strippedToolSignature(deepLink);
    expect(handledAfterStrip).not.toBe(toolQuerySignature(deepLink));

    // …and it does not accidentally collide with a DIFFERENT tool link either.
    const otherLink = new URL(`${BASE}?tool=tests`);
    expect(handledAfterStrip).not.toBe(toolQuerySignature(otherLink));
  });

  it("does not mutate the URL it is given", () => {
    const url = new URL(`${BASE}?tool=tests`);
    strippedToolSignature(url);
    expect(url.searchParams.get("tool")).toBe("tests");
  });

  it("keeps caller provenance until the routed tool closes", () => {
    const origin = {
      tool: "variants" as const,
      jobId: "j1",
      returnHref: "/jobs/j1#ideas",
      historyOwned: true as const,
    };

    expect(stateAfterToolQueryStrip({
      selectionTestDraft: {
        ideaId: "idea-1",
        ideaRevision: 1,
      },
      selectionToolOrigin: origin,
    })).toEqual({
      selectionTestDraft: undefined,
      selectionToolOrigin: origin,
    });
  });
});
