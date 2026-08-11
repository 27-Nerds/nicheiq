/**
 * The withheld-evidence banner is read by three surfaces from one constant, so its words
 * have to survive the weakest of the three: a read-only share visitor who changed nothing,
 * on a page that may render no market framing at all.
 *
 * Two rewrites have already shipped false statements here. The first promised the return of
 * "market framing" that never left (niche framing is classified `niche` in
 * backend/src/routes/schemas/sharedDiscoveryPayload.ts and keeps serving). The second named
 * "the ranked snapshot" as withheld while a ranked list of ideas rendered directly beneath
 * the banner.
 *
 * The previous version of this file is why the second one was hard to fix: six of its ten
 * assertions were literal prose pins (/^The candidate list is current, but/, /analyst take/,
 * /ranked snapshot/), so correcting the false clause meant deleting the test that guarded it.
 * A prose pin blocks the next legitimate copy fix. Everything below pins BEHAVIOUR instead:
 * the claim that must be made, and the four classes of claim that must not be. Any rewrite
 * clearing these is free to change every word.
 */
import { describe, expect, it } from "vitest";

import { EVIDENCE_WITHHELD_DETAIL, EVIDENCE_WITHHELD_TITLE } from "../labels";

const COPY = `${EVIDENCE_WITHHELD_TITLE} ${EVIDENCE_WITHHELD_DETAIL}`;

// ── The rule (see the "claims about the analysis" test below) ──
//
// Applied per CLAUSE, not per string. A hedge token sitting anywhere in the constant
// proves nothing: "The written analysis is out of date, so we may restore it later" is a
// flat staleness assertion with the hedge parked in a different clause, and a
// presence-in-string check passes it.

/** Definite references to the run's written analysis. Extend this if the copy ever renames
 *  it; the "names the analysis at all" assertion below fails loudly if it goes unmatched,
 *  so a rename cannot silently make the rule vacuous. "guidance" is deliberately absent:
 *  the shipped copy uses it indefinitely ("guidance for a different set of ideas"), which
 *  is a claim about a hypothetical document, not about this run's analysis. */
const ANALYSIS_SUBJECT = /\b(?:written analysis|analysis|analyst take|write[- ]?up)\b/i;

