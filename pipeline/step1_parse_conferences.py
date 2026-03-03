"""Step 1: Parse CCF conference list from ccf-deadlines repository."""

import json
import os
import subprocess
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).parent / ".cache"
CCF_REPO_URL = "https://github.com/ccfddl/ccf-deadlines.git"
CCF_REPO_DIR = CACHE_DIR / "ccf-deadlines"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "raw" / "conferences.json"

YEAR_MIN = 2010
YEAR_MAX = 2025

# CCF categories
CCF_CATEGORIES = {"AI", "DB", "NW", "SE", "CG", "CT", "HI", "SC", "DS", "MX"}
CCF_RANKS = {"A", "B", "C", "N"}


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

        conferences.append({
            "id": conf.get("title", "").upper().replace(" ", ""),
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
    seen_dblp = set()

    # Parse all YAML files under conference/
    for yml_file in sorted(conference_dir.rglob("*.yml")):
        confs = parse_conference_file(yml_file)
        for conf in confs:
            # Deduplicate by dblp key
            if conf["dblp"] not in seen_dblp:
                seen_dblp.add(conf["dblp"])
                all_conferences.append(conf)

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
