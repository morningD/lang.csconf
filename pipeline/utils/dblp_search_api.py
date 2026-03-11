"""DBLP Search API client — reverse-search venue keywords and fetch papers.

Used by step2c to fill SPARQL indexing gaps where proceedings exist in DBLP
but are not indexed in the RDF stream.
"""

import re
import time

import requests

from pipeline.utils.dblp_sparql import _clean_author_name

DBLP_SEARCH_API = "https://dblp.org/search/publ/api"
DBLP_MIRRORS = [
    "https://dblp.org",
    "https://dblp.uni-trier.de",
    "https://dblp.dagstuhl.de",
]
HEADERS = {"User-Agent": "lang.csconf-gap-filler/1.0 (research project)"}

# Max results per Search API page
_SEARCH_PAGE_SIZE = 1000


def _fetch_html(url: str, timeout: int = 30) -> str | None:
    """Fetch HTML from DBLP, trying mirrors on failure. Returns None on 404.

    Note: Do NOT send custom User-Agent for HTML pages. DBLP returns truncated
    lazy-loaded HTML (~24KB) to browser-like UAs, but full content (~267KB)
    with the default python-requests UA.
    """
    for mirror in DBLP_MIRRORS:
        full_url = url.replace("https://dblp.org", mirror)
        try:
            resp = requests.get(full_url, timeout=timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            time.sleep(1)
    return None


def _extract_paper_keys_from_html(html: str) -> set[str]:
    """Extract DBLP paper keys from a proceedings HTML page."""
    # Paper keys contain: letters, digits, hyphens, slashes
    raw_keys = re.findall(r'/rec/((?:conf|journals)/[\w/\-]+)', html)
    keys = set()
    for key in raw_keys:
        key = re.sub(r'\.\w+$', '', key)
        if key and key.count('/') >= 2:
            keys.add(key)
    return keys


def _extract_titles_from_html(html: str) -> list[str]:
    """Extract paper titles from a proceedings HTML page."""
    titles = re.findall(r'class="title"[^>]*>([^<]+)<', html)
    return [t.rstrip('.') for t in titles if len(t) < 300 and 'Proceedings' not in t]


def check_proceedings_years(dblp_key: str) -> set[int]:
    """Check which years have proceedings links on the DBLP index page.

    Returns a set of years that have actual proceedings page links (not just
    a heading). This distinguishes "not yet indexed" from "indexing gap".
    Only requires one HTTP request per conference.
    """
    import html as html_lib

    index_html = _fetch_html(f"https://dblp.org/db/conf/{dblp_key}/index.html")
    if not index_html:
        return set()

    index_html = html_lib.unescape(index_html)
    years_with_proceedings: set[int] = set()

    sections = re.split(r"(<h2[^>]*>.*?</h2>)", index_html, flags=re.DOTALL)
    for i, section in enumerate(sections):
        if not re.match(r"<h2", section):
            continue
        text = re.sub(r"<[^>]+>", "", section).strip()
        # Extract year from heading
        year_match = re.search(r"\b(20[12]\d)\b", text)
        if not year_match:
            continue
        year = int(year_match.group(1))

        if i + 1 < len(sections):
            content = sections[i + 1]
            # Check if there are any proceedings links
            links = re.findall(
                r'href="(?:https?://[^/]+)?(/db/conf/[^"]+\.html)"', content
            )
            if links:
                years_with_proceedings.add(year)

    return years_with_proceedings


def fetch_proceedings_data(
    dblp_key: str, year: int
) -> tuple[set[str], list[str], list[str], list[str]]:
    """Fetch paper keys, titles, and HTML from DBLP proceedings page(s).

    Returns: (paper_keys, proceedings_urls, sample_titles, html_pages)
    """
    import html as html_lib

    index_html = _fetch_html(f"https://dblp.org/db/conf/{dblp_key}/index.html")
    if not index_html:
        return set(), [], [], []

    index_html = html_lib.unescape(index_html)

    proc_urls = _find_proceedings_urls(index_html, dblp_key, year)
    if not proc_urls:
        proc_urls = _guess_proceedings_urls(dblp_key, year)

    all_keys: set[str] = set()
    used_urls: list[str] = []
    sample_titles: list[str] = []
    html_pages: list[str] = []

    for url in proc_urls:
        time.sleep(0.3)
        html = _fetch_html(url)
        if html:
            keys = _extract_paper_keys_from_html(html)
            if keys:
                all_keys.update(keys)
                used_urls.append(url)
                html_pages.append(html)
            if len(sample_titles) < 10:
                titles = _extract_titles_from_html(html)
                sample_titles.extend(titles[:10 - len(sample_titles)])

    return all_keys, used_urls, sample_titles, html_pages


def _find_proceedings_urls(index_html: str, dblp_key: str, year: int) -> list[str]:
    """Parse DBLP index page for proceedings page URLs for a given year."""
    year_str = str(year)
    urls: list[str] = []

    sections = re.split(r"(<h2[^>]*>.*?</h2>)", index_html, flags=re.DOTALL)

    for i, section in enumerate(sections):
        if not re.match(r"<h2", section):
            continue
        text = re.sub(r"<[^>]+>", "", section).strip()
        if year_str not in text:
            continue

        if i + 1 < len(sections):
            content = sections[i + 1]
        else:
            continue

        # Links can be relative (/db/conf/...) or absolute (https://dblp.*/db/conf/...)
        links = re.findall(
            r'href="(?:https?://[^/]+)?(/db/conf/[^"]+\.html)"', content
        )
        for link in links:
            basename = link.rsplit("/", 1)[-1].replace(".html", "")
            if re.search(r"w\d*$", basename):
                continue
            url = f"https://dblp.org{link}"
            if url not in urls:
                urls.append(url)

    return urls


def _guess_proceedings_urls(dblp_key: str, year: int) -> list[str]:
    """Generate candidate proceedings URLs when index page parsing fails."""
    base = f"https://dblp.org/db/conf/{dblp_key}"
    candidates = [
        f"{base}/{dblp_key}{year}.html",
        f"{base}/{dblp_key}{year}-1.html",
    ]
    urls = []
    for url in candidates:
        html = _fetch_html(url)
        if html:
            urls.append(url)
            if url.endswith("-1.html"):
                for part in range(2, 10):
                    part_url = f"{base}/{dblp_key}{year}-{part}.html"
                    part_html = _fetch_html(part_url)
                    if part_html:
                        urls.append(part_url)
                    else:
                        break
            break
    return urls


def discover_venue_keyword(
    dblp_key: str,
    proc_urls: list[str],
    sample_titles: list[str],
) -> str | None:
    """Discover the DBLP venue keyword by searching for a paper title.

    Returns: The venue keyword string (e.g., "GLOBECOM", "ECML/PKDD") or None.
    """
    if not sample_titles:
        return None

    # Derive valid conference keys from proceedings URLs
    valid_conf_keys = {dblp_key}
    for url in proc_urls:
        m = re.search(r'/db/conf/(\w+)/', url)
        if m:
            valid_conf_keys.add(m.group(1))

    # Search for paper titles to discover the venue keyword
    for title in sample_titles[:5]:
        time.sleep(1.5)
        query = f'"{title}"'
        for attempt in range(3):
            try:
                resp = requests.get(
                    DBLP_SEARCH_API,
                    params={"q": query, "format": "json", "h": "5"},
                    headers=HEADERS,
                    timeout=30,
                )
                if resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                # Verify we got valid JSON
                if not resp.text.strip():
                    time.sleep(3)
                    continue
                data = resp.json()
                break
            except Exception:
                time.sleep(3)
                continue
        else:
            continue

        hits = data.get("result", {}).get("hits", {}).get("hit", [])
        for hit in hits:
            info = hit.get("info", {})
            hit_key = info.get("key", "")
            if not any(f"conf/{k}/" in hit_key for k in valid_conf_keys):
                continue
            venue = info.get("venue")
            if venue:
                if isinstance(venue, list):
                    return venue[0]
                return venue
    return None


def fetch_papers_from_html(proc_html_pages: list[str]) -> list[dict]:
    """Parse papers directly from DBLP proceedings page HTML.

    Fallback when Search API is unavailable. Extracts titles and authors
    from the proceedings page structure.

    Args:
        proc_html_pages: List of HTML content strings from proceedings pages.

    Returns: List of {"title": str, "authors": [{"name": str, "ordinal": int}]}
    """
    papers = []

    for html in proc_html_pages:
        # DBLP entries are in <li class="entry inproceedings|article"> elements.
        # Authors: <span itemprop="author">...<span itemprop="name">Name</span>...</span>
        # Title: <span class="title" itemprop="name">Title.</span>
        entries = re.split(r'<li\s+class="entry\s+(?:inproceedings|article)', html)

        for entry in entries[1:]:
            # Extract title
            title_match = re.search(
                r'class="title"[^>]*>([^<]+)<', entry
            )
            if not title_match:
                continue
            title = title_match.group(1).strip().rstrip('.')

            if 'Proceedings' in title and len(title) > 200:
                continue

            # Extract authors from <span itemprop="author"> blocks only
            # Each author block contains <span itemprop="name">Name</span>
            author_blocks = re.findall(
                r'itemprop="author"[^>]*>.*?itemprop="name"[^>]*>([^<]+)<',
                entry,
            )
            author_names = author_blocks if author_blocks else []

            if not author_names:
                continue

            authors = []
            for idx, name in enumerate(author_names):
                name = _clean_author_name(name.strip())
                if name:
                    authors.append({"name": name, "ordinal": idx + 1})

            if title and authors:
                papers.append({"title": title, "authors": authors})

    return papers


def fetch_papers_search_api(
    venue_keyword: str,
    year: int,
    valid_keys: set[str] | None = None,
    timeout: int = 60,
) -> list[dict]:
    """Fetch papers via DBLP Search API with optional key filtering.

    Returns: List of {"title": str, "authors": [{"name": str, "ordinal": int}]}
    """
    papers = []
    offset = 0

    while True:
        time.sleep(1.5)
        query = f"venue:{venue_keyword}: year:{year}:"
        data = None
        for attempt in range(3):
            try:
                resp = requests.get(
                    DBLP_SEARCH_API,
                    params={
                        "q": query,
                        "format": "json",
                        "h": str(_SEARCH_PAGE_SIZE),
                        "f": str(offset),
                    },
                    headers=HEADERS,
                    timeout=timeout,
                )
                if resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                if not resp.text.strip():
                    time.sleep(3)
                    continue
                data = resp.json()
                break
            except Exception as e:
                if attempt == 2:
                    print(f"    Search API error: {e}")
                time.sleep(3)
        if data is None:
            break

        result = data.get("result", {})
        hits = result.get("hits", {})
        hit_list = hits.get("hit", [])
        total = int(hits.get("@total", "0"))

        if not hit_list:
            break

        for hit in hit_list:
            info = hit.get("info", {})
            key = info.get("key", "")
            title = info.get("title", "")

            if valid_keys is not None and key not in valid_keys:
                continue

            authors_raw = info.get("authors", {}).get("author", [])
            if isinstance(authors_raw, dict):
                authors_raw = [authors_raw]

            authors = []
            for idx, author_entry in enumerate(authors_raw):
                if isinstance(author_entry, dict):
                    name = author_entry.get("text", "")
                else:
                    name = str(author_entry)
                name = _clean_author_name(name)
                if name:
                    authors.append({"name": name, "ordinal": idx + 1})

            if title and authors:
                papers.append({"title": title, "authors": authors})

        offset += len(hit_list)
        if offset >= total:
            break

    return papers
