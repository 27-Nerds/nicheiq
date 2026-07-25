import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import Tooltip from "../Tooltip.svelte";

describe("Tooltip trigger semantics", () => {
  afterEach(cleanup);

  it("is focusable with a described-by description but is NOT a button", () => {
    const view = render(Tooltip, { props: { content: "Helpful explanation" } });

    // No action → no button role. A role="button" here was announced as a
    // dead control by screen readers.
    expect(view.queryByRole("button")).toBeNull();

    const wrapper = document.querySelector<HTMLElement>(".tooltip-wrapper");
    expect(wrapper).not.toBeNull();
    expect(wrapper!.getAttribute("role")).toBeNull();
    expect(wrapper!.getAttribute("tabindex")).toBe("0");

    const descId = wrapper!.getAttribute("aria-describedby");
    expect(descId).toBeTruthy();
    expect(document.getElementById(descId!)?.textContent).toBe("Helpful explanation");
  });
});
