import { afterEach, describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { cleanup, render } from "@testing-library/svelte";
import { page } from "$app/state";
import ValidationVerdict from "$lib/components/sections/ValidationVerdict.svelte";
import type { IdeaValidation } from "$lib/types/report";
import {
  PIPELINE_REFUSAL_SENTENCES,
  gradedBlock,
  legacyNotEvaluatedBlock,
  notEvaluatedBlock,
} from "./fixtures/ideaValidationBlocks";

/**
 * THE SIXTEENTH SURFACE. A refused `validate_idea` run graded nothing — six typed causes,
 * all ours. The page said so in the verdict card and again in the Next card, and rendered
 * two findings-shaped cards BETWEEN them:
 *
 *   [1] Idea check · provisional | Not evaluated | "Our own check … could not run"
 *   [2] What this check cannot see  — "No one has paid … for this idea"
 *   [3] Lowest-cost next test       — rung 1 marked NEXT: "Run 5 problem interviews
 *                                     with the buyer you named", then a landing page,
 *                                     3 pre-sales, a concierge weekend
 *   [4] Next — This run couldn't grade your idea
 *
 * This is the one copy class in the program that costs the reader money and a weekend, on
 * an idea the run never evaluated. On the read-only share it was worse: all three commit
 * panels require `!readOnly`, so the ladder was the LAST card in the component.
 *
 * Every block below is GENERATED from `build_idea_validation_block` (see
 * fixtures/ideaValidationBlocks.ts). The reason this survived rounds 4-6 is that the
 * refused fixture was hand-written with `experiment_ladder: []` — a shape the pipeline
 * cannot emit — so every assertion about the refused page ran against an empty `<ol>`.
 */

afterEach(cleanup);

const RERUN = "/new?mode=validate_idea";

/**
 * READ OFF THE COMPONENT, never transcribed (ledger G-3: two constants in the sibling spec
 * were hand-typed and both had silently drifted from the sentences the app really ships, so
 * every assertion naming them was about copy no build emits). If the declaration moves or
 * stops being a plain string literal this throws at import rather than quietly asserting on
 * a stale sentence; its non-vacuity is asserted below.
 */
const CHARGE_STANDS: string = (() => {
  const src = readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), "..", "sections", "ValidationVerdict.svelte"),
    "utf8",
  );
  const decl = src.match(/const CHARGE_STANDS\s*=\s*([\s\S]*?);\n/);
  if (!decl) throw new Error("ValidationVerdict.svelte no longer declares CHARGE_STANDS");
  const parts = [...decl[1].matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) => m[1]);
  if (!parts.length) throw new Error("CHARGE_STANDS is no longer a plain string literal");
  return parts.join("").replace(/\\"/g, '"');
})();

function cardEyebrows(data: IdeaValidation, readOnly: boolean): string[] {
  const view = render(ValidationVerdict, { props: { data, rerunHref: RERUN, readOnly } });
  return [...view.container.querySelectorAll(".iv-card")].map(
    (c) => c.querySelector(".iv-eyebrow")?.textContent?.trim() ?? "(no eyebrow)",
  );
}

/** Guards the guard: a fixture with no ladder would make every negative below vacuous. */
describe("the generated fixtures are the shapes the pipeline really emits", () => {
  it("a GRADED block carries the full four-rung ladder and three desk limits", () => {
    const graded = gradedBlock();
    expect(graded.experiment_ladder).toHaveLength(4);
    expect(graded.desk_limits).toHaveLength(3);
    expect(graded.next_experiment_index).toBe(0);
  });

  it("a pre-2026-08-14 PERSISTED refusal carries that same ladder", () => {
    const legacy = legacyNotEvaluatedBlock();
    expect(legacy.outcome).toBe("not_evaluated");
    expect(legacy.experiment_ladder).toHaveLength(4);
    expect(legacy.desk_limits).toHaveLength(3);
  });
});

describe("ValidationVerdict · a refusal prescribes no experiment and caveats no findings", () => {
  it("renders the verdict and the Next card, and nothing between them", () => {
    expect(cardEyebrows(notEvaluatedBlock(), false)).toEqual([
      "How we read your idea",
      "Idea check",
      "Next",
    ]);
  });

  it("ends the read-only share on the verdict, not on a four-rung testing plan", () => {
    const eyebrows = cardEyebrows(notEvaluatedBlock(), true);
    expect(eyebrows).toEqual(["How we read your idea", "Idea check"]);
    // Stated separately because the ordering is the defect: the share has no commit panel
    // after this component, so whatever ends it is the last thing the visitor reads.
    expect(eyebrows.at(-1)).not.toBe("Lowest-cost next test");
  });

  it("shows no ladder and no rung marked as the next action", () => {
    const view = render(ValidationVerdict, {
      props: { data: notEvaluatedBlock(), rerunHref: RERUN },
    });
    expect(view.container.querySelector(".iv-ladder")).toBeNull();
    expect(view.container.querySelector(".iv-rung-next")).toBeNull();
    expect(view.container.textContent ?? "").not.toContain("Lowest-cost next test");
    expect(view.container.textContent ?? "").not.toMatch(/problem interviews|pre-sales|concierge/i);
  });

  it("shows no desk-limit caveats over findings the refusal cleared", () => {
    const view = render(ValidationVerdict, {
      props: { data: notEvaluatedBlock(), rerunHref: RERUN },
    });
    expect(view.container.textContent ?? "").not.toContain("What this check cannot see");
    expect(view.container.textContent ?? "").not.toMatch(/No one has paid, pre-ordered/i);
  });

  it("does not hedge an absent verdict as 'provisional'", () => {
    const view = render(ValidationVerdict, {
      props: { data: notEvaluatedBlock(), rerunHref: RERUN },
    });
    const eyebrow = view.container.querySelector(".iv-verdict .iv-eyebrow");
    expect(eyebrow?.textContent?.trim()).toBe("Idea check");
  });

  it("withholds both cards from a PERSISTED pre-fix report too", () => {
    // The builder fix cannot reach reports already written to storage. If this renderer
    // only trusted `.length`, every one of those would still render the ladder.
    const view = render(ValidationVerdict, {
      props: { data: legacyNotEvaluatedBlock(), rerunHref: RERUN, readOnly: true },
    });
    expect(view.container.querySelector(".iv-ladder")).toBeNull();
    expect(view.container.textContent ?? "").not.toContain("What this check cannot see");
    expect(view.container.querySelector(".iv-verdict .iv-eyebrow")?.textContent?.trim())
      .toBe("Idea check");
  });
});

