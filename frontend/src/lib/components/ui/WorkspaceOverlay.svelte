<script lang="ts">
  import { tourState } from "$lib/tour/tourState.svelte";
	import { onMount, type Snippet } from "svelte";
	import { portal } from "$lib/actions/portal";
	import { isolateModalBackground } from "$lib/utils/modalIsolation";
	import { lockScroll } from "$lib/utils/scrollLock";

	interface Props {
		open: boolean;
		modal?: boolean;
		size?: "standard" | "wide";
		label: string;
		onClose: () => void;
		/** Overrides Escape ALONE (scrim clicks and host close buttons still call
		 *  onClose). For hosts with an intermediate state — an expanded chat window
		 *  should step down to docked on Esc, not vanish. Omit → Esc calls onClose. */
		onEscape?: () => void;
		onKeydown?: (event: KeyboardEvent) => void;
		children: Snippet;
	}

	let {
		open,
		modal = true,
		size = "wide",
		label,
		onClose,
		onEscape,
		onKeydown,
		children,
	}: Props = $props();

	let frameEl = $state<HTMLElement>();
	let layerEl = $state<HTMLDivElement>();
	let mounted = $state(false);

	// The open state may come from browser storage. Rendering the server default
	// would flash one overlay geometry before hydration applies that preference.
	onMount(() => {
		mounted = true;
	});

	const FOCUSABLE =
		'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [contenteditable="true"], [tabindex]:not([tabindex="-1"])';

	function canRestoreFocus(element: HTMLElement | null): element is HTMLElement {
		if (!element?.isConnected) return false;
		if (element.closest('[inert], [aria-hidden="true"]')) return false;
		return !element.matches("button:disabled, input:disabled, select:disabled, textarea:disabled");
	}

	$effect(() => {
		if (!open || !modal || !frameEl || !layerEl) return;

		const previousFocus =
			document.activeElement instanceof HTMLElement ? document.activeElement : null;
		const unlock = lockScroll();
		const restoreBackground = isolateModalBackground(layerEl);

		const focusFrame = requestAnimationFrame(() => frameEl?.focus());

		return () => {
			cancelAnimationFrame(focusFrame);
			restoreBackground();
			unlock();
			requestAnimationFrame(() => {
				if (canRestoreFocus(previousFocus)) previousFocus.focus();
			});
		};
	});

	function trapTab(event: KeyboardEvent) {
		if (!frameEl) return;

		const focusable = Array.from(frameEl.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
			(element) => {
				if (element.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
				const styles = window.getComputedStyle(element);
				return styles.display !== "none" && styles.visibility !== "hidden";
			},
		);

		if (focusable.length === 0) {
			event.preventDefault();
			frameEl.focus();
			return;
		}

		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		const active = document.activeElement;

		if (event.shiftKey && (active === first || !frameEl.contains(active))) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && (active === last || !frameEl.contains(active))) {
			event.preventDefault();
			first.focus();
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === "Escape") {
			event.preventDefault();
			event.stopPropagation();
			(onEscape ?? onClose)();
			return;
		}

		// A running tour portals its popover OUTSIDE this frame; our trap would make
		// its Next button unreachable and deadlock the tour. driver.js runs its own.
		if (modal && event.key === "Tab" && !tourState.active) {
			trapTab(event);
			return;
		}

		onKeydown?.(event);
	}
</script>

