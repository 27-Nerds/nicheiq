import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { TOUR_CHAPTERS, TOUR_MIN_VIEWPORT } from "../chapters";

const chapters = Object.values(TOUR_CHAPTERS);

describe("tour chapters", () => {
  it("covers the five surfaces with the planned step counts", () => {
    expect(Object.keys(TOUR_CHAPTERS).sort()).toEqual([
      "compare",
      "job-shortlist",
      "review",
      "risks",
      "validate-report",
    ]);
    expect(TOUR_CHAPTERS["job-shortlist"].steps).toHaveLength(7);
    expect(TOUR_CHAPTERS.compare.steps).toHaveLength(4);
    expect(TOUR_CHAPTERS.risks.steps).toHaveLength(4);
    expect(TOUR_CHAPTERS.review.steps).toHaveLength(3);
    expect(TOUR_CHAPTERS["validate-report"].steps).toHaveLength(6);
  });

  it("gives every step a string selector, a title and a description", () => {
    for (const chapter of chapters) {
      for (const step of chapter.steps) {
        expect(typeof step.element, `${chapter.id}: element`).toBe("string");
        expect(step.popover?.title, `${chapter.id}: title`).toBeTruthy();
        expect(step.popover?.description, `${chapter.id}: description`).toBeTruthy();
      }
    }
  });

  it("declares an explicit side and align on every step", () => {
    // Left to driver.js, an unfittable side silently falls back left -> right -> top ->
    // bottom, and when none fit it pins the popover to the bottom of the screen with no
    // arrow — detached from whatever it is describing.
    for (const chapter of chapters) {
      for (const step of chapter.steps) {
        expect(step.popover?.side, `${chapter.id}: ${step.popover?.title}`).toBeDefined();
        expect(step.popover?.align, `${chapter.id}: ${step.popover?.title}`).toBeDefined();
      }
    }
  });

  it("never sets button labels per step", () => {
    // REGRESSION: driver.js resolves `doneBtnText` from the CONFIG when rendering the
    // final step. Setting the labels per step left the last button reading "Next", so
    // the tour never looked finished.
    for (const chapter of chapters) {
      for (const step of chapter.steps) {
        const popover = step.popover as Record<string, unknown> | undefined;
        expect(popover?.nextBtnText, `${chapter.id}`).toBeUndefined();
        expect(popover?.doneBtnText, `${chapter.id}`).toBeUndefined();
        expect(popover?.prevBtnText, `${chapter.id}`).toBeUndefined();
      }
    }
  });

  it("keeps every chapter id in the backend's allowed key space", () => {
    // tutorialProgressService rejects anything else with a 400.
    for (const chapter of chapters) {
      expect(chapter.id).toMatch(/^[a-z][a-z0-9-]*$/);
      expect(chapter.id.length).toBeLessThanOrEqual(64);
    }
  });

  it("gives every chapter invitation copy", () => {
    for (const chapter of chapters) {
      expect(chapter.invitation.heading.length).toBeGreaterThan(0);
      expect(chapter.invitation.heading.length).toBeLessThanOrEqual(40);
      expect(chapter.invitation.body.length).toBeGreaterThan(0);
      expect(chapter.invitation.body.length).toBeLessThanOrEqual(120);
    }
  });

  it("keeps popover copy within the widths the layout was measured against", () => {
    for (const chapter of chapters) {
      for (const step of chapter.steps) {
        expect(String(step.popover?.title).length, `${chapter.id}`).toBeLessThanOrEqual(42);
        expect(String(step.popover?.description).length, `${chapter.id}`).toBeLessThanOrEqual(200);
      }
    }
  });

  it("never quotes a price or calls an optional step required", () => {
    const banned = /\b\d+\s*credits?\b|\byou must\b|\brequired step\b/i;
    for (const chapter of chapters) {
      for (const step of chapter.steps) {
        const copy = `${step.popover?.title} ${step.popover?.description}`;
        expect(copy, `${chapter.id}: ${step.popover?.title}`).not.toMatch(banned);
      }
    }
  });

  it("suppresses below the width where the dock and guide card collapse", () => {
    expect(TOUR_MIN_VIEWPORT).toBe(1024);
  });
});

