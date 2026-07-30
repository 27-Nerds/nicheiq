import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import Tooltip from "../Tooltip.svelte";

describe("Tooltip trigger semantics", () => {
  afterEach(cleanup);

  it("uses one native help button with a described-by description", () => {
    const view = render(Tooltip, { props: { content: "Helpful explanation" } });

    const wrapper = view.getByRole("button", { name: "More information" });
    expect(wrapper).toHaveClass("tooltip-wrapper");
    expect(wrapper).not.toHaveAttribute("tabindex");

    const descId = wrapper.getAttribute("aria-describedby");
    expect(descId).toBeTruthy();
    expect(document.getElementById(descId!)?.textContent).toBe("Helpful explanation");
    expect(wrapper.querySelector("[aria-label]")).toBeNull();
  });
});
