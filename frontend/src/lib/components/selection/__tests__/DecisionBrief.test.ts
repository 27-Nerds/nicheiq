import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DecisionBrief from "../DecisionBrief.svelte";
import type { SelectionDecisionProfile } from "$lib/types/job";

const mocks = vi.hoisted(() => ({
  getSolutions: vi.fn(),
  saveSelectionDecisionProfile: vi.fn(),
}));

vi.mock("$lib/api", () => ({
  getSolutions: mocks.getSolutions,
  saveSelectionDecisionProfile: mocks.saveSelectionDecisionProfile,
}));

const SAVED_PROFILE: SelectionDecisionProfile = {
  preset: "solo_bootstrap",
  weeklyTime: "under_10",
  budget: "under_1k",
  team: "solo",
  buildModel: "self",
  revenueHorizon: "90_days",
  distributionAdvantages: ["seo", "community", "existing_audience"],
  strengths: "Trusted niche community",
  hardConstraints: "No 24/7 operations",
};

const AUDIENCE_DRIFT = {
  requested_audience: "independent veterinary clinics across multiple locations",
  dossier_primary_segment: "Independent Single-Location General Practices with Manual Drug Logs",
  recommended_source_segments: [
    "Specialty, Emergency, and Referral Hospitals with High-Volume Controlled-Drug Workflows",
  ],
  message: "You asked to reach “independent veterinary clinics across multiple locations”. The dossier centers “Independent Single-Location General Practices with Manual Drug Logs”, while the recommendation is built for “Specialty, Emergency, and Referral Hospitals with High-Volume Controlled-Drug Workflows”. Validate that buyer shift before funding or building the recommendation.",
};

