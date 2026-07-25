import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OwnerEvidenceLedger, { discardOwnerEvidenceDraft, ownerEvidenceDraftIsDirty } from "../OwnerEvidenceLedger.svelte";

const mocks = vi.hoisted(() => ({
  getSelectionOwnerEvidence: vi.fn(),
  createSelectionOwnerEvidence: vi.fn(),
  retractSelectionOwnerEvidence: vi.fn(),
}));

vi.mock("$lib/api", () => mocks);

const row = {
  id: "123e4567-e89b-42d3-a456-426614174000",
  jobId: "job-1",
  ideaId: "idea-signal",
  ideaRevision: 3,
  lens: "demand" as const,
  kind: "CUSTOMER_QUOTE" as const,
  position: "CONTRADICTS" as const,
  title: "Interview with an operations lead",
  content: "The team has the problem but will not pay for another dashboard.",
  sourceUrl: "https://example.com/interview",
  observedAt: "2026-07-15T00:00:00.000Z",
  createdAt: "2026-07-16T00:00:00.000Z",
  retractedAt: null,
  retractionReason: null,
};

describe("OwnerEvidenceLedger", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    // The draft lives in module state so it can survive remounts; reset it
    // between tests so cases stay independent.
    discardOwnerEvidenceDraft();
    mocks.getSelectionOwnerEvidence.mockResolvedValue({ evidence: [], editable: true });
  });

  it("adds evidence to the exact idea revision and lens without changing scores", async () => {
    const savedRow = { ...row, title: row.content };
    mocks.createSelectionOwnerEvidence.mockResolvedValue({ evidence: savedRow, cached: false });
    const onChanged = vi.fn();
    const view = render(OwnerEvidenceLedger, {
      props: {
        jobId: "job-1",
        ideaId: "idea-signal",
        ideaTitle: "Signal Desk for operators",
        ideaRevision: 3,
        lens: "demand",
        onChanged,
      },
    });

    await waitFor(() => expect(mocks.getSelectionOwnerEvidence).toHaveBeenCalledWith("job-1"));
    await fireEvent.click(view.getByText("Your evidence", { selector: "strong" }));
    await fireEvent.click(view.getByRole("button", { name: "Add your evidence" }));
    const editor = view.getByRole("region", { name: "Record what you learned" });
    expect(editor).toBeInTheDocument();
    expect(within(editor).getByText("Signal Desk for operators · revision 3 · customer demand")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Why this matters" })).toBeInTheDocument();
    const observation = within(editor).getByLabelText("What did you learn?", { exact: false });
    const sourceType = within(editor).getByLabelText("Source type", { exact: false });
    expect(observation.compareDocumentPosition(sourceType) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await fireEvent.input(observation, { target: { value: row.content } });
    await fireEvent.change(sourceType, { target: { value: "CUSTOMER_QUOTE" } });
    await fireEvent.click(within(editor).getByRole("radio", { name: "Raises a concern" }));
    await fireEvent.click(within(editor).getByRole("button", { name: "Save evidence" }));

    await waitFor(() => expect(mocks.createSelectionOwnerEvidence).toHaveBeenCalledWith("job-1", expect.objectContaining({
      ideaId: "idea-signal",
      ideaRevision: 3,
      lens: "demand",
      kind: "CUSTOMER_QUOTE",
      position: "CONTRADICTS",
      title: row.content,
      content: row.content,
    })));
    expect(view.getAllByText(savedRow.title)).toHaveLength(2);
    expect(onChanged).toHaveBeenCalledOnce();
  });

  it("opens an analyst evidence draft without adding it and preserves dirty owner input", async () => {
    const firstPrefill = {
      requestId: "copilot-evidence-1",
      ideaId: "idea-signal",
      ideaRevision: 3,
      lens: "demand" as const,
      values: {
        kind: "CUSTOMER_QUOTE" as const,
        position: "CONTRADICTS" as const,
        title: "Interview with an operations lead",
        content: "The team has the problem but will not pay for another dashboard.",
        sourceUrl: "https://example.com/interview",
        observedAt: "2026-07-15T00:00:00.000Z",
      },
    };
    const baseProps = {
      jobId: "job-1",
      ideaId: "idea-signal",
      ideaTitle: "Signal Desk for operators",
      ideaRevision: 3,
      lens: "demand" as const,
    };
    const view = render(OwnerEvidenceLedger, {
      props: { ...baseProps, prefill: firstPrefill },
    });

    const editor = await view.findByRole("region", { name: "Record what you learned" });
    expect(within(editor).getByDisplayValue(firstPrefill.values.title)).toBeInTheDocument();
    expect(within(editor).getByLabelText(/Observed on/)).toHaveValue("2026-07-15");
    expect(within(editor).getByDisplayValue(firstPrefill.values.sourceUrl)).toBeInTheDocument();
    expect(mocks.createSelectionOwnerEvidence).not.toHaveBeenCalled();

    await fireEvent.input(within(editor).getByLabelText("Short title", { exact: false }), {
      target: { value: "My unsaved owner title" },
    });
    await view.rerender({
      ...baseProps,
      prefill: {
        ...firstPrefill,
        requestId: "copilot-evidence-2",
        values: { ...firstPrefill.values, title: "A replacement analyst title" },
      },
    });

    expect(await view.findByRole("alert")).toHaveTextContent("unfinished evidence form");
    expect(within(editor).getByDisplayValue("My unsaved owner title")).toBeInTheDocument();
    expect(mocks.createSelectionOwnerEvidence).not.toHaveBeenCalled();
  });

  it("rejects an analyst evidence draft for another exact revision or lens", async () => {
    const view = render(OwnerEvidenceLedger, {
      props: {
        jobId: "job-1",
        ideaId: "idea-signal",
        ideaRevision: 3,
        lens: "demand",
        prefill: {
          requestId: "copilot-evidence-stale",
          ideaId: "idea-signal",
          ideaRevision: 2,
          lens: "competition",
          values: { title: "Old evidence" },
        },
      },
    });

    await waitFor(() => expect(view.getByRole("alert")).toHaveTextContent("different candidate revision or evidence lens"));
    expect(view.queryByRole("region", { name: "Record what you learned" })).not.toBeInTheDocument();
  });

  it("keeps entered evidence when source validation fails and maps Not sure to context", async () => {
    const observation = "The source describes the problem but does not show buying intent.";
    mocks.createSelectionOwnerEvidence.mockResolvedValue({
      evidence: { ...row, position: "CONTEXT", kind: "LINK", title: observation, content: observation },
      cached: false,
    });
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });

    await waitFor(() => expect(mocks.getSelectionOwnerEvidence).toHaveBeenCalledWith("job-1"));
    await fireEvent.click(view.getByText("Your evidence", { selector: "strong" }));
    await fireEvent.click(view.getByRole("button", { name: "Add your evidence" }));
    const editor = view.getByRole("region", { name: "Record what you learned" });
    const observationField = within(editor).getByLabelText("What did you learn?", { exact: false });
    await fireEvent.input(observationField, { target: { value: observation } });
    await fireEvent.change(within(editor).getByLabelText("Source type", { exact: false }), {
      target: { value: "LINK" },
    });
    await fireEvent.click(within(editor).getByRole("radio", { name: "Not sure" }));
    await fireEvent.click(within(editor).getByRole("button", { name: "Save evidence" }));

    const sourceField = within(editor).getByLabelText("Source URL", { exact: false });
    expect(await within(editor).findByText("Add the web address for this source.")).toBeInTheDocument();
    expect(observationField).toHaveValue(observation);
    expect(sourceField).toHaveFocus();
    expect(mocks.createSelectionOwnerEvidence).not.toHaveBeenCalled();

    await fireEvent.input(sourceField, { target: { value: "ftp://example.com/source" } });
    await fireEvent.blur(sourceField);
    expect(await within(editor).findByText("Use a web address that starts with http:// or https://.")).toBeInTheDocument();

    await fireEvent.input(sourceField, { target: { value: "https://example.com/source" } });
    expect(within(editor).queryByText("Use a web address that starts with http:// or https://.")).not.toBeInTheDocument();
    await fireEvent.click(within(editor).getByRole("button", { name: "Save evidence" }));
    await waitFor(() => expect(mocks.createSelectionOwnerEvidence).toHaveBeenCalledWith("job-1", expect.objectContaining({
      kind: "LINK",
      position: "CONTEXT",
      title: observation,
      content: observation,
      sourceUrl: "https://example.com/source",
    })));
  });

  it("keeps a typed draft bound to its original lens", async () => {
    const onReturnToDraft = vi.fn();
    const baseProps = {
      jobId: "job-1",
      ideaId: "idea-signal",
      ideaTitle: "Signal Desk for operators",
      ideaRevision: 3,
      lens: "demand" as const,
    };
    const view = render(OwnerEvidenceLedger, { props: { ...baseProps, onReturnToDraft } });

    await waitFor(() => expect(mocks.getSelectionOwnerEvidence).toHaveBeenCalledWith("job-1"));
    await fireEvent.click(view.getByRole("button", { name: "Add your evidence" }));
    const editor = view.getByRole("region", { name: "Record what you learned" });
    // The add form lives inside the ledger disclosure, not orphaned below it.
    expect(editor.closest("details")).not.toBeNull();
    await fireEvent.input(within(editor).getByLabelText("What did you learn?", { exact: false }), {
      target: { value: "Owners already pay for a manual workaround." },
    });
    expect(ownerEvidenceDraftIsDirty()).toBe(true);

    await view.rerender({ ...baseProps, lens: "competition" as const, onReturnToDraft });

    const warning = view.getByRole("alert");
    expect(warning).toHaveTextContent("This draft belongs to Signal Desk for operators · revision 3 · customer demand.");
    expect(view.queryByLabelText("What did you learn?", { exact: false })).not.toBeInTheDocument();
    await fireEvent.click(within(warning).getByRole("button", { name: "Return to draft" }));
    expect(onReturnToDraft).toHaveBeenCalledWith({
      jobId: "job-1",
      ideaId: "idea-signal",
      ideaRevision: 3,
      lens: "demand",
    });
    await view.rerender({ ...baseProps, onReturnToDraft });
    expect(view.getByLabelText("What did you learn?", { exact: false })).toHaveValue(
      "Owners already pay for a manual workaround.",
    );
  });

  it("keeps the typed draft bound to its original candidate across a remount", async () => {
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });
    await waitFor(() => expect(mocks.getSelectionOwnerEvidence).toHaveBeenCalledWith("job-1"));
    await fireEvent.click(view.getByRole("button", { name: "Add your evidence" }));
    await fireEvent.input(view.getByLabelText("What did you learn?", { exact: false }), {
      target: { value: "Kept across the remount." },
    });
    view.unmount();

    const onReturnToDraft = vi.fn();
    const next = render(OwnerEvidenceLedger, {
      props: {
        jobId: "job-1",
        ideaId: "idea-other",
        ideaRevision: 1,
        lens: "demand",
        onReturnToDraft,
      },
    });
    const warning = await next.findByRole("alert");
    expect(warning).toHaveTextContent("This draft belongs to Selected candidate · revision 3 · customer demand.");
    await fireEvent.click(within(warning).getByRole("button", { name: "Return to draft" }));
    expect(onReturnToDraft).toHaveBeenCalledWith({
      jobId: "job-1",
      ideaId: "idea-signal",
      ideaRevision: 3,
      lens: "demand",
    });
    expect(next.queryByLabelText("What did you learn?", { exact: false })).not.toBeInTheDocument();
  });

  it("keeps the save announcement after an invalidateAll remount", async () => {
    const savedRow = { ...row, title: row.content };
    mocks.createSelectionOwnerEvidence.mockResolvedValue({ evidence: savedRow, cached: false });
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });
    await waitFor(() => expect(mocks.getSelectionOwnerEvidence).toHaveBeenCalledWith("job-1"));
    await fireEvent.click(view.getByRole("button", { name: "Add your evidence" }));
    const editor = view.getByRole("region", { name: "Record what you learned" });
    await fireEvent.input(within(editor).getByLabelText("What did you learn?", { exact: false }), {
      target: { value: row.content },
    });
    await fireEvent.change(within(editor).getByLabelText("Source type", { exact: false }), {
      target: { value: "CUSTOMER_QUOTE" },
    });
    await fireEvent.click(within(editor).getByRole("radio", { name: "Raises a concern" }));
    await fireEvent.click(within(editor).getByRole("button", { name: "Save evidence" }));
    await waitFor(() => expect(view.getByText(/Evidence saved. Recheck demand/)).toBeInTheDocument());
    view.unmount();

    const next = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });
    await waitFor(() => expect(mocks.getSelectionOwnerEvidence).toHaveBeenCalled());
    // "Evidence loaded" lands in a separate status node; the save
    // announcement survives the remount instead of being clobbered.
    expect(next.getByText(/Evidence saved. Recheck demand/)).toBeInTheDocument();
  });

  it("wires the effect-picker error to the radiogroup", async () => {
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });
    await waitFor(() => expect(mocks.getSelectionOwnerEvidence).toHaveBeenCalledWith("job-1"));
    await fireEvent.click(view.getByRole("button", { name: "Add your evidence" }));
    const editor = view.getByRole("region", { name: "Record what you learned" });
    await fireEvent.input(within(editor).getByLabelText("What did you learn?", { exact: false }), {
      target: { value: "An observation without a chosen effect." },
    });
    await fireEvent.change(within(editor).getByLabelText("Source type", { exact: false }), {
      target: { value: "NOTE" },
    });
    await fireEvent.click(within(editor).getByRole("button", { name: "Save evidence" }));

    const group = within(editor).getByRole("radiogroup", { name: "What does this evidence suggest?" });
    await waitFor(() => expect(group).toHaveAttribute("aria-invalid", "true"));
    expect(group.getAttribute("aria-describedby")).toContain("owner-evidence-position-error");
    expect(within(editor).getByText("Choose how this affects the idea.")).toHaveAttribute(
      "id",
      "owner-evidence-position-error",
    );
  });

  it("marks owner evidence rows as unverified", async () => {
    mocks.getSelectionOwnerEvidence.mockResolvedValue({ evidence: [row], editable: true });
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });

    await waitFor(() => expect(view.getByText(/1 saved/)).toBeInTheDocument());
    expect(view.getByText("Unverified")).toBeInTheDocument();
  });

  it("surfaces the retract error on the reason field", async () => {
    mocks.getSelectionOwnerEvidence.mockResolvedValue({ evidence: [row], editable: true });
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });
    await waitFor(() => expect(view.getByText(/1 saved/)).toBeInTheDocument());
    await fireEvent.click(view.getByText(row.title));
    await fireEvent.click(view.getByRole("button", { name: "Retract" }));
    await fireEvent.click(view.getByRole("button", { name: "Confirm retraction" }));

    const reason = view.getByLabelText("Why are you retracting this?", { exact: false });
    await waitFor(() => expect(reason).toHaveAttribute("aria-invalid", "true"));
    expect(view.getByRole("alert")).toHaveTextContent("Add a short reason for the retraction.");
    expect(mocks.retractSelectionOwnerEvidence).not.toHaveBeenCalled();
  });

  it("routes footer Cancel through the retract dirty-close gate", async () => {
    mocks.getSelectionOwnerEvidence.mockResolvedValue({ evidence: [row], editable: true });
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });

    await waitFor(() => expect(view.getByText(/1 saved/)).toBeInTheDocument());
    await fireEvent.click(view.getByText(row.title));
    await fireEvent.click(view.getByRole("button", { name: "Retract" }));
    await fireEvent.input(view.getByLabelText("Why are you retracting this?", { exact: false }), {
      target: { value: "The attribution needs correction." },
    });
    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));

    expect(view.getByRole("dialog", { name: "Retract evidence" })).toBeInTheDocument();
    expect(view.getByRole("status")).toHaveTextContent(
      "Your reason has not been saved. Close again to discard it.",
    );
    await fireEvent.click(view.getByRole("button", { name: "Discard changes" }));
    await waitFor(() => expect(view.queryByRole("dialog", { name: "Retract evidence" })).not.toBeInTheDocument());
  });

  it("retracts in place and keeps the immutable record visible", async () => {
    mocks.getSelectionOwnerEvidence.mockResolvedValue({ evidence: [row], editable: true });
    const retracted = {
      ...row,
      retractedAt: "2026-07-16T12:00:00.000Z",
      retractionReason: "The attribution was incorrect.",
    };
    mocks.retractSelectionOwnerEvidence.mockResolvedValue({ evidence: retracted, cached: false });
    const view = render(OwnerEvidenceLedger, {
      props: { jobId: "job-1", ideaId: "idea-signal", ideaRevision: 3, lens: "demand" },
    });

    await waitFor(() => expect(view.getByText(/1 saved/)).toBeInTheDocument());
    await fireEvent.click(view.getByText("Your evidence", { selector: "strong" }));
    await fireEvent.click(view.getByText(row.title));
    await fireEvent.click(view.getByRole("button", { name: "Retract" }));
    expect(view.getByRole("dialog", { name: "Retract evidence" })).toBeInTheDocument();
    await fireEvent.input(view.getByLabelText("Why are you retracting this?", { exact: false }), {
      target: { value: "The attribution was incorrect." },
    });
    await fireEvent.click(view.getByRole("button", { name: "Confirm retraction" }));

    await waitFor(() => expect(mocks.retractSelectionOwnerEvidence).toHaveBeenCalledWith(
      "job-1",
      row.id,
      "The attribution was incorrect.",
    ));
    expect(view.getByText("Retracted (1)")).toBeInTheDocument();
  });
});
