/**
 * payability_class enum → human label, shared by report/gate/design-preview surfaces.
 * Covers the full live enum; anything outside it falls back to a title-cased slug so
 * a new backend value degrades to something readable instead of a raw slug.
 */
const PAYABILITY_LABELS: Record<string, string> = {
  "personal-wallet": "Personal wallet",
  "prosumer-wallet": "Prosumer wallet",
  "smb-budget": "Small-business budget",
  "corporate-budget": "Corporate budget",
  mixed: "Mixed",
};

export function formatPayabilityClass(value: string | null | undefined): string | null {
  const slug = value?.trim();
  if (!slug) return null;
  const known = PAYABILITY_LABELS[slug];
  if (known) return known;
  const words = slug.replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
