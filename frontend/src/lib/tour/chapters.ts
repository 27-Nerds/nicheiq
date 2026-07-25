import type { TourStep } from './tourController';

/**
 * The tutorial content: four per-surface chapters, offered on that surface's first visit.
 *
 * Every chapter exists to kill one of three misconceptions:
 *   1. Only the shortlist is required — every optional check can be skipped.
 *   2. Nothing in the optional tools changes the Discovery ranking or any score.
 *   3. One run is priced flat for 1-3 ideas, and nothing is charged until the final confirm.
 *
 * Placement (`side`/`align`) is deliberate, not decorative. driver.js measures the
 * target's VIEWPORT rect; when the requested side doesn't fit it falls back
 * left → right → top → bottom, and when none fit it pins the popover to the bottom of the
 * screen with no arrow — visually detached from what it is describing. The notes on each
 * step record why its side was chosen.
 */

export interface TourChapter {
  id: string;
  /** Copy for the first-visit invitation. */
  invitation: { heading: string; body: string };
  steps: TourStep[];
}

export const JOB_SHORTLIST_CHAPTER: TourChapter = {
  id: 'job-shortlist',
  invitation: {
    heading: 'A quick tour of the shortlist',
    body: 'Five short steps, about a minute, and you can close it at any point.',
  },
  steps: [
    {
      element: '[data-annotation-anchor="shortlist-header"]',
      popover: {
        title: 'The only step that is required',
        description:
          'Discovery is finished. Picking one to three ideas is the whole requirement here; every other tool on this page is something you can skip.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      // The header row, NOT the whole table: a table taller than the viewport scrolls to
      // top and then fits no side, collapsing to the bottom-pinned fallback. The header
      // also holds the sort buttons this copy is about.
      element: '[data-tour="ranked-list"]',
      popover: {
        title: 'Where the ranking comes from',
        description:
          'These scores were set during Discovery and stay fixed. Sorting a column reorders what you see; it never recalculates anything or moves an idea up.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: '[data-tour="shortlist-checkbox"]',
      popover: {
        title: 'What the checkbox commits to',
        description:
          'Only a ticked row joins the shortlist, and three is the ceiling: a fourth stays inert until you deselect one. Opening a title to read it commits to nothing.',
        // Left of the checkbox there is only the 1.35rem rank cell and the sidebar.
        side: 'right',
        align: 'start',
      },
    },
    {
      // aria-labelledby, not the scoped class: the class is Svelte-scoped and the
      // design system reserves the right to rename it.
      element: 'section[aria-labelledby="decision-guide-title"]',
      popover: {
        title: 'A suggestion, not a checklist',
        description:
          'Whatever appears here is a suggestion, and skipping it holds nothing up. The statuses below report what is done; tools themselves open from the sidebar.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: 'aside[aria-label="Ideas for Deep Research"]',
      popover: {
        title: 'Your shortlist, always visible',
        description:
          'The dock follows you down the page with the current count, removable ideas, and the way through to Review and start. A disabled button states its reason beside it.',
        // The dock is position:fixed at the bottom of the viewport — `bottom` would put
        // the popover off-screen. `center` keeps it clear of the analyst window, which
        // occupies the bottom-right corner.
        side: 'top',
        align: 'center',
      },
    },
  ],
};

export const COMPARE_CHAPTER: TourChapter = {
  id: 'compare',
  invitation: {
    heading: 'A quick tour of Compare trade-offs',
    body: 'Four steps, under a minute, and Escape closes it whenever you want.',
  },
  steps: [
    {
      element: '[role="radiogroup"][aria-label="Comparison view"]',
      popover: {
        title: 'Two views of the same shortlist',
        description:
          'Research evidence shows what Discovery found. Fit for you reads the same ideas against your own constraints. Switching between them changes the columns, never a score.',
        // The header is a space-between flex row, so the control sits top-right.
        side: 'bottom',
        align: 'end',
      },
    },
    {
      // The <section>, not #scope-title: that id belongs to a label in the LEFT column,
      // while the candidate pills this copy describes are the sibling column.
      element: 'section[aria-labelledby="scope-title"]',
      popover: {
        title: 'Editing the shortlist from here',
        description:
          'Ideas can be added or dropped here without returning to the job page. One shown in the strip but not yet added stays outside the shortlist until you add it.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: '#fit-action-title',
      popover: {
        title: 'Fit for you is private and free',
        description:
          'Save your build limits first and this reads each idea against your time, budget and reach. It is personal feasibility, costs nothing, and leaves research scores untouched.',
        side: 'bottom',
        align: 'start',
      },
      // Only exists under ?view=founder AND with 2+ ideas; the host switches the view.
      waitForElement: 1500,
    },
    {
      element: '[data-tour="workspace-commit"]',
      popover: {
        title: 'The way out at any point',
        description:
          'This strip sits at the foot of every tool page. With one to three ideas saved it reads Review and start, and no optional check has to be finished first.',
        // The CTA sits at the right end of a full-width strip; `left` has ~700px of
        // clear space and pushes the popover away from the docked analyst window.
        side: 'left',
        align: 'center',
      },
    },
  ],
};

export const RISKS_CHAPTER: TourChapter = {
  id: 'risks',
  invitation: {
    heading: 'A quick tour of Check the evidence',
    body: 'Four steps, under a minute, and leaving part-way loses nothing.',
  },
  steps: [
    {
      // NOT #challenge-title — that heading reads "Choose a risk area", which is the
      // next step's subject. The free/re-read boundary lives in the page intro.
      element: '[data-tour="evidence-intro"]',
      popover: {
        title: 'A re-read, not a new search',
        description:
          'The check is free and looks only at sources already saved with this project; it does not go out to the web. What it finds never moves a score or your shortlist.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      // The whole rail, so all four areas are spotlit. Never call selectLens() — it
      // moves focus, and the rail is a roving-tabindex tablist.
      element: 'nav[aria-label="Risk areas"]',
      popover: {
        title: 'Four areas, checked separately',
        description:
          'Demand, buyer reach, differentiation and buildability each hold one check per exact idea revision. A cannot-answer result marks a gap in the record, not a weak idea.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: '#assumption-map-title',
      popover: {
        title: 'Questions to resolve stay open',
        description:
          'Saving a question tracks it and blocks nothing. Keep the ones whose answer would change what you research, and set impact yourself: it is your judgement, not a score.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      // Points at the BUTTON that opens the form, not the form itself. The form lives
      // behind two guards with no external trigger, and inside a closed <details> its
      // selector still matches a 0x0 element — so skipMissingElement would not save us.
      element: '[data-tour="add-evidence"]',
      popover: {
        title: 'Evidence you add yourself',
        description:
          'Anything you record here is filed against this exact idea revision as unverified and read by the next check, though it moves no score by itself.',
        side: 'bottom',
        align: 'end',
      },
    },
  ],
};

export const REVIEW_CHAPTER: TourChapter = {
  id: 'review',
  invitation: {
    heading: 'A quick tour before you commit',
    body: 'Three steps, well under a minute, and closing it starts nothing.',
  },
  steps: [
    {
      // The price sentence, not #selected-ideas-title — that heading is the count.
      element: '[data-tour="flat-price"]',
      popover: {
        title: 'Three slots, one price',
        // The anchor already states the flat price (and now prints the figure inline),
        // so this adds the consequence instead of repeating the fact.
        description:
          'Because the cost does not scale with the shortlist, a second or third idea is free leverage. If two candidates are genuinely close, research both rather than guessing between them.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: '[data-tour="risk-summary"]',
      popover: {
        title: 'Unchecked is not blocked',
        // The panel itself now says "you can continue because this step is optional",
        // so lead with the part it leaves out: what the panel IS.
        description:
          'Open questions and skipped areas both carry into the run untouched. This panel is a record of what you chose to check, never a gate on starting.',
        // Full left-column width, so no side gutter fits; `top` overlays the list the
        // user has already read rather than risking the fold.
        side: 'top',
        align: 'start',
      },
    },
    {
      element: 'div[aria-label="Credit summary"]',
      popover: {
        title: 'Check the arithmetic first',
        // The three facts this step used to state (charged on start / shortlist locks /
        // failed runs refund) are now printed verbatim in the `.price-notes` list right
        // below this anchor. Point at them rather than repeating them.
        description:
          'This is the live price, not a remembered estimate, and the last row is what you will be left with. The notes underneath cover when you are charged and what a failed run returns.',
        // Low in the sticky right-hand aside, with the scope card to its left.
        side: 'left',
        align: 'center',
      },
    },
  ],
};

export const TOUR_CHAPTERS: Record<string, TourChapter> = {
  [JOB_SHORTLIST_CHAPTER.id]: JOB_SHORTLIST_CHAPTER,
  [COMPARE_CHAPTER.id]: COMPARE_CHAPTER,
  [RISKS_CHAPTER.id]: RISKS_CHAPTER,
  [REVIEW_CHAPTER.id]: REVIEW_CHAPTER,
};

/** Below this the dock becomes a bare bar, the guide card collapses, and a ~300px
 *  popover is a full-screen takeover with no visible spotlight. */
export const TOUR_MIN_VIEWPORT = 1024;
