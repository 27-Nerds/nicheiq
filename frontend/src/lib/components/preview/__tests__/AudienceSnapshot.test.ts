import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import AudienceSnapshot from "../AudienceSnapshot.svelte";
import type { AudienceMapping } from "$lib/types/report";

const fiveSegments: AudienceMapping = {
  primary_target_segment: "DIY biohackers",
  audience_segments: [
    { segment_name: "DIY biohackers" },
    { segment_name: "Longevity clinics" },
    { segment_name: "Peptide resellers" },
    { segment_name: "Compounding pharmacists" },
    { segment_name: "Fitness coaches" },
  ],
};

describe("AudienceSnapshot segment disclosure", () => {
  afterEach(cleanup);

  it("caps at 3 segments by default with accurate count copy and a collapsed toggle", () => {
    const view = render(AudienceSnapshot, { props: { data: fiveSegments } });

    expect(view.getByText("Peptide resellers")).toBeInTheDocument();
    expect(view.queryByText("Compounding pharmacists")).not.toBeInTheDocument();
    expect(view.getByText(/Showing the first 3 of 5 captured segments\./)).toBeInTheDocument();

    const toggle = view.getByRole("button", { name: "Show all 5 segments" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("reveals all segments on toggle, updates copy, and collapses back", async () => {
    const view = render(AudienceSnapshot, { props: { data: fiveSegments } });

    const toggle = view.getByRole("button", { name: "Show all 5 segments" });
    await fireEvent.click(toggle);

    expect(view.getByText("Compounding pharmacists")).toBeInTheDocument();
    expect(view.getByText("Fitness coaches")).toBeInTheDocument();
    expect(view.getByText(/Showing all 5 captured segments\./)).toBeInTheDocument();

    const collapse = view.getByRole("button", { name: "Show fewer" });
    expect(collapse).toHaveAttribute("aria-expanded", "true");

    await fireEvent.click(collapse);
    expect(view.queryByText("Compounding pharmacists")).not.toBeInTheDocument();
    expect(view.getByText(/Showing the first 3 of 5 captured segments\./)).toBeInTheDocument();
  });

  it("renders no disclosure when 3 or fewer segments exist", () => {
    const view = render(AudienceSnapshot, {
      props: {
        data: {
          audience_segments: fiveSegments.audience_segments!.slice(0, 3),
        },
      },
    });

    expect(view.queryByRole("button", { name: /Show all/ })).not.toBeInTheDocument();
    expect(view.queryByText(/captured segments/)).not.toBeInTheDocument();
  });
});
