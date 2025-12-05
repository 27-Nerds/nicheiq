<script lang="ts">
	import './layout.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>NicheIQ Report Viewer</title>
	<meta name="description" content="View comprehensive NicheIQ market research reports" />
</svelte:head>

{@render children()}
