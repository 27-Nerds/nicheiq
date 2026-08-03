/**
 * PRODUCER/CONSUMER CONTRACT TEST — do not hand-build the payload here.
 *
 * The thesis-grouping UI shipped dead: the pipeline emitted `idea_theses` as an OBJECT
 * (`{family_source, theses[], uncovered_families[], unassigned[]}`) with `members[]` and
 * `assumption`, while the frontend reader expected a top-level ARRAY with
 * `member_idea_names[]` and `text`. Every test passed, because every test built its
 * fixture from the frontend's own (wrong) types — a suite that mints its own fixtures
 * cannot see a producer/consumer mismatch.
 *
 * So the fixture below is CAPTURED, verbatim, from a real pipeline run
 * (`output/checkpoints/checkpoint_independent_veterinary_clinics_managing_medication_
 * 86e765e5…_20260802_150313/metadata.json`, trimmed to 2 theses / 1 uncovered family /
 * 1 unassigned idea). If the Python contract moves, this test fails.
 */

import { describe, it, expect } from "vitest";
import pipelineIdeaTheses from "./fixtures/pipelineIdeaTheses.json";
import type { IdeaThesisPartition } from "$lib/types/report";
import { readIdeaTheses, readUncoveredFamilies } from "$lib/types/ideaThesis";

/** An imported JSON module widens every string literal, so the two enum fields arrive
 *  as plain `string`. Every key name and every nesting level is still checked exactly —
 *  which is the drift this test exists to catch. */
type JsonWidened<T> = T extends string ? string
  : T extends object ? { [K in keyof T]: JsonWidened<T[K]> }
  : T;

// Compile-time half of the contract: the captured payload must satisfy the declared
// shape. `npm run check` fails here if report.ts and the pipeline disagree.
const partition: JsonWidened<IdeaThesisPartition> = pipelineIdeaTheses;
// The report field is the partition OBJECT, not an array of theses.
const report = { idea_theses: partition };

describe("ideaThesis readers — real pipeline payload", () => {
  it("reads theses out of the partition object, not a top-level array", () => {
    const theses = readIdeaTheses(report);

    expect(theses).toHaveLength(2);
    expect(theses.map((t) => t.family_id))
      .toEqual(["inventory-accuracy", "controlled-drug-compliance"]);
    expect(theses[0].display_label).toBe("Inventory Accuracy");
    expect(theses[0].buyer).toBe("Inventory Manager");
    expect(theses[0].triggering_job)
      .toBe("Maintain accurate medication counts and reorder levels");
    expect(theses[0].lead_idea_name).toBe("CountPad Vet");
    expect(theses[0].incumbent_status).toBe("partial");
    expect(theses[0].incumbent_vendors).toEqual(["VetSnap"]);
  });

  it("reads members[] objects, carrying the per-variant angle", () => {
    const [, compliance] = readIdeaTheses(report);

    expect(compliance.members.map((m) => m.name)).toEqual([
      "Controlled Medication Dispense Closeout Ledger",
      "VetControlled Ledger",
      "WitnessWire",
    ]);
    expect(compliance.members[0].winning_angle).toBe("vertical_workflow");
    expect(compliance.members[2].winning_angle).toBe("novel_differentiation");
    expect(compliance.members[1].idea_tier).toBe("merged");
    expect(compliance.members[1].source_frame).toBe("workflow");
  });

  it("reads the fatal assumption off `assumption`, attributed to idea and source field", () => {
    const [inventory] = readIdeaTheses(report);

    expect(inventory.fatal_assumptions).toHaveLength(2);
    expect(inventory.fatal_assumptions[0].idea_name).toBe("CountPad Vet");
    expect(inventory.fatal_assumptions[0].source_field).toBe("data_access_model");
    expect(inventory.fatal_assumptions[0].assumption).toContain("Required data route is not confirmed");
    expect(inventory.fatal_assumptions[1].assumption)
      .toBe("Serves an adjacent audience, not the stated target audience.");
  });

  it("reads uncovered families from inside the partition, not off the report root", () => {
    const uncovered = readUncoveredFamilies(report);

    expect(uncovered).toHaveLength(1);
    expect(uncovered[0].family_id).toBe("system-integration");
    expect(uncovered[0].display_label).toBe("System Integration");
    expect(uncovered[0].member_pain_ids).toHaveLength(2);
    // `reason` is an enum token; `reason_detail` is the sentence.
    expect(uncovered[0].reason).toBe("no_surviving_idea");
    expect(uncovered[0].reason_detail).toContain("no concept survived");

    // The array form the reader used to demand carries nothing.
    expect(readUncoveredFamilies({ uncovered_families: partition.uncovered_families }))
      .toHaveLength(0);
  });

  it("leaves the partition's unassigned ideas out of the thesis list", () => {
    // They are not a family — the workbench folds them into "Not yet grouped" by
    // simply not finding them in any thesis's members.
    const names = readIdeaTheses(report).flatMap((t) => t.members.map((m) => m.name));

    expect(partition.unassigned.map((u) => u.idea_name)).toEqual(["CS Log Reconciliation Audit Kit"]);
    expect(names).not.toContain("CS Log Reconciliation Audit Kit");
  });

  it("drops a malformed entry instead of crashing the ranked list", () => {
    const theses = readIdeaTheses({
      idea_theses: { theses: [{ display_label: "No family id" }, partition.theses[0]] },
    });

    expect(theses.map((t) => t.family_id)).toEqual(["inventory-accuracy"]);
    expect(readIdeaTheses(null)).toEqual([]);
    expect(readIdeaTheses({ idea_theses: "nope" })).toEqual([]);
    expect(readUncoveredFamilies({})).toEqual([]);
  });
});