describe("DecisionBrief", () => {
  beforeEach(() => {
    mocks.getSolutions.mockResolvedValue({
      artifactVerification: "verified",
      previewReport: null,
    });
  });

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
    await fireEvent.click(view.getByRole("button", { name: "Add build limits" }));
    expect(view.getByRole("dialog", { name: "Your build limits" })).toBeInTheDocument();
    expect(view.queryByLabelText(/Advantages you already have/)).not.toBeInTheDocument();
    await fireEvent.click(view.getByRole("radio", { name: /Solo bootstrap/ }));
    await fireEvent.click(view.getByRole("radio", { name: "Under 10" }));
    await fireEvent.click(view.getByRole("button", { name: /Add launch context/ }));
    await fireEvent.click(view.getByRole("button", { name: "Existing audience" }));
    await fireEvent.input(view.getByLabelText(/Advantages you already have/), {
      target: { value: "Trusted niche community" },
    });
    await fireEvent.input(view.getByLabelText(/Hard constraints/), {
      target: { value: "No 24/7 operations" },
    });
    await fireEvent.click(view.getByRole("button", { name: "Save build limits" }));

    await waitFor(() => expect(mocks.saveSelectionDecisionProfile).toHaveBeenCalledOnce());
    expect(mocks.saveSelectionDecisionProfile).toHaveBeenCalledWith("job-1", SAVED_PROFILE);
    expect(onSaved).toHaveBeenCalledWith(SAVED_PROFILE);
  });

  it("summarizes a saved profile before editing", () => {
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: SAVED_PROFILE, onSaved: vi.fn() },
    });

    const summary = view.getByLabelText("Saved build limits");
    expect(summary).toHaveTextContent("Under 10 hrs / week");
    expect(summary).toHaveTextContent("Under $1k");
    expect(summary).toHaveTextContent("Revenue within 90 days");
    expect(view.getByRole("button", { name: "Edit build limits" })).toBeInTheDocument();
  });

  it("keeps the saved constraints readable in the compact owner summary", () => {
    const view = render(DecisionBrief, {
      props: {
        jobId: "job-1",
        profile: SAVED_PROFILE,
        variant: "summary",
        onSaved: vi.fn(),
      },
    });

    const row = view.getByLabelText("Build limits summary");
    const limits = view.getByLabelText("Saved build limits");
    expect(row).toHaveTextContent("Build limits saved");
    expect(limits).toHaveTextContent("Under 10 hrs / week");
    expect(limits).toHaveTextContent("Under $1k");
    expect(limits).toHaveTextContent("Solo");
    expect(limits).toHaveTextContent("I will build the software");
    expect(limits).toHaveTextContent("Revenue within 90 days");
    expect(limits).toHaveTextContent("SEO, Communities, Existing audience");
    expect(row.querySelectorAll("button")).toHaveLength(1);
  });

  it("keeps the worksheet open and reports a save failure", async () => {
    mocks.saveSelectionDecisionProfile.mockRejectedValue(new Error("Founder context could not be saved"));
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: null, onSaved: vi.fn() },
    });

    await fireEvent.click(view.getByRole("button", { name: "Add build limits" }));
    await fireEvent.click(view.getByRole("button", { name: "Save build limits" }));

    expect(await view.findByRole("alert")).toHaveTextContent("Founder context could not be saved");
    expect(view.getByRole("button", { name: "Save build limits" })).toBeInTheDocument();
  });

  it("offers a clearly named contractor build model and saves it separately from team size", async () => {
    const outsourced = { ...SAVED_PROFILE, buildModel: "contractor" as const };
    mocks.saveSelectionDecisionProfile.mockResolvedValue({
      selectionDecisionProfile: outsourced,
    });
    const onSaved = vi.fn();
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: SAVED_PROFILE, onSaved },
    });

    await fireEvent.click(view.getByRole("button", { name: "Edit build limits" }));
    await fireEvent.click(view.getByRole("radio", { name: "Hire a contractor or agency to build it" }));
    await fireEvent.click(view.getByRole("button", { name: "Save build limits" }));

    await waitFor(() => expect(mocks.saveSelectionDecisionProfile).toHaveBeenCalledOnce());
    expect(mocks.saveSelectionDecisionProfile).toHaveBeenCalledWith("job-1", outsourced);
    expect(onSaved).toHaveBeenCalledWith(outsourced);
  });

  it("renders a legacy profile without silently treating solo as self-build", () => {
    const { buildModel: _buildModel, ...legacy } = SAVED_PROFILE;
    const view = render(DecisionBrief, {
      props: {
        jobId: "job-1",
        profile: legacy as SelectionDecisionProfile,
        onSaved: vi.fn(),
      },
    });

    const summary = view.getByLabelText("Saved build limits");
    expect(summary).toHaveTextContent("Solo");
    expect(summary).toHaveTextContent("Not specified (legacy profile)");
    expect(summary).not.toHaveTextContent("I will build the software");
  });

  it("preserves an unspecified build model when editing a legacy profile", async () => {
    const { buildModel: _buildModel, ...legacy } = SAVED_PROFILE;
    mocks.saveSelectionDecisionProfile.mockResolvedValue({
      selectionDecisionProfile: legacy,
    });
    const onSaved = vi.fn();
    const view = render(DecisionBrief, {
      props: {
        jobId: "job-1",
        profile: legacy as SelectionDecisionProfile,
        onSaved,
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Edit build limits" }));
    expect(view.getByRole("radiogroup", { name: "Who builds the software?" })).toBeInTheDocument();
    expect(view.queryByRole("radio", { name: "I will build the software", checked: true })).not.toBeInTheDocument();
    expect(view.queryByRole("radio", { name: "Hire a contractor or agency to build it", checked: true })).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Save build limits" }));
    await waitFor(() => expect(mocks.saveSelectionDecisionProfile).toHaveBeenCalledWith("job-1", legacy));
    expect(onSaved).toHaveBeenCalledWith(legacy);
  });

  it("places the audience caveat where the recommendation is acted on", () => {
    const view = render(DecisionBrief, {
      props: {
        jobId: "job-1",
        profile: SAVED_PROFILE,
        audienceDrift: AUDIENCE_DRIFT,
        onSaved: vi.fn(),
      },
    });

    const notice = view.getByRole("note", { name: "Audience mismatch before recommendation" });
    expect(notice).toHaveTextContent("Before you act on this recommendation");
    expect(notice).toHaveTextContent(AUDIENCE_DRIFT.message);
  });

  it("loads the audience caveat from the verified production solutions payload", async () => {
    mocks.getSolutions.mockResolvedValue({
      artifactVerification: "verified",
      previewReport: { audience_mapping: { audience_drift_notice: AUDIENCE_DRIFT } },
    });
    const view = render(DecisionBrief, {
      props: { jobId: "job-live", profile: SAVED_PROFILE, onSaved: vi.fn() },
    });

    const notice = await view.findByRole("note", { name: "Audience mismatch before recommendation" });
    expect(mocks.getSolutions).toHaveBeenCalledWith("job-live");
    expect(notice).toHaveTextContent(AUDIENCE_DRIFT.message);
  });

  it("does not trust an audience caveat from an unverified solutions payload", async () => {
    mocks.getSolutions.mockResolvedValue({
      artifactVerification: "untrusted",
      previewReport: { audience_mapping: { audience_drift_notice: AUDIENCE_DRIFT } },
    });
    const view = render(DecisionBrief, {
      props: { jobId: "job-untrusted", profile: SAVED_PROFILE, onSaved: vi.fn() },
    });

    await waitFor(() => expect(mocks.getSolutions).toHaveBeenCalledWith("job-untrusted"));
    expect(view.queryByRole("note", { name: "Audience mismatch before recommendation" })).not.toBeInTheDocument();
  });

  it("renders no recommendation caveat when audiences agree", () => {
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: SAVED_PROFILE, onSaved: vi.fn() },
    });
    expect(view.queryByRole("note", { name: "Audience mismatch before recommendation" })).not.toBeInTheDocument();
  });

  it("routes the footer Cancel through the dirty gate", async () => {
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: null, onSaved: vi.fn() },
    });

    await fireEvent.click(view.getByRole("button", { name: "Add build limits" }));
    await fireEvent.click(view.getByRole("button", { name: /Add launch context/ }));
    await fireEvent.input(view.getByLabelText(/Hard constraints/), {
      target: { value: "No weekend operations" },
    });

    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));
    expect(view.getByRole("dialog", { name: "Your build limits" })).toBeInTheDocument();
    expect(view.getByText(/unsaved changes/i)).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Discard changes" }));
    expect(view.queryByRole("dialog", { name: "Your build limits" })).not.toBeInTheDocument();
  });

  it("closes a clean editor from the footer Cancel on the first click", async () => {
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: null, onSaved: vi.fn() },
    });

    await fireEvent.click(view.getByRole("button", { name: "Add build limits" }));
    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));

    expect(view.queryByRole("dialog", { name: "Your build limits" })).not.toBeInTheDocument();
    expect(view.queryByText(/unsaved changes/i)).not.toBeInTheDocument();
  });

  it("keeps dirty context in the popup until the owner explicitly discards it", async () => {
    const view = render(DecisionBrief, {
      props: { jobId: "job-1", profile: null, onSaved: vi.fn() },
    });

    await fireEvent.click(view.getByRole("button", { name: "Add build limits" }));
    await fireEvent.click(view.getByRole("button", { name: /Add launch context/ }));
    await fireEvent.input(view.getByLabelText(/Hard constraints/), {
      target: { value: "No weekend operations" },
    });
    await fireEvent.click(view.getByRole("button", { name: "Close Your build limits" }));

    expect(view.getByRole("dialog", { name: "Your build limits" })).toBeInTheDocument();
    expect(view.getByText(/unsaved changes/i)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Discard changes" }));
    expect(view.queryByRole("dialog", { name: "Your build limits" })).not.toBeInTheDocument();
  });
});