/**
 * REGRESSION GUARD. `[data-tour="shortlist-checkbox"]` was targeted by a step for months
 * while the row it belonged to had moved inside a collapsible thesis card, so the step
 * silently bottom-pinned itself with no arrow. A dead selector produces no error anywhere
 * — driver.js skips it — which is exactly why it needs a test.
 *
 * This checks every token of every selector against the markup that renders it: the
 * attribute VALUE has to be one a component actually emits, and an `aria-labelledby`
 * target has to be an id that exists. It cannot prove a node is on screen at any given
 * moment (several anchors are deliberately conditional), only that something renders it.
 */
describe("every selector a chapter targets resolves against the source", () => {
  const FILES = [
    "src/lib/components/selection/SelectionWorkbench.svelte",
    "src/lib/components/selection/DecisionRail.svelte",
    "src/lib/components/selection/EvidenceChallenge.svelte",
    "src/lib/components/selection/AssumptionMap.svelte",
    "src/lib/components/ui/SegmentControl.svelte",
    "src/routes/(app)/jobs/[jobId]/selection/+layout.svelte",
    "src/routes/(app)/jobs/[jobId]/selection/compare/+page.svelte",
    "src/routes/(app)/jobs/[jobId]/selection/risks/+page.svelte",
    "src/routes/(app)/jobs/[jobId]/selection/review/+page.svelte",
    // "Check my idea" report page (validate-report chapter anchors)
    "src/lib/components/sections/ValidationVerdict.svelte",
    "src/routes/(app)/jobs/[jobId]/+page.svelte",
  ];
  const source = FILES.map((f) => readFileSync(f, "utf8")).join("\n");

  /** Every value an attribute is given, whether written flat or through a ternary. */
  function valuesOf(attribute: string): Set<string> {
    const found = new Set<string>();
    const pattern = new RegExp(`${attribute}=(?:"([^"]*)"|\\{([^{}]*)\\})`, "g");
    for (const [, literal, expression] of source.matchAll(pattern)) {
      if (literal) found.add(literal);
      for (const [, quoted] of (expression ?? "").matchAll(/"([^"]*)"/g)) found.add(quoted);
    }
    return found;
  }

  const ids = new Set([...source.matchAll(/\bid="([^"{]+)"/g)].map(([, id]) => id));
  // A wrapper component's `label` prop becomes the rendered aria-label (SegmentControl).
  const labels = new Set([...valuesOf("aria-label"), ...valuesOf("label")]);
  const byAttribute: Record<string, Set<string>> = {
    "data-tour": valuesOf("data-tour"),
    "data-annotation-anchor": valuesOf("data-annotation-anchor"),
    "aria-label": labels,
    "aria-labelledby": ids,
    role: valuesOf("role"),
  };

  const targets = chapters.flatMap((chapter) =>
    chapter.steps.map((step) => ({
      where: `${chapter.id}: ${step.popover?.title}`,
      selector: String(step.element),
    })),
  );

  it("renders every attribute and id a step selector asks for", () => {
    expect(targets.length).toBeGreaterThan(0);
    for (const { where, selector } of targets) {
      let checked = 0;
      for (const [, attribute, value] of selector.matchAll(/\[([\w-]+)="([^"]+)"\]/g)) {
        const known = byAttribute[attribute];
        expect(known, `${where}: no source rule for [${attribute}]`).toBeDefined();
        expect([...known!], `${where}: ${attribute}="${value}" is targeted but never rendered`)
          .toContain(value);
        checked += 1;
      }
      for (const [, id] of selector.matchAll(/#([\w-]+)/g)) {
        expect([...ids], `${where}: #${id} is targeted but no element carries that id`)
          .toContain(id);
        checked += 1;
      }
      expect(checked, `${where}: selector "${selector}" asserts nothing`).toBeGreaterThan(0);
    }
  });

  it("keeps the single-instance anchors guarded to one row", () => {
    // These three sit inside `{#each}` bodies. Without a guard the selector would match
    // once per row, and driver.js would spotlight whichever came first in document order.
    const workbench = readFileSync("src/lib/components/selection/SelectionWorkbench.svelte", "utf8");
    expect(workbench).toContain('data-tour={key === tourAnchorKey ? "shortlist-checkbox" : undefined}');
    expect(workbench).toContain('data-tour={groupIndex === 0 ? "thesis-group" : undefined}');
    expect(workbench).toContain('data-tour="recommendation-split"');
  });
});
