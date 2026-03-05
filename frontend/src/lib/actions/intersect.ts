import type { Action } from 'svelte/action';

interface IntersectOptions {
	threshold?: number;
	onIntersect?: () => void;
}

export const intersect: Action<HTMLElement, IntersectOptions | undefined> = (node, options) => {
	let visible = false;
	const observer = new IntersectionObserver(
		([entry]) => {
			if (entry.isIntersecting && !visible) {
				visible = true;
				options?.onIntersect?.();
				observer.disconnect();
			}
		},
		{ threshold: options?.threshold ?? 0.1 }
	);
	observer.observe(node);
	return { destroy: () => observer.disconnect() };
};
