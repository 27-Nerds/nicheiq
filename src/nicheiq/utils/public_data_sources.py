"""Deterministic recognition of well-known public data sources in data-route claims.

Motivation (indie-hackers run-2 review, 2026-07-03): the tool-grounded route verifier
(`verify_data_routes`) decides ONLY from web-search snippets, and sparse snippets made it
misclassify canonically public sources — GitHub's REST API came back "restricted", SAM.gov
"paywalled". A claim that names a famous free source shouldn't hinge on search recall.

Two layers of data:
- `_public_apis_generated.PUBLIC_APIS` — ~1.4k free APIs (auth: none or free key) from
  github.com/public-apis/public-apis (regenerate via scripts/generate_public_apis_data.py).
- `CURATED_SOURCES` — major government / statistics / research registries the repo misses
  (SAM.gov, Eurostat, BLS, NVD, PubMed, ...) plus aliases for sources whose repo entry
  can't be matched safely (e.g. the GitHub REST API itself).

Matching is deliberately conservative — a false positive here blesses a route as "public"
and skips verification entirely, so:
- DOMAIN match: the entry's docs domain appears in the text (repo-hosting/marketplace
  domains were excluded at generation time).
- PHRASE match: multi-word names (>= 8 chars) as a word-boundary phrase — distinctive
  enough on their own ("Open Food Facts", "UK Companies House").
- TOKEN+API match: single-token names only when immediately followed by "API"/"dataset"/
  "database"/"registry"/"data" ("GBIF API", "Wikidata dataset") — never a bare word hit
  ("Cats", "Base", "Coffee" appear as plain API names upstream).
"""
from __future__ import annotations

import re
from functools import lru_cache

from ._public_apis_generated import PUBLIC_APIS

