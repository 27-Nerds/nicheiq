import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import IdeaClarifyCard, {
  buildSkipSummary,
  flattenClarifyAnswers,
  type ClarifyAnswers,
  type ClarifyScanResult,
} from "../IdeaClarifyCard.svelte";

afterEach(cleanup);

function scan(overrides: Partial<ClarifyScanResult> = {}): ClarifyScanResult {
  return {
    parse_confidence: "low",
    fields: {
      audience: { value: "wedding photographers", confidence: "high", guess: "wedding photographers" },
      problem: { value: null, confidence: "low", guess: "missed invoice deadlines" },
      delivery: { value: null, confidence: "none", guess: null },
    },
    questions: [
      {
        id: "q-problem",
        field: "problem",
        prompt: "What problem does it solve?",
        chips: [
          { id: "c1", label: "Missed deadlines" },
          { id: "c2", label: "Lost files" },
        ],
        allow_other: true,
      },
    ],
    ...overrides,
  };
}

function baseProps(overrides: Record<string, unknown> = {}) {
  return {
    scan: scan(),
    answers: {} as ClarifyAnswers,
    cardState: "ready" as const,
    discoveryPrice: 5,
    loading: false,
    onanswer: vi.fn(),
    onclear: vi.fn(),
    onstart: vi.fn(),
    onrescan: vi.fn(),
    onswitchmode: vi.fn(),
    ...overrides,
  };
}

