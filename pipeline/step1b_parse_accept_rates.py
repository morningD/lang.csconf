"""Step 1b: Parse acceptance rates from multiple sources and merge."""

import csv
import json
import re
import subprocess
from pathlib import Path

import yaml

PIPELINE_DIR = Path(__file__).parent
CACHE_DIR = PIPELINE_DIR / ".cache"
DATA_DIR = PIPELINE_DIR.parent / "data"
OUTPUT_FILE = DATA_DIR / "raw" / "accept_rates.json"

# Repo URLs
CS_CONF_STATS_URL = "https://github.com/Xovee/cs-conf-stats.git"
CSCONFERENCES_URL = "https://github.com/emeryberger/csconferences.git"
LIXIN4EVER_URL = "https://github.com/lixin4ever/Conference-Acceptance-Rate.git"
SECURITY_RATES_URL = "https://github.com/puzhuoliu/Computer-Security-Conference-Acceptance-Rate.git"

CS_CONF_STATS_DIR = CACHE_DIR / "cs-conf-stats"
CSCONFERENCES_DIR = CACHE_DIR / "csconferences"
CCF_DEADLINES_DIR = CACHE_DIR / "ccf-deadlines"
LIXIN4EVER_DIR = CACHE_DIR / "conference-acceptance-rate"
SECURITY_RATES_DIR = CACHE_DIR / "security-acceptance-rate"

CONFERENCES_CS_URL = "https://www.conferences-computer.science/"

# Map source conference names → our conference IDs
# Only entries that differ from uppercase(name) need to be listed
ALIASES = {
    # cs-conf-stats series names
    "NeurIPS": "NEURIPS",
    "ACM MM": "ACMMM",
    "KDD": "SIGKDD",
    "IEEE S&P": "S&P",
    "USENIX Security": "USENIXSECURITY",
    "Asiacrypt": "ASIACRYPT",
    "Crypto": "CRYPTO",
    "Eurocrypt": "EUROCRYPT",
    "USENIX ATC": "USENIXATC",
    "CODES-ISSS": "CODES+ISSS",
    "UbiComp": "UBICOMP",
    "SIGGRAPH": "ACMSIGGRAPH",
    "SIGGRAPH Asia": "ACMSIGGRAPHASIA",
    "Eurographics": "EUROGRAPHICS",
    "VIS": "IEEEVIS",
    "VR": "IEEEVR",
    "EuroVis": "EUROVIS",
    "EuroSys": "EUROSYS",
    "SenSys": "SENSYS",
    "MobiCom": "MOBICOM",
    "MobiSys": "MOBISYS",
    "PPoPP": "PPOPP",
    "TACAS": "ETAPS",
    # emeryberger names
    "Oakland": "S&P",
    "UsenixSec": "USENIXSECURITY",
    "USENIX-ATC": "USENIXATC",
    "EuroCrypt": "EUROCRYPT",
    "CGO": "IEEE-ACMCGO",
    # lixin4ever names
    "NAACL-HLT": "NAACL",
    "TheWebConf": "WWW",
    "RecSys": "RECSYS",
    # puzhuoliu names
    "SEC": "USENIXSECURITY",
    # conferences-computer.science names
    "QEST+FORMATS": "QEST",
    "PerCom": "PERCOM",
}


