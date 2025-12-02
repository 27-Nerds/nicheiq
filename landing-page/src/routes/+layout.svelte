<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>NicheIQ - Validated Market Research in 12 Minutes</title>
	<link rel="icon" href="/favicon.svg" />
</svelte:head>

{@render children()}