# (canonical name, aliases/phrases, domains) — all matched case-insensitively. Aliases use
# the PHRASE rule (multi-word) or TOKEN+API rule (single word) automatically.
CURATED_SOURCES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("GitHub REST API", ("github api", "github rest api", "github graphql api",
                         "github public api", "github issues api", "github releases api",
                         "github search api", "github pull requests api", "github pull requests",
                         "github advisory database", "github archive", "gharchive"),
     ("api.github.com", "gharchive.org")),
    ("OSV (Open Source Vulnerabilities)", ("open source vulnerabilities", "osv api"),
     ("osv.dev",)),
    ("PyPI", ("pypi",), ("pypi.org",)),
    ("npm Registry", ("npm",), ("registry.npmjs.org", "npmjs.com")),
    ("RubyGems", ("rubygems",), ("rubygems.org",)),
    ("Packagist", ("packagist",), ("packagist.org",)),
    ("Maven Central", ("maven central",), ("search.maven.org",)),
    ("Stack Exchange Data Dump", ("stack overflow data dump", "stack exchange data dump"), ()),
    ("SEC CIK database", ("sec cik", "cik database"), ()),
    ("SAM.gov", ("sam.gov",), ("sam.gov",)),
    ("USAspending", ("usaspending",), ("usaspending.gov",)),
    ("SEC EDGAR", ("sec edgar", "edgar filings", "edgar full-text"), ("sec.gov",)),
    ("TED (EU public procurement)", ("ted europa", "tenders electronic daily"), ("ted.europa.eu",)),
    ("UK Companies House", ("companies house",), ("company-information.service.gov.uk",)),
    ("Eurostat", ("eurostat",), ("ec.europa.eu/eurostat",)),
    ("OECD", ("oecd data", "oecd statistics", "oecd api"), ("data.oecd.org", "stats.oecd.org")),
    ("IMF Data", ("imf data", "imf api"), ("data.imf.org",)),
    ("World Bank Open Data", ("world bank",), ("data.worldbank.org", "api.worldbank.org")),
    ("UN Comtrade", ("comtrade",), ("comtrade.un.org", "comtradeapi.un.org")),
    ("WHO GHO", ("who global health observatory", "who gho"), ("who.int",)),
    ("ILOSTAT", ("ilostat",), ("ilostat.ilo.org",)),
    ("ECB Data Portal", ("ecb data", "ecb statistical"), ("data.ecb.europa.eu", "sdw.ecb.europa.eu")),
    ("US Bureau of Labor Statistics", ("bureau of labor statistics", "bls api", "bls data"),
     ("bls.gov",)),
    ("US Census Bureau", ("census bureau", "census api", "american community survey"),
     ("census.gov",)),
    ("USDA", ("usda nass", "usda fooddata", "usda quick stats", "usda api", "usda data"),
     ("usda.gov", "nal.usda.gov")),
    ("NOAA", ("noaa api", "noaa data", "noaa climate"), ("noaa.gov",)),
    ("US EIA", ("eia api", "energy information administration"), ("eia.gov",)),
    ("NIST NVD", ("nist nvd", "national vulnerability database", "nvd api"), ("nvd.nist.gov",)),
    ("CISA KEV", ("cisa kev", "known exploited vulnerabilities"), ("cisa.gov",)),
    ("data.gov", ("data.gov",), ("data.gov", "api.data.gov")),
    ("data.europa.eu", ("data.europa.eu",), ("data.europa.eu",)),
    ("GovInfo", ("govinfo",), ("govinfo.gov",)),
    ("CourtListener", ("courtlistener", "recap archive"), ("courtlistener.com",)),
    ("PubMed / NCBI E-utilities", ("pubmed", "ncbi e-utilities", "ncbi entrez"),
     ("pubmed.ncbi.nlm.nih.gov", "eutils.ncbi.nlm.nih.gov")),
    ("ClinicalTrials.gov", ("clinicaltrials.gov", "clinical trials api"), ("clinicaltrials.gov",)),
    ("Semantic Scholar", ("semantic scholar",), ("semanticscholar.org",)),
    ("OpenStreetMap / Overpass", ("openstreetmap", "overpass api"),
     ("openstreetmap.org", "overpass-api.de")),
    ("crates.io", ("crates.io",), ("crates.io",)),
    ("Hacker News (Algolia)", ("hacker news api", "hn algolia", "algolia hn"),
     ("hn.algolia.com", "hacker-news.firebaseio.com")),
    ("Stack Exchange API", ("stack exchange api", "stackexchange api", "stack overflow api"),
     ("api.stackexchange.com",)),
    ("OpenDota", ("opendota",), ("opendota.com",)),
    ("iNaturalist", ("inaturalist",), ("inaturalist.org",)),
    ("MLCommons / MLPerf", ("mlcommons", "mlperf"), ("mlcommons.org",)),
    ("Wikidata", ("wikidata",), ("wikidata.org", "query.wikidata.org")),
    ("GDELT", ("gdelt",), ("gdeltproject.org",)),
    ("Common Crawl", ("common crawl",), ("commoncrawl.org",)),
    ("Internet Archive", ("internet archive", "wayback machine"), ("archive.org",)),
    # 2026-07-09: combined-query recall miss (live EPA RSL case, see idea_improvement_loop_v4
    # comment) — these canonical public datasets were reachable by web search but missed by
    # retrieval because they never got their own allowlist entry.
    ("EPA Regional Screening Levels (RSL)", ("epa regional screening levels", "epa rsl",
                                              "epa soil screening levels", "regional screening levels",
                                              "regional screening level table", "soil screening levels"),
     ("epa.gov",)),
    ("USDA Plant Hardiness Zone Map", ("usda plant hardiness zone map", "plant hardiness zone map",
                                       "plant hardiness zone", "usda plant hardiness"),
     ("planthardiness.ars.usda.gov",)),
    ("ASPCA Toxic and Non-Toxic Plants List", ("aspca toxic and non-toxic plants",
                                                "aspca toxic plant list", "aspca plant list",
                                                "toxic and non-toxic plants list"),
     ("aspca.org",)),
    ("HUD-USPS ZIP Code Crosswalk", ("hud usps zip code crosswalk", "hud zip code crosswalk",
                                     "usps zip code crosswalk", "zip code to county crosswalk",
                                     "zip-county crosswalk"),
     ("huduser.gov",)),
    ("Census ZIP Code Tabulation Areas (ZCTA)", ("zip code tabulation areas", "census zcta",
                                                  "census county relationship file",
                                                  "zcta to county relationship file",
                                                  "census zip code tabulation areas"),
     ("census.gov",)),
    # 2026-08 (S4.4): regulated-industries data routes missed their allowlist entries too.
    # "ecfr" alone is excluded from aliases — a bare 4-char token is too easy to false-positive
    # via the exact-name sub-token pass; the domain + full phrase are unambiguous on their own.
    ("eCFR", ("electronic code of federal regulations",), ("ecfr.gov",)),
    ("DailyMed", ("dailymed",), ("dailymed.nlm.nih.gov",)),
    ("FDA National Drug Code Directory", ("ndc directory", "national drug code directory",
                                          "fda ndc"), ("fda.gov", "open.fda.gov")),
    ("DEA Diversion Control Division", ("dea diversion", "diversion control division"),
     ("deadiversion.usdoj.gov",)),
    ("FDA Green Book", ("fda green book", "approved animal drug products"),
     ("animaldrugsatfda.fda.gov",)),
)

