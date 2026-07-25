import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { TOUR_CHAPTERS, TOUR_MIN_VIEWPORT } from "../chapters";

const chapters = Object.values(TOUR_CHAPTERS);

describe("tour chapters", () => {
  it("covers the four surfaces with the planned step counts", () => {
    expect(Object.keys(TOUR_CHAPTERS).sort()).toEqual([
      "compare",
      "job-shortlist",
      "review",
      "risks",
    ]);
    expect(TOUR_CHAPTERS["job-shortlist"].steps).toHaveLength(5);
    expect(TOUR_CHAPTERS.compare.steps).toHaveLength(4);
    expect(TOUR_CHAPTERS.risks.steps).toHaveLength(4);
    expect(TOUR_CHAPTERS.review.steps).toHaveLength(3);
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

describe("every data-tour anchor a chapter targets exists in the source", () => {
  const FILES = [
    "src/lib/components/selection/SelectionWorkbench.svelte",
    "src/lib/components/selection/EvidenceChallenge.svelte",
    "src/routes/(app)/jobs/[jobId]/selection/+layout.svelte",
    "src/routes/(app)/jobs/[jobId]/selection/risks/+page.svelte",
    "src/routes/(app)/jobs/[jobId]/selection/review/+page.svelte",
  ];
  const source = FILES.map((f) => readFileSync(f, "utf8")).join("\n");

  const targeted = chapters
    .flatMap((c) => c.steps.map((s) => String(s.element)))
    .map((sel) => sel.match(/\[data-tour="([^"]+)"\]/)?.[1])
    .filter((name): name is string => Boolean(name));

  it("finds at least one instrumented element per data-tour anchor", () => {
    expect(targeted.length).toBeGreaterThan(0);
    for (const name of targeted) {
      expect(source, `data-tour="${name}" is targeted but never rendered`).toContain(`"${name}"`);
    }
  });
});
