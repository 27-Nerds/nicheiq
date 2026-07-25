/**
 * Keyboard and pointer behavior for the selection workspace "Add candidate"
 * menu. Extracted from the selection layout so the focus contract (Escape and
 * Tab both close AND return focus to the trigger; outside pointerdown closes)
 * is unit-testable without a full layout harness. The layout supplies a host
 * that reads/writes its own reactive state.
 */

export interface AddScopeMenuHost {
  /** Whether the add-candidate menu is currently open. */
  isOpen(): boolean;
  /** Open or close the menu. */
  setOpen(open: boolean): void;
  /** Return keyboard focus to the "Add candidate" trigger button. */
  focusTrigger(): void;
  /** Focus the first or last menu item (the host may await a render tick). */
  focusItem(position: "first" | "last"): void;
  /** Menu item elements in DOM order (empty when the menu is closed). */
  items(): HTMLElement[];
  /** Root element containing the trigger and the menu, for outside-click checks. */
  root(): Node | null;
}

/** ArrowDown/ArrowUp on the closed trigger opens the menu on first/last item. */
export function triggerKeydown(host: AddScopeMenuHost, event: KeyboardEvent): void {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  event.preventDefault();
  host.setOpen(true);
  host.focusItem(event.key === "ArrowDown" ? "first" : "last");
}

/** Roving focus inside the open menu; Tab closes and restores the trigger. */
export function menuKeydown(host: AddScopeMenuHost, event: KeyboardEvent): void {
  if (event.key === "Tab") {
    // Close and hand focus back to the trigger BEFORE default Tab handling
    // runs: the focused menuitem is about to leave the DOM, and tabbing from
    // a removed node restarts from <body>. From the trigger, the browser's
    // default Tab (or Shift+Tab) proceeds to the natural neighbor.
    host.setOpen(false);
    host.focusTrigger();
    return;
  }
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const items = host.items();
  if (!items.length) return;
  event.preventDefault();
  const current = items.indexOf(document.activeElement as HTMLElement);
  const next = event.key === "Home"
    ? 0
    : event.key === "End"
      ? items.length - 1
      : event.key === "ArrowDown"
        ? (current + 1 + items.length) % items.length
        : (current - 1 + items.length) % items.length;
  items[next]?.focus();
}

/** Escape anywhere in the workspace closes the open menu and restores focus. */
export function escapeKeydown(host: AddScopeMenuHost, event: KeyboardEvent): void {
  if (event.key !== "Escape" || !host.isOpen()) return;
  host.setOpen(false);
  host.focusTrigger();
}

/** A pointerdown outside the trigger+menu root closes the open menu. */
export function outsidePointerdown(host: AddScopeMenuHost, event: PointerEvent): void {
  if (!host.isOpen()) return;
  const target = event.target;
  if (target instanceof Node && host.root()?.contains(target)) return;
  host.setOpen(false);
}
