import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OwnerEvidenceLedger from "../OwnerEvidenceLedger.svelte";

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
    mocks.getSelectionOwnerEvidence.mockResolvedValue({ evidence: [], editable: true });
  });

  it("adds evidence to the exact idea revision and lens without changing scores", async () => {
    mocks.createSelectionOwnerEvidence.mockResolvedValue({ evidence: row, cached: false });
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
    await fireEvent.click(view.getByText(/Your evidence/));
    await fireEvent.click(view.getByRole("button", { name: "Add evidence" }));
    expect(view.getByRole("dialog", { name: "Add owner evidence" })).toBeInTheDocument();
    expect(view.getByText("Signal Desk for operators · revision 3 · demand lens")).toBeInTheDocument();
    expect(view.getByText("Record one concrete observation")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Why this matters" })).toBeInTheDocument();
    await fireEvent.click(view.getByRole("radio", { name: "Contradicts" }));
    await fireEvent.input(view.getByLabelText("Finding title", { exact: false }), { target: { value: row.title } });
    await fireEvent.input(view.getByLabelText("What did you observe?", { exact: false }), { target: { value: row.content } });
    await fireEvent.click(view.getByRole("button", { name: "Add to ledger" }));

    await waitFor(() => expect(mocks.createSelectionOwnerEvidence).toHaveBeenCalledWith("job-1", expect.objectContaining({
      ideaId: "idea-signal",
      ideaRevision: 3,
      lens: "demand",
      position: "CONTRADICTS",
      title: row.title,
      content: row.content,
    })));
    expect(view.getByText(row.title)).toBeInTheDocument();
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

    const dialog = await view.findByRole("dialog", { name: "Add owner evidence" });
    expect(within(dialog).getByDisplayValue(firstPrefill.values.title)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Observed on/)).toHaveValue("2026-07-15");
    expect(mocks.createSelectionOwnerEvidence).not.toHaveBeenCalled();

    await fireEvent.input(within(dialog).getByLabelText("Finding title", { exact: false }), {
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
    expect(within(dialog).getByDisplayValue("My unsaved owner title")).toBeInTheDocument();
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
    expect(view.queryByRole("dialog", { name: "Add owner evidence" })).not.toBeInTheDocument();
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

    await waitFor(() => expect(view.getByText(/1 active/)).toBeInTheDocument());
    await fireEvent.click(view.getByText(/Your evidence/));
    await fireEvent.click(view.getByText(row.title));
    await fireEvent.click(view.getByRole("button", { name: "Retract" }));
    expect(view.getByRole("dialog", { name: "Retract owner evidence" })).toBeInTheDocument();
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
