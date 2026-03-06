"""DBLP SPARQL client — batch-query papers + authors via sparql.dblp.org."""

import re
from collections import defaultdict

import requests

SPARQL_ENDPOINT = "https://sparql.dblp.org/sparql"

QUERY_TEMPLATE = """\
PREFIX dblp: <https://dblp.org/rdf/schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?stream ?year ?paper ?title ?authorName ?ordinal WHERE {{
  VALUES (?stream ?year) {{
{values}
  }}
  ?paper dblp:publishedInStream ?stream .
  ?paper dblp:yearOfPublication ?year .
  ?paper dblp:title ?title .
  ?paper dblp:hasSignature ?sig .
  ?sig dblp:signatureOrdinal ?ordinal .
  ?sig dblp:signatureDblpName ?authorName .
}}
"""

# Regex to extract 2-digit year suffix from DBLP paper keys (e.g., "conf/acl/FooBar24" → 24)
_URI_YEAR_RE = re.compile(r"(\d{2})[a-z]?$")


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
    paper_authors: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    stream_prefix = "https://dblp.org/streams/conf/"

    for row in data.get("results", {}).get("bindings", []):
        stream_uri = row["stream"]["value"]
        key = stream_uri.removeprefix(stream_prefix)
        year = int(row["year"]["value"])
        title = row["title"]["value"]
        author_name = _clean_author_name(row["authorName"]["value"])
        ordinal = int(row["ordinal"]["value"])

        # Fix DBLP yearOfPublication bugs: extract real year from paper URI key.
        # E.g., conf/acl/ChangLLWWL24 → 2024, but DBLP says yearOfPublication=2014.
        paper_uri = row["paper"]["value"]
        paper_key = paper_uri.rsplit("/", 1)[-1]
        m = _URI_YEAR_RE.search(paper_key)
        if m:
            suffix = int(m.group(1))
            uri_year = 2000 + suffix if suffix <= 99 else 1900 + suffix
            if uri_year != year and abs(uri_year - year) > 1:
                year = uri_year

        paper_authors[(key, year, title)].append({
            "name": author_name,
            "ordinal": ordinal,
        })

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
