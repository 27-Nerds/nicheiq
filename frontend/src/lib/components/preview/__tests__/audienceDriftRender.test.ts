/**
 * What the reader actually sees when the run's recommendation follows a different buyer.
 *
 * The notice is written in Python and rendered verbatim by two components on two different
 * surfaces, so neither a Python test nor a component test built from a hand-written string can
 * show that the sentence reaching the screen is fit to read. The fixture here is the exemplar
 * run's OWN output, regenerated and re-asserted by
 * `tests/unit/flows/test_audience_drift_live_path.py::test_the_frontend_fixture_is_this_run_s_own_output`.
 *
 * Two things are checked against the DOM: the sentence is present where the decision is made,
 * and it is free of the vocabulary the pipeline uses about itself. An earlier version of this
 * message opened "The dossier centers ..." on both surfaces — a word no buyer of this product
 * has been given any way to interpret.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/svelte";
import notice from "./fixtures/audienceDriftNotice.exemplar.json";
import AudienceSnapshot from "../AudienceSnapshot.svelte";
import DecisionBrief from "$lib/components/selection/DecisionBrief.svelte";

const { getSolutions } = vi.hoisted(() => ({ getSolutions: vi.fn() }));
vi.mock("$lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  getSolutions,
}));

beforeEach(() => {
  getSolutions.mockReset();
  getSolutions.mockResolvedValue({ artifactVerification: "untrusted", previewReport: null });
});
afterEach(cleanup);

/** Words the pipeline uses about itself, none of which name anything the reader can see. */
const INTERNAL_VOCABULARY = [
  "dossier",
  "corpus",
  "candidate pool",
  "source_segment",
  "primary_target_segment",
  "audience_drift",
  "fact pack",
  "materializer",
];

describe("the audience-drift notice as rendered", () => {
  it("states the buyer change beside the audience it contradicts", () => {
    render(AudienceSnapshot, {
      props: { data: { primary_target_segment: "x", audience_drift_notice: notice } },
    });

    const rendered = screen.getByRole("note", { name: "Audience mismatch" });
    expect(rendered).toHaveTextContent(notice.message);
  });

  it("states the buyer change again at the point the recommendation is acted on", () => {
    render(DecisionBrief, { props: { jobId: "job_1", profile: null, onSaved: vi.fn(), audienceDrift: notice } });

    const rendered = screen.getByRole("note", {
      name: "Audience mismatch before recommendation",
    });
    expect(rendered).toHaveTextContent(notice.message);
  });

  it.each([
    ["AudienceSnapshot", () => render(AudienceSnapshot, {
      props: { data: { primary_target_segment: "x", audience_drift_notice: notice } },
    })],
    ["DecisionBrief", () => render(DecisionBrief, {
      props: { jobId: "job_1", profile: null, onSaved: vi.fn(), audienceDrift: notice },
    })],
  ])("%s says it in words the reader was sold", (_surface, mount) => {
    const view = mount();

    const text = (view.container.textContent ?? "").toLowerCase();
    for (const term of INTERNAL_VOCABULARY) {
      expect(text).not.toContain(term);
    }
  });

  it("does not read a report written before the check as a clean bill of health", async () => {
    // A hash-verified asset from a materializer that had no buyer comparison: the field is
    // absent, not null. Silence here would tell the reader the buyer was checked and matched.
    getSolutions.mockResolvedValue({
      artifactVerification: "verified",
      previewReport: { audience_mapping: { primary_target_segment: "Something" } },
    });

    render(DecisionBrief, { props: { jobId: "job_legacy", profile: null, onSaved: vi.fn() } });

    const rendered = await screen.findByRole("note", { name: "Audience check unavailable" });
    expect(rendered).toHaveTextContent(/nothing here has checked the recommendation/i);
  });

  it("stays quiet when a current report genuinely found no buyer change", async () => {
    getSolutions.mockResolvedValue({
      artifactVerification: "verified",
      previewReport: {
        audience_mapping: { primary_target_segment: "Something", audience_drift_notice: null },
      },
    });

    render(DecisionBrief, { props: { jobId: "job_current", profile: null, onSaved: vi.fn() } });

    await waitFor(() => expect(getSolutions).toHaveBeenCalled());
    expect(screen.queryByRole("note", { name: "Audience check unavailable" })).toBeNull();
    expect(screen.queryByRole("note", { name: /Audience mismatch/ })).toBeNull();
  });

  it("names which part of the buyer identity changed, not just that something did", () => {
    render(AudienceSnapshot, {
      props: { data: { primary_target_segment: "x", audience_drift_notice: notice } },
    });

    const rendered = screen.getByRole("note", { name: "Audience mismatch" });
    expect(rendered).toHaveTextContent(
      /research settled on a different operating scale than you asked for/,
    );
    expect(rendered).toHaveTextContent(
      /recommendation is built for a different type of practice than the research settled on/,
    );
  });
});
