interface IsolationState {
  count: number;
  inert: boolean;
  ariaHidden: string | null;
}

const isolationStates = new WeakMap<HTMLElement, IsolationState>();

function acquireIsolation(element: HTMLElement) {
  const existing = isolationStates.get(element);
  if (existing) {
    existing.count += 1;
    return;
  }

  isolationStates.set(element, {
    count: 1,
    inert: element.inert,
    ariaHidden: element.getAttribute("aria-hidden"),
  });
  element.inert = true;
  element.setAttribute("aria-hidden", "true");
}

function releaseIsolation(element: HTMLElement) {
  const state = isolationStates.get(element);
  if (!state) return;

  state.count -= 1;
  if (state.count > 0) return;

  element.inert = state.inert;
  if (state.ariaHidden === null) element.removeAttribute("aria-hidden");
  else element.setAttribute("aria-hidden", state.ariaHidden);
  isolationStates.delete(element);
}

/**
 * Makes every body child except the supplied portaled modal unavailable to
 * assistive technology and pointer/keyboard interaction. The saved state is
 * reference-counted so nested form overlays restore parent overlays exactly.
 *
 * Elements carrying `data-modal-exempt` are never inertified: they are
 * portaled utility surfaces designed to keep working ABOVE modals (the
 * annotation toolbar), not page background.
 */
export function isolateModalBackground(modalLayer: HTMLElement): () => void {
  if (typeof document === "undefined") return () => {};

  const siblings = Array.from(document.body.children).filter(
    (element): element is HTMLElement =>
      element instanceof HTMLElement &&
      element !== modalLayer &&
      !element.hasAttribute("data-modal-exempt") &&
      !["SCRIPT", "STYLE", "LINK"].includes(element.tagName),
  );

  siblings.forEach(acquireIsolation);

  let released = false;
  return () => {
    if (released) return;
    released = true;
    siblings.forEach(releaseIsolation);
  };
}
