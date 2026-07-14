<script lang="ts">
  // Test harness — Sheet takes a `children` snippet, which can't be passed through
  // testing-library's plain props object.
  import Sheet from "../Sheet.svelte";

  let { open = true, onClose = () => {} }: { open?: boolean; onClose?: () => void } = $props();
</script>

<Sheet {open} title="Niche checkpoint" {onClose}>
  {#snippet children()}
    <p>Past conversation</p>
    <button type="button">Inner action</button>
  {/snippet}
</Sheet>
