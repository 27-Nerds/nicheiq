import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import IdeaReferenceText from "$lib/components/IdeaReferenceText.svelte";
import type { IdeaReference } from "$lib/utils/ideaReferences";

const reference: IdeaReference = {
  id: "ranked:LiquipediaGapDetector",
  label: "Esports data gap monitor",
  kind: "ranked",
  solutionName: "LiquipediaGapDetector",
  aliases: ["LiquipediaGapDetector", "Liquipedia Gap Detector"],
};

afterEach(cleanup);

describe("IdeaReferenceText", () => {
  it("renders the reference's display label instead of the matched codename", async () => {
    const onOpen = vi.fn();
    const view = render(IdeaReferenceText, {
      props: {
        content: "Start with LiquipediaGapDetector because the buyer is clear.",
        references: [reference],
        onOpen,
      },
    });

    const link = view.getByRole("button", { name: /Esports data gap monitor.*open details/ });
    expect(view.container).not.toHaveTextContent("LiquipediaGapDetector");
    // Non-reference text stays verbatim around the swapped link label
    // (textContent also carries the link's sr-only ", open details" hint).
    expect(view.container).toHaveTextContent(/^Start with Esports data gap monitor/);
    expect(view.container).toHaveTextContent(/because the buyer is clear\.$/);

    await fireEvent.click(link);
    expect(onOpen).toHaveBeenCalledWith(reference);
  });

  it("keeps non-reference text verbatim", () => {
    const view = render(IdeaReferenceText, {
      props: { content: "No idea names in this sentence.", references: [reference] },
    });

    expect(view.container).toHaveTextContent("No idea names in this sentence.");
    expect(view.queryByRole("button")).toBeNull();
  });

  it("renders the display label inside markdown-decorated links", async () => {
    const view = render(IdeaReferenceText, {
      props: {
        content: "Start with LiquipediaGapDetector now.",
        references: [reference],
        markdown: true,
      },
    });

    const link = await view.findByRole("button", { name: /Esports data gap monitor.*open details/ });
    expect(link.dataset.ideaReferenceId).toBe(reference.id);
    expect(view.container).not.toHaveTextContent("LiquipediaGapDetector");
  });
});
