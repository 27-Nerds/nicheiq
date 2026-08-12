"""Canonical primary delivery surfaces for solution ideas."""

from __future__ import annotations

import re
from typing import Literal

DeliveryFormat = Literal[
    "web-app",
    "mobile-app",
    "desktop-app",
    "browser-extension",
    "platform-plugin",
    "api",
    "bot-assistant",
    "data-product",
    "report",
    "service",
    "physical-product",
    "other",
]

DELIVERY_FORMAT_VOCAB = (
    "web-app",
    "mobile-app",
    "desktop-app",
    "browser-extension",
    "platform-plugin",
    "api",
    "bot-assistant",
    "data-product",
    "report",
    "service",
    "physical-product",
    "other",
)

_ALIASES = {
    "web app": "web-app",
    "web application": "web-app",
    "website": "web-app",
    "mobile app": "mobile-app",
    "mobile application": "mobile-app",
    "ios app": "mobile-app",
    "android app": "mobile-app",
    "desktop app": "desktop-app",
    "desktop application": "desktop-app",
    "browser extension": "browser-extension",
    "chrome extension": "browser-extension",
    "firefox extension": "browser-extension",
    "safari extension": "browser-extension",
    "browser add on": "browser-extension",
    "browser addon": "browser-extension",
    "platform plugin": "platform-plugin",
    "platform app": "platform-plugin",
    "shopify app": "platform-plugin",
    "wordpress plugin": "platform-plugin",
    "figma plugin": "platform-plugin",
    "api": "api",
    "developer api": "api",
    "bot": "bot-assistant",
    "bot assistant": "bot-assistant",
    "chatbot": "bot-assistant",
    "data product": "data-product",
    "dataset": "data-product",
    "data feed": "data-product",
    "report": "report",
    "pdf report": "report",
    "service": "service",
    "managed service": "service",
    "consulting service": "service",
    "physical product": "physical-product",
    "hardware": "physical-product",
    "device": "physical-product",
    "other": "other",
}

_INFERENCE_PATTERNS = (
    ("browser-extension", r"\b(?:browser|chrome|firefox|safari)\s+(?:extension|add[ -]?on)\b"),
    ("mobile-app", r"\b(?:mobile|ios|android)\s+(?:app|application)\b"),
    ("desktop-app", r"\b(?:desktop|windows|mac(?:os)?)\s+(?:app|application)\b"),
    ("platform-plugin", r"\b(?:shopify\s+app|wordpress\s+plugin|figma\s+plugin|platform\s+(?:app|plugin))\b"),
    ("bot-assistant", r"\b(?:slack|discord|teams)\s+bot\b|\b(?:chatbot|bot assistant|conversational assistant)\b"),
    ("web-app", r"\b(?:web\s+(?:app|application|dashboard)|browser-based\s+(?:app|application|dashboard|tool))\b"),
    ("api", r"\b(?:developer|rest|graphql|public)\s+api\b|\bapi\s+(?:product|service|endpoint)\b"),
    ("data-product", r"\b(?:downloadable\s+)?dataset\b|\bdata\s+(?:product|feed)\b"),
    ("report", r"\b(?:pdf|benchmark|audit|research|monthly|weekly)\s+report\b"),
    ("service", r"\b(?:managed|consulting|done-for-you|professional)\s+service\b"),
    ("physical-product", r"\b(?:physical\s+product|hardware\s+(?:product|device)|connected\s+device)\b"),
)

def _key(value: str) -> str:
    return " ".join(re.sub(r"[_-]+", " ", value.strip().casefold()).split())


def normalize_delivery_format(value: str | None) -> DeliveryFormat | None:
    """Normalize a format label; abstain when prose is not an explicit known alias."""
    if not value:
        return None
    key = _key(str(value))
    return _ALIASES.get(key)  # type: ignore[return-value]


def _explicit_formats(text: str) -> tuple[DeliveryFormat, ...]:
    formats: list[DeliveryFormat] = []
    for delivery_format, pattern in _INFERENCE_PATTERNS:
        if re.search(pattern, text):
            formats.append(delivery_format)  # type: ignore[arg-type]
    return tuple(formats)


def infer_delivery_format(text: str | None) -> DeliveryFormat | None:
    """Return one explicit surface, ``other`` for several, or None when prose is silent."""
    formats = _explicit_formats(" ".join((text or "").casefold().split()))
    if len(formats) == 1:
        return formats[0]
    return "other" if formats else None
