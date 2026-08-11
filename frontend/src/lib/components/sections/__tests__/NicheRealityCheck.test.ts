/**
 * NicheRealityCheck is the single choke point for niche-verdict prose.
 *
 * Three surfaces render it — the job page Overview, the public share link
 * (SharedDiscoveryView) and SelectionWorkbench — and only SelectionWorkbench used to
 * rewrite the pipeline vocabulary before handing the verdict over. So `corpus`,
 * `web-verified` and `paid wedge` shipped to paying users through the other two. These
 * tests pass the component RAW pipeline data, exactly as those two callers do, and assert
 * nothing internal survives to the DOM. A future caller that forgets to sanitise is safe
 * by construction.
 */

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import NicheRealityCheck from "../NicheRealityCheck.svelte";
import type { NicheDifficultyVerdict } from "$lib/types/report";
import { buyerFacingNicheDifficultyVerdict } from "$lib/selection/buyerFacingResearchProse";
import exemplar from "$lib/selection/__tests__/fixtures/nicheDifficultyVerdict.exemplar.json";

afterEach(cleanup);

const RAW = exemplar.niche_difficulty_verdict as NicheDifficultyVerdict;

/**
 * `cold[- ]start` and not `cold-start`: niche_difficulty.py:920 emits the SPACED form
 * inside "that's frictions (cold start, crowded tooling)", which the hyphen-only pattern
 * never caught.
 */
const PIPELINE_VOCABULARY =
  /\bcorpus\b|cold[- ]start|web-verified|paid wedge|Thin early signal|seed it|scrape it|\bwedge\b/i;

describe("NicheRealityCheck sanitises what it renders", () => {
  it("rewrites raw pipeline prose handed straight from a caller", async () => {
    const view = render(NicheRealityCheck, { props: { verdict: RAW, context: "discovery" } });

    expect(
      await view.findByText(
        "Most ideas need a body of data that does not exist yet. Plan how to collect, "
          + "create, or obtain access to it before the product is useful.",
      ),
    ).toBeInTheDocument();
    expect(
      view.getByText(
        "Buyers here are small-business operators. They are price-aware but used to "
          + "paying for tools that save time or win customers.",
      ),
    ).toBeInTheDocument();
    expect(view.getByText(/The collected evidence drifts from the stated audience/))
      .toHaveTextContent("Tighten the entry point");
    expect(view.getByText(/10 tools checked on the web/))
      .toHaveTextContent("Early evidence is limited. Deep Research can validate it.");
    expect(view.getByText(/gap in the collected evidence/))
      .toHaveTextContent("published prices checked on the web");
  });

  it("leaves no pipeline vocabulary and no em/en dash anywhere in the DOM", () => {
    const view = render(NicheRealityCheck, { props: { verdict: RAW, context: "discovery" } });

    const text = view.container.textContent ?? "";
    expect(text).not.toMatch(PIPELINE_VOCABULARY);
    expect(text).not.toMatch(/[–—]/);
  });

  it("still drops the Software Fit prefix from the headline", () => {
    const view = render(NicheRealityCheck, { props: { verdict: RAW, context: "discovery" } });

    const heading = view.getByRole("heading", { level: 3 });
    expect(heading).toHaveTextContent("automating inventory and controlled substance compliance");
    expect(heading.textContent).not.toMatch(/Software Fit/i);
  });

  it("renders identically whether the caller pre-sanitised or not", () => {
    const raw = render(NicheRealityCheck, { props: { verdict: RAW, context: "report" } });
    const rawText = raw.container.textContent;
    cleanup();

    const pre = render(NicheRealityCheck, {
      props: { verdict: buyerFacingNicheDifficultyVerdict(RAW)!, context: "report" },
    });
    expect(pre.container.textContent).toBe(rawText);
  });
});
