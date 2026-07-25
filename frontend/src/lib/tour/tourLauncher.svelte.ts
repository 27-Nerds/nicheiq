/**
 * Lets the page header restart the tour for whichever surface the user is on, without
 * the header needing to know which chapter that is.
 *
 * The mounted `TourHost` registers its restart function here; the header renders its
 * control only while one is registered, so the button never appears on a surface with no
 * chapter (or for a user without the decision-tools grant).
 */

let _restart = $state<(() => void) | null>(null);

export const tourLauncher = {
  get available(): boolean {
    return _restart !== null;
  },

  /** Returns an unregister function for the host's `onDestroy`. */
  register(restart: () => void): () => void {
    _restart = restart;
    return () => {
      // Guard against a late unmount clearing a newer host's registration.
      if (_restart === restart) _restart = null;
    };
  },

  restart(): void {
    _restart?.();
  },
};
