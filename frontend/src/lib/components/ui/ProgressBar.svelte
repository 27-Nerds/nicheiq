<script lang="ts">
	interface Props {
		value: number; // 0-1 or 0-100
		max?: number;
		label?: string;
		showValue?: boolean;
		variant?: 'default' | 'success' | 'warning' | 'error';
	}

	let { value, max = 1, label, showValue = true, variant = 'default' }: Props = $props();

	// Normalize value to percentage
	const percentage = $derived(Math.min(100, Math.max(0, (value / max) * 100)));

	const variantColors: Record<string, string> = {
		default: 'bg-accent',
		success: 'bg-success',
		warning: 'bg-warning',
		error: 'bg-error'
	};

	// Auto-detect variant based on value
	function getAutoVariant(pct: number): string {
		if (pct >= 70) return 'success';
		if (pct >= 40) return 'warning';
		return 'error';
	}

	const finalVariant = $derived(variant === 'default' ? getAutoVariant(percentage) : variant);
</script>

<div class="w-full">
	{#if label || showValue}
		<div class="flex justify-between items-center mb-2">
			{#if label}
				<span class="text-sm text-text-secondary">{label}</span>
			{/if}
			{#if showValue}
				<span class="text-sm font-mono text-text-muted">{percentage.toFixed(0)}%</span>
			{/if}
		</div>
	{/if}
	<div class="progress-bar">
		<div
			class="progress-bar-fill {variantColors[finalVariant]}"
			style="width: {percentage}%"
		></div>
	</div>
</div>
