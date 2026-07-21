<script lang="ts">
	import type { Snippet } from "svelte";
	import { portal } from "$lib/actions/portal";
	import { isolateModalBackground } from "$lib/utils/modalIsolation";
	import { lockScroll } from "$lib/utils/scrollLock";

	interface Props {
		open: boolean;
		modal?: boolean;
		size?: "standard" | "wide";
		label: string;
		onClose: () => void;
		onKeydown?: (event: KeyboardEvent) => void;
		children: Snippet;
	}

	let {
		open,
		modal = true,
		size = "wide",
		label,
		onClose,
		onKeydown,
		children,
	}: Props = $props();

	let frameEl = $state<HTMLElement>();
	let layerEl = $state<HTMLDivElement>();

	const FOCUSABLE =
		'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

	$effect(() => {
		if (!open || !modal || !frameEl || !layerEl) return;

		const previousFocus =
			document.activeElement instanceof HTMLElement ? document.activeElement : null;
		const unlock = lockScroll();
		const restoreBackground = isolateModalBackground(layerEl);

		requestAnimationFrame(() => frameEl?.focus());

		return () => {
			restoreBackground();
			unlock();
			requestAnimationFrame(() => {
				if (previousFocus?.isConnected && !previousFocus.closest('[inert], [aria-hidden="true"]')) {
					previousFocus.focus();
				}
			});
		};
	});

	function trapTab(event: KeyboardEvent) {
		if (!frameEl) return;

		const focusable = Array.from(frameEl.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
			(element) => !element.hasAttribute("disabled") && element.tabIndex !== -1,
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
			onClose();
			return;
		}

		if (modal && event.key === "Tab") {
			trapTab(event);
			return;
		}

		onKeydown?.(event);
	}
</script>

{#if open}
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
		z-index: var(--z-overlay, 30);
		pointer-events: none;
	}

	.workspace-overlay--modal {
		z-index: var(--z-modal, 40);
	}

	.workspace-overlay__scrim {
		position: absolute;
		inset: 0;
		pointer-events: auto;
		background: color-mix(in srgb, var(--color-text-primary) 55%, transparent);
		animation: workspace-scrim-in 180ms ease-out both;
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
		right: max(1rem, env(safe-area-inset-right));
		bottom: max(1rem, env(safe-area-inset-bottom));
		width: min(26rem, calc(100vw - 2rem));
		height: min(34rem, calc(100dvh - 2rem));
		animation: workspace-overlay-in 180ms ease-out both;
	}

	.workspace-overlay--docked .workspace-overlay__frame > :global(*) {
		border-radius: 0.9rem;
		box-shadow:
			0 1.25rem 3.5rem color-mix(in srgb, var(--ink, #1f1d1a) 18%, transparent),
			0 0 0 1px color-mix(in srgb, var(--ink, #1f1d1a) 8%, transparent);
	}

	.workspace-overlay--modal .workspace-overlay__frame {
		top: max(1.5rem, 3vh);
		right: max(1.5rem, 3vw);
		bottom: max(1.5rem, 3vh);
		left: max(1.5rem, 3vw);
		width: auto;
		height: auto;
		max-width: 76rem;
		margin-inline: auto;
		animation: workspace-overlay-expand 220ms ease-out both;
	}

	.workspace-overlay--modal.workspace-overlay--standard .workspace-overlay__frame {
		max-width: 56rem;
	}

	.workspace-overlay--modal .workspace-overlay__frame > :global(*) {
		border: 1px solid color-mix(in srgb, var(--ink, #1f1d1a) 12%, transparent);
		border-radius: var(--workspace-overlay-radius, 1.25rem);
		box-shadow:
			0 2rem 6rem color-mix(in srgb, #181512 30%, transparent),
			0 0 0 1px color-mix(in srgb, white 18%, transparent);
	}

	:global(.job-page-shell.has-sticky-bar)
		.workspace-overlay--docked
		.workspace-overlay__frame {
		bottom: calc(max(1rem, env(safe-area-inset-bottom)) + 5rem);
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
			transform: translateY(0.75rem) scale(0.985);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}

	@keyframes workspace-overlay-expand {
		from {
			opacity: 0;
			transform: translateY(0.5rem) scale(0.99);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}

	@media (max-width: 639px) {
		.workspace-overlay--docked .workspace-overlay__frame {
			right: max(0.75rem, env(safe-area-inset-right));
			bottom: max(0.75rem, env(safe-area-inset-bottom));
			left: max(0.75rem, env(safe-area-inset-left));
			width: auto;
			height: min(36rem, calc(100dvh - 1.5rem));
		}

		.workspace-overlay--modal .workspace-overlay__frame {
			top: max(0.5rem, env(safe-area-inset-top));
			right: max(0.5rem, env(safe-area-inset-right));
			bottom: max(0.5rem, env(safe-area-inset-bottom));
			left: max(0.5rem, env(safe-area-inset-left));
		}

		.workspace-overlay--modal .workspace-overlay__frame > :global(*) {
			--workspace-overlay-radius: 0.9rem;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.workspace-overlay__scrim,
		.workspace-overlay__frame {
			animation: none;
		}
	}
</style>
