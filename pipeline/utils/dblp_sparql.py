"""DBLP SPARQL client — batch-query papers + authors via sparql.dblp.org."""

import re
from collections import Counter, defaultdict

import requests

from pipeline.utils.filters import is_proceedings_volume

SPARQL_ENDPOINT = "https://sparql.dblp.org/sparql"

QUERY_TEMPLATE = """\
PREFIX dblp: <https://dblp.org/rdf/schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?stream ?year ?paper ?title ?venue ?authorName ?ordinal WHERE {{
  VALUES (?stream ?year) {{
{values}
  }}
  ?paper dblp:publishedInStream ?stream .
  ?paper dblp:yearOfPublication ?year .
  ?paper dblp:title ?title .
  ?paper dblp:publishedIn ?venue .
  ?paper dblp:hasSignature ?sig .
  ?sig dblp:signatureOrdinal ?ordinal .
  ?sig dblp:signatureDblpName ?authorName .
}}
"""

# Regex to extract 2-digit year suffix from DBLP paper keys (e.g., "conf/acl/FooBar24" → 24)
_URI_YEAR_RE = re.compile(r"(\d{2})[a-z]?$")

# Proceedings volume keys use pattern like "2023-10" (year-part_number) — not real papers
_PROCEEDINGS_KEY_RE = re.compile(r"^\d{4}-\d+$")

# Venue patterns to exclude (workshop/companion proceedings mixed into main conf stream)
# Also excludes DBLP "@" workshop notation (e.g., "MLSA@PKDD/ECML")
_EXCLUDED_VENUE_RE = re.compile(
    r"\bWorkshop|\bCompanion\b|\bTutorial\b|@",
    re.IGNORECASE,
)


def _find_workshop_abbreviation_venues(
    paper_venues: dict[tuple[str, int, str], str],
) -> set[tuple[str, str]]:
    """Detect abbreviated workshop venue names (e.g., ICCVW, ICSTW, DSN-W).

    For each (key, year), find the dominant venue (most papers) and check if
    other venues are workshop abbreviation variants: {dominant}W, {dominant}-W,
    {dominant}EW (case-insensitive).

    Returns set of (key, venue) pairs that should be excluded.
    """
    # Count papers per (key, venue), ignoring year to find stable dominant venue
    key_venue_counts: dict[str, Counter] = defaultdict(Counter)
    for (key, _year, _title), venue in paper_venues.items():
        key_venue_counts[key][venue] += 1

    exclude: set[tuple[str, str]] = set()
    for key, counts in key_venue_counts.items():
        dominant = counts.most_common(1)[0][0]
        dom_upper = dominant.upper()
        # Also check against stream key itself (e.g., key="iccv" → "ICCV")
        # This handles edge cases where a batch only has workshop papers
        key_upper = key.upper()
        for venue in counts:
            if venue == dominant:
                continue
            v = venue.upper()
            # {Dominant}W, {Dominant}-W, {Dominant}EW
            if v in (f"{dom_upper}W", f"{dom_upper}-W", f"{dom_upper}EW"):
                exclude.add((key, venue))
            # Also check against stream key: {KEY}W, {KEY}-W, {KEY}EW
            elif key_upper != dom_upper and v in (
                f"{key_upper}W", f"{key_upper}-W", f"{key_upper}EW"
            ):
                exclude.add((key, venue))
    return exclude


def _build_values_block(pairs: list[tuple[str, int]]) -> str:
    """Build the VALUES clause for a batch of (dblp_key, year) pairs."""
    lines = []
    for key, year in pairs:
        stream = f"<https://dblp.org/streams/conf/{key}>"
        lines.append(f'    ({stream} "{year}"^^xsd:gYear)')
    return "\n".join(lines)


def _clean_author_name(name: str) -> str:
    """Remove DBLP disambiguation suffixes (e.g., 'Wei Wang 0001' → 'Wei Wang')."""
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return name


def fetch_batch_sparql(
    pairs: list[tuple[str, int]],
    timeout: int = 120,
) -> dict[tuple[str, int], list[dict]]:
    """Batch-query multiple (dblp_key, year) pairs via SPARQL.

    Returns: {(dblp_key, year): [{"title": str, "authors": [{"name": str, "ordinal": int}]}]}
    """
    if not pairs:
        return {}

    values_block = _build_values_block(pairs)
    query = QUERY_TEMPLATE.format(values=values_block)

    resp = requests.post(
        SPARQL_ENDPOINT,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    # Parse: group rows by (stream, year, title) → collect authors
    # row keys: stream, year, title, authorName, ordinal
    # Also track venue per paper for workshop abbreviation detection
    paper_authors: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    paper_venues: dict[tuple[str, int, str], str] = {}
    stream_prefix = "https://dblp.org/streams/conf/"

    for row in data.get("results", {}).get("bindings", []):
        stream_uri = row["stream"]["value"]
        key = stream_uri.removeprefix(stream_prefix)
        year = int(row["year"]["value"])
        title = row["title"]["value"]
        venue = row.get("venue", {}).get("value", "")
        author_name = _clean_author_name(row["authorName"]["value"])
        ordinal = int(row["ordinal"]["value"])

        # Skip workshop/companion proceedings mixed into the main conf stream
        if _EXCLUDED_VENUE_RE.search(venue):
            continue

        # Skip proceedings volume editor entries (not real papers)
        if is_proceedings_volume(title):
            continue

        # Extract real conference year from paper URI key.
        # DBLP URI keys encode the conference year in a 2-digit suffix
        # (e.g., conf/acl/FooBar24 → 2024). This is more reliable than
        # yearOfPublication, which can lag by 1 year when proceedings are
        # published the following year.
        paper_uri = row["paper"]["value"]
        paper_key = paper_uri.rsplit("/", 1)[-1]
        # Skip proceedings volume keys (e.g., "2023-10" for Part 10)
        if _PROCEEDINGS_KEY_RE.match(paper_key):
            continue
        m = _URI_YEAR_RE.search(paper_key)
        if m:
            suffix = int(m.group(1))
            uri_year = 2000 + suffix if suffix <= 99 else 1900 + suffix
            # Only use URI year if it's in our data range (avoids noise like 2089)
            if 2010 <= uri_year <= 2026 and uri_year != year:
                year = uri_year

        paper_key_tuple = (key, year, title)
        paper_authors[paper_key_tuple].append({
            "name": author_name,
            "ordinal": ordinal,
        })
        paper_venues[paper_key_tuple] = venue

    # Second pass: filter workshop abbreviation venues (e.g., ICCVW, ICSTW, DSN-W)
    # These bypass the word-based _EXCLUDED_VENUE_RE filter.
    ws_abbrev = _find_workshop_abbreviation_venues(paper_venues)
    if ws_abbrev:
        filtered = 0
        for paper_key_tuple in list(paper_authors):
            key, _year, _title = paper_key_tuple
            venue = paper_venues.get(paper_key_tuple, "")
            if (key, venue) in ws_abbrev:
                del paper_authors[paper_key_tuple]
                filtered += 1
        if filtered:
            venues_str = ", ".join(f"{v} (stream {k})" for k, v in sorted(ws_abbrev))
            print(f"  Filtered {filtered} papers from workshop abbreviation venues: {venues_str}")

    # Group by (dblp_key, year) → list of papers with sorted authors
    result: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for (key, year, title), authors in paper_authors.items():
        authors.sort(key=lambda a: a["ordinal"])
        result[(key, year)].append({
            "title": title,
            "authors": authors,
        })

    # Ensure all requested pairs appear in result (even if empty)
    for pair in pairs:
        if pair not in result:
            result[pair] = []

    return dict(result)