describe("IdeaClarifyCard", () => {
  it("shows a skeleton with an aria-live region while scanning", () => {
    const view = render(IdeaClarifyCard, { props: baseProps({ cardState: "scanning", scan: null }) });
    expect(view.getByText(/reading your idea/i)).toBeInTheDocument();
  });

  it("shows the failopen message and a Start now button on timeout/error", async () => {
    const props = baseProps({ cardState: "failopen", scan: null });
    const view = render(IdeaClarifyCard, { props });

    expect(view.getByText(/couldn't read your idea in time/i)).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /start now/i }));
    expect(props.onstart).toHaveBeenCalledOnce();
  });

  it("renders a high-confidence field as confirmed with no Change control", () => {
    const view = render(IdeaClarifyCard, { props: baseProps() });
    expect(view.getByText(/who it's for: wedding photographers/i)).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Change" })).not.toBeInTheDocument();
  });

  it("renders a question's chips and answers via onanswer on click", async () => {
    const props = baseProps();
    const view = render(IdeaClarifyCard, { props });

    expect(view.getByText("What problem does it solve?")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("radio", { name: "Missed deadlines" }));

    expect(props.onanswer).toHaveBeenCalledWith("problem", {
      kind: "chip",
      chipId: "c1",
      label: "Missed deadlines",
    });
  });

  it("moves selection with the roving-tabindex arrow-key handler", async () => {
    const props = baseProps();
    const view = render(IdeaClarifyCard, { props });

    const first = view.getByRole("radio", { name: "Missed deadlines" });
    await fireEvent.keyDown(first, { key: "ArrowRight" });

    expect(props.onanswer).toHaveBeenCalledWith("problem", {
      kind: "chip",
      chipId: "c2",
      label: "Lost files",
    });
  });

  it("collapses an answered row with a Change control that calls onclear", async () => {
    const props = baseProps({
      answers: { problem: { kind: "chip", chipId: "c1", label: "Missed deadlines" } },
    });
    const view = render(IdeaClarifyCard, { props });

    expect(view.getByText(/problem it solves: missed deadlines/i)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Change" }));
    expect(props.onclear).toHaveBeenCalledWith("problem");
  });

  it("commits a free-text 'Other' answer on Enter", async () => {
    const props = baseProps();
    const view = render(IdeaClarifyCard, { props });

    await fireEvent.click(view.getByRole("button", { name: /^other/i }));
    const input = view.getByPlaceholderText(/type your own/i);
    await fireEvent.input(input, { target: { value: "Duplicate client uploads" } });
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(props.onanswer).toHaveBeenCalledWith("problem", {
      kind: "other",
      text: "Duplicate client uploads",
    });
  });

  it("shows the couldn't-tell message and a mode-switch link at parse_confidence none", async () => {
    const props = baseProps({ scan: scan({ parse_confidence: "none", questions: [] }) });
    const view = render(IdeaClarifyCard, { props });

    expect(view.getByText(/couldn't tell what the product is/i)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Switch to Explore a niche" }));
    expect(props.onswitchmode).toHaveBeenCalledOnce();
  });

  it("labels the primary button 'Run with best guess' when nothing is answered", () => {
    const view = render(IdeaClarifyCard, { props: baseProps() });
    expect(view.getByRole("button", { name: /run with best guess/i })).toBeInTheDocument();
  });

  it("labels the primary button 'Start the check' once anything is answered", () => {
    const view = render(IdeaClarifyCard, {
      props: baseProps({ answers: { problem: { kind: "chip", chipId: "c1", label: "Missed deadlines" } } }),
    });
    expect(view.getByRole("button", { name: /start the check/i })).toBeInTheDocument();
  });

  it("labels the primary button 'Re-read and continue' while stale, and wires it to onrescan", async () => {
    const props = baseProps({ cardState: "stale" });
    const view = render(IdeaClarifyCard, { props });

    const button = view.getByRole("button", { name: /re-read and continue/i });
    await fireEvent.click(button);

    expect(props.onrescan).toHaveBeenCalledOnce();
    expect(props.onstart).not.toHaveBeenCalled();
  });

  it("disables chips while stale", () => {
    const view = render(IdeaClarifyCard, { props: baseProps({ cardState: "stale" }) });
    expect(view.getByRole("radio", { name: "Missed deadlines" })).toBeDisabled();
  });

  it("shows the discovery price with pluralized CREDITS", () => {
    const view = render(IdeaClarifyCard, { props: baseProps({ discoveryPrice: 5 }) });
    expect(view.getByText(/not charged yet.*5 credits on start/i)).toBeInTheDocument();
  });

  it("shows singular CREDIT at price 1", () => {
    const view = render(IdeaClarifyCard, { props: baseProps({ discoveryPrice: 1 }) });
    expect(view.getByText(/not charged yet.*1 credit on start/i)).toBeInTheDocument();
  });
});

describe("flattenClarifyAnswers", () => {
  it("returns an empty string with no answers", () => {
    expect(flattenClarifyAnswers({})).toBe("");
  });

  it("flattens answers into appendable pitch lines in field order", () => {
    expect(
      flattenClarifyAnswers({
        delivery: { kind: "chip", chipId: "d1", label: "A Chrome extension" },
        audience: { kind: "other", text: "Wedding photographers" },
      }),
    ).toBe("\n\nWho it's for: Wedding photographers\nHow it works: A Chrome extension");
  });

  it("skips a field whose free-text answer is blank", () => {
    expect(flattenClarifyAnswers({ problem: { kind: "other", text: "   " } })).toBe("");
  });
});

describe("buildSkipSummary", () => {
  it("matches the plan's exact null-guess phrasing", () => {
    const result = scan({
      fields: {
        audience: { value: null, confidence: "none", guess: null },
        problem: { value: null, confidence: "high", guess: null },
        delivery: { value: null, confidence: "high", guess: null },
      },
    });
    expect(buildSkipSummary(result, {})).toBe("If you skip: we'll have to guess who it's for.");
  });

  it("uses the field's guess text when one is available", () => {
    const result = scan({
      fields: {
        audience: { value: null, confidence: "high", guess: null },
        problem: { value: null, confidence: "low", guess: "missed invoice deadlines" },
        delivery: { value: null, confidence: "high", guess: null },
      },
    });
    expect(buildSkipSummary(result, {})).toBe("If you skip: we'll guess missed invoice deadlines.");
  });

  it("excludes already-answered fields from the summary", () => {
    const result = scan({
      fields: {
        audience: { value: null, confidence: "none", guess: null },
        problem: { value: null, confidence: "none", guess: null },
        delivery: { value: null, confidence: "high", guess: null },
      },
    });
    const answers: ClarifyAnswers = { audience: { kind: "other", text: "Freelancers" } };
    expect(buildSkipSummary(result, answers)).toBe("If you skip: we'll have to guess what problem it solves.");
  });

  it("returns null once every field is confirmed or answered", () => {
    const result = scan({
      fields: {
        audience: { value: "x", confidence: "high", guess: "x" },
        problem: { value: "y", confidence: "high", guess: "y" },
        delivery: { value: "z", confidence: "high", guess: "z" },
      },
    });
    expect(buildSkipSummary(result, {})).toBeNull();
  });
});
