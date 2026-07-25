import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import ProgressRing from "../ProgressRing.svelte";

describe("ProgressRing score help", () => {
  afterEach(cleanup);

  it("uses the product's 0–100 display scale and caller-provided meaning", () => {
    const view = render(ProgressRing, {
      props: {
        value: 0.82,
        label: "Feasibility",
        description: "Whether the core product is technically possible with the known data and integrations.",
        animate: false,
      },
    });

    expect(view.getByText(/Feasibility: 82%/)).toBeTruthy();
    expect(view.getByText(/Whether the core product is technically possible/)).toBeTruthy();
    expect(view.queryByText(/Excellent|Strong|Moderate|Needs Work|Critical/)).toBeNull();
  });
});
