import { describe, expect, it } from "vitest";

import { deliveryFormatLabel } from "./deliveryFormatLabels";

describe("deliveryFormatLabel()", () => {
  it("labels the public delivery-format vocabulary", () => {
    expect(deliveryFormatLabel("browser-extension")).toBe("Browser extension");
    expect(deliveryFormatLabel("api")).toBe("API");
    expect(deliveryFormatLabel("data-product")).toBe("Data product");
  });

  it("uses a readable fallback without inferring a format", () => {
    expect(deliveryFormatLabel("interactive-kiosk")).toBe("Interactive kiosk");
    expect(deliveryFormatLabel(null)).toBe("");
  });
});