/** Epistemic hedges. Each must sit in the SAME clause as the claim it weakens. */
const HEDGE = /\b(?:cannot confirm|can(?:'|’)?t confirm|can not confirm|unable to confirm|may|might)\b/i;

/** Freshness/currency predicates. Even hedged, these frame the unknown as the AGE of the
 *  analysis; the thing that is actually unknown is whether it BINDS to the ideas on screen.
 *  Four of the six reasons are unverifiability, where the analysis may be perfectly
 *  current, so age is the wrong axis regardless of how softly it is asserted. */
const FRESHNESS_PREDICATE =
  /\b(?:current|up[- ]to[- ]date|out of date|outdated|stale|fresh|old(?:er)?|recent|latest|no longer (?:current|accurate|valid))\b/i;

/** Sentences, then clauses. Clause breaks are conjunction-anchored rather than every comma,
 *  so a hedge is never severed from its own object by an appositive. */
function clausesOf(copy: string): string[] {
  return copy
    .split(/(?<=[.!?])\s+/)
    .flatMap((sentence) =>
      sentence.split(
        /(?:,\s*|\s+)(?=(?:so|but|yet|because|while|though|although|however|rather than)\b)|;\s*/i,
      ),
    )
    .map((clause) => clause.trim())
    .filter(Boolean);
}

/** Every clause that refers to the analysis must carry its own hedge and must not be a
 *  freshness claim. Returns one named violation per offending clause. */
function analysisClaimViolations(label: string, copy: string): string[] {
  const violations: string[] = [];
  for (const clause of clausesOf(copy)) {
    if (!ANALYSIS_SUBJECT.test(clause)) continue;
    if (!HEDGE.test(clause)) {
      violations.push(`${label}: unhedged claim about the analysis -> "${clause}"`);
    }
    if (FRESHNESS_PREDICATE.test(clause)) {
      violations.push(`${label}: analysis framed as a freshness claim -> "${clause}"`);
    }
  }
  return violations;
}

function copyViolations(title: string, detail: string): string[] {
  // Title and detail are checked as separate strings: the title carries no terminal
  // period, so concatenating them would fuse the title into the detail's first sentence.
  return [...analysisClaimViolations("title", title), ...analysisClaimViolations("detail", detail)];
}

describe("EVIDENCE_WITHHELD copy", () => {
  it("still states that the ideas themselves are current", () => {
    // The banner sits above a live, votable, ranked list on two of the three surfaces.
    // Whatever else it says, it must not read as "this list is broken".
    expect(EVIDENCE_WITHHELD_DETAIL).toMatch(/\bideas\b[^.]*\bare current\b/i);
  });

  it("claims the binding is unconfirmed, never flatly that the analysis is stale", () => {
    // THE RULE, symmetric to the market-sentence rule below: the banner may only make the
    // weakest claim that is true in every state that raises it.
    //
    // `UntrustedRunArtifactReason` (backend/src/services/currentSelectionContext.ts:30-36)
    // has six values. Only TWO are staleness:
    //   version_mismatch    the analysis was written against a different pool version
    //   content_mismatch    the stored fingerprint disagrees with the ideas on screen
    // The other FOUR are UNVERIFIABILITY, where the analysis may describe these very ideas:
    //   legacy_missing_version, legacy_missing_fingerprint
    //       every job created before migration 20260809180000_candidate_pool_version, which
    //       leaves the binding NULL because it "cannot be reconstructed safely"; the check
    //       then fails closed. That is every pre-migration job in AWAITING_SELECTION.
    //   unresolvable_candidate_pool
    //       the pool could not be read, so nothing was compared.
    //   preview_unavailable
    //       returned purely on `status !== 'AWAITING_SELECTION'`, which includes
    //       REGENERATING (isSelectionPhase covers it). backend
    //       discoveryShares.portfolioSummary.test.ts asserts the fingerprint STILL MATCHES
    //       until the new batch lands, so "out of date" is false on every
    //       "generate more ideas" click.
    // A flat staleness assertion is therefore false in four of six states, and so is any
    // claim that puts the analysis on a freshness axis at all.
    expect(copyViolations(EVIDENCE_WITHHELD_TITLE, EVIDENCE_WITHHELD_DETAIL)).toEqual([]);
  });

  it("names the analysis, so the rule above cannot pass vacuously", () => {
    // If a rewrite renames the analysis to a noun ANALYSIS_SUBJECT does not know, no clause
    // is analysis-bearing and the rule holds trivially. Fail here instead, loudly, so the
    // fix is "teach ANALYSIS_SUBJECT the new noun" rather than a silently disarmed guard.
    expect(
      clausesOf(`${EVIDENCE_WITHHELD_TITLE}. ${EVIDENCE_WITHHELD_DETAIL}`)
        .filter((clause) => ANALYSIS_SUBJECT.test(clause)).length,
    ).toBeGreaterThan(0);
  });

  it("rejects the four drafts a presence-in-string hedge check let through", () => {
    // The guard this replaced asked only whether a hedge token appeared SOMEWHERE in the
    // detail. Every draft below satisfies that and is still false in most of the six
    // states, so each one is proof that presence-in-string is not the rule. These are
    // rejected counterexamples, never shipped text; they cannot ossify the live copy.
    const rejected: Array<[string, string, string]> = [
      // Hedge parked in a second clause, leaving a flat staleness assertion in the first.
      ["hedge in another clause", EVIDENCE_WITHHELD_TITLE,
        "The written analysis is out of date, so we may restore it later"],
      // The round-19 detail: "is not" is the same flat assertion, only elided.
      ["round-19 flat staleness", EVIDENCE_WITHHELD_TITLE,
        "The ideas themselves are current. The written analysis of them is not, so we are "
        + "holding it back rather than show guidance that describes an earlier set. Anything "
        + "still shown about the market describes the niche as a whole, not these ideas."],
      // The round-15 shape: an unhedged promise about what the analysis will do.
      ["round-15 return promise", EVIDENCE_WITHHELD_TITLE,
        "The ideas themselves are current. The written analysis will return after refresh. "
        + "Anything still shown about the market describes the niche as a whole, not these ideas."],
      // Hedged, but on the wrong axis: four of six reasons are unverifiability, where the
      // analysis may be perfectly current and only its binding to these ideas is unknown.
      ["freshness-axis title", "We can't confirm the analysis is current", EVIDENCE_WITHHELD_DETAIL],
    ];
    for (const [name, title, detail] of rejected) {
      expect(copyViolations(title, detail), name).not.toEqual([]);
    }
  });

  it("does not reuse internal vocabulary (enumerated regressions, not the rule)", () => {
    // Backward-looking list: each entry shipped once. It is kept for cheap regression
    // value and is NOT a definition of "internal vocabulary" -- it would not catch
    // framing, payload, pool, revision, receipt, manifest or materialized. The rule the
    // copy is actually held to is the first assertion above plus the market-sentence
    // assertion below; this list only stops the exact words that already went out.
    //
    // Each of these renders somewhere the banner does not: `alternative_solutions` is the
    // Phase 2/3 full report (ReportContent.svelte), and snapshot/version/artifact are
    // internal nouns with no on-screen referent at all. Naming them either contradicts what
    // is visible or means nothing to a buyer.
    for (const jargon of [/ranked snapshot/i, /evidence snapshot/i, /\bsnapshot\b/i,
      /\bartifacts?\b/i, /this version/i, /\bfingerprints?\b/i, /\bdossiers?\b/i]) {
      expect(COPY).not.toMatch(jargon);
    }
  });

  it("uses the module's own nouns for the pool", () => {
    // "shortlist" is the user's SAVED collection (SHORTLIST_NOUN) and "candidates" is a
    // retired synonym; using either to mean the generated pool overloads a live term.
    expect(COPY).not.toMatch(/shortlist/i);
    expect(COPY).not.toMatch(/candidates?\b/i);
  });

  it("does not attribute the staleness to something the reader did", () => {
    // On the public share the viewer is `interactive={false}` and can only vote or comment,
    // so any "your change" phrasing addresses the wrong person.
    expect(COPY).not.toMatch(/your (?:latest |recent )?(?:change|edit|update)/i);
    expect(COPY).not.toMatch(/you (?:changed|edited|updated)/i);
  });

  it("does not promise the return of framing that never left", () => {
    expect(COPY).not.toMatch(/market framing[^.]*will return/i);
    expect(COPY).not.toMatch(/will return after refresh/i);
  });

  it("keeps claims about the market conditional, for surfaces that render none", () => {
    // /selection/* subroutes show the banner with no Reality Check card beside it, so a flat
    // assertion that market framing is on screen would be false there.
    const marketSentence = EVIDENCE_WITHHELD_DETAIL
      .split(/(?<=\.)\s+/)
      .find((s) => /\bmarket\b/i.test(s));
    expect(marketSentence).toBeDefined();
    expect(marketSentence).toMatch(/\b(?:any|anything|if)\b/i);
  });

  it("obeys the module's no-dash copy rule", () => {
    expect(COPY).not.toMatch(/[–—]/);
  });

  it("stays short enough to read above a live list", () => {
    expect(EVIDENCE_WITHHELD_DETAIL.length).toBeLessThanOrEqual(280);
  });
});
