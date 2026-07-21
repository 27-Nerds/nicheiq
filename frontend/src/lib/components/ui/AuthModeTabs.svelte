<script lang="ts">
	import { page } from '$app/state';

	interface Props {
		active: 'register' | 'login';
	}

	let { active }: Props = $props();

	// Preserve ?returnTo across the switch so post-auth redirect stays intact.
	const search = $derived(page.url.search);

	const registerHref = $derived(`/register${search}`);
	const loginHref = $derived(`/login${search}`);
</script>

<div class="auth-tabs" role="tablist" aria-label="Authentication mode">
	<a
		href={registerHref}
		class="auth-tab"
		class:is-active={active === 'register'}
		role="tab"
		aria-selected={active === 'register'}
		aria-current={active === 'register' ? 'page' : undefined}
		data-sveltekit-noscroll
	>
		Sign Up
	</a>
	<a
		href={loginHref}
		class="auth-tab"
		class:is-active={active === 'login'}
		role="tab"
		aria-selected={active === 'login'}
		aria-current={active === 'login' ? 'page' : undefined}
		data-sveltekit-noscroll
	>
		Log in
	</a>
</div>

<style>
	/* ui/SegmentControl compact density (§6) — AuthModeTabs stays link-based
	   (real navigation between /register and /login, not a value toggle), so
	   it reuses the compact recipe's tokens rather than importing the
	   button/radiogroup component itself. Grid instead of inline-flex so the
	   two tabs split the full card width. */
	.auth-tabs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2px;
		padding: 3px;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border-emphasis);
		border-radius: var(--radius-md);
		margin-bottom: var(--space-6);
	}

	.auth-tab {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.3rem 0.7rem;
		border: 1px solid transparent;
		border-radius: var(--radius-sm);
		font-family: var(--font-body);
		font-weight: 600;
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
		background: transparent;
		text-decoration: none;
		transition:
			background var(--duration-fast) var(--ease-default),
			color var(--duration-fast) var(--ease-default),
			border-color var(--duration-fast) var(--ease-default);
	}

	.auth-tab:hover {
		color: var(--color-text-primary);
	}

	.auth-tab:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	.auth-tab.is-active {
		border-color: var(--color-accent);
		background: var(--color-bg-elevated);
		color: var(--color-text-primary);
		box-shadow: var(--shadow-sm);
	}

	.auth-tab.is-active:hover {
		color: var(--color-text-primary);
	}
</style>
