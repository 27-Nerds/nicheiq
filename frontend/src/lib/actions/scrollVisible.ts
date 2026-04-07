/**
 * Svelte action that adds `.visible` class when element scrolls into view.
 * Used to trigger CSS animations (e.g., tier-bar scaleX fills).
 *
 * Usage: <div use:scrollVisible> or <div use:scrollVisible={{ threshold: 0.5 }}>
 */
export function scrollVisible(node: HTMLElement, opts?: { threshold?: number }) {
  const observer = new IntersectionObserver(
    ([entry]) => {
      if (entry.isIntersecting) {
        node.classList.add('visible');
        observer.disconnect();
      }
    },
    { threshold: opts?.threshold ?? 0.3 }
  );
  observer.observe(node);
  return {
    destroy() {
      observer.disconnect();
    },
  };
}
