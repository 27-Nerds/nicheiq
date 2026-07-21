<script lang="ts">
  import Popover from "../Popover.svelte";
  import WorkspaceOverlay from "../WorkspaceOverlay.svelte";

  interface Props {
    withActions?: boolean;
  }

  let { withActions = true }: Props = $props();
</script>

<button type="button">Page background</button>

<WorkspaceOverlay open label="Test workspace" onClose={() => {}}>
  <div>
    <button type="button">Workspace background</button>
    <Popover title="Keyboard details" label="Open keyboard details">
      {#snippet trigger()}
        <span>Details</span>
      {/snippet}

      <p>Portaled explanatory content.</p>
      {#if withActions}
        <button type="button">First panel action</button>
        <a href="/details">Last panel action</a>
      {/if}
    </Popover>
  </div>
</WorkspaceOverlay>
