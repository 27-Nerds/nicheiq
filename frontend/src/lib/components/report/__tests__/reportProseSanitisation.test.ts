/**
 * D12, third layer: the render surfaces of the PAID Deep Research artifact.
 *
 * The string function was already "correct" for two rounds while the render layer leaked.
 * ReportBrief printed `niche_difficulty_verdict.key_challenges` verbatim under
 * "Decision-changing risks" — on the real exemplar that is
 *
 *   "The corpus drifts from the stated audience — tighten the wedge or the product will
 *    end up serving the wrong user."
 *
 * and ReportContent printed `idea_portfolio_summary` raw in the "Earlier idea-pool
 * assessment" note. So these assertions are made against the DOM, from RAW pipeline data,
 * not against the sanitiser's return value.
 *
 * The verdict fixture is the captured pipeline exemplar
 * (`$lib/selection/__tests__/fixtures/nicheDifficultyVerdict.exemplar.json`), whose
 * provenance is asserted against `src/nicheiq/utils/niche_difficulty.py` itself in
 * `buyerFacingResearchProse.test.ts`. It is never hand-written here.
 */

import { cleanup, render, within } from "@testing-library/svelte";
import { page } from "$app/state";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { NicheDifficultyVerdict, Report } from "$lib/types/report";
import exemplar from "$lib/selection/__tests__/fixtures/nicheDifficultyVerdict.exemplar.json";
import capturedAlternatives from
  "$lib/components/sections/__tests__/fixtures/alternativeSolutions.captured.json";
import capturedCaveats from
  "$lib/components/selection/__tests__/fixtures/qualityCaveats.captured.json";
import capturedAdjustments from
  "$lib/components/selection/__tests__/fixtures/userAdjustments.captured.json";
import {
  CLAUSE_DASH,
  INTERNAL_TOKEN,
  LOWER_CASED_START,
  PRODUCER_PHRASE,
} from "$lib/components/selection/__tests__/fixtures/coverageNoteAssertions";
import ReportBrief from "../ReportBrief.svelte";
import ReportContent from "$lib/components/ReportContent.svelte";

afterEach(cleanup);

const RAW_VERDICT = exemplar.niche_difficulty_verdict as NicheDifficultyVerdict;
const RAW_PORTFOLIO_SUMMARY = exemplar.idea_portfolio_summary;

const PIPELINE_VOCABULARY =
  /\bcorpus\b|cold[- ]start|web-verified|paid wedge|Thin early signal|seed it|scrape it|\bwedge\b/i;

/** Everything above, plus the raw field names the idea cards carry and the verdict does not. */
const IDEA_VOCABULARY = new RegExp(
  `${PIPELINE_VOCABULARY.source}|mechanism parity|\\bdata_feas\\b|\\bbuild_feas\\b`,
  "i",
);

const CAPTURED_ALTERNATIVES = capturedAlternatives as {
  why: string;
  file: string;
  path: string;
  value: string;
}[];

function report(overrides: Partial<Report> = {}): Report {
  return {
    niche: "Veterinary controlled-substance compliance",
    executive_summary: "A generated summary.",
    selected_solution_name: "VetLedger",
    selection_rationale: "A grounded recommendation.",
    competitor_profiles: [],
    generated_at: "2026-07-25T12:00:00.000Z",
    ...overrides,
  };
}

describe("ReportBrief renders no pipeline vocabulary", () => {
  it("sanitises the niche-difficulty challenges it prints as decision-changing risks", () => {
    const view = render(ReportBrief, {
      props: {
        report: report({ niche_difficulty_verdict: RAW_VERDICT }),
        evidenceHref: "/jobs/job-1/report?view=evidence",
        planHref: "/jobs/job-1/report?view=plan",
      },
    });

    const risks = view.getByRole("heading", { name: "Decision-changing risks" })
      .closest("section")!;

    expect(within(risks).getByText(/drifts from the stated audience/)).toHaveTextContent(
      "The collected evidence drifts from the stated audience. Tighten the entry point "
        + "or the product will end up serving the wrong user.",
    );
    expect(within(risks).getByText(/does not exist yet/)).toHaveTextContent(
      "Most ideas need a body of data that does not exist yet. Plan how to collect, "
        + "create, or obtain access to it before the product is useful.",
    );
    expect(risks.textContent).not.toMatch(PIPELINE_VOCABULARY);
    expect(risks.textContent).not.toMatch(/[—–]/);
  });

  it("leaves no pipeline vocabulary anywhere in the brief, including the conclusion", () => {
    // With no go/no-go verdict the conclusion falls back to the challenge list too, so the
    // same raw sentence reached a second slot on the page.
    const view = render(ReportBrief, {
      props: {
        report: report({
          niche_difficulty_verdict: RAW_VERDICT,
          idea_portfolio_summary: RAW_PORTFOLIO_SUMMARY,
        }),
        evidenceHref: "/jobs/job-1/report?view=evidence",
        planHref: "/jobs/job-1/report?view=plan",
      },
    });

    const text = view.container.textContent ?? "";
    expect(text).not.toMatch(PIPELINE_VOCABULARY);
    expect(text).not.toMatch(/[—–]/);
  });

  it("renders identically whether the caller pre-sanitised or not", async () => {
    const { buyerFacingReport } = await import("$lib/selection/buyerFacingResearchProse");
    const props = {
      evidenceHref: "/jobs/job-1/report?view=evidence",
      planHref: "/jobs/job-1/report?view=plan",
    };
    const raw = render(ReportBrief, {
      props: { ...props, report: report({ niche_difficulty_verdict: RAW_VERDICT }) },
    });
    const rawText = raw.container.textContent;
    cleanup();

    const pre = render(ReportBrief, {
      props: {
        ...props,
        report: buyerFacingReport(report({ niche_difficulty_verdict: RAW_VERDICT })),
      },
    });
    expect(pre.container.textContent).toBe(rawText);
  });
});

