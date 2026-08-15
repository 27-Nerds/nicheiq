/**
 * The share page's `<meta name="description">` is the one sentence a link preview shows
 * before anyone opens the page. On a "Check my idea" run it read "Review the shared idea
 * check for: …" whenever an `idea_validation` block existed — and that block is emitted on
 * a REFUSED run too, so a run that never graded the idea advertised a check to everyone the
 * link reached.
 *
 * The fix branches on the outcome. Nothing pinned it, so this does: head metadata is
 * invisible to every on-page assertion in the suite, which is exactly why it drifted.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import PageComponent from "../+page.svelte";
import type { DiscoveryShareData } from "$lib/api";
import type { IdeaValidation } from "$lib/types/report";
import {
  gradedBlock,
  notEvaluatedBlock,
} from "$lib/components/__tests__/fixtures/ideaValidationBlocks";

/**
 * GENERATED, not hand-written (2026-08-15). This file used to build ONE block —
 * `{ idea_name: "Vet Invoice Reconciler", parts: [], anchored_pains: [], competitors: [],
 * kill_risks: [] }` — and flip only `outcome` between the two cases. Two things were wrong
 * with it, and the second was load-bearing:
 *
 * 1. As a GRADED block it is a shape the pipeline cannot emit: a graded block carries three
 *    parts, twelve competitors and two kill risks. Trap 1 on four more fields.
 * 2. As a REFUSED block it carried `idea_name: "Vet Invoice Reconciler"` — and every refusal
 *    emits `idea_name: null`. So the refused-share assertion was pinning a `<meta>`
 *    description built from an idea name that a real refusal never has, on the one surface
 *    (head metadata) no on-page assertion can see.
 */
const GRADED = gradedBlock();
const REFUSED = notEvaluatedBlock();

function shareData(idea_validation: IdeaValidation | null): DiscoveryShareData {
  return {
    shareType: "discovery",
    niche: "vet clinics",
    solutions: [],
    discoveryData: null,
    previewReport: idea_validation
      ? ({ idea_validation } as unknown as DiscoveryShareData["previewReport"])
      : null,
    voteSummary: { totalVotes: 0, solutionVotes: {} },
  };
}

const description = () =>
  document.head.querySelector('meta[name="description"]')?.getAttribute("content") ?? "";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
});

afterEach(() => {
  cleanup();
  document.head.querySelectorAll('meta[name="description"]').forEach((n) => n.remove());
  vi.unstubAllGlobals();
});

describe("shared discovery — link preview description", () => {
  it("does not advertise a check on a run that refused to grade the idea", () => {
    render(PageComponent, {
      props: {
        data: { discovery: shareData(REFUSED), shareToken: "tok", allowIndexing: false },
      } as never,
    });
    // A real refusal has NO `idea_name`, so the title falls back to the run's niche — which
    // on a `validate_idea` run is the user's own pitch. Asserted as the fallback rather than
    // as a name, because pinning a name here is what made the old fixture impossible.
    expect(REFUSED.idea_name).toBeNull();
    expect(description()).toBe(
      'A shared idea check for "vet clinics" that could not be completed, with the '
      + "approaches the run did generate.");
    expect(description()).not.toContain("Review the shared idea check for");
  });

  it("still advertises a graded check", () => {
    render(PageComponent, {
      props: {
        data: { discovery: shareData(GRADED), shareToken: "tok", allowIndexing: false },
      } as never,
    });
    expect(description()).toBe(`Review the shared idea check for: ${GRADED.idea_name}`);
  });

  it("leaves a plain discovery share on the voting sentence", () => {
    render(PageComponent, {
      props: {
        data: { discovery: shareData(null), shareToken: "tok", allowIndexing: false },
      } as never,
    });
    expect(description()).toBe("Vote on solution ideas for: vet clinics");
  });
});
