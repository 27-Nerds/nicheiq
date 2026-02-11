import type { PricingStrategy } from "$lib/types/report";

/**
 * Format a concise pricing summary from the structured pricing object.
 * Mirrors the Python PricingStrategyResult.format_summary() logic.
 */
export function formatPricingSummary(pricing: PricingStrategy): string {
	const parts: string[] = [pricing.pricing_model];

	if (pricing.pricing_model === "Freemium-Lite") {
		// 2-tier model: Free + Pro. Use pro price, fall back to starter if pro is missing
		const displayPrice =
			pricing.recommended_pro_price || pricing.recommended_starter_price;
		if (displayPrice) {
			parts.push(`${displayPrice} pro`);
		}
	} else {
		if (pricing.recommended_starter_price) {
			parts.push(`${pricing.recommended_starter_price} starter`);
		}
		if (pricing.recommended_pro_price) {
			parts.push(`${pricing.recommended_pro_price} pro`);
		}
	}

	if (pricing.recommended_enterprise_price) {
		parts.push(`${pricing.recommended_enterprise_price} enterprise`);
	}

	if (parts.length > 1) {
		return `${parts[0]}: ${parts.slice(1).join(", ")}`;
	}
	return parts[0];
}
