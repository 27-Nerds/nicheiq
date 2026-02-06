export async function openCookiePreferences(): Promise<void> {
  const CookieConsent = await import("vanilla-cookieconsent");
  CookieConsent.showPreferences();
}
