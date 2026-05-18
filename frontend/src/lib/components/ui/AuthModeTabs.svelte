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
	.auth-tabs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 4px;
		padding: 4px;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-full);
		margin-bottom: var(--space-6);
	}

	.auth-tab {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.625rem 1rem;
		font-family: var(--font-body);
		font-weight: var(--font-semibold);
		font-size: var(--text-md);
		color: var(--color-text-muted);
		background: transparent;
		border-radius: var(--radius-full);
		text-decoration: none;
		transition:
			background var(--duration-normal) var(--ease-default),
			color var(--duration-normal) var(--ease-default);
	}

	.auth-tab:hover {
		color: var(--color-text-primary);
	}

	.auth-tab:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	.auth-tab.is-active {
		background: var(--color-bg-elevated);
		color: var(--color-text-primary);
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
	}

	.auth-tab.is-active:hover {
		color: var(--color-text-primary);
	}
</style>
