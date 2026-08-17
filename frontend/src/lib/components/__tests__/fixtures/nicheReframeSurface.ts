/**
 * Shared assertions for the Stage-1 reframe disclosure, plus the two captured runs it is
 * driven with.
 *
 * Round 1 shipped this disclosure with a component test that HAND-BUILT
 * `report = { niche, niche_context }` and passed it to `UnifiedHero`. The one page that
 * mounts that hero passes a synthesized object with no `niche_context` on it, so the gate
 * read `undefined` on every production render while the test stayed green — the
 * producer/consumer mismatch `docs/PRODUCER_CONSUMER_MISMATCHES.md` catalogues.
 *
 * So the surface tests that import this helper feed the artifact to the REAL consumer
 * (the page, the report, the shared view) and assert on rendered DOM. `expectDiscloses`
 * additionally refuses a disclosure that renders inside an `aria-hidden`/`inert` subtree:
 * the round-1 mount sat inside `<div aria-hidden="true" inert>` behind a blur, and text
 * nobody can read is not a disclosure.
 */
import { expect } from "vitest";
import type { NicheContext } from "$lib/types/report";
import reframedCapture from "./nicheReframe.reframed.captured.json";
import onNicheCapture from "./nicheReframe.onNiche.captured.json";

export type CapturedRun = {
  niche: string;
  generated_at?: string;
  executive_summary?: string;
  selected_solution_name?: string;
  selection_rationale?: string;
  niche_context: NicheContext;
};

/** Stage 1 classified this run's input as `segment_of_niche` and researched the parent
 *  market instead. Everything below is read off the capture, never re-typed. */
export const REFRAMED_RUN = reframedCapture as unknown as CapturedRun;
/** Stage 1 classified this run's input as `niche`: nothing was substituted. */
export const ON_NICHE_RUN = onNicheCapture as unknown as CapturedRun;

/** The words the user submitted — the subject line of a possibly multi-line pitch. */
export function submittedInput(run: CapturedRun): string {
  const first = run.niche_context.niche_input.split("\n")[0].trim();
  // Not `?? ""`: an empty needle makes `toContain` vacuously true.
  if (!first) throw new Error("capture has no submitted input to disclose");
  return first;
}

/**
 * The property under test on every surface: a reframed run tells the reader, in text they
 * can actually reach, which words it started from. Asserted on the submitted string read
 * out of the capture, so the wording around it stays free to change.
 */
export function expectDiscloses(container: HTMLElement, run: CapturedRun): HTMLElement {
  // Guard the input, not the conclusion: a capture that stopped being a reframed run
  // would make this pass for the wrong reason.
  expect(run.niche_context.audience_scope).not.toBe("niche");

  const disclosure = container.querySelector<HTMLElement>(".niche-reframe");
  expect(disclosure, "reframed run rendered no disclosure on this surface").not.toBeNull();
  expect(disclosure!.textContent).toContain(submittedInput(run));
  expect(
    disclosure!.closest('[aria-hidden="true"], [inert]'),
    "disclosure rendered inside an aria-hidden/inert subtree — unreadable, so it does not count",
  ).toBeNull();
  return disclosure!;
}

/** Nothing was substituted, so the surface must say nothing. */
export function expectSilent(container: HTMLElement): void {
  expect(container.querySelector(".niche-reframe")).toBeNull();
}
