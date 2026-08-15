import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import ValidationVerdict from "$lib/components/sections/ValidationVerdict.svelte";
import type { IdeaValidation } from "$lib/types/report";
import { SEED_FAILURE_COPY, notEvaluatedBlock } from "./fixtures/ideaValidationBlocks";

/**
 * The Next card is the SECOND layer that renders a refusal, and it used to hold its own copy:
 * one hardcoded sentence for all six typed causes — "Run it again, or rephrase it in your own
 * words." So a run killed by OUR judge outage rendered the honest backend headline ("that is a
 * fault on our side, not with your idea") in the verdict card and, one card down, told the user
 * to rewrite their idea. A backend test asserting the headline map is exactly the check that
 * missed it.
 *
 * These assert the CONTRACT, not the sentences: the page renders `failure_next_step` verbatim
 * and authors no failure copy of its own. Whether that copy blames the user is asserted once,
 * over the live set of causes, in `tests/unit/crews/test_seed_pipeline.py` — putting the
 * sentences here too would recreate the duplicate-copy defect in a test.
 */

/**
 * TAKEN FROM THE PRODUCER, not transcribed (G-3, round 11). Both constants used to be
 * hand-typed, and both had drifted: the headline ended "…could not run this time." where the
 * real one continues "…so we stopped rather than report a verdict we had not verified — a
 * fault on our side, not with your idea", and the next step was cut off mid-sentence. Neither
 * blamed the user, so the blame-word blacklist that policed this file could not see either —
 * they were simply sentences no cause emits, asserted under a name claiming they came from
 * the backend. `seedFailureCopy.generated.json` is generated from `SEED_FAILURE_COPY` by
 * tests/unit/report/test_not_evaluated_fixture_contract.py.
 */
const NEXT_STEP_FROM_BACKEND = SEED_FAILURE_COPY.identity_judge_unavailable.next_step;
const HEADLINE_FROM_BACKEND = SEED_FAILURE_COPY.identity_judge_unavailable.headline;

/**
 * GENERATED, not hand-written (fixtures/ideaValidationBlocks.ts). The dict that used to sit
 * here carried a one-rung `experiment_ladder` and a single desk limit; the pipeline emits
 * four rungs and three limits on a refusal, so this file's renders never showed the cards
 * that were actually on the refused page. Only the run's narrative is overridden.
 */
const notEvaluated = (overrides: Partial<IdeaValidation> = {}): IdeaValidation =>
  notEvaluatedBlock({
    headline: HEADLINE_FROM_BACKEND,
    failure_next_step: NEXT_STEP_FROM_BACKEND,
    user_idea_text: "A browser extension that drafts context-aware support replies.",
    user_idea_brief: "A browser extension that drafts context-aware support replies.",
    // Derived, not typed — the narrative varies only the pool count.
    alternatives: { ...notEvaluatedBlock().alternatives, count: 0, top: [] },
    ...overrides,
  });

afterEach(cleanup);

describe("ValidationVerdict · not_evaluated Next card", () => {
  it("renders the backend's per-cause next step and prescribes no rewrite of the pitch", () => {
    const view = render(ValidationVerdict, {
      props: { data: notEvaluated(), rerunHref: "/new?mode=validate_idea" },
    });

    const card = view.container.querySelector(".iv-commit");
    expect(card).not.toBeNull();
    expect(card).toHaveTextContent(NEXT_STEP_FROM_BACKEND);
    // The contradiction itself: our-fault verdict up top, "rephrase it" down here.
    expect(card?.textContent ?? "").not.toMatch(/rephrase|reword|rewrite|in your own words/i);
    // The re-run escape hatch stays — refusal is only recoverable if the user can retry.
    expect(view.getByRole("link", { name: /Run the check again/ })).toHaveAttribute(
      "href",
      "/new?mode=validate_idea",
    );
  });

  it("invents no sentence when a pre-2026-08-14 report carries no next step", () => {
    const legacy = notEvaluated();
    delete (legacy as unknown as Record<string, unknown>).failure_next_step;
    const view = render(ValidationVerdict, {
      props: { data: legacy, rerunHref: "/new?mode=validate_idea" },
    });

    const card = view.container.querySelector(".iv-commit");
    expect(card?.querySelector("p.iv-body-text")).toBeNull();
    expect(card?.textContent ?? "").not.toMatch(/rephrase|reword|rewrite|in your own words/i);
    expect(view.getByRole("link", { name: /Run the check again/ })).toBeInTheDocument();
  });

  it("carries a DIFFERENT cause's next step through unchanged — no local map", () => {
    // A DIFFERENT cause's next step — the real one, so this asserts the component passes
    // through copy the pipeline can actually emit rather than a paraphrase of it.
    const other = SEED_FAILURE_COPY.identity_changed_during_scoring.next_step;
    const view = render(ValidationVerdict, {
      props: {
        data: notEvaluated({
          failure_reason: "identity_changed_during_scoring",
          failure_next_step: other,
        }),
        rerunHref: "/new?mode=validate_idea",
      },
    });

    const card = view.container.querySelector(".iv-commit");
    expect(card).toHaveTextContent(other);
    expect(card).not.toHaveTextContent(NEXT_STEP_FROM_BACKEND);
  });
});

/**
 * THE SAME PAGE, POINTING BOTH WAYS. The echo card's redo link asked "Does this miss your
 * intent? Edit and rerun" on every outcome, including the one where the Next card says
 * "nothing in it caused this — there is nothing to change before you retry". Both open the
 * same prefilled re-run, so the contradiction bought nothing: what it cost was the honesty
 * of the refusal, by implying the user's wording was the thing to fix.
 */
describe("ValidationVerdict · not_evaluated echo card", () => {
  it("offers no 'edit your pitch' redo while the Next card says nothing needs changing", () => {
    const view = render(ValidationVerdict, {
      props: { data: notEvaluated(), rerunHref: "/new?mode=validate_idea" },
    });

    expect(view.queryByText(/Does this miss your intent/)).not.toBeInTheDocument();
    expect(view.queryByText(/Edit and rerun/)).not.toBeInTheDocument();
    // The retry itself survives — it just lives on the card that explains the cause.
    expect(view.getByRole("link", { name: /Run the check again/ })).toHaveAttribute(
      "href",
      "/new?mode=validate_idea",
    );
  });

  it("still offers it on an outcome where the reading COULD be what the user disputes", () => {
    const view = render(ValidationVerdict, {
      props: {
        data: notEvaluated({
          outcome: "worth_testing",
          idea_name: "ReplyContext",
          headline: "The problem behind ReplyContext shows up in real threads.",
          failure_reason: undefined,
          failure_next_step: undefined,
        }),
        rerunHref: "/new?mode=validate_idea",
      },
    });

    expect(view.getByText(/Does this miss your intent/)).toBeInTheDocument();
  });
});
