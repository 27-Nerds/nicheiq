const DELIVERY_FORMAT_LABELS: Record<string, string> = {
  "web-app": "Web app",
  "mobile-app": "Mobile app",
  "desktop-app": "Desktop app",
  "browser-extension": "Browser extension",
  "platform-plugin": "Platform plugin",
  api: "API",
  "bot-assistant": "Bot or assistant",
  "data-product": "Data product",
  report: "Report",
  service: "Service",
  "physical-product": "Physical product",
  other: "Other",
};

export function deliveryFormatLabel(value?: string | null): string {
  if (!value) return "";
  return (
    DELIVERY_FORMAT_LABELS[value]
    ?? value
      .split("-")
      .map((word, index) => (
        index === 0
          ? word.charAt(0).toUpperCase() + word.slice(1)
          : word
      ))
      .join(" ")
  );
}
