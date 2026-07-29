import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RisksPage from "./+page.svelte";
import { discardOwnerEvidenceDraft } from "$lib/components/selection/OwnerEvidenceLedger.svelte";

const navMocks = vi.hoisted(() => ({
  goto: vi.fn(),
  invalidateAll: vi.fn(),
  replaceState: vi.fn(),
}));
const apiMocks = vi.hoisted(() => ({
  getSelectionAssumptions: vi.fn(),
  getSelectionChallenges: vi.fn(),
  runSelectionChallenge: vi.fn(),
  getSelectionOwnerEvidence: vi.fn(),
  createSelectionOwnerEvidence: vi.fn(),
  retractSelectionOwnerEvidence: vi.fn(),
}));

vi.mock("$app/navigation", () => navMocks);
vi.mock("$app/state", () => ({
  page: {
    url: new URL("http://localhost/jobs/job-1/selection/risks"),
    state: {},
  },
}));
vi.mock("$lib/api", () => apiMocks);
vi.mock("$lib/selection/workspaceTools", () => ({
  getWorkspaceTools: () => ({
    openVariants: vi.fn(),
    openTestPlanner: vi.fn(),
  }),
  workspaceIdeaKey: (idea: { idea_id?: string; solution_name?: string; idea_revision?: number }) =>
    `${idea.idea_id ?? idea.solution_name}@${idea.idea_revision ?? 1}`,
}));

function idea(overrides: Record<string, unknown>) {
  return {
    idea_id: "idea-a",
    idea_revision: 1,
    solution_name: "Candidate A",
    description: "A candidate.",
    value_proposition: "vp",
    ...overrides,
  };
}

function data() {
  const ideas = [
    idea({ idea_id: "idea-a", solution_name: "Candidate A" }),
    idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
  ];
  return {
    job: { id: "job-1", status: "AWAITING_SELECTION" },
    workspace: {
      ideas,
      refs: ideas.map((entry) => ({ ideaId: entry.idea_id, ideaRevision: entry.idea_revision ?? 1 })),
      canonicalQuery: "?idea=idea-a%401&idea=idea-b%401",
      lens: "demand",
    },
    decisionState: null,
  } as never;
}

describe("risks page", () => {
  beforeEach(() => {
    discardOwnerEvidenceDraft();
    apiMocks.getSelectionAssumptions.mockResolvedValue({ assumptions: [] });
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [], stale: [] });
    apiMocks.getSelectionOwnerEvidence.mockResolvedValue({ evidence: [], editable: true });
  });

  afterEach(() => {
    cleanup();
    discardOwnerEvidenceDraft();
    vi.clearAllMocks();
  });

  it("requires an inline decision before switching candidates while an evidence draft is dirty", async () => {
    const view = render(RisksPage, { props: { data: data() } });

    await fireEvent.click(await view.findByRole("button", { name: "Add your evidence" }));
    await fireEvent.input(await view.findByLabelText("What did you learn?", { exact: false }), {
      target: { value: "Unsaved observation on candidate A." },
    });

    const otherCandidate = view.getByRole("radio", { name: "Candidate B · idea 2" });
    await fireEvent.click(otherCandidate);
    expect(navMocks.goto).not.toHaveBeenCalled();
    expect(view.getByRole("alert")).toHaveTextContent("Switch candidates?");
    await waitFor(() => expect(view.getByRole("radio", { name: "Candidate A · idea 1" })).toHaveAttribute("aria-checked", "true"));

    await fireEvent.click(view.getByRole("button", { name: "Stay here" }));
    expect(view.queryByRole("alert")).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("radio", { name: "Candidate B · idea 2" }));
    await fireEvent.click(view.getByRole("button", { name: "Switch and keep draft" }));
    expect(navMocks.goto).toHaveBeenCalledWith(
      expect.stringContaining("ideaId=idea-b"),
      expect.objectContaining({ replaceState: true }),
    );
  });

  it("switches candidates without a prompt when nothing is dirty", async () => {
    const view = render(RisksPage, { props: { data: data() } });

    await fireEvent.click(await view.findByRole("radio", { name: "Candidate B · idea 2" }));
    expect(view.queryByRole("alert")).not.toBeInTheDocument();
    expect(navMocks.goto).toHaveBeenCalledWith(
      expect.stringContaining("ideaId=idea-b"),
      expect.objectContaining({ replaceState: true }),
    );
  });

  it("shows one direct questions-to-resolve empty state", async () => {
    const view = render(RisksPage, { props: { data: data() } });

    expect(await view.findByRole("heading", { name: "Questions to resolve" })).toBeInTheDocument();
    expect(await view.findByText("No questions saved yet.")).toBeInTheDocument();
    expect(view.queryByText("No questions to resolve saved yet")).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: /Show questions to resolve/ })).not.toBeInTheDocument();
    expect(view.getByRole("button", { name: /Add a question to resolve/ })).toBeInTheDocument();
  });
});
