import { describe, expect, it } from "vitest";
import { formatPayabilityClass } from "./payability";

describe("formatPayabilityClass", () => {
  it.each([
    ["personal-wallet", "Personal wallet"],
    ["prosumer-wallet", "Prosumer wallet"],
    ["smb-budget", "Small-business budget"],
    ["corporate-budget", "Corporate budget"],
    ["mixed", "Mixed"],
  ])("maps the live enum value %s", (slug, label) => {
    expect(formatPayabilityClass(slug)).toBe(label);
  });

  it("falls back to a title-cased slug for unknown values", () => {
    expect(formatPayabilityClass("business-wallet")).toBe("Business wallet");
    expect(formatPayabilityClass("enterprise_budget")).toBe("Enterprise budget");
  });

  it("returns null for missing values", () => {
    expect(formatPayabilityClass(null)).toBeNull();
    expect(formatPayabilityClass(undefined)).toBeNull();
    expect(formatPayabilityClass("  ")).toBeNull();
  });
});