describe("ReportContent renders no pipeline vocabulary", () => {
  // The portfolio note and the incumbent-scope note live on the Evidence view's Sources
  // topic, not on the brief.
  beforeEach(() => {
    (page as unknown as { url: URL }).url = new URL(
      "http://localhost/jobs/job-1/report?view=evidence&topic=sources",
    );
  });

  it("sanitises the earlier idea-pool assessment note", () => {
    const view = render(ReportContent, {
      props: {
        report: report({
          idea_portfolio_summary: RAW_PORTFOLIO_SUMMARY,
          niche_difficulty_verdict: RAW_VERDICT,
        }),
        jobId: "job-1",
      },
    });

    const note = view.getByText(/Buyers in this niche demonstrably pay for tooling/);
    expect(note).toHaveTextContent(
      "Buyers in this niche demonstrably pay for tooling: willingness to pay is not the "
        + "primary risk. Early evidence is limited. Deep Research can validate it.",
    );
    expect(note.textContent).not.toMatch(PIPELINE_VOCABULARY);
  });

  it("keeps the incumbent-scope note out of pipeline vocabulary", () => {
    const view = render(ReportContent, {
      props: {
        report: report({
          market_reality: {
            wallet: { evidence: "Clinics already pay $290/mo for IDEXX Neo." },
            incumbents: [{ name: "IDEXX Neo", pricing: "$290/mo", focus: "PIMS", gap: "", source: "" }],
          },
        } as Partial<Report>),
        jobId: "job-1",
      },
    });

    const scope = view.getByText(/Incumbents checked on the web across the niche/);
    expect(scope.textContent).not.toMatch(PIPELINE_VOCABULARY);
    expect(scope.textContent).not.toMatch(/[—–]/);
  });
});

/**
 * `data_quality_summary.quality_caveats` and `user_adjustments`, the FOURTH sibling surface.
 *
 * The shortlist sanitised both fields for a whole round while this surface printed them as
 * they arrived: `quality_caveats` through `CoverageNotes.svelte`, which prints each string
 * verbatim, and `user_adjustments` through a bare `report.user_adjustments?.join(" ")` in the
 * "How this run was shaped" note. Measured over the 165 distinct values of the two fields
 * under `output/`, 71 printed a producer phrase here and 73 a raw em/en dash. The suite that
 * should have caught it — this one — covered the verdict and the portfolio summary and
 * silently omitted these two.
 *
 * Same doctrine as every block above: RAW captured pipeline values in, DOM out.
 */
