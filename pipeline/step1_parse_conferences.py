"""Step 1: Parse CCF conference list from ccf-deadlines repository."""

import json
import os
import subprocess
from pathlib import Path

import yaml

PIPELINE_DIR = Path(__file__).parent
CACHE_DIR = PIPELINE_DIR / ".cache"
CCF_REPO_URL = "https://github.com/ccfddl/ccf-deadlines.git"
CCF_REPO_DIR = CACHE_DIR / "ccf-deadlines"
OUTPUT_FILE = PIPELINE_DIR.parent / "data" / "raw" / "conferences.json"
MANUAL_CONFERENCES_FILE = PIPELINE_DIR / "manual_conferences.json"

YEAR_MIN = 2010
YEAR_MAX = 2025

# CCF categories
CCF_CATEGORIES = {"AI", "DB", "NW", "SE", "CG", "CT", "HI", "SC", "DS", "MX"}
CCF_RANKS = {"A", "B", "C", "N"}

# Override conference IDs to resolve naming conflicts
# Key: (generated_id, dblp_key) → new_id
ID_OVERRIDES = {
    ("FSE", "fse"): "FSE-CRYPTO",  # Fast Software Encryption (crypto) conflicts with SIGSOFT FSE
}

# Override wrong CCF ranks from upstream ccf-deadlines
# Key: generated_id → corrected rank
RANK_OVERRIDES = {
    "ACMSIGGRAPHASIA": "N",  # Not in any CCF list; ccf-deadlines wrongly marks it as A
}

# Override wrong DBLP keys from upstream ccf-deadlines
# Values can be a string (single key) or a list (multiple streams to merge)
DBLP_KEY_OVERRIDES = {
    "icme": "icmcs",
    "icpc": "iwpc",
    "sigspatial": "gis",
    "eusipcolyon": "eusipco",
    "APWeb": "apweb",
    "ccs": "asiaccs",  # AsiaCCS was pulling ACM CCS data
    "pkdd": ["pkdd", "ecml"],  # ECML-PKDD splits across two DBLP streams
    "sigsoft": ["sigsoft", "esec"],  # ESEC/FSE merges both SIGSOFT FSE and ESEC streams
    "cade": ["cade", "ijcar"],  # CADE/IJCAR alternates between CADE and IJCAR names
}


def clone_or_pull_repo():
    """Clone or pull the ccf-deadlines repository."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CCF_REPO_DIR.exists():
        print("Pulling latest ccf-deadlines...")
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=CCF_REPO_DIR,
            check=True,
            capture_output=True,
        )
    else:
        print("Cloning ccf-deadlines...")
        subprocess.run(
            ["git", "clone", "--depth", "1", CCF_REPO_URL, str(CCF_REPO_DIR)],
            check=True,
            capture_output=True,
        )


def parse_conference_file(filepath: Path) -> list[dict]:
    """Parse a single YAML conference file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return []

    # The YAML files can contain a single conf or a list
    if isinstance(data, dict):
        data = [data]

    conferences = []
    for conf in data:
        if not isinstance(conf, dict):
            continue

        dblp_key = conf.get("dblp")
        if not dblp_key:
            continue
        dblp_key = DBLP_KEY_OVERRIDES.get(dblp_key, dblp_key)
        # dblp_key can now be a string or a list of strings

        # Extract rank
        rank_info = conf.get("rank", {})
        ccf_rank = rank_info.get("ccf", "N") if isinstance(rank_info, dict) else "N"
        if ccf_rank not in CCF_RANKS:
            ccf_rank = "N"

        # Extract category
        category = conf.get("sub", "MX")
        if category not in CCF_CATEGORIES:
            category = "MX"

        # Extract available years from confs list
        years = set()
        confs_list = conf.get("confs", [])
        if isinstance(confs_list, list):
            for c in confs_list:
                if isinstance(c, dict) and "year" in c:
                    year = c["year"]
                    if isinstance(year, int) and YEAR_MIN <= year <= YEAR_MAX:
                        years.add(year)

        # If no explicit year list, assume all years in range
        if not years:
            years = set(range(YEAR_MIN, YEAR_MAX + 1))

        generated_id = conf.get("title", "").upper().replace(" ", "").replace("/", "-")
        # Apply ID overrides for naming conflicts
        dblp_for_lookup = dblp_key if isinstance(dblp_key, str) else dblp_key[0]
        final_id = ID_OVERRIDES.get((generated_id, dblp_for_lookup), generated_id)

        # Apply rank overrides for wrong upstream CCF ranks
        ccf_rank = RANK_OVERRIDES.get(final_id, ccf_rank)

        conferences.append({
            "id": final_id,
            "title": conf.get("title", ""),
            "description": conf.get("description", ""),
            "category": category,
            "rank": ccf_rank,
            "dblp": dblp_key,
            "years": sorted(years),
        })

    return conferences


def run(force: bool = False):
    """Run step 1: parse conferences."""
    clone_or_pull_repo()

    conference_dir = CCF_REPO_DIR / "conference"
    if not conference_dir.exists():
        print(f"Conference directory not found: {conference_dir}")
        return []

    all_conferences = []
    seen_ids = set()

    # Parse all YAML files under conference/
    for yml_file in sorted(conference_dir.rglob("*.yml")):
        confs = parse_conference_file(yml_file)
        for conf in confs:
            # Deduplicate by conference id (dblp can be a list now)
            if conf["id"] not in seen_ids:
                seen_ids.add(conf["id"])
                all_conferences.append(conf)

    # Merge manual conferences (not in ccf-deadlines)
    if MANUAL_CONFERENCES_FILE.exists():
        with open(MANUAL_CONFERENCES_FILE, "r", encoding="utf-8") as f:
            manual = json.load(f)
        for conf in manual:
            if conf["id"] not in seen_ids:
                seen_ids.add(conf["id"])
                all_conferences.append(conf)
                print(f"  Added manual conference: {conf['id']} ({conf['title']})")

    # Sort by rank (A first) then by title
    rank_order = {"A": 0, "B": 1, "C": 2, "N": 3}
    all_conferences.sort(key=lambda c: (rank_order.get(c["rank"], 9), c["title"]))

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_conferences, f, indent=2, ensure_ascii=False)

    print(f"Parsed {len(all_conferences)} conferences with DBLP keys → {OUTPUT_FILE}")
    return all_conferences


if __name__ == "__main__":
    run()
