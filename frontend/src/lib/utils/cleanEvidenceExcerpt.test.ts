import { describe, expect, it } from "vitest";
import { cleanEvidenceExcerpt } from "./cleanEvidenceExcerpt";

describe("cleanEvidenceExcerpt", () => {
  it("strips backslash-escaped markdown bullets and joins flattened list items (live example)", () => {
    expect(
      cleanEvidenceExcerpt("\\- 100% of samples had Tetrahydrofuran \\- 26% had Arsenic..."),
    ).toBe("100% of samples had Tetrahydrofuran · 26% had Arsenic...");
  });

  it("marks a snippet that starts mid-word with a leading ellipsis (live example)", () => {
    expect(cleanEvidenceExcerpt("g about peptides they can buy online.")).toBe(
      "…about peptides they can buy online.",
    );
  });

  it("marks a snippet that ends mid-token with a trailing ellipsis (live example)", () => {
    expect(cleanEvidenceExcerpt("People in the group keep taking reta ")).toBe(
      "People in the group keep taking…",
    );
  });

  it("strips backslash escapes before other markdown punctuation", () => {
    expect(cleanEvidenceExcerpt("See \\[the label\\] and \\*dosage\\* notes.")).toBe(
      "See [the label] and *dosage* notes.",
    );
  });

  it("drops a leading list marker instead of turning it into a separator", () => {
    expect(cleanEvidenceExcerpt("- No third-party testing at all.")).toBe(
      "No third-party testing at all.",
    );
  });

  it("collapses newlines and repeated whitespace", () => {
    expect(cleanEvidenceExcerpt("First  line\n- second line.")).toBe(
      "First line · second line.",
    );
  });

  it("leaves a clean complete quote untouched", () => {
    expect(cleanEvidenceExcerpt("The vendor never shipped my order.")).toBe(
      "The vendor never shipped my order.",
    );
  });

  it("returns an empty string for whitespace-only input", () => {
    expect(cleanEvidenceExcerpt("   \n  ")).toBe("");
  });

  it("does not double-mark a quote that already ends with an ellipsis", () => {
    expect(cleanEvidenceExcerpt("Nobody verifies purity…")).toBe("Nobody verifies purity…");
  });
});