describe("ReportContent renders no producer prose in the coverage notes", () => {
  beforeEach(() => {
    (page as unknown as { url: URL }).url = new URL(
      "http://localhost/jobs/job-1/report?view=evidence&topic=sources",
    );
  });

  const RAW_CAVEATS = capturedCaveats.map((entry) => entry.value);
  const RAW_ADJUSTMENTS = capturedAdjustments.map((entry) => entry.value);

  function coverageNotes(report_: Report): { notes: string[]; shaped: string } {
    const view = render(ReportContent, { props: { report: report_, jobId: "job-1" } });
    const block = view.container.querySelector('[aria-label="Idea-set coverage notes"]');
    expect(block, "the coverage-notes block is not on the page").toBeTruthy();
    return {
      notes: [...block!.querySelectorAll("li")].map((li) => li.textContent?.trim() ?? ""),
      shaped: view.container.querySelector(".portfolio-note")?.textContent?.trim() ?? "",
    };
  }

  it("sanitises every captured quality caveat CoverageNotes prints", () => {
    const { notes } = coverageNotes(
      report({
        data_quality_summary: { overall_data_quality: "MEDIUM", quality_caveats: RAW_CAVEATS },
      }),
    );

    expect(notes).toHaveLength(RAW_CAVEATS.length);
    for (const [index, note] of notes.entries()) {
      const where = `${capturedCaveats[index].file} ${capturedCaveats[index].path}`;
      expect(note, where).not.toMatch(PRODUCER_PHRASE);
      expect(note, where).not.toMatch(CLAUSE_DASH);
      expect(note, where).not.toMatch(INTERNAL_TOKEN);
      expect(note, where).not.toMatch(LOWER_CASED_START);
    }
  });

  it("gives the calibration caveat the same reading the shortlist gives it", () => {
    // The deep walk runs FIRST on this surface, so `data_access_model` has already become
    // "data route" by the time the stanza sees it — the raw field name the shortlist matches
    // never arrives here, and the status was left printing "(data route: unverified)".
    const calibration = RAW_CAVEATS.find((value) => value.startsWith("Calibration note"))!;
    const { notes } = coverageNotes(
      report({
        data_quality_summary: { overall_data_quality: "MEDIUM", quality_caveats: [calibration] },
      }),
    );

    expect(notes[0]).toBe(
      'Research caveat for "AgencySeatTaxCalc" uses a data source "Deterministic arithmetic '
        + "on the user's own inputs\" to support market fit, but the source check did not confirm "
        + "it (Data access: Not verified). Treat the market fit as not verified for data access.",
    );
  });

  it("sanitises the user_adjustments the run-shape note joins into a paragraph", () => {
    const { shaped } = coverageNotes(
      report({
        user_adjusted: true,
        user_adjustments: RAW_ADJUSTMENTS,
        data_quality_summary: { overall_data_quality: "MEDIUM", quality_caveats: RAW_CAVEATS },
      } as Partial<Report>),
    );

    expect(shaped).toContain(
      "Gate 2 (audience & pains): excluded 1 pain point(s) from ideation. Local bookings "
        + "often signal party intent or boundary violations.",
    );
    expect(shaped).not.toMatch(CLAUSE_DASH);
    expect(shaped).not.toMatch(PRODUCER_PHRASE);
    expect(shaped).not.toMatch(INTERNAL_TOKEN);
  });
});

/**
 * The IDEA objects hanging off the paid report. `buyerFacingReport` is field-scoped to the
 * verdict and the portfolio summary, so `alternative_solutions[]` and
 * `selected_solution_details` reached AlternativesSection and TechnicalBlueprint carrying the
 * idea vocabulary — `critic_concern` through `humanizeInternalJargon`, which knows none of
 * it, and `data_acquisition_notes` straight into the badge tooltips.
 *
 * The strings are RAW captures from the run artifacts under `output/`; the fixture records
 * the file and JSON path of each.
 */
describe("ReportContent renders no idea vocabulary on the alternatives path", () => {
  beforeEach(() => {
    (page as unknown as { url: URL }).url = new URL(
      "http://localhost/jobs/job-1/report?view=evidence&topic=competition&detail=full",
    );
  });

  const captured = CAPTURED_ALTERNATIVES;

  it("sanitises alternative_solutions[].critic_concern at the report boundary", () => {
    const view = render(ReportContent, {
      props: {
        report: report({
          alternative_solutions: captured.map((entry, index) => ({
            solution_name: `Candidate ${index + 1}`,
            summary: "A candidate.",
            ...(entry.path.endsWith("data_acquisition_notes")
              ? { data_access_model: "public", data_acquisition_notes: entry.value }
              : { critic_concern: entry.value }),
          })),
        }),
        jobId: "job-1",
      },
    });

    const alternatives = view.container.querySelector("#alternatives")!;
    expect(alternatives).toBeTruthy();
    expect(alternatives.textContent).not.toMatch(IDEA_VOCABULARY);
    expect(
      within(alternatives as HTMLElement).getByText(/defensible entry point in a high-pain area/),
    ).toBeInTheDocument();
    expect(
      within(alternatives as HTMLElement).getByText(/but feature overlap shows VetSnap/),
    ).toBeInTheDocument();
    expect(
      within(alternatives as HTMLElement).getByTitle(/User-submitted fix reports/)
        .getAttribute("title"),
    ).not.toMatch(IDEA_VOCABULARY);
  });

  it("sanitises selected_solution_details.data_acquisition_notes for the blueprint tooltip", () => {
    // TechnicalBlueprint lives on the plan view's Product & build topic, not the evidence view.
    (page as unknown as { url: URL }).url = new URL(
      "http://localhost/jobs/job-1/report?view=plan&topic=product&detail=full",
    );
    const notes = captured.find((entry) => /cold[- ]start corpus/i.test(entry.value))!.value;
    const view = render(ReportContent, {
      props: {
        report: report({
          selected_solution_details: {
            description: "The selected idea.",
            solution_name: "VetLedger",
            technical_approach: "A scheduled reconciliation job.",
            data_feasibility_score: 0.6,
            data_access_model: "public",
            data_acquisition_notes: notes,
          },
        }),
        jobId: "job-1",
      },
    });

    const badge = view.getByTitle(/User-submitted fix reports/);
    expect(badge.getAttribute("title")).toBe(
      "User-submitted fix reports via web form; requires up-front dataset but no technical "
        + "barriers.",
    );
  });
});
