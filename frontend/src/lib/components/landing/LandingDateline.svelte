<script lang="ts">
	import { editionLabel, isFallbackEdition } from '$lib/seo/edition';
	import { formatCompact } from '$lib/utils/format-numbers';

	interface Props {
		reportsRun: number | null;
		discussionsMined: number | null;
		catalogLastUpdated: string | null;
	}

	let { reportsRun, discussionsMined, catalogLastUpdated }: Props = $props();

	// Low-count gate: small live numbers read as low adoption, not proof.
	// null (failed fetch) never clears the gate.
	const showReports = $derived(reportsRun != null && reportsRun >= 1000);
	const showDiscussions = $derived(discussionsMined != null && discussionsMined >= 50000);

	const edition = $derived(editionLabel(catalogLastUpdated));
	const editionText = $derived(
		isFallbackEdition(edition) ? 'Latest edition' : `Edition · ${edition}`
	);
</script>

<div class="dateline">
	<div class="landing-container dateline-row" aria-label="Live catalog statistics">
		<span class="d-edition">{editionText}</span>
		{#if showReports}
			<span class="d-dot" aria-hidden="true">·</span>
			<span class="d-stat"><span class="d-num">{reportsRun!.toLocaleString()}</span> reports run</span>
		{/if}
		{#if showDiscussions}
			<span class="d-dot" aria-hidden="true">·</span>
			<span class="d-stat"><span class="d-num">{formatCompact(discussionsMined!)}</span> discussions mined</span>
		{/if}
	</div>
</div>

<style>
	/* Editorial folio strip — same kicker tokens as the catalog hero dateline
	   (CatalogIndexHero), carrying the almanac voice onto the landing page. */
	.dateline {
		border-top: 1px solid var(--color-border);
		border-bottom: 1px solid var(--color-border);
		padding: 15px 0;
	}
	.dateline-row {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		align-items: baseline;
		gap: 8px 10px;
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-text-muted);
		font-weight: 600;
	}
	.d-edition {
		color: var(--color-accent);
		font-weight: 700;
	}
	.d-dot {
		color: var(--color-text-muted);
		opacity: 0.55;
	}
	.d-stat {
		color: var(--color-text-muted);
	}
	.d-num {
		color: var(--color-text-primary);
		font-weight: 700;
		font-feature-settings: 'tnum' 1, 'calt' 1;
	}
</style>