/**
 * H-3 (round 12) — A COMMERCIAL DISCLOSURE THAT VANISHED WITH THE PRICE.
 *
 * All SEVEN typed causes end in "Run the check again" (counted from `SEED_FAILURE_COPY`,
 * 2026-08-15 — this line and the ledger both said "eight", which no version of that dict has
 * ever had; trap 20 again). The refusal card printed its cost line
 * under `{#if checkCost != null && creditBalance != null}` with NO `{:else}`, while both other
 * rerun affordances in the same component fall back to "(starts a new paid check)".
 * `discoveryCostUnavailable` is initialised TRUE in `(app)/+layout.server.ts:36` and cleared
 * only inside `if (costsRes?.ok)` — so ANY billing-load failure dropped the disclosure
 * entirely, on the one branch that has just told the user the failure was ours. Reachable by
 * default, not by contrivance: the unmocked render below is the failing state.
 *
 * The property is disclosure, not the number: the price may be unknown, but "this costs money"
 * never is.
 *
 * TRAP 1, INSIDE THE FIX FOR H-3 (2026-08-15). The paragraph above used to end "…and
 * `creditBalance` stays null unless the balance fetch succeeds". THAT IS FALSE, and the
 * "balance fetch failed" row below was built from it with `creditBalance: null` — a shape the
 * app cannot emit. `(app)/+layout.server.ts` seeds `creditBalance = 0` at :27 and
 * `balanceUnavailable = true` at :34, and assigns BOTH only inside `if (balanceRes?.ok)` at
 * :64. A failed balance fetch therefore arrives as a finite `0`, which sailed through
 * `ValidationVerdict`'s `typeof value === "number"` read and rendered **"BALANCE 0"** — a
 * confidently wrong number on the panel that has just said the failure was ours. Driven in a
 * real render before the fix; the component now gates on `balanceUnavailable`, exactly as
 * `jobs/[jobId]/selection/review/+page.svelte:328-332` already did.
 *
 * So each row below now carries the load-state FLAGS the layout really sets alongside the
 * values it really seeds, and the table asserts a third property: no row may print a balance
 * the layout did not successfully fetch. `0` is a legitimate balance, so no assertion on the
 * VALUE can separate these two cases — only the flag can.
 */
describe("ValidationVerdict · the refusal's rerun is disclosed as paid in every billing state", () => {
  const originalData = page.data;
  afterEach(() => { page.data = originalData; });

  // Each row is the payload `(app)/+layout.server.ts` REALLY produces in that state — the
  // seeded VALUES included, not only the flags. `creditBalance: 0` on the two failing rows is
  // the whole point: it is the seed, it is finite, and it must never be printed.
  const BILLING_STATES: [string, Record<string, unknown>, boolean][] = [
    ["billing loaded", {
      creditBalance: 12,
      stageCosts: { discovery: 99 },
      billingLoadState: { discoveryCostUnavailable: false, balanceUnavailable: false },
    }, true],
    ["the stage-cost fetch failed", {
      creditBalance: 12,
      stageCosts: { discovery: 99 },
      billingLoadState: { discoveryCostUnavailable: true, balanceUnavailable: false },
    }, false],
    // The layout seeds 0 and leaves `balanceUnavailable` TRUE — it never emits null. Pinning
    // `null` here is precisely what let "BALANCE 0" ship.
    ["the balance fetch failed", {
      creditBalance: 0,
      stageCosts: { discovery: 99 },
      billingLoadState: { discoveryCostUnavailable: false, balanceUnavailable: true },
    }, false],
    // The layout's genuine initial state: every flag true, every value at its seed. Was `{}`,
    // which is not a payload the layout can produce either.
    ["the whole billing load failed (the layout's initial state)", {
      creditBalance: 0,
      stageCosts: { discovery: 0 },
      billingLoadState: { discoveryCostUnavailable: true, balanceUnavailable: true },
    }, false],
  ];

  for (const [name, data, priced] of BILLING_STATES) {
    it(`discloses that the rerun is paid when ${name}`, () => {
      page.data = data as typeof page.data;
      const view = render(ValidationVerdict, {
        props: { data: notEvaluatedBlock(), rerunHref: RERUN },
      });
      const card = [...view.container.querySelectorAll(".iv-card")]
        .find((c) => c.querySelector(`a[href="${RERUN}"]`));
      expect(card, "no card carries the rerun link").toBeTruthy();
      const text = (card?.textContent ?? "").replace(/ /g, " ");
      expect(text, `"Run the check again" with no indication it is paid — ${name}`)
        .toMatch(/CREDITS|PAID CHECK/);
      // …and when the price IS known it is still the price, not the fallback: a disclosure
      // rule satisfied by always printing the vaguer sentence would be a regression.
      expect(text.includes("99 CREDITS") && text.includes("BALANCE 12"), name).toBe(priced);
      // A balance we did not successfully fetch is never shown, in ANY spelling. This asserts
      // on the FLAG, never on the number: `0` is both the layout's seed and a perfectly real
      // balance, so no assertion about the value can tell the two apart.
      const flags = data.billingLoadState as { balanceUnavailable?: boolean } | undefined;
      if (flags?.balanceUnavailable) {
        expect(text, `a balance was printed though the fetch failed — ${name}`)
          .not.toMatch(/BALANCE/);
      }
      // S15 — and the charge ALREADY TAKEN stands, said beside the price in every state.
      // Pricing the next check while saying nothing about this one is what let "our fault"
      // plus "a new paid check" read as "the failed run was free".
      expect(text, `the standing charge was never disclosed — ${name}`)
        .toContain(CHARGE_STANDS);
    });
  }
});

/**
 * S15 — THE CHARGE THAT ALREADY STANDS (owner decision 2026-08-15: Option B, no refund).
 *
 * A refused run keeps the full discovery charge: it is taken at job creation
 * (`creditService.ts:906`), the refusal is deliberately non-fatal, the run ends at
 * AWAITING_SELECTION, and nothing on that path refunds. That is now the intended behaviour
 * and it is pinned in `backend/src/services/__tests__/refusedRunCharge.test.ts`. What was
 * missing was the other half of the deal: the card said the failure was ours and offered a
 * "new paid check", and never once said the first charge was kept.
 *
 * The properties below are about SHAPE, not eloquence — one sentence, one place, on every
 * surface that offers the paid retry and on none that doesn't.
 */