_TOKEN_CUES = r"(?:rest\s+|graphql\s+|public\s+|open\s+|v\d+\s+)?(?:api|apis|dataset|datasets|database|registry|data)"
_GENERIC_SINGLE = frozenset({
    # single-token repo names that are common English words — token+API adjacency is still
    # too loose for these ("weather API", "news API" are category phrases, not source names)
    "weather", "news", "sports", "finance", "music", "movies", "books", "jokes", "quotes",
    "recipes", "currency", "country", "countries", "calendar", "dictionary", "translation",
    "email", "photos", "images", "video", "audio", "maps", "search", "trivia", "facts",
    "cats", "dogs", "coffee", "beer", "wine", "humor", "advice", "bored", "base", "block",
    "ghost", "codex", "halo", "forza", "dune", "brazil", "classify", "citi", "chomp",
})


def _entry_patterns() -> list[tuple[str, str, str]]:
    """(canonical_name, kind, needle) triples; kind in {domain, phrase, token}."""
    out: list[tuple[str, str, str]] = []
    for name, aliases, domains in CURATED_SOURCES:
        for d in domains:
            out.append((name, "domain", d.lower()))
        for a in aliases:
            kind = "phrase" if (" " in a or "." in a) else "token"
            out.append((name, kind, a.lower()))
    for name, domain in PUBLIC_APIS:
        if domain:
            out.append((name, "domain", domain))
        n = name.strip()
        if " " in n:
            if len(n) >= 8:
                out.append((name, "phrase", n.lower()))
        elif len(n) >= 4 and n.lower() not in _GENERIC_SINGLE:
            out.append((name, "token", n.lower()))
    return out


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[str, re.Pattern]]:
    pats: list[tuple[str, re.Pattern]] = []
    for name, kind, needle in _entry_patterns():
        esc = re.escape(needle)
        if kind == "domain":
            # domain anywhere (own token: not inside a longer hostname label)
            pats.append((name, re.compile(rf"(?<![\w.-]){esc}(?![\w-])", re.I)))
        elif kind == "phrase":
            pats.append((name, re.compile(rf"\b{esc}\b", re.I)))
        else:  # token: only as an explicit source reference — "<Name> API/dataset/..."
            pats.append((name, re.compile(rf"\b{esc}\s+{_TOKEN_CUES}\b", re.I)))
    return pats


@lru_cache(maxsize=1)
def _exact_names() -> dict[str, str]:
    """normalized alias/name/domain -> canonical name, for whole-part/sub-token exact
    matching. A data_sources list item that IS the source name ("PyPI", "crates.io") — or a
    bare name inside a registry list ("(npm, PyPI, RubyGems)") — carries no API-cue context,
    so the cue-adjacency rule would miss it; an exact match on the full short fragment is
    just as unambiguous. Curated aliases qualify at >= 3 chars ("npm"); repo names need
    >= 4 and the generic stoplist — same false-positive discipline as the pattern rules."""
    out: dict[str, str] = {}
    for name, aliases, domains in CURATED_SOURCES:
        for needle in (name.lower(), *[a.lower() for a in aliases], *[d.lower() for d in domains]):
            if len(needle) >= 3 and needle not in _GENERIC_SINGLE:
                out.setdefault(needle, name)
    for name, domain in PUBLIC_APIS:
        for needle in (name.strip().lower(), domain):
            if needle and len(needle) >= 4 and needle not in _GENERIC_SINGLE:
                out.setdefault(needle, name)
    return out


def retrieve_known_sources(parts) -> list[tuple[str, str]] | None:
    """RETRIEVAL step: if EVERY non-empty part matches a recognized public source, return
    [(part, matched_names)] pairs; else None. The all-parts rule is the safety contract —
    a famous source listed next to an unknown vendor feed must never bless the whole route.
    matched_names carries ALL hits for the part ("npm Registry, PyPI, RubyGems, crates.io"
    for a multi-registry part) — showing only the first hit made the confirm LLM correctly
    reject the pair as under-matched. The match is retrieval, NOT a verdict: pass the pairs
    to llm_confirm_known_route."""
    cleaned = [p.strip() for p in (parts or []) if p and p.strip()]
    if not cleaned:
        return None
    out: list[tuple[str, str]] = []
    for p in cleaned:
        names = _match_all_known_public_sources(p)
        if not names:
            return None
        out.append((p, ", ".join(names)))
    return out


