import { describe, it, expect } from "vitest";
import { normalizeDataAccess, humanizeTag } from "./ideaTagLabels";

describe("normalizeDataAccess", () => {
  it("passes canonical values through unchanged", () => {
    for (const v of [
      "public",
      "freemium",
      "paywalled",
      "unofficial",
      "restricted",
      "blocked",
      "unverified",
    ]) {
      expect(normalizeDataAccess(v)).toBe(v);
    }
  });

  it("folds boundary aliases into the canonical vocabulary", () => {
    expect(normalizeDataAccess("none")).toBe("public");
    expect(normalizeDataAccess("not-data-dependent")).toBe("public");
    expect(normalizeDataAccess("official")).toBe("public");
    expect(normalizeDataAccess("licensed")).toBe("paywalled");
  });

  it("is case- and whitespace-insensitive", () => {
    expect(normalizeDataAccess("  None ")).toBe("public");
    expect(normalizeDataAccess("PUBLIC")).toBe("public");
  });

  it("returns null for empty and unknown values so callers can omit the field", () => {
    expect(normalizeDataAccess(undefined)).toBeNull();
    expect(normalizeDataAccess(null)).toBeNull();
    expect(normalizeDataAccess("")).toBeNull();
    expect(normalizeDataAccess("mystery-source")).toBeNull();
  });

  it("yields a display label instead of a raw token for legacy values", () => {
    // Regression: "none" used to render literally as "Data: None".
    expect(humanizeTag(normalizeDataAccess("none"))).toBe("Public data");
    expect(humanizeTag(normalizeDataAccess("not-data-dependent"))).toBe("Public data");
  });
});