describe("ValidationVerdict · the standing charge is disclosed exactly where the retry is", () => {
  const originalData = page.data;
  afterEach(() => { page.data = originalData; });

  const BILLING_LOADED = {
    creditBalance: 12,
    stageCosts: { discovery: 99 },
    billingLoadState: { discoveryCostUnavailable: false, balanceUnavailable: false },
  };

  it("the sentence read off the component actually says the thing", () => {
    // Guards the extraction: a regex that returned "" would make every assertion above
    // vacuously green ("" is contained in everything).
    expect(CHARGE_STANDS.length).toBeGreaterThan(40);
    expect(CHARGE_STANDS).toMatch(/charged/i);
    expect(CHARGE_STANDS).toMatch(/refund/i);
  });

  it("says it ONCE, not once per typed cause", () => {
    page.data = BILLING_LOADED as typeof page.data;
    const view = render(ValidationVerdict, {
      props: { data: notEvaluatedBlock(), rerunHref: RERUN },
    });
    const text = (view.container.textContent ?? "").replace(/ /g, " ");
    const hits = text.split(CHARGE_STANDS).length - 1;
    expect(hits, "the standing charge is duplicated on the page").toBe(1);
  });

  it("does not depend on the artifact: a refusal carrying no typed cause still discloses it", () => {
    // Pre-2026-08-14 refusals carry neither `failure_reason` nor `failure_next_step`, and
    // the fact is true of them too. If this sentence ever moves onto the persisted block it
    // will silently stop rendering here, which is the fail-OPEN shape (ledger trap 16).
    page.data = BILLING_LOADED as typeof page.data;
    const bare = notEvaluatedBlock();
    delete (bare as unknown as Record<string, unknown>).failure_next_step;
    delete (bare as unknown as Record<string, unknown>).failure_reason;
    const view = render(ValidationVerdict, { props: { data: bare, rerunHref: RERUN } });
    expect((view.container.textContent ?? "").replace(/ /g, " ")).toContain(CHARGE_STANDS);
  });

  it("prices the retry and the standing charge in SEPARATE strings", () => {
    // The retry price may change (a cheaper same-run retry is an open question); the fact
    // that this run's credits were spent will not. Neither sentence may absorb the other,
    // or replacing one means re-editing the other.
    expect(CHARGE_STANDS).not.toMatch(/credits|balance|new check|paid check/i);
  });

  it("is absent from the read-only share, which offers no retry to disclose", () => {
    page.data = BILLING_LOADED as typeof page.data;
    const view = render(ValidationVerdict, {
      props: { data: notEvaluatedBlock(), rerunHref: "", readOnly: true },
    });
    const text = (view.container.textContent ?? "").replace(/ /g, " ");
    expect(text).not.toContain(CHARGE_STANDS);
    // Guards the guard: the absence must come from there being no commit panel, not from a
    // fixture that renders nothing.
    expect(view.container.querySelector(".iv-commit")).toBeNull();
    expect(text).toContain("Not evaluated");
  });

  it("is absent from a GRADED check, which never lost the user anything", () => {
    page.data = BILLING_LOADED as typeof page.data;
    const view = render(ValidationVerdict, {
      props: { data: gradedBlock(), rerunHref: RERUN },
    });
    expect((view.container.textContent ?? "").replace(/ /g, " ")).not.toContain(CHARGE_STANDS);
  });
});

/**
 * The policy that keeps the above from rotting: no spec may hand-author the pipeline's
 * idea-check copy. Two properties, because the failure has two shapes.
 *
 * IT IS AN AST RULE NOW, NOT A REGEX (2026-08-15). The previous version derived its field set
 * from the ARRAY-valued keys of the generated fixtures and matched values with
 * `field:\s*(?:\[|new Array|Array.of|Array.from)`. Both halves were shape restrictions, and a
 * critic drove seven plants through it; SIX survived:
 *
 *   parts: JSON.parse('[…]')                     · competitors: Object.freeze([…])
 *   kill_risks: ([…])                            · anchored_pains: structuredClone([…])
 *   refinement: { kept: […], changed: […] }       — an OBJECT, so not in the field set at all
 *   headline: "Try rephrasing your idea so we can understand it better."
 *   failure_next_step: "Try rephrasing your idea so we can understand it better."
 *
 * The value predicate is now shape-free: a structured field must DERIVE from the generated
 * fixtures, and how the value is spelled is irrelevant — array literal, constructor call,
 * `JSON.parse`, `structuredClone`, a parenthesised expression, or a nested object all fail
 * identically. The last two plants are not a structure problem at all; they are the
 * single-source-of-copy problem, and they are caught by the second property below, which is
 * the TypeScript half of `test_no_cause_tells_the_user_to_rephrase_a_failure_that_is_ours`
 * (tests/unit/crews/test_seed_pipeline.py). Python has had that assertion since round 4 and
 * the frontend did not, which is how a spec could pin a sentence blaming the user for a
 * failure that is ours.
 *
 * SCOPE IS STRUCTURAL TOO. The rule fires only inside an IDEA-CHECK BLOCK POSITION — an object
 * literal that is typed `IdeaValidation`, assigned to an `idea_validation` property, passed to
 * one of the fixture accessors, or spreads a value that is one of those. That matters: keys
 * like `outcome`, `headline` and `competitors` are ordinary words elsewhere in this tree
 * (batch activity has an `outcome`, every idea has a `headline`), and a rule keyed on names
 * alone flagged 284 sites, 274 of which have nothing to do with idea checks. A rule that
 * shouts at unrelated code is a rule that gets an exemption.
 *
 * G-2 (round 11) — THE SCOPE CHECK USED TO READ ONLY THE LITERAL'S IMMEDIATE PARENT, and a
 * critic walked past it twice with shapes that compile and typecheck:
 *
 *   const iv = mk() as IdeaValidation;   // the literal's parent is a `return`, not a cast
 *   const iv = { … } as unknown as IdeaValidation;   // the inner cast names `unknown`
 *
 * Block position is now computed FORWARD instead of asked backward. Every expression in a
 * declared idea-check position — a variable typed `IdeaValidation`, an `as` chain ending in
 * it (however many hops, whatever the intermediate types), an `idea_validation` property, a
 * fixture-accessor argument, or the return type of a same-file function — is RESOLVED to the
 * object literals it can actually be, following same-file consts, ternaries and calls into
 * the callee's own `return`s. Those literals are the scoped set.
 *
 * Its boundary, so nobody reads more into it: resolution is same-file. A helper that builds
 * the block in ANOTHER module and is imported here is out of reach, exactly as the analyst
 * prompt scan's cross-file limit is. That is not a hole the next plant can be written into
 * casually — the helper would have to live in a second file with no idea-check typing of its
 * own — but it is a limit, and it is written down rather than implied.
 *
 * THE BOUNDARY, STATED. The banned set is every key the generated blocks carry as an ARRAY OR
 * AN OBJECT — the union of both blocks, so a field populated when graded and empty when
 * refused is covered. Keys whose value is `null` in BOTH blocks (`red_team_findings`,
 * `incumbent_parity`, `duplicate_of`, …) are out of scope for a reason that is not laziness:
 * there is no reference shape to derive from, so a spec exercising the "adversarial review
 * killed it" rendering has nowhere to get one. Scalars are out of scope for the opposite
 * reason — a spec legitimately varies the pitch and the failure cause per narrative — and are
 * governed by the copy property instead. Both boundaries are the judgement; the field set
 * inside them is derived and nobody has to remember to extend it.
 */
