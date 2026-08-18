import { afterEach, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { cleanup, render } from "@testing-library/svelte";
import ValidationVerdict from "$lib/components/sections/ValidationVerdict.svelte";
import type { IdeaValidation, IdeaValidationPivot } from "$lib/types/report";
import { gradedBlock } from "./fixtures/ideaValidationBlocks";
import PIPELINE_PIVOTS from "./fixtures/pivotClampText.captured.json";

/**
 * CLAMPED, NOT TRUNCATED — the pivot panel's two long text fields.
 *
 * `research_flow.py` used to store `rejected_pitch` as `value_proposition[:160]`, and the
 * accepted revision's `changes` as the same field at `[:200]`. A user read the result and
 * reported it as broken data: "…so practices stuck on Eaglesoft or D" — a mid-word cut with
 * no ellipsis, in a paragraph presenting the sentence as the revision's pitch. Nothing
 * required either bound (no column, no schema, no LLM consumer), and the sibling
 * `rejected_name` in the same record was never cut at all.
 *
 * Both slices are gone. The length limit now lives HERE, as a CSS line clamp, and the
 * difference between the two mechanisms is exactly what this spec pins:
 *
 *   - clamping folds the overflow with a REAL ellipsis, at whatever the viewport's line
 *     length actually is, and leaves the whole string in the DOM — selectable, copyable,
 *     and reachable by assistive tech;
 *   - truncating destroys the tail before it ever reaches the page.
 *
 * So "the full text is present in the DOM" is the load-bearing assertion, not the clamp
 * declaration. Both are checked, because either alone would pass while the other regressed.
 */

/**
 * The two pivot records are VENDORED, not authored and not imported across the repo root:
 * `noEscapingTestImports.test.ts` forbids a spec resolving outside `src/`, and
 * `fixtures/pivotClampText.captured.json` records the source file and JSON path for each
 * value so it stays traceable to the producer-generated python fixtures it came from.
 * `tests/unit/flows/test_pivot_clamp_fixture_contract.py` fails in Python the moment the
 * vendored copy drifts from those blocks — the graded block's own pivot is `not_attempted`,
 * so there is nothing in `ideaValidationBlocks.ts` to derive a long pivot from.
 * Everything except the pivot comes from the real graded block.
 */
type CapturedPivot = { key: string; value: IdeaValidationPivot };
const CAPTURED = PIPELINE_PIVOTS as unknown as CapturedPivot[];

function pivotNamed(key: string): IdeaValidationPivot {
  const hit = CAPTURED.find((r) => r.key === key);
  if (!hit) throw new Error(`pivotClampText.captured.json has no "${key}" record`);
  return hit.value;
}

const blockWith = (key: string): IdeaValidation => gradedBlock({ pivot: pivotNamed(key) });

/** Required prop; irrelevant to the clamp, so one constant for all three renders. */
const RERUN = "/new?mode=validate_idea";

/**
 * jsdom does not apply Svelte's scoped styles (0 <style> nodes in the test document) and
 * cssstyle drops `-webkit-line-clamp` as an unknown property, so `getComputedStyle` cannot
 * be the oracle here. The component's own <style> block is, read as text: the assertion is
 * that a clamp rule exists and names the element the markup actually renders.
 */
const COMPONENT_CSS = (() => {
  const src = readFileSync("src/lib/components/sections/ValidationVerdict.svelte", "utf8");
  const style = /<style[^>]*>([\s\S]*)<\/style>/.exec(src);
  if (!style) throw new Error("ValidationVerdict.svelte has no <style> block");
  // Comments out first: this file documents its rules heavily and the prose contains
  // commas, so a selector list parsed with the comment still attached never matches.
  return style[1].replace(/\/\*[\s\S]*?\*\//g, "");
})();

/**
 * EVERY declaration block whose selector list includes `selector`, concatenated.
 * `.iv-pivot-rejected` is styled by two rules (its own margin/measure block and the shared
 * clamp block) and CSS accumulates across both — looking only at the first match asserts
 * against the wrong half of the cascade.
 */
function rulesFor(selector: string): string {
  return COMPONENT_CSS.split("}")
    .filter((r) => {
      const brace = r.indexOf("{");
      if (brace === -1) return false;
      return r
        .slice(0, brace)
        .split(",")
        .some((s) => s.trim() === selector);
    })
    .join("\n");
}

function expectClampedBy(selector: string) {
  const rule = rulesFor(selector);
  expect(rule, `no CSS rule declares \`${selector}\``).not.toBe("");
  // The three-property line-clamp idiom used everywhere else in this codebase
  // (EvidenceAppendix, PageHeader, UnifiedHero). Any one missing and the text either
  // does not fold or folds without the ellipsis.
  expect(rule).toMatch(/display:\s*-webkit-box/);
  expect(rule).toMatch(/-webkit-line-clamp:\s*\d+/);
  expect(rule).toMatch(/-webkit-box-orient:\s*vertical/);
  expect(rule).toMatch(/overflow:\s*hidden/);
  // Muted-meta discipline (frontend/CLAUDE.md): a length limit is not a place to
  // introduce brand color or a hover affordance.
  expect(rule).not.toMatch(/--color-accent|:hover|translate/);
}

afterEach(cleanup);

describe("ValidationVerdict · pivot text is clamped, never truncated", () => {
  it("keeps the whole rejected pitch in the DOM and clamps it in CSS", () => {
    const data = blockWith("rejected");
    const pitch = data.pivot?.rejected_pitch ?? "";
    expect(pitch.length, "captured record carries no rejected pitch to clamp").toBeGreaterThan(
      120,
    );

    const view = render(ValidationVerdict, { props: { data, rerunHref: RERUN } });
    const el = view.container.querySelector(".iv-pivot-rejected");
    expect(el, "the rejected-revision paragraph did not render").not.toBeNull();

    // VERBATIM, to the last character — a renderer that shortened the string (slice,
    // substring, an "… more" split) would fail here even though it looked identical.
    expect(el?.textContent ?? "").toContain(pitch);
    expect(el?.textContent ?? "").toContain(data.pivot?.rejected_name ?? "");

    expectClampedBy(".iv-pivot-rejected");
  });

  it("keeps the whole `changes` value in the DOM and clamps that cell in CSS", () => {
    const data = blockWith("accepted");
    const changes = data.pivot?.changes ?? "";
    expect(changes.length, "captured record carries no `changes` value").toBeGreaterThan(120);

    const view = render(ValidationVerdict, { props: { data, rerunHref: RERUN } });
    const cell = view.container.querySelector(".iv-echo-row dd.iv-clamp-3");
    expect(cell, "the Changed cell lost its clamp hook").not.toBeNull();
    expect(cell?.textContent).toBe(changes);

    expectClampedBy(".iv-echo-row dd.iv-clamp-3");
  });

  it("clamps only the long pivot fields — the sibling echo cells are untouched", () => {
    // `Kept` and `Gap we aimed at` sit in the same <dl>, and the refinement panel a few
    // cards up uses the same `.iv-echo-row dd` selector. Clamping that shared selector
    // would have silently folded all of them, which is why the hook is a class.
    const data = blockWith("accepted");
    const view = render(ValidationVerdict, { props: { data, rerunHref: RERUN } });
    const cells = [...view.container.querySelectorAll(".iv-echo-row dd")];
    const clamped = cells.filter((c) => c.classList.contains("iv-clamp-3"));
    expect(cells.length).toBeGreaterThan(1);
    expect(clamped).toHaveLength(1);
    expect(clamped[0].textContent).toBe(data.pivot?.changes ?? "");
  });
});
