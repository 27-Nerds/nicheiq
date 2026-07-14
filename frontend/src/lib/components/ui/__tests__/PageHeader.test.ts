import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import PageHeader from "../PageHeader.svelte";

const longTopic =
  "Employees trying to figure out which AI skills to learn and where to expand their professional knowledge to stay employable, overwhelmed by scattered courses and conflicting advice about what their role will actually require";

describe("PageHeader research-topic variant", () => {
  afterEach(() => {
    cleanup();
  });

  it("keeps the default title treatment unchanged", () => {
    const { getByRole } = render(PageHeader, { props: { title: longTopic } });

    const heading = getByRole("heading", { level: 1, name: longTopic });
    expect(heading).not.toHaveClass("page-header-title--research-topic", "page-header-title--long");
    expect(heading).not.toHaveAttribute("title");
  });

  it("applies the compact treatment and full-text tooltip to long research topics", () => {
    const { getByRole } = render(PageHeader, { props: { title: longTopic, titleVariant: "research-topic" } });

    const heading = getByRole("heading", { level: 1, name: longTopic });
    expect(heading).toHaveClass("page-header-title--research-topic", "page-header-title--long");
    expect(heading).toHaveAttribute("title", longTopic);
  });
});
