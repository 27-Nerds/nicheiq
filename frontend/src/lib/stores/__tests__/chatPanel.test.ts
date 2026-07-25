import { beforeEach, describe, expect, it } from "vitest";
import { chatPanel } from "../chatPanel.svelte";

describe("chatPanel store", () => {
  beforeEach(() => {
    localStorage.clear();
    // Module singleton — reset window state and drafts between tests.
    chatPanel.close();
    chatPanel.setDraft("job-1", "");
    chatPanel.setDraft("job-2", "");
    chatPanel.open();
  });

  it("steps expanded → docked → launcher (the Esc ladder the layout wires)", () => {
    chatPanel.expand();
    expect(chatPanel.isExpanded).toBe(true);

    // First Esc (layout's onEscape): expanded collapses to docked, not closed.
    chatPanel.dock();
    expect(chatPanel.isExpanded).toBe(false);
    expect(chatPanel.isOpen).toBe(true);

    // Second Esc: docked closes.
    chatPanel.close();
    expect(chatPanel.isOpen).toBe(false);
  });

  describe("composer drafts (survive the {#if open} unmount)", () => {
    it("persists a draft per job across close/reopen", () => {
      chatPanel.setDraft("job-1", "half a thought");
      chatPanel.close();
      chatPanel.open();
      expect(chatPanel.draft("job-1")).toBe("half a thought");
    });

    it("keeps drafts independent between jobs", () => {
      chatPanel.setDraft("job-1", "about job one");
      chatPanel.setDraft("job-2", "about job two");
      expect(chatPanel.draft("job-1")).toBe("about job one");
      expect(chatPanel.draft("job-2")).toBe("about job two");
    });

    it("clears the draft when the mirrored text is empty (sent or erased)", () => {
      chatPanel.setDraft("job-1", "will be sent");
      chatPanel.setDraft("job-1", "");
      expect(chatPanel.draft("job-1")).toBe("");
    });

    it("returns empty string for jobs without a draft", () => {
      expect(chatPanel.draft("job-never-seen")).toBe("");
    });
  });
});
