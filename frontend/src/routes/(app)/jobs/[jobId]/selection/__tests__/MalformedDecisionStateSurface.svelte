<script lang="ts">
  import SelectionLayout from "../+layout.svelte";
  import ReviewPage from "../review/+page.svelte";

  let { data }: { data: any } = $props();
</script>

<SelectionLayout {data}>
  <ReviewPage {data} />
</SelectionLayout>
