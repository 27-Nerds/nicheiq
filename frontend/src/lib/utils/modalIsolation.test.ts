import { afterEach, describe, expect, it } from "vitest";
import { isolateModalBackground } from "./modalIsolation";

describe("isolateModalBackground", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("inertifies body children but never data-modal-exempt surfaces", () => {
    const pageRoot = document.createElement("div");
    const toolbar = document.createElement("div");
    // The annotation toolbar's contract: portaled to <body>, works above modals.
    toolbar.setAttribute("data-modal-exempt", "");
    const modalLayer = document.createElement("div");
    document.body.append(pageRoot, toolbar, modalLayer);

    const release = isolateModalBackground(modalLayer);

    expect(pageRoot.inert).toBe(true);
    expect(pageRoot.getAttribute("aria-hidden")).toBe("true");
    expect(modalLayer.inert).toBeFalsy();
    expect(toolbar.inert).toBeFalsy();
    expect(toolbar.hasAttribute("aria-hidden")).toBe(false);

    release();
    expect(pageRoot.inert).toBeFalsy();
    expect(pageRoot.hasAttribute("aria-hidden")).toBe(false);
  });

  it("keeps the exemption under nested isolation (reference counting untouched)", () => {
    const pageRoot = document.createElement("div");
    const toolbar = document.createElement("div");
    toolbar.setAttribute("data-modal-exempt", "");
    const outerModal = document.createElement("div");
    const innerModal = document.createElement("div");
    document.body.append(pageRoot, toolbar, outerModal, innerModal);

    const releaseOuter = isolateModalBackground(outerModal);
    const releaseInner = isolateModalBackground(innerModal);

    expect(toolbar.inert).toBeFalsy();
    expect(outerModal.inert).toBe(true); // inner isolates the outer overlay

    releaseInner();
    expect(outerModal.inert).toBeFalsy();
    expect(pageRoot.inert).toBe(true); // still held by the outer modal

    releaseOuter();
    expect(pageRoot.inert).toBeFalsy();
    expect(toolbar.inert).toBeFalsy();
  });
});
