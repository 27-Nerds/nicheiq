import { describe, expect, it } from "vitest";
import { normalizePainSignal } from "$lib/utils/painSignal";

describe("normalizePainSignal", () => {
  it("strips rank prefix, severity metadata, and rationale tail from a live legacy entry", () => {
    expect(
      normalizePainSignal(
        "1. Adverse Reactions and Safety Concerns from Nail Products (Severity 8.0/10, Mentions 10): reduces risk by flagging harmful ingredients",
      ),
    ).toBe("Adverse Reactions and Safety Concerns from Nail Products");
  });

  it("passes a clean modern pain title through unchanged", () => {
    const clean = "Adverse reactions and safety concerns from nail products";
    expect(normalizePainSignal(clean)).toBe(clean);
  });

  it("strips a rank prefix alone", () => {
    expect(normalizePainSignal("12. Manual invoice chasing")).toBe("Manual invoice chasing");
  });

  it("strips severity metadata without a rationale tail", () => {
    expect(normalizePainSignal("Manual invoice chasing (Severity 6.5/10, Mentions 4)")).toBe(
      "Manual invoice chasing",
    );
  });

  it("keeps text between the parenthetical and the rationale colon", () => {
    expect(
      normalizePainSignal("Manual invoice chasing (Severity 6.5/10) for freelancers: wastes hours"),
    ).toBe("Manual invoice chasing for freelancers");
  });

  it("leaves a colon alone when there is no severity parenthetical", () => {
    const titled = "Setup: hard to configure staging environments";
    expect(normalizePainSignal(titled)).toBe(titled);
  });

  it("trims surrounding whitespace", () => {
    expect(normalizePainSignal("  2.  Churn blindness (Severity 7/10): no early signal ")).toBe(
      "Churn blindness",
    );
  });
});
