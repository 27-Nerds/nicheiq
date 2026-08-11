import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import ResearchContextNotes from "../ResearchContextNotes.svelte";
import captured from "./fixtures/qualityCaveats.captured.json";
import {
  CLAUSE_DASH,
  INTERNAL_TOKEN,
  LOWER_CASED_START,
  PRODUCER_PHRASE,
} from "./fixtures/coverageNoteAssertions";

/**
 * `fixtures/qualityCaveats.captured.json` is CAPTURED, not written: each entry records the
 * run artifact and the JSON path its `value` was copied from byte-for-byte, so a test here
 * cannot assert against prose the pipeline never produced. Eight caveats, chosen off a sweep
 * of the 165 distinct `data_quality_summary.quality_caveats` + `user_adjustments` values
 * under `output/` — one per defect class the old hand-rolled chain shipped.
 *
 * The assertion regexes are shared with the PAID report's suite, which renders the same two
 * fields through `CoverageNotes.svelte` — see `fixtures/coverageNoteAssertions.ts`.
 */
const RAW_CAVEATS = captured.map((entry) => entry.value);
function caveat(fragment: string): string {
  const hit = RAW_CAVEATS.find((value) => value.includes(fragment));
  if (!hit) throw new Error(`no captured caveat contains ${fragment}`);
  return hit;
}

function renderNotes(coverageNotes: string[]): string[] {
  const view = render(ResearchContextNotes, { props: { coverageNotes, userAdjustments: [] } });
  (view.container.querySelector("details") as HTMLDetailsElement).open = true;
  const notes = [...view.container.querySelectorAll("li")].map((li) => li.textContent ?? "");
  cleanup();
  return notes;
}

