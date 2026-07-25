/**
 * Shared "a tour is driving the page" flag.
 *
 * Lives in its own module so overlay primitives (WorkspaceOverlay, FormOverlay, Sheet)
 * can read it without importing the tour controller — which pulls in driver.js and would
 * defeat the lazy import.
 *
 * Those overlays each run their own Tab trap. driver.js portals its popover to <body>,
 * OUTSIDE the overlay's frame, and runs a Tab trap of its own. With both active, Tab
 * cannot reach the popover's Next button and the tour deadlocks — so the overlays stand
 * down while this is true.
 */
export const tourState = $state({
  /** True from the moment a tour starts driving until it is destroyed. */
  active: false,
});
