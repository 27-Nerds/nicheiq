"""ASCII slugify helper for stable theme/category identifiers."""

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Lowercase, collapse non-alphanumerics to dashes, strip leading/trailing dashes."""
    return _NON_ALNUM.sub("-", text.lower()).strip("-")