describe("no spec hand-authors the pipeline's idea-check copy", () => {
  /**
   * `src`, not `src/lib`. An earlier version resolved two levels up from
   * `src/lib/components/__tests__` and landed on `src/lib`, so it walked 131 of 174 spec
   * files and left `src/routes/` — including `validateNotEvaluatedSurface.test.ts`, THE
   * FILE THE DEFECT CAME FROM — entirely unpoliced.
   */
  const SRC_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
  const SKIP_DIRS = new Set(["node_modules", ".svelte-kit", "dist", "build"]);

  /**
   * TEST SCOPE, not "files named *.test.ts". The natural home for a future hand-written
   * variant is a HELPER beside `ideaValidationBlocks.ts` — a plain `.ts` file inside
   * `__tests__/`, which a filename rule waves straight through.
   */
  const inTestScope = (path: string) => {
    const unix = path.split(sep).join("/");
    return unix.includes("/__tests__/") || /\.(test|spec)\.(ts|svelte)$/.test(unix);
  };

  function walk(dir: string, found: string[] = []): string[] {
    for (const entry of readdirSync(dir)) {
      if (SKIP_DIRS.has(entry)) continue;
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) walk(full, found);
      else if (/\.(ts|svelte)$/.test(entry) && inTestScope(full)) found.push(full);
    }
    return found;
  }

  const policed = () => walk(SRC_ROOT).map((f) => relative(SRC_ROOT, f).split(sep).join("/"));

  /** The names a spec may derive an idea-check value FROM. */
  const FIXTURE_SOURCES = new Set([
    "gradedBlock", "notEvaluatedBlock", "legacyNotEvaluatedBlock", "GRADED", "REFUSED",
    // The vendored refusal register (G-3): a spec needing a specific cause's sentence takes
    // it from here, and that counts as a derivation like any other.
    "SEED_FAILURE_COPY",
  ]);

  /**
   * THE BANNED FIELDS, read out of the generated blocks. Any key either block carries as a
   * list OR an object is a value the pipeline COMPOSES, and a spec that types an equivalent is
   * asserting a shape it has not checked against the producer.
   */
  const PIPELINE_STRUCTURED_FIELDS = new Set(
    [gradedBlock(), notEvaluatedBlock(), legacyNotEvaluatedBlock()].flatMap((block) =>
      Object.entries(block as unknown as Record<string, unknown>)
        .filter(([, value]) => value !== null && typeof value === "object")
        .map(([key]) => key),
    ),
  );

  /**
   * G-3 (round 11) — THE COPY RULE IS DERIVE-OR-FAIL NOW, NOT A KEYWORD BLACKLIST.
   *
   * It used to be a list: `"rephras", "reword", "rewrit", "in your own words", …`. Round 10
   * had already watched that list lose to an INFLECTION — the plant read "Try REPHRASING
   * your idea", which matched none of "rephrase"/"reword"/"rewrite" — and stemmed it. A
   * round-11 critic then walked past the stemmed version with `re-word`, `re-phrase`,
   * `re-writing`, `reformulate`, `restate`, "be more specific" and "clarify your
   * description". Lengthening the list is the move this program has watched fail four
   * times, and it fails the same way each time: the ban side of a guard is where a list is
   * always incomplete, and an incomplete ban fails OPEN.
   *
   * There IS a real property here, and the objection that blocked it ("`SEED_FAILURE_COPY`
   * is Python-side") was answered a round ago by the blocks themselves: they are Python-side
   * too, and they are VENDORED — generated by a contract test that fails in Python the
   * moment the two disagree. The refusal register is now vendored the same way
   * (`seedFailureCopy.generated.json`), so the rule is the one that already works for the
   * structured fields: **a refusal `headline` or `failure_next_step` in a spec must be a
   * sentence the producer can actually emit.** A sentence blaming the user is unwritable
   * because no cause carries one — no vocabulary required, and the next spelling nobody
   * thought of is covered for free.
   *
   * It also caught what the blacklist could not: three sentences already shipped in
   * `ValidationVerdict.notEvaluated.test.ts` were TRUNCATIONS and paraphrases of real copy
   * — hand-authored strings no producer emits, asserted as "FROM_BACKEND". Blameless, and
   * exactly the trap-9 class the block fixtures exist to end, one layer down in the scalars.
   *
   * SCOPE, stated. The rule applies to the two refusal-copy scalars, and only where the
   * block is a refusal: a literal that declares a GRADED `outcome`, or overrides
   * `gradedBlock()`, is out (a graded headline is composed from the idea and is not a closed
   * set). `undefined` is allowed — deleting a field is how the legacy-artifact tests are
   * written. And a value DERIVED from the fixtures or from the vendored register passes, as
   * everywhere else in this guard.
   *
   * The Python half is unchanged and stays a stemmed blacklist for a different reason:
   * there it polices SHIPPED copy by enumerating `live_typed_failure_causes()`, a closed set
   * it can iterate — a backstop over content that is already derived, not the only net.
   */
  const REFUSAL_COPY_FIELDS = new Set(["headline", "failure_next_step"]);
  const GRADED_OUTCOMES = new Set([
    "worth_testing", "occupied", "premise_unproven", "ruled_out",
  ]);

  interface Finding { file: string; line: number; key: string; detail: string }

  function scan(file: string, source: string) {
    const script = file.endsWith(".svelte")
      ? (source.match(/<script[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? "")
      : source;
    const sf = ts.createSourceFile(file, script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);

    const typeNames = (node: ts.Node | undefined) => {
      const names: string[] = [];
      const visit = (n: ts.Node) => {
        if (ts.isTypeReferenceNode(n) && ts.isIdentifier(n.typeName)) names.push(n.typeName.text);
        ts.forEachChild(n, visit);
      };
      if (node) visit(node);
      return names;
    };
    const unwrap = (node: ts.Node): ts.Node =>
      ts.isAsExpression(node) || ts.isParenthesizedExpression(node)
        ? unwrap(node.expression)
        : node;

    const blockVars = new Set<string>();
    /** Filled once `fnReturns` is known; read by `derivesFromFixture`, which runs later. */
    const wrapperNames = new Set<string>();
    const consts = new Map<string, ts.Expression>();
    const derivesFromFixture = (node: ts.Node, seen = new Set<string>()): boolean => {
      let found = false;
      const visit = (n: ts.Node) => {
        if (found) return;
        if (ts.isIdentifier(n)) {
          if (FIXTURE_SOURCES.has(n.text) || blockVars.has(n.text) || wrapperNames.has(n.text)) {
            found = true;
            return;
          }
          // …and THROUGH a same-file const. A file that names the producer's sentence once
          // and uses the name is deriving, exactly as if it had inlined the expression.
          if (!seen.has(n.text)) {
            const source = consts.get(n.text);
            if (source && derivesFromFixture(source, new Set(seen).add(n.text))) {
              found = true;
              return;
            }
          }
        }
        ts.forEachChild(n, visit);
      };
      visit(node);
      return found;
    };
    /**
     * H-1 (round 12) — TAINT PRESENCE IS NOT THE STATED PROPERTY.
     *
     * `derivesFromFixture` answers "does this expression MENTION the producer anywhere?". That
     * is the right question for finding block vars and wrapper functions, and the wrong one for
     * the two refusal-copy scalars, whose stated rule is **a sentence the producer can actually
     * emit**. Both of these mention the producer and neither is emittable:
     *
     *     `${SEED_FAILURE_COPY.x.next_step} If it keeps stopping, try describing your idea
     *      differently.`                        ← appends blame to a derived sentence
     *     SEED_FAILURE_COPY.x.next_step.replace("our side", "your side")
     *                                           ← inverts whose fault it was
     *
     * The claim and the predicate differed, which is this ledger's trap 7. Of the two repairs
     * the brief offered, THE PREDICATE IS MADE TO MATCH THE CLAIM — the claim is what the
     * guard's value rests on, and weakening it to "mentions the producer" would leave the two
     * sentences above shippable in a spec.
     *
     * A refusal scalar must therefore be a PURE REFERENCE to producer copy: a fixture name, a
     * property or index path off one, an accessor call, a ternary of those, or a template with
     * exactly one substitution and no text of its own. Concatenation, added literal text and
     * method calls are TRANSFORMATIONS, and a transformed sentence is one the producer cannot
     * emit. The structural-field rule at the call site below keeps the looser predicate on
     * purpose: `{ ...gradedBlock().alternatives, count: 2 }` is a legitimate shape-variation
     * and is not copy put in front of a reader.
     */
    const verbatimFromProducer = (node: ts.Node, seen = new Set<string>()): boolean => {
      const n = unwrap(node);
      if (ts.isIdentifier(n)) {
        if (FIXTURE_SOURCES.has(n.text) || blockVars.has(n.text) || wrapperNames.has(n.text)) {
          return true;
        }
        if (seen.has(n.text)) return false;
        const source = consts.get(n.text);
        return source !== undefined && verbatimFromProducer(source, new Set(seen).add(n.text));
      }
      // A path INTO producer copy is still producer copy.
      if (ts.isPropertyAccessExpression(n) || ts.isElementAccessExpression(n)
        || ts.isNonNullExpression(n)) {
        return verbatimFromProducer(n.expression, seen);
      }
      if (ts.isConditionalExpression(n)) {
        return verbatimFromProducer(n.whenTrue, seen) && verbatimFromProducer(n.whenFalse, seen);
      }
      // `notEvaluatedBlock()` is producer copy; `SEED_FAILURE_COPY.x.next_step.replace(…)` is a
      // method ON producer copy, which is a transformation of it.
      if (ts.isCallExpression(n)) {
        return ts.isIdentifier(n.expression)
          && (FIXTURE_SOURCES.has(n.expression.text) || wrapperNames.has(n.expression.text));
      }
      // `${x}` alone is x. Any literal text around it is text the producer never wrote.
      if (ts.isTemplateExpression(n)) {
        return n.head.text === ""
          && n.templateSpans.length === 1
          && n.templateSpans[0].literal.text === ""
          && verbatimFromProducer(n.templateSpans[0].expression, seen);
      }
      return false;
    };

    const collect = (node: ts.Node) => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
        consts.set(node.name.text, node.initializer);
        const init = unwrap(node.initializer);
        const annotated = typeNames(node.type).includes("IdeaValidation")
          || (ts.isAsExpression(node.initializer)
            && typeNames(node.initializer.type).includes("IdeaValidation"));
        const fromAccessor = ts.isCallExpression(init) && ts.isIdentifier(init.expression)
          && FIXTURE_SOURCES.has(init.expression.text);
        const spreadsBlock = ts.isObjectLiteralExpression(init) && init.properties.some(
          (p) => ts.isSpreadAssignment(p) && derivesFromFixture(p.expression),
        );
        if (annotated || fromAccessor || spreadsBlock) blockVars.add(node.name.text);
      }
      ts.forEachChild(node, collect);
    };
    // Twice: a block var may be declared after the one that derives from it.
    collect(sf);
    collect(sf);

    /**
     * G-2 — block position, computed FORWARD. Every expression that SITS in an idea-check
     * position is resolved to the object literals it can be: through consts, ternaries,
     * `as` chains of any length, and into a same-file callee's own `return`s. A literal
     * reached that way is in scope no matter what its immediate parent happens to be.
     */
    const fnReturns = new Map<string, ts.Expression[]>();
    const collectFns = (node: ts.Node) => {
      const record = (name: string, fn: ts.SignatureDeclaration & { body?: ts.Node }) => {
        const body = fn.body;
        if (!body) return;
        if (!ts.isBlock(body)) { fnReturns.set(name, [body as ts.Expression]); return; }
        const out: ts.Expression[] = [];
        const walkReturns = (n: ts.Node) => {
          if (ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n)) return;
          if (ts.isReturnStatement(n) && n.expression) out.push(n.expression);
          ts.forEachChild(n, walkReturns);
        };
        ts.forEachChild(body, walkReturns);
        fnReturns.set(name, out);
      };
      if (ts.isFunctionDeclaration(node) && node.name) record(node.name.text, node);
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer
        && (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer))) {
        record(node.name.text, node.initializer);
      }
      ts.forEachChild(node, collectFns);
    };
    collectFns(sf);

    /**
     * Same-file WRAPPERS around a fixture accessor — `const notEvaluated = (o = {}) =>
     * notEvaluatedBlock({ …, ...o })` is the natural way to write a file's narrative once,
     * and it moved every override one call out of the guard's reach. A function whose
     * returns derive from a fixture counts as an accessor: its arguments are block
     * positions, and its call is a derivation.
     */
    const wrapperFns = new Set<string>();
    for (const [name, rets] of fnReturns) {
      if (rets.some((r) => derivesFromFixture(r))) wrapperFns.add(name);
    }
    for (const name of wrapperFns) wrapperNames.add(name);
    const isAccessorName = (name: string) => FIXTURE_SOURCES.has(name) || wrapperFns.has(name);

    const blockLiterals = new Set<ts.ObjectLiteralExpression>();
    const markBlockExpression = (expr: ts.Node, depth = 0) => {
      if (depth > 6) return;
      const bare = unwrap(expr);
      if (ts.isObjectLiteralExpression(bare)) { blockLiterals.add(bare); return; }
      if (ts.isConditionalExpression(bare)) {
        markBlockExpression(bare.whenTrue, depth + 1);
        markBlockExpression(bare.whenFalse, depth + 1);
        return;
      }
      if (ts.isIdentifier(bare)) {
        const source = consts.get(bare.text);
        if (source && source !== bare) markBlockExpression(source, depth + 1);
        return;
      }
      if (ts.isCallExpression(bare) && ts.isIdentifier(bare.expression)) {
        for (const ret of fnReturns.get(bare.expression.text) ?? []) {
          markBlockExpression(ret, depth + 1);
        }
      }
    };

    /** `x as unknown as IdeaValidation` — walk the whole cast chain, not just one hop. */
    const castChainNamesBlock = (node: ts.Node): boolean => {
      let cur: ts.Node | undefined = node;
      while (cur && (ts.isAsExpression(cur) || ts.isParenthesizedExpression(cur)
        || ts.isSatisfiesExpression(cur))) {
        if ((ts.isAsExpression(cur) || ts.isSatisfiesExpression(cur))
          && typeNames(cur.type).includes("IdeaValidation")) return true;
        cur = cur.parent;
      }
      return false;
    };

    const seedBlockPositions = (node: ts.Node) => {
      if (ts.isVariableDeclaration(node) && node.initializer
        && typeNames(node.type).includes("IdeaValidation")) {
        markBlockExpression(node.initializer);
      }
      if ((ts.isAsExpression(node) || ts.isSatisfiesExpression(node))
        && typeNames(node.type).includes("IdeaValidation")) {
        markBlockExpression(node.expression);
      }
      if (ts.isPropertyAssignment(node)
        && (ts.isIdentifier(node.name) || ts.isStringLiteral(node.name))
        && node.name.text === "idea_validation") {
        markBlockExpression(node.initializer);
      }
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)
        && isAccessorName(node.expression.text)) {
        for (const arg of node.arguments) markBlockExpression(arg);
      }
      // A same-file helper that DECLARES it builds one.
      if ((ts.isFunctionDeclaration(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node))
        && typeNames(node.type).includes("IdeaValidation")) {
        const name = ts.isFunctionDeclaration(node) && node.name
          ? node.name.text
          : (node.parent && ts.isVariableDeclaration(node.parent) && ts.isIdentifier(node.parent.name)
            ? node.parent.name.text
            : null);
        for (const ret of (name ? fnReturns.get(name) : null) ?? []) markBlockExpression(ret);
      }
      ts.forEachChild(node, seedBlockPositions);
    };
    // Twice, for the same reason `collect` runs twice: a helper may be declared after its use.
    seedBlockPositions(sf);
    seedBlockPositions(sf);

    /** Is this block a REFUSAL? Graded blocks compose their headline from the idea, so their
     *  copy is not a closed set and cannot be derive-or-fail. */
    const isRefusalLiteral = (obj: ts.ObjectLiteralExpression): boolean => {
      for (const prop of obj.properties) {
        if (!ts.isPropertyAssignment(prop)) continue;
        const name = ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name)
          ? prop.name.text : null;
        if (name !== "outcome") continue;
        const value = unwrap(prop.initializer);
        if ((ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value))
          && GRADED_OUTCOMES.has(value.text)) return false;
      }
      const parent = obj.parent;
      if (parent && ts.isCallExpression(parent) && ts.isIdentifier(parent.expression)
        && parent.expression.text === "gradedBlock") return false;
      return true;
    };

    const inBlockPosition = (obj: ts.ObjectLiteralExpression): boolean => {
      if (blockLiterals.has(obj)) return true;
      if (castChainNamesBlock(obj.parent)) return true;
      const parent = obj.parent;
      if (parent && ts.isCallExpression(parent) && ts.isIdentifier(parent.expression)
        && isAccessorName(parent.expression.text)) {
        return true;
      }
      return obj.properties.some(
        (p) => ts.isSpreadAssignment(p) && derivesFromFixture(p.expression),
      );
    };

    /** Every string this expression can put in front of a reader, resolving same-file consts. */
    const strings = (node: ts.Node, seen = new Set<string>()): string[] => {
      const out: string[] = [];
      const visit = (n: ts.Node) => {
        if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)
          || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)) {
          out.push(n.text);
        }
        if (ts.isIdentifier(n) && !seen.has(n.text)) {
          seen.add(n.text);
          const source = consts.get(n.text);
          if (source) out.push(...strings(source, seen));
        }
        ts.forEachChild(n, visit);
      };
      visit(node);
      return out;
    };

    const structural: Finding[] = [];
    const blaming: Finding[] = [];
    const visit = (node: ts.Node) => {
      if (ts.isObjectLiteralExpression(node) && inBlockPosition(node)) {
        for (const prop of node.properties) {
          if (!ts.isPropertyAssignment(prop)) continue;
          const key = ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name)
            ? prop.name.text
            : (ts.isComputedPropertyName(prop.name) && ts.isStringLiteral(prop.name.expression)
              ? prop.name.expression.text
              : null);
          if (!key) continue;
          const { line } = sf.getLineAndCharacterOfPosition(prop.getStart());
          const detail = prop.getText().replace(/\s+/g, " ").slice(0, 70);
          if (PIPELINE_STRUCTURED_FIELDS.has(key) && !derivesFromFixture(prop.initializer)) {
            structural.push({ file, line: line + 1, key, detail });
          }
          // H-1: `verbatimFromProducer`, not `derivesFromFixture` — this is the copy rule, and
          // its claim is emittability, not the presence of the producer's name somewhere in
          // the expression. See the predicate's own doc.
          if (REFUSAL_COPY_FIELDS.has(key) && isRefusalLiteral(node)
            && !verbatimFromProducer(prop.initializer)) {
            const value = unwrap(prop.initializer);
            const literal = ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)
              ? value.text
              : null;
            const isUndefined = ts.isIdentifier(value) && value.text === "undefined";
            if (!isUndefined && (literal === null || !PIPELINE_REFUSAL_SENTENCES.has(literal))) {
              blaming.push({ file, line: line + 1, key, detail });
            }
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sf);
    return { structural, blaming };
  }

  const scanTree = () => {
    const structural: Finding[] = [];
    const blaming: Finding[] = [];
    for (const abs of walk(SRC_ROOT)) {
      const rel = relative(SRC_ROOT, abs).split(sep).join("/");
      const found = scan(rel, readFileSync(abs, "utf8"));
      structural.push(...found.structural);
      blaming.push(...found.blaming);
    }
    return { structural, blaming };
  };

  const show = (findings: Finding[]) =>
    findings.map((f) => `${f.file}:${f.line}  ${f.key} — ${f.detail}`);

  it("polices the files the defect actually came from", () => {
    // NAMED, not counted. `> 50` was an older guard and it passed at 131 while the walk was
    // missing the entire routes tree — a count cannot fail for the reason that matters.
    const files = policed();
    expect(files).toContain(
      "routes/(app)/jobs/[jobId]/__tests__/validateNotEvaluatedSurface.test.ts",
    );
    expect(files).toContain("lib/components/__tests__/fixtures/ideaValidationBlocks.ts");
    expect(files).toContain("lib/components/__tests__/ValidationVerdict.refusedCards.test.ts");
  });

  it("derives the banned fields from the generated blocks, past both earlier shape limits", () => {
    // The four the critic proved an array-keyed set could not stop, plus the object-valued one
    // that was never in it at all. Written as data, not as a second list to maintain: each of
    // these IS a list or an object in the fixtures, so this fails if the derivation stops.
    for (const field of [
      "parts", "competitors", "kill_risks", "anchored_pains", // shape-dodged, in the old set
      "refinement", "pivot", "alternatives", "score_bands", // objects — absent from the old set
      "desk_limits", "experiment_ladder", // the two the old set actually named
    ]) {
      expect([...PIPELINE_STRUCTURED_FIELDS], field).toContain(field);
    }
    expect(PIPELINE_STRUCTURED_FIELDS.size).toBeGreaterThan(10);
    // Scalars stay out: they are the copy property's business, not this one's.
    for (const scalar of ["outcome", "headline", "failure_next_step", "idea_name"]) {
      expect([...PIPELINE_STRUCTURED_FIELDS], scalar).not.toContain(scalar);
    }
  });

  it("catches all seven plants, whatever shape the value is spelled in", () => {
    // Every field name is INTERPOLATED, never typed adjacent to a `:` in this file, so the
    // policy cannot flag its own positive controls — the only escape from that would be a
    // self-exemption, which is how a policy file stops policing itself.
    const n = (name: string) => name.split("|").join("");
    const [PARTS, RIVALS, RISKS, PAINS, REFINE, HEAD, NEXT] = [
      "par|ts", "competi|tors", "kill|_risks", "anchored|_pains", "refine|ment",
      "head|line", "failure|_next_step",
    ].map(n);
    const plants = [
      `${PARTS}: JSON.parse('[{"key":"problem_real"}]')`,
      `${RIVALS}: Object.freeze([{ name: "Existing Helpdesk" }])`,
      `${RISKS}: ([{ claim: "x" }])`,
      `${PAINS}: structuredClone([{ title: "y" }])`,
      `${REFINE}: { kept: ["audience"], changed: ["mechanism"] }`,
      `${HEAD}: "Try rephrasing your idea so we can understand it better."`,
      `${NEXT}: "Try rephrasing your idea so we can understand it better."`,
    ];
    for (const plant of plants) {
      const source = `const iv: IdeaValidation = { ${plant} };`;
      const found = scan("planted.ts", source);
      expect(
        found.structural.length + found.blaming.length,
        `the guard did not see: ${plant}`,
      ).toBeGreaterThan(0);
    }
  });

  /**
   * G-2 — the two SCOPE escapes, which are a different failure from the seven above: the value
   * is hand-authored in the banned shape and the guard never looks at it, because the literal's
   * immediate parent is a `return` or an intermediate `unknown` cast. Both compile and both
   * typecheck. Measured against the round-10 predicate: 0 of 2 caught.
   */
  it("catches the two scope escapes: a helper's literal cast at the call site, and a double cast", () => {
    const n = (name: string) => name.split("|").join("");
    const PARTS = n("par|ts");
    const escapes = [
      // 1 — the literal lives in a helper; the cast happens at the call site.
      `function mk() { return { ${PARTS}: [{ key: "problem_real" }] }; }\n`
        + `const iv = mk() as IdeaValidation;`,
      // 2 — the cast chain launders through `unknown`, so no single hop names the type.
      `const iv = { ${PARTS}: [{ key: "problem_real" }] } as unknown as IdeaValidation;`,
      // 3 (ours) — the helper DECLARES the type; nothing is cast anywhere.
      `function mk(): IdeaValidation { return { ${PARTS}: [{ key: "problem_real" }] }; }\n`
        + `const iv = mk();`,
      // 4 (ours) — the literal arrives through a const, then a cast.
      `const raw = { ${PARTS}: [{ key: "problem_real" }] };\n`
        + `const iv = raw as IdeaValidation;`,
      // 5 (ours) — a ternary in a typed position, hand-authored on one branch only.
      `const iv: IdeaValidation = flag ? gradedBlock() : { ${PARTS}: [{ key: "problem_real" }] };`,
    ];
    for (const source of escapes) {
      const found = scan("planted.ts", source);
      expect(
        found.structural.length + found.blaming.length,
        `the guard did not see:\n${source}`,
      ).toBeGreaterThan(0);
    }
  });

  /**
   * G-3 — THE DELTA, MEASURED. Seven spellings a critic used to walk past the stemmed
   * blacklist, plus the two the blacklist did catch. The new rule catches all nine for the
   * same reason (no cause emits them); the old list is re-run here on the same strings so
   * the improvement is a number in this file rather than a claim in a comment.
   */
  it("catches every rewrite-prescription the blame-word list could not", () => {
    const ROUND_10_BLAME_WORDS = [
      "rephras", "reword", "rewrit", "in your own words", "wording",
      "phrase it", "describe it differently",
    ];
    const sentences: [string, boolean][] = [
      // [sentence, did the round-10 stemmed list see it?]
      ["Try rephrasing your idea so we can understand it better.", true],
      // MEASURED, against the brief: `re-word` was listed as an escape and is NOT one —
      // "re-wording" contains "wording", which the round-10 list carries. The other six are.
      ["Try re-wording your idea and run the check again.", true],
      ["Please re-phrase your description and retry.", false],
      ["Consider re-writing the pitch before another attempt.", false],
      ["Reformulate your idea and try again.", false],
      ["Restate what the product does, then rerun.", false],
      ["Be more specific about what your product does.", false],
      ["Clarify your description and run the check again.", false],
      ["Add detail to what you submitted before retrying.", false],
    ];
    const n = (name: string) => name.split("|").join("");
    const NEXT = n("failure|_next_step");
    for (const [sentence, oldRuleSaw] of sentences) {
      const source = `const iv = notEvaluatedBlock({ ${NEXT}: ${JSON.stringify(sentence)} });`;
      const found = scan("planted.ts", source);
      expect(
        found.structural.length + found.blaming.length,
        `the derive-or-fail rule did not see: ${sentence}`,
      ).toBeGreaterThan(0);
      expect(
        ROUND_10_BLAME_WORDS.some((w) => sentence.toLowerCase().includes(w)),
        `the round-10 list's verdict on "${sentence}" has changed; re-derive the delta`,
      ).toBe(oldRuleSaw);
    }
    // …and the register it checks against is the producer's, not a list in this file.
    expect(PIPELINE_REFUSAL_SENTENCES.size).toBeGreaterThanOrEqual(14);
    for (const sentence of PIPELINE_REFUSAL_SENTENCES) {
      expect(
        ROUND_10_BLAME_WORDS.some((w) => sentence.toLowerCase().includes(w)),
        `a SHIPPED refusal sentence prescribes a rewrite: ${sentence}`,
      ).toBe(false);
    }
  });

  /**
   * H-1 — the derivation predicate used to be a taint-PRESENCE check, so any expression that
   * merely NAMED the producer passed the copy rule however it mangled the sentence afterwards.
   * The first two are the shapes a round-12 critic measured; the rest were found here by
   * asking what else "mentions the producer" admits. Every one was GREEN.
   */
  it("catches copy that names the producer and then transforms it", () => {
    const n = (name: string) => name.split("|").join("");
    const NEXT = n("failure|_next_step");
    const HEAD = n("head|line");
    const laundered = [
      // blame appended to a derived sentence
      "`${SEED_FAILURE_COPY.identity_judge_unavailable." + NEXT + "}"
        + " If it keeps stopping, try describing your idea differently.`",
      // the sentence inverted: whose fault it was, reversed
      "SEED_FAILURE_COPY.identity_judge_unavailable." + NEXT
        + '.replace("our side", "your side")',
      // string concatenation rather than a template
      "SEED_FAILURE_COPY.identity_judge_unavailable." + NEXT
        + ' + " Be more specific about what your product does."',
      // producer copy truncated to drop the half that takes the blame
      "SEED_FAILURE_COPY.identity_judge_unavailable." + NEXT + ".split(\". \")[0]",
      // a ternary with one derived arm and one hand-written arm
      'flag ? SEED_FAILURE_COPY.identity_judge_unavailable.' + NEXT
        + ' : "Reword your pitch and try again."',
      // the producer named in a dead branch, the shipped text hand-authored
      "[SEED_FAILURE_COPY].length > 0 ? \"Clarify your description and retry.\" : \"\"",
    ];
    for (const value of laundered) {
      for (const key of [NEXT, HEAD]) {
        const source = `const iv = notEvaluatedBlock({ ${key}: ${value} });`;
        const found = scan("planted.ts", source);
        expect(
          found.structural.length + found.blaming.length,
          `a transformation of producer copy passed the copy rule: ${key}: ${value}`,
        ).toBeGreaterThan(0);
      }
    }
  });

  it("still allows deriving from the generated fixture, and varying a narrative scalar", () => {
    const allowed = [
      `const a: IdeaValidation = { desk_limits: GRADED.desk_limits };`,
      `const b = notEvaluatedBlock({ experiment_ladder: gradedBlock().experiment_ladder });`,
      `const c = notEvaluatedBlock({ alternatives: { ...gradedBlock().alternatives, count: 2 } });`,
      // A DIFFERENT cause's next step — the ValidationVerdict contract test needs exactly
      // this. DEV-C called it a legitimate hand-write; it is not one any more, because the
      // register the producer owns is vendored and the real sentence is available here.
      `const d = notEvaluatedBlock({`
        + ` failure_next_step: SEED_FAILURE_COPY.identity_changed_during_scoring.next_step });`,
      // Deleting a field: how the legacy-artifact tests are written.
      `const f = notEvaluatedBlock({ failure_next_step: undefined });`,
      // A graded outcome's headline is composed from the idea, so it is not a closed set and
      // the copy rule deliberately does not reach it.
      `const g = notEvaluatedBlock({ outcome: "worth_testing", headline: "ReplyContext shows up." });`,
      `const e = notEvaluatedBlock({ user_idea_text: "A browser extension." });`,
    ];
    for (const source of allowed) {
      const found = scan("allowed.ts", source);
      expect(show([...found.structural, ...found.blaming]), source).toEqual([]);
    }
  });

  it("has no hand-authored structured idea-check value", () => {
    const { structural } = scanTree();
    expect(
      show(structural),
      structural.length
        ? "These specs compose a value the pipeline owns. Derive it from notEvaluatedBlock() / "
          + "gradedBlock() (__tests__/fixtures/ideaValidationBlocks.ts) instead — a block the "
          + "pipeline cannot produce is what made three rounds of refused-page assertions pass "
          + "vacuously, and HOW the value is spelled has nothing to do with it."
        : undefined,
    ).toEqual([]);
  });

  it("has no refusal copy a spec invented instead of taking from the producer", () => {
    const { blaming } = scanTree();
    expect(
      show(blaming),
      blaming.length
        ? "These specs put a refusal sentence in front of a reader that no typed cause "
          + "emits. Take it from SEED_FAILURE_COPY (fixtures/ideaValidationBlocks.ts, "
          + "generated from the producer) or from the block itself. This is what replaced "
          + "the blame-word blacklist: a sentence that blames the user for a failure that "
          + "is ours is unwritable because no cause carries one — the register does not "
          + "have to guess which words it would be spelled with."
        : undefined,
    ).toEqual([]);
  });
});

describe("ValidationVerdict · the graded control (withheld, not deleted)", () => {
  it("still renders both cards, the full ladder and the provisional hedge", () => {
    const view = render(ValidationVerdict, {
      props: { data: gradedBlock(), rerunHref: RERUN },
    });
    expect(view.container.textContent ?? "").toContain("What this check cannot see");
    expect(view.container.textContent ?? "").toContain("Lowest-cost next test");
    expect(view.container.querySelectorAll(".iv-ladder li")).toHaveLength(4);
    expect(view.container.querySelector(".iv-rung-next")?.textContent ?? "")
      .toContain("Run 5 problem interviews");
    expect(view.container.querySelector(".iv-verdict .iv-eyebrow")?.textContent?.trim())
      .toBe("Idea check · provisional");
  });
});
