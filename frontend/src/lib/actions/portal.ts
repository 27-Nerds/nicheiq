import type { Action } from 'svelte/action';

export const portal: Action<HTMLElement> = (node) => {
	document.body.appendChild(node);
	return {
		destroy() {
			node.remove();
		}
	};
};
