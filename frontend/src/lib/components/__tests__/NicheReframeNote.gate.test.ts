/**
 * The gate itself: WHEN the Stage-1 reframe disclosure speaks.
 *
 * These four cases are round 1's, moved off `UnifiedHero` — the hero's only production
 * mount is an `aria-hidden`/`inert` blurred teaser, so the disclosure now lives in
 * `NicheReframeNote` and is mounted on the surfaces a reader actually reads. The gate's
 * logic is unchanged: Stage 1's own recorded `audience_scope`, silent on `niche` and on
 * an absent scope, never a similarity heuristic (token overlap between input and derived
 * description does not separate the two cases — the reframed London run below scores 0.67,
 * inside the on-niche band).
 *
 * WHERE it renders is not this file's job: `nicheReframeSurfaces.test.ts`,
 * `nicheReframeDisclosure.test.ts` and `nicheReframeMounts.test.ts` cover that, because a
 * component test that supplies a prop no caller passes is exactly what shipped round 1.
 */
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import NicheReframeNote from "../NicheReframeNote.svelte";
import {
  ON_NICHE_RUN,
  REFRAMED_RUN,
  expectDiscloses,
  expectSilent,
  submittedInput,
} from "./fixtures/nicheReframeSurface";

afterEach(cleanup);

describe("Stage-1 reframe disclosure gate", () => {
  it("discloses the submitted input when Stage 1 researched a wider market", () => {
    const view = render(NicheReframeNote, { props: { context: REFRAMED_RUN.niche_context } });

    expectDiscloses(view.container, REFRAMED_RUN);
  });

  it("stays silent when Stage 1 researched the niche the user named", () => {
    expect(ON_NICHE_RUN.niche_context.audience_scope).toBe("niche");

    const view = render(NicheReframeNote, { props: { context: ON_NICHE_RUN.niche_context } });

    expectSilent(view.container);
  });

  it("stays silent on a run that predates the audience-scope classifier", () => {
    const view = render(NicheReframeNote, {
      props: { context: { ...REFRAMED_RUN.niche_context, audience_scope: null } },
    });

    expectSilent(view.container);
  });

  it("shows the subject line of a multi-line idea-check submission", () => {
    const firstLine = submittedInput(REFRAMED_RUN);
    const view = render(NicheReframeNote, {
      props: {
        context: {
          ...REFRAMED_RUN.niche_context,
          niche_input: [
            firstLine,
            "Find out what AI assistants know about your business.",
            "How it works: a simple web app.",
          ].join("\n"),
        },
      },
    });

    const disclosure = view.container.querySelector(".niche-reframe");
    expect(disclosure?.textContent).toContain(firstLine);
    expect(disclosure?.textContent).not.toContain("How it works");
  });

  it("does not assert that findings actually landed outside the submitted focus", () => {
    // The run records that the SCOPE was widened. It does not record that any particular
    // finding fell outside the submitted focus, so the sentence may only say "may".
    const view = render(NicheReframeNote, { props: { context: REFRAMED_RUN.niche_context } });

    const text = view.container.querySelector(".niche-reframe")!.textContent!;
    expect(text).toContain("may sit outside");
    expect(text).not.toMatch(/findings sit\s+outside/);
  });
});
