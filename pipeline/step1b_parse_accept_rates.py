"""Step 1b: Parse acceptance rates from multiple sources and merge."""

import csv
import json
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

CS_CONF_STATS_DIR = CACHE_DIR / "cs-conf-stats"
CSCONFERENCES_DIR = CACHE_DIR / "csconferences"
CCF_DEADLINES_DIR = CACHE_DIR / "ccf-deadlines"

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
    "UbiComp": "UBICOMP-ISWC",
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
    "NeurIPS": "NEURIPS",
    "EuroCrypt": "EUROCRYPT",
    "CGO": "IEEE-ACMCGO",
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


def merge_sources(
    ccf_rates: dict[str, list[dict]],
    cs_stats: dict[str, list[dict]],
    emeryberger: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """Merge three sources with priority: ccf-deadlines > cs-conf-stats > emeryberger."""
    # Collect all conference IDs
    all_ids = set(ccf_rates) | set(cs_stats) | set(emeryberger)

    merged: dict[str, list[dict]] = {}
    for conf_id in sorted(all_ids):
        # Build year → entry mapping, lowest priority first
        by_year: dict[int, dict] = {}

        for entry in emeryberger.get(conf_id, []):
            by_year[entry["year"]] = entry

        for entry in cs_stats.get(conf_id, []):
            by_year[entry["year"]] = entry

        for entry in ccf_rates.get(conf_id, []):
            by_year[entry["year"]] = entry

        if by_year:
            merged[conf_id] = sorted(by_year.values(), key=lambda x: -x["year"])

    return merged


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 1b: parse and merge acceptance rates."""
    print("Fetching acceptance rate sources...")
    _clone_or_pull(CS_CONF_STATS_URL, CS_CONF_STATS_DIR)
    _clone_or_pull(CSCONFERENCES_URL, CSCONFERENCES_DIR)
    # ccf-deadlines is already cloned by step 1

    print("Loading sources...")
    ccf_rates = load_ccf_deadlines_rates()
    cs_stats = load_cs_conf_stats()
    emeryberger = load_emeryberger()

    print(f"  ccf-deadlines: {len(ccf_rates)} conferences")
    print(f"  cs-conf-stats: {len(cs_stats)} conferences")
    print(f"  emeryberger:   {len(emeryberger)} conferences")

    # Load our conference IDs to filter to known conferences
    conf_file = DATA_DIR / "raw" / "conferences.json"
    known_ids: set[str] | None = None
    if conf_file.exists():
        with open(conf_file, "r", encoding="utf-8") as f:
            known_ids = {c["id"] for c in json.load(f)}

    merged = merge_sources(ccf_rates, cs_stats, emeryberger)

    # Filter to known conference IDs
    if known_ids is not None:
        unknown = set(merged.keys()) - known_ids
        if unknown:
            print(f"  Skipping {len(unknown)} unmatched IDs: {', '.join(sorted(unknown)[:10])}{'...' if len(unknown) > 10 else ''}")
        merged = {k: v for k, v in merged.items() if k in known_ids}

    # Apply conference filter if specified
    if conferences_filter:
        merged = {k: v for k, v in merged.items() if k in conferences_filter}

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    total_entries = sum(len(v) for v in merged.values())
    print(f"Acceptance rates: {len(merged)} conferences, {total_entries} year-entries → {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
