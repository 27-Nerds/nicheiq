<script lang="ts">
  // Pure presentational legend for the Trifecta D/F/O dials.
</script>

<div class="tri-legend">
  <span class="k demand">Demand</span>
  <span class="k feasibility">Feasibility</span>
  <span class="k opportunity">Opportunity</span>
</div>

<style>
  .tri-legend {
    display: flex;
    gap: 12px;
    font-size: 11px;
    color: var(--color-text-muted);
  }
  .k {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .k::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 2px;
  }
  .k.demand::before {
    background: var(--color-accent);
  }
  .k.feasibility::before {
    background: var(--color-info);
  }
  .k.opportunity::before {
    background: var(--color-success);
  }
</style>
