// Shared body-scroll lock for overlays (Sheet, the expanded analyst window, …).
//
// Locks `<html>`, not `<body>` — this app scrolls the document element (see
// app.css: no height/overflow-y on html, only overflow-x on body), so locking
// body alone is a no-op and the page keeps scrolling behind the overlay.
//
// Reference-counted: multiple overlays can be open at once (e.g. the expanded
// chat window locks the page, then a Sheet opens on top of it). Only the first
// acquire applies the lock, only the last release restores it, and it restores
// the PREVIOUS inline styles rather than hardcoding "" so nested locks never
// clobber each other.
//
// Also compensates for the vanishing scrollbar's width via padding-right so
// the page doesn't jolt sideways when overflow is hidden.
let lockCount = 0;
let prevOverflow = "";
let prevPaddingRight = "";

export function lockScroll(): () => void {
  if (typeof document === "undefined") return () => {};

  if (lockCount === 0) {
    const root = document.documentElement;
    prevOverflow = root.style.overflow;
    prevPaddingRight = root.style.paddingRight;
    const gutter = window.innerWidth - root.clientWidth;
    root.style.overflow = "hidden";
    if (gutter > 0) root.style.paddingRight = `${gutter}px`;
  }
  lockCount++;

  let released = false;
  return () => {
    if (released) return;
    released = true;
    lockCount--;
    if (lockCount === 0) {
      const root = document.documentElement;
      root.style.overflow = prevOverflow;
      root.style.paddingRight = prevPaddingRight;
    }
  };
}