def _match_all_known_public_sources(text: str, cap: int = 6) -> list[str]:
    """All distinct known-source hits in ``text`` (same rules as the single-hit matcher,
    plus a sub-token pass: bare names inside a delimiter list — "(npm, PyPI, RubyGems)" —
    carry no API-cue context, so try each short fragment against the exact-name dict)."""
    if not text or not text.strip():
        return []
    hits: list[str] = []
    exact = _exact_names()
    for frag in re.split(r"[,;()/]", text):
        frag = frag.strip().strip(".,;:[]'\" ").lower()
        if frag and len(frag) <= 40:
            name = exact.get(frag)
            if name and name not in hits:
                hits.append(name)
    for name, pat in _compiled():
        if name not in hits and pat.search(text):
            hits.append(name)
            if len(hits) >= cap:
                break
    return hits


def llm_confirm_known_route(matches: list[tuple[str, str]], *, context: str = "") -> str | None:
    """CONFIRMATION step over the retrieved allowlist entries: one cheap structured call that
    checks each claimed part genuinely refers to its matched source AND the capability the
    claim needs is the kind that source publicly provides — a name-pattern hit alone is too
    broad (name coincidences; public platforms whose SPECIFIC data is partner-gated).
    Returns the deduped canonical names when confirmed; None on rejection OR any error —
    callers fall through to the full web-search verifier, so this can only reduce risk."""
    if not matches:
        return None
    from loguru import logger
    from pydantic import BaseModel, Field

    from ..config.settings import settings
    from .llm_service import LLMService

    class _RouteConfirm(BaseModel):
        confirmed: bool = False
        note: str = Field("", description="One line: which pair fails and why, or 'all match'.")

    lines = "\n".join(f'- claimed: "{p[:160]}" -> matched source: {n}' for p, n in matches)
    prompt = (
        "An idea's data-route claims were each name-matched to a KNOWN free/public data "
        "source. Confirm the matches are REAL, not superficial.\n\n"
        f"CLAIM -> MATCHED SOURCE PAIRS:\n{lines}\n\n"
        + (f"IDEA CONTEXT: {context[:400]}\n\n" if context else "")
        + "confirmed=true ONLY if EVERY claimed part (a) actually refers to its matched "
          "source — not a different product with a similar name — (b) needs the kind of "
          "data that source PUBLICLY provides, and (c) if the claim or idea context implies "
          "recurring/fresh data (real-time, weekly, monthly updates), the source is known "
          "to publish at that cadence — a static, archival, or historical-only dataset "
          "behind a matched name => confirmed=false. A public platform whose specific "
          "claimed data is private, partner-gated, or paid => confirmed=false. When unsure "
          "about any pair, confirmed=false (a false confirm skips verification; a false "
          "reject only costs one web search)."
    )
    try:
        r, _usage = LLMService.invoke_structured(
            prompt=prompt, output_model=_RouteConfirm, temperature=0.1, timeout=45,
            model_name=settings.pain_point_validation_llm, reasoning_effort="none",
            creative=True)
        if getattr(r, "confirmed", False):
            return ", ".join(dict.fromkeys(n for _, n in matches))
        logger.info(f"[allowlist] LLM rejected source match "
                    f"({(getattr(r, 'note', '') or '')[:120]}) — falling through to web verify")
        return None
    except Exception as e:
        logger.warning(f"[allowlist] confirm failed, falling through to web verify: {str(e)[:100]}")
        return None


def match_known_public_source(text: str) -> str | None:
    """Return the canonical name of a well-known free/public data source referenced in
    ``text``, or None. Conservative by design (see module docstring) — a miss falls
    through to the web-search verifier, a hit short-circuits it."""
    if not text or not text.strip():
        return None
    stripped = text.strip().strip(".,;:()[]'\" ").lower()
    if len(stripped) <= 40:
        hit = _exact_names().get(stripped)
        if hit:
            return hit
    for name, pat in _compiled():
        if pat.search(text):
            return name
    return None
