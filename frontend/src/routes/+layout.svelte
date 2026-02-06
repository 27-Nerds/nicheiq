<script lang="ts">
  import "../app.css";
  import Analytics from "$lib/components/Analytics.svelte";

  let { children } = $props();
</script>

<Analytics />
{@render children()}
