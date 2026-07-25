// How the analyst window is presented on the selection page — remembered per user.
//
// It is an OVERLAY, never a column in the page. Two earlier attempts got this wrong:
// a 20rem grid rail squeezed the analyst's paragraphs to ~35 characters per line
// (readable band is 45-75), and a wider grid track just moved the squeeze onto the
// candidate table — then collapsed into a slab of chat wedged into the page flow
// below 1440px. The work is the candidate table; the analyst accompanies it.
//
// Three states, in the messenger idiom people already know:
//   launcher  — a pill in the corner. Nothing on screen but the way back in.
//   docked    — a floating window over the bottom-right. Read while you scan the table.
//   expanded  — a centered full-height window at reading width, for a long answer.
const KEY = "nicheiq.chatPanel.v2";

export type ChatWindowState = "launcher" | "docked" | "expanded";

function load(): ChatWindowState {
  if (typeof localStorage === "undefined") return "docked";
  const raw = localStorage.getItem(KEY);
  // `expanded` is a full-screen takeover, not a preference to arrive into on a job the
  // user just opened — it degrades to `docked` on load. launcher/docked genuinely are
  // a global preference and persist as-is.
  if (raw === "launcher" || raw === "docked") return raw;
  return "docked";
}

let _state = $state<ChatWindowState>(load());

// Unsent composer text, per job. The overlay unmounts its ChatThread on close
// ({#if open}), which used to destroy the draft with it — Esc or a scrim click
// silently ate whatever the user was writing. Session-scoped on purpose: a
// draft should survive close/reopen, not a full page reload.
const _drafts = $state<Record<string, string>>({});

function persist() {
  if (typeof localStorage === "undefined") return;
  // Never persist `expanded` — see `load()`.
  if (_state === "expanded") return;
  try {
    localStorage.setItem(KEY, _state);
  } catch {
    // Private mode / quota — the window still works, it just won't remember.
  }
}

export const chatPanel = {
  get state() { return _state; },
  get isOpen() { return _state !== "launcher"; },
  get isExpanded() { return _state === "expanded"; },

  open() {
    if (_state === "launcher") _state = "docked";
    persist();
  },
  close() {
    _state = "launcher";
    persist();
  },
  expand() {
    _state = "expanded";
    persist();
  },
  dock() {
    _state = "docked";
    persist();
  },
  toggleExpanded() {
    _state = _state === "expanded" ? "docked" : "expanded";
    persist();
  },

  /** The unsent composer draft for a job — "" when none. */
  draft(jobId: string): string {
    return _drafts[jobId] ?? "";
  },
  /** Mirror of the composer's text. Empty text clears the entry (a sent or
   *  deliberately erased draft must not resurrect on reopen). */
  setDraft(jobId: string, text: string) {
    if (text) _drafts[jobId] = text;
    else delete _drafts[jobId];
  },
};
