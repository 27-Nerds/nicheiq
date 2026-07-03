"""Sync src/nicheiq/utils/_public_apis_generated.py with the upstream public-apis README.

Source: https://github.com/public-apis/public-apis (community-curated list of free APIs,
~1.6k entries). We keep entries whose Auth is `No` (fully open) or `apiKey` (free key) —
both are an obtainable public data route in the pipeline's vocabulary. OAuth entries are
dropped (user-context auth is not a bulk data route).

Usage:
    source .venv/bin/activate
    python scripts/generate_public_apis_data.py            # fetch upstream, regenerate if changed
    python scripts/generate_public_apis_data.py --check    # report drift only, write nothing
    python scripts/generate_public_apis_data.py <readme>   # parse a local README copy instead

The generated module header carries a sha256 of the parsed entry set — re-running against
an unchanged upstream is a no-op, so this is safe to run on a schedule.
"""
from __future__ import annotations

import hashlib
import re
import sys
import urllib.request
from urllib.parse import urlparse

OUT = "src/nicheiq/utils/_public_apis_generated.py"
UPSTREAM = "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"

# Hosts that carry many UNRELATED entries' docs (or are API marketplaces) — a domain match
# on these would be meaningless, so their entries get name-matching only.
DOMAIN_BLOCKLIST_SUFFIXES = (
    "github.com", "github.io", "gitlab.com", "bitbucket.org", "medium.com", "notion.site",
    "gitbook.io", "readthedocs.io", "readthedocs.org", "google.com", "rapidapi.com",
    "herokuapp.com", "vercel.app", "netlify.app", "web.app", "firebaseapp.com",
)


def _domain(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower().lstrip("www.")
    except ValueError:
        return ""
    if not host or "." not in host or len(host) < 6:
        return ""
    if any(host == s or host.endswith("." + s) for s in DOMAIN_BLOCKLIST_SUFFIXES):
        return ""
    return host


def parse(readme_text: str) -> list[tuple[str, str]]:
    cat = None
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for ln in readme_text.splitlines():
        m = re.match(r"^### (.+)", ln)
        if m:
            cat = m.group(1).strip()
            continue
        if not (ln.startswith("|") and cat) or "Description" in ln or "---" in ln:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        nm = re.match(r"\[([^\]]+)\]\(([^)]+)\)", cells[0])
        if not nm:
            continue
        name, url = nm.group(1).strip(), nm.group(2).strip()
        auth = cells[2].replace("`", "").strip()
        if auth not in ("No", "apiKey"):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((name, _domain(url)))
    return out


def _entries_hash(entries: list[tuple[str, str]]) -> str:
    return hashlib.sha256(repr(sorted(entries)).encode()).hexdigest()[:16]


def _current_hash() -> str | None:
    try:
        for ln in open(OUT, encoding="utf-8"):
            m = re.search(r"entries-sha256:(\w+)", ln)
            if m:
                return m.group(1)
    except OSError:
        return None
    return None


def _fetch_upstream() -> str:
    req = urllib.request.Request(UPSTREAM, headers={"User-Agent": "nicheiq-allowlist-sync"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main() -> None:
    check_only = "--check" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        text = open(args[0], encoding="utf-8").read()
        origin = args[0]
    else:
        text = _fetch_upstream()
        origin = UPSTREAM
    entries = parse(text)
    if not entries or len(entries) < 500:
        # an upstream format change must never silently wipe the allowlist
        raise SystemExit(f"refusing to write: parsed only {len(entries)} entries from {origin}")
    new_hash = _entries_hash(entries)
    if new_hash == _current_hash():
        print(f"up to date ({len(entries)} entries, sha {new_hash})")
        return
    if check_only:
        print(f"DRIFT: upstream has changed (parsed {len(entries)} entries, "
              f"sha {new_hash} vs current {_current_hash()}). Re-run without --check to sync.")
        raise SystemExit(1)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(
            '"""GENERATED — do not edit by hand. Sync: scripts/generate_public_apis_data.py.\n\n'
            "Free public APIs (auth: none or free key) from github.com/public-apis/public-apis.\n"
            "Each entry: (name, docs_domain_or_empty). Matching rules live in\n"
            "public_data_sources.py — this module is data only.\n"
            f"entries-sha256:{new_hash}\n"
            '"""\n\n'
            "PUBLIC_APIS: tuple[tuple[str, str], ...] = (\n"
        )
        for name, dom in entries:
            f.write(f"    ({name!r}, {dom!r}),\n")
        f.write(")\n")
    print(f"wrote {OUT}: {len(entries)} entries (sha {new_hash})")


if __name__ == "__main__":
    main()