describe("ResearchContextNotes", () => {
  afterEach(cleanup);

  it("materializes pipeline notes and wallet classes as buyer-facing copy", async () => {
    const view = render(ResearchContextNotes, {
      props: {
        coverageNotes: [
          'Calibration note for "Signal Desk" cites a data route, but the route verifier did not confirm it (data_access_model: unverified). Treat the market-fit score as unverified on the data-route dimension.',
        ],
        userAdjustments: [],
        marketReality: {
          incumbents: [{ name: "Known tool", pricing: "$29/month", focus: "Alerts", gap: "Workflow" }],
          wallet: { wallet_class: "paying", evidence: "Several adopted tools publish paid plans." },
        },
      },
    });

    await fireEvent.click(view.getByText("Data caveats"));
    expect(view.getByText(/Research caveat for "Signal Desk"/)).toHaveTextContent(
      "uses a data source, but the source check did not confirm it (Data access: Not verified)",
    );
    await fireEvent.click(view.getByText("Market reality"));
    expect(view.getByText("Paid tools are established")).toBeInTheDocument();
    expect(view.container.textContent).not.toMatch(
      /Calibration note|route verifier|data_access_model|data route|market-fit score|\bpaying\b/,
    );
  });

  it("rewrites every remaining pipeline caveat from the real exemplar", async () => {
    const view = render(ResearchContextNotes, {
      props: {
        coverageNotes: [
          "“Reconcile controlled medication dispensing, wastage, and physical counts” was prioritised for ideation as the closest match to your niche focus; research scored a related pain higher on severity (“Prepare complete controlled-substance records for DEA audits”, 0.82 vs 0.68).",
          "Novelty/obviousness collapsed to exact complements this run — treat the two originality axes as one signal.",
          "Idea-set coverage — validated pains with no idea: Transfer Cubex and inventory procedures to new clinic staff; Match PIMS inventory counts and reports to physical stock. Concentration may reflect where the real opportunity is, not a defect — shown for your judgment.",
        ],
        userAdjustments: [],
      },
    });

    await fireEvent.click(view.getByText("Data caveats"));
    expect(view.getByText(/was used as the main idea focus/)).toHaveTextContent(
      "received a higher severity score: 82 versus 68",
    );
    expect(view.getByText(/Distinctiveness and conventionality/)).toHaveTextContent(
      "Treat them as one signal.",
    );
    expect(view.getByText(/2 validated problems have no matching idea yet/)).toHaveTextContent(
      "review it before narrowing the shortlist",
    );
    expect(view.container.textContent).not.toMatch(
      /prioritised for ideation|research scored|Novelty\/obviousness|Idea-set coverage|[—–]/i,
    );
  });

  it("omits each unavailable exemplar price and never prints the wallet enum", async () => {
    const view = render(ResearchContextNotes, {
      props: {
        coverageNotes: [],
        userAdjustments: [],
        marketReality: {
          incumbents: [
            { name: "VetSnap", pricing: "$300/mo", focus: "Compliance", gap: "Operations" },
            { name: "IDEXX Neo", pricing: "$290/mo flat", focus: "PIMS", gap: "Inventory" },
            { name: "Covetrus Pulse", pricing: "unknown", focus: "Practice management", gap: "Pharmacy" },
            { name: "ezyVet", pricing: "unknown", focus: "PIMS", gap: "Drug logging" },
            { name: "DaySmart Vet", pricing: "$99-399/mo", focus: "Records", gap: "Automation" },
            { name: "Avimark", pricing: "unknown", focus: "Legacy PIMS", gap: "Integrations" },
            { name: "Cornerstone", pricing: "unknown", focus: "PIMS", gap: "Cloud features" },
            { name: "Hippo Manager", pricing: "unknown", focus: "Practice management", gap: "Inventory" },
            { name: "NaVetor", pricing: "unknown", focus: "PIMS", gap: "Compliance" },
            { name: "Cubex", pricing: "unknown", focus: "Dispensing", gap: "PIMS integration" },
          ],
          wallet: { wallet_class: "paying", evidence: "$99-399/mo plans are already in use." },
        },
      },
    });

    await fireEvent.click(view.getByText("Market reality"));
    expect(view.getByRole("columnheader", { name: "Pricing" })).toBeInTheDocument();
    expect(view.getByText("$300/mo")).toBeInTheDocument();
    expect(view.getByText("$290/mo flat")).toBeInTheDocument();
    expect(view.getByText("$99-399/mo")).toBeInTheDocument();
    const unavailablePriceCell = view.getByText("Covetrus Pulse").closest("tr")?.querySelectorAll("td")[1];
    expect(unavailablePriceCell).toHaveTextContent("");
    expect(view.getByText("Paid tools are established")).toBeInTheDocument();
    expect(view.container.textContent).not.toMatch(/\bunknown\b|\bpaying\b/i);
  });

  it("omits the pricing column when no comparable tool has a published price", async () => {
    const view = render(ResearchContextNotes, {
      props: {
        coverageNotes: [],
        userAdjustments: [],
        marketReality: {
          incumbents: [
            { name: "Tool A", pricing: "unknown", focus: "Scheduling", gap: "Reporting" },
            { name: "Tool B", pricing: "unknown", focus: "Payments", gap: "Exports" },
          ],
        },
      },
    });

    await fireEvent.click(view.getByText("Market reality"));
    expect(view.queryByRole("columnheader", { name: "Pricing" })).not.toBeInTheDocument();
  });

  // ───────────────────────────────────────────────────────────────────────────
  // The shared authority. `userFacingNote` used to end in a blind replace of every
  // em/en dash by ". " and never called `humanizeInternalJargon` — so it was the third
  // hand-rolled sanitiser in this family, and the only one with no owner for `WTP`.
  // ───────────────────────────────────────────────────────────────────────────

  it("prints no internal field name and no lower-cased sentence start for any captured caveat", () => {
    const rendered = renderNotes(RAW_CAVEATS);
    expect(rendered).toHaveLength(RAW_CAVEATS.length);
    for (const [index, note] of rendered.entries()) {
      const where = `${captured[index].file} ${captured[index].path}`;
      expect(note, where).not.toMatch(INTERNAL_TOKEN);
      expect(note, where).not.toMatch(LOWER_CASED_START);
      expect(note, where).not.toMatch(PRODUCER_PHRASE);
      expect(note, where).not.toMatch(CLAUSE_DASH);
    }
  });

  it("reads the coverage note's concentration clause, which the producer joins in front", () => {
    // `unified_solution_crew.py:9583-9592` "; ".joins a concentration note and an
    // uncovered-pains note under one head. Round 1's pattern required the second clause to
    // follow the head immediately, so this shape fell through to the word rules and printed
    // "Idea-set coverage — 3 of 5 ideas address …" with the producer's own em dash.
    const [note] = renderNotes([caveat("ideas address \"Inability")]);
    expect(note).toBe(
      '5 of 7 ideas address "Inability to verify grey-market peptide purity and safety". '
        + "1 validated problem has no matching idea yet: Fear of accelerating cancer growth "
        + "with angiogenic peptides. This concentration may point to the strongest "
        + "opportunity, so review it before narrowing the shortlist.",
    );
  });

  it("glosses the PainPoint repr the coverage checker interpolates into a caveat", () => {
    const [note] = renderNotes([caveat("representative_quote=")]);
    // The FIFTH key. It has no underscore, so `INTERNAL_TOKEN`'s snake_case branch could not
    // see it and `title='Burnout and Mental Health Struggles'` reached the buyer for a whole
    // round with the suite reporting the map complete.
    expect(note).toContain("problem title='Burnout and Mental Health Struggles'");
    expect(note).toContain("severity score=0.9");
    expect(note).toContain("commercial-intent score=0.6");
    expect(note).toContain("representative quote=");
    expect(note).toContain("source platform='Reddit r/gamedev'");
    // The buyer's own words inside the repr are a QUOTATION and stay verbatim.
    expect(note).toContain("I am burnt the F out.");
  });

  it("renames the acronym and the field name the coverage caveat pairs them with", () => {
    const [note] = renderNotes([caveat("pain_points_addressed")]);
    expect(note).toContain("the #1 pain point by severity+commercial intent");
    expect(note).toContain("the selected solution's addressed problems list");
  });

  it("names the SEO volume table the ratio caveat compares against", () => {
    const [note] = renderNotes([caveat("seo_analytics")]);
    expect(note).toContain("vs SEO analytics total volume (1,908,170)");
  });

  it("turns a clause dash into a CAPITALISED sentence, on both captured shapes", () => {
    const [probe, cap] = renderNotes([
      caveat("Mechanism-parity probe"),
      caveat("the diversity cap of 2"),
    ]);
    expect(probe).toContain("for 11 of 13 ideas. This usually means the searches");
    expect(cap).toContain("across source'). Above the diversity cap of 2.");
  });

  it("keeps a tight en-dash range intact and re-renders its own output unchanged", () => {
    const once = renderNotes([caveat("15–20 minutes")]);
    // `\s*[—–]\s*` matched the range with ZERO spaces, so a second pass printed
    // "takes 15. 20 minutes" — the surface renders a re-read report, so it must be idempotent.
    expect(once[0]).toContain("takes 15–20 minutes, causing delays to work");
    expect(renderNotes(once)).toEqual(once);
  });

  it("still owns the calibration-note stanza no shared authority covers", () => {
    const [note] = renderNotes([caveat("AgencySeatTaxCalc")]);
    expect(note).toBe(
      'Research caveat for "AgencySeatTaxCalc" uses a data source "Deterministic arithmetic '
        + "on the user's own inputs\" to support market fit, but the source check did not confirm "
        + "it (Data access: Not verified). Treat the market fit as not verified for data access.",
    );
  });
});
