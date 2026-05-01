<script lang="ts">
  import TriDial from "./TriDial.svelte";

  interface Scores {
    demand: number | null;
    feasibility: number | null;
    opportunity: number | null;
  }

  interface Props {
    scores: Scores;
    size?: "md" | "lg" | "xl";
  }

  let { scores, size = "md" }: Props = $props();
</script>

<div class="trifecta" data-size={size}>
  <TriDial type="demand" value={scores.demand} {size} />
  <TriDial type="feasibility" value={scores.feasibility} {size} />
  <TriDial type="opportunity" value={scores.opportunity} {size} />
</div>

<style>
  .trifecta {
    display: inline-flex;
    gap: 4px;
    align-items: center;
  }
  .trifecta[data-size="lg"],
  .trifecta[data-size="xl"] {
    gap: 8px;
  }
</style>