def _clone_or_pull(url: str, dest: Path):
    """Clone or pull a git repository."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  Pulling {dest.name}...")
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=dest, check=False, capture_output=True,
        )
    else:
        print(f"  Cloning {dest.name}...")
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            check=True, capture_output=True,
        )


def _resolve_id(name: str) -> str:
    """Map a source conference name to our conference ID."""
    if name in ALIASES:
        return ALIASES[name]
    return name.upper().replace(" ", "").replace("/", "-")


def load_cs_conf_stats() -> dict[str, list[dict]]:
    """Load cs-conf-stats data/conf.json. Returns {conf_id: [{year, submitted, accepted}]}."""
    conf_file = CS_CONF_STATS_DIR / "data" / "conf.json"
    if not conf_file.exists():
        print("  cs-conf-stats/data/conf.json not found, skipping")
        return {}

    with open(conf_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    result: dict[str, list[dict]] = {}
    for conf in data.get("conferences", []):
        series = conf.get("series", "")
        if series == "Template":
            continue
        conf_id = _resolve_id(series)

        entries = []
        for yd in conf.get("yearly_data", []):
            year = yd.get("year")
            mt = yd.get("main_track", {})
            num_acc = mt.get("num_acc")
            num_sub = mt.get("num_sub")
            if year and num_acc and num_sub and num_sub > 0:
                entries.append({
                    "year": int(year),
                    "submitted": int(num_sub),
                    "accepted": int(num_acc),
                })

        if entries:
            result[conf_id] = sorted(entries, key=lambda x: -x["year"])

    return result


def load_ccf_deadlines_rates() -> dict[str, list[dict]]:
    """Load ccf-deadlines accept_rates/*/*.yml. Returns {conf_id: [{year, submitted, accepted}]}."""
    accept_dir = CCF_DEADLINES_DIR / "accept_rates"
    if not accept_dir.exists():
        print("  ccf-deadlines/accept_rates not found, skipping")
        return {}

    result: dict[str, list[dict]] = {}
    for yml_file in accept_dir.rglob("*.yml"):
        with open(yml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or not isinstance(data, list):
            continue

        for conf in data:
            title = conf.get("title", "")
            conf_id = _resolve_id(title)

            entries = []
            for ar in conf.get("accept_rates", []):
                year = ar.get("year")
                submitted = ar.get("submitted")
                accepted = ar.get("accepted")
                if year and submitted and accepted and submitted > 0:
                    entries.append({
                        "year": int(year),
                        "submitted": int(submitted),
                        "accepted": int(accepted),
                    })

            if entries:
                result[conf_id] = sorted(entries, key=lambda x: -x["year"])

    return result


def load_emeryberger() -> dict[str, list[dict]]:
    """Load emeryberger/csconferences CSV. Returns {conf_id: [{year, submitted, accepted}]}."""
    csv_file = CSCONFERENCES_DIR / "csconferences.csv"
    if not csv_file.exists():
        print("  csconferences/csconferences.csv not found, skipping")
        return {}

    raw: dict[str, list[dict]] = {}
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Conference", "").strip()
            if not name:
                continue
            conf_id = _resolve_id(name)

            year = row.get("Year", "")
            accepted = row.get("Accepted", "")
            submitted = row.get("Submitted", "")
            if not year or not accepted or not submitted:
                continue
            try:
                year_int = int(year)
                acc_int = int(accepted)
                sub_int = int(submitted)
            except (ValueError, TypeError):
                continue
            if sub_int <= 0:
                continue

            raw.setdefault(conf_id, []).append({
                "year": year_int,
                "submitted": sub_int,
                "accepted": acc_int,
            })

    # Sort each conference's entries by year descending
    for conf_id in raw:
        raw[conf_id].sort(key=lambda x: -x["year"])

    return raw


def _parse_md_table_row(row_text: str) -> tuple[str, int, int, int] | None:
    """Parse a markdown table row like |CONF'YY | rate% (acc/sub) | ... |.
    Returns (conf_name, year, submitted, accepted) or None."""
    cells = [c.strip() for c in row_text.split("|")]
    cells = [c for c in cells if c]
    if len(cells) < 2:
        return None

    # Parse conference name + year from first cell (e.g. "ACL'21", "CVPR'24")
    name_cell = cells[0].strip()
    # Skip "Findings" entries — those are secondary tracks
    if "Findings" in name_cell:
        return None
    m = re.match(r"^(.+?)['\u2019](\d{2})\s*$", name_cell)
    if not m:
        return None
    conf_name = m.group(1).strip()
    year_short = int(m.group(2))
    year = 2000 + year_short if year_short < 50 else 1900 + year_short

    # Look for (accepted/submitted) pattern in the "Long Paper" column (cells[1])
    rate_cell = cells[1] if len(cells) > 1 else ""
    # Match patterns like "25.0% (173/692)" or "29.9% (540/1807)"
    acc_sub = re.search(r"\((\d+)\s*/\s*(\d+)\)", rate_cell)
    if not acc_sub:
        return None
    accepted = int(acc_sub.group(1))
    submitted = int(acc_sub.group(2))
    if submitted <= 0:
        return None
    return conf_name, year, submitted, accepted


