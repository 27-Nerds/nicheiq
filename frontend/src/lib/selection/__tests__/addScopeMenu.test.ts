import { beforeEach, describe, expect, it } from "vitest";
import {
  escapeKeydown,
  menuKeydown,
  outsidePointerdown,
  triggerKeydown,
  type AddScopeMenuHost,
} from "$lib/selection/addScopeMenu";

/** DOM-backed fake of the selection layout's add-candidate menu. */
function makeHarness(itemCount = 3) {
  const root = document.createElement("div");
  const trigger = document.createElement("button");
  trigger.textContent = "Add candidate";
  root.appendChild(trigger);
  const items: HTMLButtonElement[] = [];
  for (let index = 0; index < itemCount; index += 1) {
    const item = document.createElement("button");
    item.setAttribute("role", "menuitem");
    item.textContent = `Idea ${index + 1}`;
    root.appendChild(item);
    items.push(item);
  }
  const outside = document.createElement("button");
  document.body.append(root, outside);

  let open = false;
  const focusItemCalls: Array<"first" | "last"> = [];
  const host: AddScopeMenuHost = {
    isOpen: () => open,
    setOpen: (next) => { open = next; },
    focusTrigger: () => trigger.focus(),
    // The real host awaits a tick before focusing; record intent AND focus
    // synchronously so tests can assert both.
    focusItem: (position) => {
      focusItemCalls.push(position);
      items[position === "first" ? 0 : items.length - 1]?.focus();
    },
    items: () => [...root.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')],
    root: () => root,
  };

  return {
    host,
    trigger,
    items,
    outside,
    focusItemCalls,
    isOpen: () => open,
    setOpen: (next: boolean) => { open = next; },
  };
}

function key(keyName: string): KeyboardEvent {
  return new KeyboardEvent("keydown", { key: keyName, cancelable: true, bubbles: true });
}

beforeEach(() => {
  document.body.innerHTML = "";
});

describe("triggerKeydown", () => {
  it("ArrowDown opens the menu on the first item", () => {
    const h = makeHarness();
    const event = key("ArrowDown");
    triggerKeydown(h.host, event);
    expect(h.isOpen()).toBe(true);
    expect(event.defaultPrevented).toBe(true);
    expect(h.focusItemCalls).toEqual(["first"]);
  });

  it("ArrowUp opens the menu on the last item", () => {
    const h = makeHarness();
    triggerKeydown(h.host, key("ArrowUp"));
    expect(h.isOpen()).toBe(true);
    expect(h.focusItemCalls).toEqual(["last"]);
  });

  it("ignores other keys", () => {
    const h = makeHarness();
    const event = key("Enter");
    triggerKeydown(h.host, event);
    expect(h.isOpen()).toBe(false);
    expect(event.defaultPrevented).toBe(false);
  });
});

describe("menuKeydown", () => {
  it("Tab closes the menu AND returns focus to the trigger without cancelling the event", () => {
    // Regression: Tab used to only close the menu. The focused menuitem left
    // the DOM, so the browser's default Tab restarted from <body>, stranding
    // keyboard users. Focus must be back on the trigger before default Tab
    // handling runs.
    const h = makeHarness();
    h.setOpen(true);
    h.items[1].focus();
    const event = key("Tab");
    menuKeydown(h.host, event);
    expect(h.isOpen()).toBe(false);
    expect(document.activeElement).toBe(h.trigger);
    // Default Tab must still run so focus proceeds from the trigger.
    expect(event.defaultPrevented).toBe(false);
  });

  it("Shift+Tab gets the same close-and-refocus treatment", () => {
    const h = makeHarness();
    h.setOpen(true);
    h.items[0].focus();
    const event = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, cancelable: true });
    menuKeydown(h.host, event);
    expect(h.isOpen()).toBe(false);
    expect(document.activeElement).toBe(h.trigger);
    expect(event.defaultPrevented).toBe(false);
  });

  it("ArrowDown/ArrowUp cycle through the items", () => {
    const h = makeHarness();
    h.setOpen(true);
    h.items[0].focus();
    menuKeydown(h.host, key("ArrowDown"));
    expect(document.activeElement).toBe(h.items[1]);
    menuKeydown(h.host, key("ArrowUp"));
    expect(document.activeElement).toBe(h.items[0]);
    menuKeydown(h.host, key("ArrowUp"));
    expect(document.activeElement).toBe(h.items[2]);
  });

  it("Home and End jump to the first and last item", () => {
    const h = makeHarness();
    h.setOpen(true);
    h.items[1].focus();
    menuKeydown(h.host, key("End"));
    expect(document.activeElement).toBe(h.items[2]);
    menuKeydown(h.host, key("Home"));
    expect(document.activeElement).toBe(h.items[0]);
  });
});

describe("escapeKeydown", () => {
  it("closes the open menu and restores focus to the trigger", () => {
    const h = makeHarness();
    h.setOpen(true);
    h.items[0].focus();
    escapeKeydown(h.host, key("Escape"));
    expect(h.isOpen()).toBe(false);
    expect(document.activeElement).toBe(h.trigger);
  });

  it("does nothing when the menu is closed", () => {
    const h = makeHarness();
    h.outside.focus();
    escapeKeydown(h.host, key("Escape"));
    expect(h.isOpen()).toBe(false);
    expect(document.activeElement).toBe(h.outside);
  });
});

describe("outsidePointerdown", () => {
  function pointerdownOn(target: Element): PointerEvent {
    const event = new Event("pointerdown", { bubbles: true }) as PointerEvent;
    Object.defineProperty(event, "target", { value: target });
    return event;
  }

  it("closes the menu on a pointerdown outside the trigger+menu root", () => {
    const h = makeHarness();
    h.setOpen(true);
    outsidePointerdown(h.host, pointerdownOn(h.outside));
    expect(h.isOpen()).toBe(false);
  });

  it("keeps the menu open on a pointerdown inside the root", () => {
    const h = makeHarness();
    h.setOpen(true);
    outsidePointerdown(h.host, pointerdownOn(h.items[0]));
    expect(h.isOpen()).toBe(true);
  });
});
