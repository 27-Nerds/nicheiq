import { describe, expect, it } from "vitest";
import { sourceFrameLabel } from "../sourceFrameLabels";

describe("sourceFrameLabel", () => {
  it("labels user-triggered candidate origins without guessing unknown values", () => {
    expect(sourceFrameLabel("user_seed")).toBe("Submitted idea");
    expect(sourceFrameLabel("owner_synthesis")).toBe("Branched direction");
    expect(sourceFrameLabel("additional_batch")).toBe("Additional batch");
    expect(sourceFrameLabel("unknown")).toBe("");
  });
});
