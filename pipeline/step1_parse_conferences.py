"""Step 1: Load conference list from conferences_base.json and apply CCF rank/category overrides."""

import json
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
DATA_DIR = PIPELINE_DIR.parent / "data"
BASE_CONFERENCES_FILE = PIPELINE_DIR / "conferences_base.json"
CCF_RANK_HISTORY_FILE = DATA_DIR / "ccf-versions" / "ccf_rank_history.json"
OUTPUT_FILE = DATA_DIR / "raw" / "conferences.json"

# The latest CCF version to use as the authoritative source for rank and category.
LATEST_CCF_VERSION = "2026"


def run(force: bool = False):
    """Run step 1: load conferences and apply CCF overrides."""
    # Load base conference list (the single source of truth for conference metadata)
    with open(BASE_CONFERENCES_FILE, "r", encoding="utf-8") as f:
        conferences = json.load(f)

    # Load CCF rank history (with rank + category per version)
    ccf_history = {}
    if CCF_RANK_HISTORY_FILE.exists():
        with open(CCF_RANK_HISTORY_FILE, "r", encoding="utf-8") as f:
            ccf_history = json.load(f)

    # Apply CCF rank and category overrides
    updated_ranks = 0
    updated_categories = 0
    for conf in conferences:
        conf_id = conf["id"]
        history = ccf_history.get(conf_id)
        if not history:
            # Not in any CCF list → rank N, keep base category
            if conf["rank"] != "N":
                conf["rank"] = "N"
                updated_ranks += 1
            continue

        # Find the latest CCF version this conference appears in
        if LATEST_CCF_VERSION in history:
            entry = history[LATEST_CCF_VERSION]
        else:
            # Conference was in older CCF editions but dropped from latest → rank N
            # Use the most recent version for category
            sorted_versions = sorted(history.keys(), reverse=True)
            entry = history[sorted_versions[0]]
            if conf["rank"] != "N":
                conf["rank"] = "N"
                updated_ranks += 1
            # Still update category from the most recent version
            if isinstance(entry, dict) and "category" in entry:
                new_cat = entry["category"]
                if conf["category"] != new_cat:
                    conf["category"] = new_cat
                    updated_categories += 1
            continue

        # Conference is in the latest CCF version
        if isinstance(entry, dict):
            new_rank = entry["rank"]
            new_cat = entry["category"]
        else:
            # Old format compatibility: entry is just a rank string
            new_rank = entry
            new_cat = None

        if conf["rank"] != new_rank:
            updated_ranks += 1
            conf["rank"] = new_rank

        if new_cat and conf["category"] != new_cat:
            updated_categories += 1
            conf["category"] = new_cat

    # Sort by rank (A first) then by title
    rank_order = {"A": 0, "B": 1, "C": 2, "N": 3}
    conferences.sort(key=lambda c: (rank_order.get(c["rank"], 9), c["title"]))

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(conferences, f, indent=2, ensure_ascii=False)

    print(f"Loaded {len(conferences)} conferences from {BASE_CONFERENCES_FILE.name}")
    if updated_ranks:
        print(f"  Updated {updated_ranks} ranks from CCF {LATEST_CCF_VERSION}")
    if updated_categories:
        print(f"  Updated {updated_categories} categories from CCF history")
    print(f"  → {OUTPUT_FILE}")
    return conferences


if __name__ == "__main__":
    run()
