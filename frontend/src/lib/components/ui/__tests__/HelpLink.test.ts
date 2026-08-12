import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import HelpLink from "../HelpLink.svelte";

describe("HelpLink", () => {
  afterEach(cleanup);

  it("preserves the current workflow by opening contextual help in a new tab", () => {
    const view = render(HelpLink, {
      props: {
        href: "/help/methodology",
        label: "How scoring works",
      },
    });

    const link = view.getByRole("link", {
      name: "How scoring works (opens in a new tab)",
    });

    expect(link).toHaveAttribute("href", "/help/methodology");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