{#if mounted && open}
	<div
		bind:this={layerEl}
		use:portal
		class="workspace-overlay"
		class:workspace-overlay--modal={modal}
		class:workspace-overlay--docked={!modal}
		class:workspace-overlay--standard={size === "standard"}
		data-workspace-overlay={modal ? "modal" : "docked"}
		data-workspace-overlay-size={size}
	>
		{#if modal}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="workspace-overlay__scrim" aria-hidden="true" onclick={onClose}></div>
		{/if}

		<section
			bind:this={frameEl}
			class="workspace-overlay__frame"
			role={modal ? "dialog" : undefined}
			aria-modal={modal ? "true" : undefined}
			aria-label={label}
			tabindex="-1"
			onkeydown={handleKeydown}
		>
			{@render children()}
		</section>
	</div>
{/if}

<style>
	.workspace-overlay {
		position: fixed;
		inset: 0;
		z-index: var(--z-overlay);
		pointer-events: none;
	}

	.workspace-overlay--modal {
		z-index: var(--z-modal);
	}

	.workspace-overlay__scrim {
		position: absolute;
		inset: 0;
		pointer-events: auto;
		background: color-mix(in srgb, var(--color-text-primary) 55%, transparent);
		animation: workspace-scrim-in var(--duration-fast) var(--ease-out) both;
	}

	.workspace-overlay__frame {
		position: absolute;
		z-index: 1;
		display: flex;
		min-width: 0;
		min-height: 0;
		pointer-events: auto;
		outline: none;
	}

	.workspace-overlay__frame:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	/* Height contract: the frame is viewport-bounded (inset-positioned for the
	   modal, sized for the dock), and the single child fills it exactly. The
	   child owns its internal scrolling; it must never exceed the frame. */
	.workspace-overlay__frame > :global(*) {
		flex: 1;
		min-width: 0;
		min-height: 0;
		max-height: 100%;
	}

	.workspace-overlay--docked .workspace-overlay__frame {
		right: max(var(--space-4), env(safe-area-inset-right));
		/* DecisionRail publishes its measured height on the document root. Because
		   both surfaces are body-portaled and bottom-anchored, reserve that height
		   here and in the viewport-bounded height instead of covering the commit CTA. */
		bottom: max(
			calc(var(--decision-rail-height, 0px) + var(--space-4)),
			env(safe-area-inset-bottom)
		);
		width: min(26rem, calc(100vw - var(--space-8)));
		height: min(
			34rem,
			calc(100dvh - var(--decision-rail-height, 0px) - var(--space-8))
		);
		animation: workspace-overlay-in var(--duration-fast) var(--ease-out) both;
	}

	.workspace-overlay--docked .workspace-overlay__frame > :global(*) {
		border: 1px solid var(--color-border-emphasis);
		border-radius: var(--radius-xl);
		box-shadow: var(--shadow-lg);
	}

	.workspace-overlay--modal .workspace-overlay__frame {
		top: max(var(--space-6), 3vh);
		right: max(var(--space-6), 3vw);
		bottom: max(var(--space-6), 3vh);
		left: max(var(--space-6), 3vw);
		width: auto;
		height: auto;
		max-width: 76rem;
		margin-inline: auto;
		animation: workspace-overlay-expand var(--duration-normal) var(--ease-out) both;
	}

	.workspace-overlay--modal.workspace-overlay--standard .workspace-overlay__frame {
		max-width: 56rem;
		top: max(var(--space-8), 5vh);
		bottom: max(var(--space-8), 5vh);
	}

	.workspace-overlay--modal .workspace-overlay__frame > :global(*) {
		border: 1px solid var(--color-border-emphasis);
		border-radius: var(--radius-xl);
		box-shadow: var(--shadow-lg);
	}

	@keyframes workspace-scrim-in {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	@keyframes workspace-overlay-in {
		from {
			opacity: 0;
			transform: translateY(var(--space-3)) scale(0.985);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}

	@keyframes workspace-overlay-expand {
		from {
			opacity: 0;
			transform: translateY(var(--space-2)) scale(0.99);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}

	@media (max-width: 639px) {
		.workspace-overlay--docked .workspace-overlay__frame {
			right: max(var(--space-3), env(safe-area-inset-right));
			bottom: max(
				calc(var(--decision-rail-height, 0px) + var(--space-3)),
				env(safe-area-inset-bottom)
			);
			left: max(var(--space-3), env(safe-area-inset-left));
			width: auto;
			height: min(
				36rem,
				calc(100dvh - var(--decision-rail-height, 0px) - var(--space-6))
			);
		}

		.workspace-overlay--modal .workspace-overlay__frame {
			top: max(var(--space-2), env(safe-area-inset-top));
			right: max(var(--space-2), env(safe-area-inset-right));
			bottom: max(var(--space-2), env(safe-area-inset-bottom));
			left: max(var(--space-2), env(safe-area-inset-left));
		}

		.workspace-overlay--modal.workspace-overlay--standard .workspace-overlay__frame {
			top: max(var(--space-2), env(safe-area-inset-top));
			bottom: max(var(--space-2), env(safe-area-inset-bottom));
		}

		.workspace-overlay--modal .workspace-overlay__frame > :global(*) {
			border-radius: var(--radius-lg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.workspace-overlay__scrim,
		.workspace-overlay__frame {
			animation: none;
		}
	}
</style>