def load_lixin4ever() -> dict[str, list[dict]]:
    """Load lixin4ever/Conference-Acceptance-Rate README.md tables."""
    readme = LIXIN4EVER_DIR / "README.md"
    if not readme.exists():
        print("  conference-acceptance-rate/README.md not found, skipping")
        return {}

    with open(readme, "r", encoding="utf-8") as f:
        content = f.read()

    raw: dict[str, list[dict]] = {}
    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        parsed = _parse_md_table_row(line)
        if not parsed:
            continue
        conf_name, year, submitted, accepted = parsed
        conf_id = _resolve_id(conf_name)
        raw.setdefault(conf_id, []).append({
            "year": year,
            "submitted": submitted,
            "accepted": accepted,
        })

    for conf_id in raw:
        raw[conf_id].sort(key=lambda x: -x["year"])
    return raw


def load_security_rates() -> dict[str, list[dict]]:
    """Load puzhuoliu/Computer-Security-Conference-Acceptance-Rate README.md tables."""
    readme = SECURITY_RATES_DIR / "README.md"
    if not readme.exists():
        print("  security-acceptance-rate/README.md not found, skipping")
        return {}

    with open(readme, "r", encoding="utf-8") as f:
        content = f.read()

    raw: dict[str, list[dict]] = {}
    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        # Format: | Oakland'25 | 14.7% | 256/1739 |
        name_cell = cells[0]
        m = re.match(r"^(.+?)['\u2019](\d{2})\s*$", name_cell)
        if not m:
            continue
        conf_name = m.group(1).strip()
        year_short = int(m.group(2))
        year = 2000 + year_short if year_short < 50 else 1900 + year_short

        # Third cell has "accepted/submitted"
        paper_cell = cells[2] if len(cells) > 2 else ""
        acc_sub = re.search(r"(\d+)\s*/\s*(\d+)", paper_cell)
        if not acc_sub:
            continue
        accepted = int(acc_sub.group(1))
        submitted = int(acc_sub.group(2))
        if submitted <= 0:
            continue

        conf_id = _resolve_id(conf_name)
        raw.setdefault(conf_id, []).append({
            "year": year,
            "submitted": submitted,
            "accepted": accepted,
        })

    for conf_id in raw:
        raw[conf_id].sort(key=lambda x: -x["year"])
    return raw


