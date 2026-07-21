import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import DecisionBrief from "../DecisionBrief.svelte";
import type { SelectionDecisionProfile } from "$lib/types/job";

const mocks = vi.hoisted(() => ({
  saveSelectionDecisionProfile: vi.fn(),
}));

vi.mock("$lib/api", () => ({
  saveSelectionDecisionProfile: mocks.saveSelectionDecisionProfile,
}));

const SAVED_PROFILE: SelectionDecisionProfile = {
  preset: "solo_bootstrap",
  weeklyTime: "under_10",
  budget: "under_1k",
  team: "solo",
  revenueHorizon: "90_days",
  distributionAdvantages: ["seo", "community", "existing_audience"],
  strengths: "Trusted niche community",
  hardConstraints: "No 24/7 operations",
};

describe("DecisionBrief", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("saves founder constraints without presenting them as research scores", async () => {
    mocks.saveSelectionDecisionProfile.mockResolvedValue({
      selectionDecisionProfile: SAVED_PROFILE,
    });
    const onSaved = vi.fn();
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: null, onSaved },
    });

    expect(view.getByText(/They will not change the research score\./)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Add build constraints" }));
    expect(view.getByRole("dialog", { name: "Your build constraints" })).toBeInTheDocument();
    await fireEvent.click(view.getByRole("radio", { name: /Solo bootstrap/ }));
    await fireEvent.click(view.getByRole("radio", { name: "Under 10" }));
    await fireEvent.click(view.getByRole("button", { name: "Existing audience" }));
    await fireEvent.input(view.getByLabelText(/Advantages you already have/), {
      target: { value: "Trusted niche community" },
    });
    await fireEvent.input(view.getByLabelText(/Hard constraints/), {
      target: { value: "No 24/7 operations" },
    });
    await fireEvent.click(view.getByRole("button", { name: "Save build constraints" }));

    await waitFor(() => expect(mocks.saveSelectionDecisionProfile).toHaveBeenCalledOnce());
    expect(mocks.saveSelectionDecisionProfile).toHaveBeenCalledWith("job-1", SAVED_PROFILE);
    expect(onSaved).toHaveBeenCalledWith(SAVED_PROFILE);
  });

  it("summarizes a saved profile before editing", () => {
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: SAVED_PROFILE, onSaved: vi.fn() },
    });

    const summary = view.getByLabelText("Saved build constraints");
    expect(summary).toHaveTextContent("Under 10 hrs / week");
    expect(summary).toHaveTextContent("Under $1k");
    expect(summary).toHaveTextContent("Revenue within 90 days");
    expect(view.getByRole("button", { name: "Edit build constraints" })).toBeInTheDocument();
  });

  it("keeps the worksheet open and reports a save failure", async () => {
    mocks.saveSelectionDecisionProfile.mockRejectedValue(new Error("Founder context could not be saved"));
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: null, onSaved: vi.fn() },
    });

    await fireEvent.click(view.getByRole("button", { name: "Add build constraints" }));
    await fireEvent.click(view.getByRole("button", { name: "Save build constraints" }));

    expect(await view.findByRole("alert")).toHaveTextContent("Founder context could not be saved");
    expect(view.getByRole("button", { name: "Save build constraints" })).toBeInTheDocument();
  });

  it("keeps dirty context in the popup until the owner explicitly discards it", async () => {
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: null, onSaved: vi.fn() },
    });

    await fireEvent.click(view.getByRole("button", { name: "Add build constraints" }));
    await fireEvent.input(view.getByLabelText(/Hard constraints/), {
      target: { value: "No weekend operations" },
    });
    await fireEvent.click(view.getByRole("button", { name: "Close Your build constraints" }));

    expect(view.getByRole("dialog", { name: "Your build constraints" })).toBeInTheDocument();
    expect(view.getByText(/unsaved changes/i)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Discard changes" }));
    expect(view.queryByRole("dialog", { name: "Your build constraints" })).not.toBeInTheDocument();
  });
});