def load_conferences_cs() -> dict[str, list[dict]]:
    """Scrape conferences-computer.science for acceptance rates."""
    try:
        import requests
    except ImportError:
        print("  requests not installed, skipping conferences-computer.science")
        return {}

    try:
        resp = requests.get(CONFERENCES_CS_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Failed to fetch conferences-computer.science: {e}")
        return {}

    html = resp.text
    raw: dict[str, list[dict]] = {}

    # Split by conf-title to pair conference names with their acceptance rates
    parts = html.split("conf-title")
    for part in parts[1:]:
        title_m = re.search(r'<abbr[^>]*>([^<]+)</abbr>', part)
        if not title_m:
            continue
        full_name = title_m.group(1)
        # Strip year suffix (e.g., "EMSOFT 2026" → "EMSOFT")
        conf_name = re.sub(r"\s*\d{4}$", "", full_name).strip()

        rate_m = re.search(r"✅ Acceptance rate: ([^<]+)", part)
        if not rate_m:
            continue
        rate_text = rate_m.group(1)

        conf_id = _resolve_id(conf_name)

        # Extract entries: patterns like "24% (27/111) in 2018" or "33% (2016)"
        # Pattern 1: "XX% (acc/sub) in YYYY" or "XX% (acc/sub, YYYY)"
        for m in re.finditer(
            r"(\d+(?:\.\d+)?)\s*%\s*\((\d+)\s*/\s*(\d+)\)\s*(?:in\s+)?(\d{4})?", rate_text
        ):
            accepted = int(m.group(2))
            submitted = int(m.group(3))
            year_str = m.group(4)
            if not year_str:
                continue
            year = int(year_str)
            if submitted <= 0 or year < 2000:
                continue
            raw.setdefault(conf_id, []).append({
                "year": year,
                "submitted": submitted,
                "accepted": accepted,
            })

        # Pattern 2: "XX% (YYYY, acc/sub)" — alternate format
        for m in re.finditer(
            r"(\d+(?:\.\d+)?)\s*%\s*\((\d{4}),\s*(\d+)\s*/\s*(\d+)\)", rate_text
        ):
            year = int(m.group(2))
            accepted = int(m.group(3))
            submitted = int(m.group(4))
            if submitted <= 0 or year < 2000:
                continue
            raw.setdefault(conf_id, []).append({
                "year": year,
                "submitted": submitted,
                "accepted": accepted,
            })

    # Deduplicate by (conf_id, year) — keep last seen
    for conf_id in raw:
        by_year: dict[int, dict] = {}
        for entry in raw[conf_id]:
            by_year[entry["year"]] = entry
        raw[conf_id] = sorted(by_year.values(), key=lambda x: -x["year"])

    return raw


def merge_sources(
    sources: list[dict[str, list[dict]]],
) -> dict[str, list[dict]]:
    """Merge sources with priority: first source = lowest, last = highest.

    Sources should be ordered from lowest to highest priority.
    On year conflict, higher-priority source wins.
    """
    all_ids: set[str] = set()
    for source in sources:
        all_ids.update(source.keys())

    merged: dict[str, list[dict]] = {}
    for conf_id in sorted(all_ids):
        by_year: dict[int, dict] = {}
        # Apply in order: lowest priority first, highest last (overwrites)
        for source in sources:
            for entry in source.get(conf_id, []):
                by_year[entry["year"]] = entry

        if by_year:
            merged[conf_id] = sorted(by_year.values(), key=lambda x: -x["year"])

    return merged


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 1b: parse and merge acceptance rates."""
    print("Fetching acceptance rate sources...")
    _clone_or_pull(CS_CONF_STATS_URL, CS_CONF_STATS_DIR)
    _clone_or_pull(CSCONFERENCES_URL, CSCONFERENCES_DIR)
    _clone_or_pull(LIXIN4EVER_URL, LIXIN4EVER_DIR)
    _clone_or_pull(SECURITY_RATES_URL, SECURITY_RATES_DIR)
    # ccf-deadlines is already cloned by step 1

    print("Loading sources...")
    ccf_rates = load_ccf_deadlines_rates()
    cs_stats = load_cs_conf_stats()
    emeryberger = load_emeryberger()
    lixin4ever = load_lixin4ever()
    security = load_security_rates()
    conferences_cs = load_conferences_cs()

    print(f"  ccf-deadlines:              {len(ccf_rates)} conferences")
    print(f"  cs-conf-stats:              {len(cs_stats)} conferences")
    print(f"  emeryberger:                {len(emeryberger)} conferences")
    print(f"  lixin4ever:                 {len(lixin4ever)} conferences")
    print(f"  security-rates:             {len(security)} conferences")
    print(f"  conferences-computer.science: {len(conferences_cs)} conferences")

    # Load our conference IDs to filter to known conferences
    conf_file = DATA_DIR / "raw" / "conferences.json"
    known_ids: set[str] | None = None
    if conf_file.exists():
        with open(conf_file, "r", encoding="utf-8") as f:
            known_ids = {c["id"] for c in json.load(f)}

    # Merge: lowest priority first → highest priority last
    merged = merge_sources([
        conferences_cs,      # 7. conferences-computer.science (lowest)
        security,            # 6. puzhuoliu security rates
        lixin4ever,          # 5. lixin4ever AI conferences
        emeryberger,         # 4. emeryberger/csconferences
        cs_stats,            # 2. cs-conf-stats
        ccf_rates,           # 1. ccf-deadlines (highest)
    ])

    # Filter to known conference IDs
    if known_ids is not None:
        unknown = set(merged.keys()) - known_ids
        if unknown:
            print(f"  Skipping {len(unknown)} unmatched IDs: {', '.join(sorted(unknown)[:10])}{'...' if len(unknown) > 10 else ''}")
        merged = {k: v for k, v in merged.items() if k in known_ids}

    # Apply conference filter: merge into existing file instead of overwriting
    if conferences_filter:
        filter_set = set(conferences_filter)
        existing = {}
        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        # Remove filtered conferences from existing, then add fresh data
        for k in list(existing.keys()):
            if k in filter_set:
                del existing[k]
        for k, v in merged.items():
            if k in filter_set:
                existing[k] = v
        merged = dict(sorted(existing.items()))

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    total_entries = sum(len(v) for v in merged.values())
    print(f"Acceptance rates: {len(merged)} conferences, {total_entries} year-entries → {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
