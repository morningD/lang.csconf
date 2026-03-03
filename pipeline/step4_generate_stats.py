"""Step 4: Generate aggregated statistics from classified author data."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pipeline.utils.nationality_to_lang import LANGUAGE_COLORS, LANGUAGE_GROUPS

DATA_DIR = Path(__file__).parent.parent / "data"
CLASSIFIED_DIR = DATA_DIR / "classified" / "authors"
RAW_DIR = DATA_DIR / "raw"
STATS_DIR = DATA_DIR / "stats"


def load_conferences() -> list[dict]:
    """Load conference metadata."""
    conf_file = RAW_DIR / "conferences.json"
    if not conf_file.exists():
        return []
    with open(conf_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_classified() -> list[dict]:
    """Load all classified author files."""
    all_data = []
    for f in sorted(CLASSIFIED_DIR.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            all_data.append(json.load(fh))
    return all_data


def compute_language_distribution(authors: list[dict]) -> dict[str, int]:
    """Count authors by language group."""
    counts = defaultdict(int)
    for a in authors:
        lang = a.get("language", "Other")
        counts[lang] += 1
    return dict(counts)


def run(force: bool = False):
    """Run step 4: generate aggregated statistics."""
    conferences = load_conferences()
    conf_meta = {c["id"]: c for c in conferences}
    all_data = load_all_classified()

    if not all_data:
        print("No classified data found. Run step 3 first.")
        return

    # Prepare output directories
    for subdir in ["by_conference", "by_category", "by_rank"]:
        (STATS_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # Accumulators
    global_by_year = defaultdict(lambda: defaultdict(int))
    global_total = defaultdict(int)
    conf_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    cat_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    rank_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    total_papers = 0
    conf_years_seen = defaultdict(set)

    for entry in all_data:
        conf_id = entry.get("conference", "")
        year = entry.get("year", 0)
        authors = entry.get("authors", [])

        if not conf_id or not year:
            continue

        total_papers += len(authors)
        conf_years_seen[conf_id].add(year)

        # Get conference metadata
        meta = conf_meta.get(conf_id, {})
        category = meta.get("category", "MX")
        rank = meta.get("rank", "N")

        dist = compute_language_distribution(authors)

        for lang, count in dist.items():
            global_by_year[year][lang] += count
            global_total[lang] += count
            conf_data[conf_id][year][lang] += count
            cat_data[category][year][lang] += count
            rank_data[rank][year][lang] += count

    # 1. meta.json
    meta_json = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_papers": total_papers,
        "total_conferences": len(conf_years_seen),
        "year_range": [2010, 2025],
        "languages": LANGUAGE_GROUPS,
        "language_colors": LANGUAGE_COLORS,
    }
    _write_json(STATS_DIR / "meta.json", meta_json)

    # 2. global_summary.json
    global_summary = {
        "total": dict(global_total),
        "by_year": {str(y): dict(langs) for y, langs in sorted(global_by_year.items())},
    }
    _write_json(STATS_DIR / "global_summary.json", global_summary)

    # 3. by_conference/{conf}.json
    for conf_id, year_data in conf_data.items():
        meta = conf_meta.get(conf_id, {})
        conf_stats = {
            "id": conf_id,
            "title": meta.get("title", conf_id),
            "description": meta.get("description", ""),
            "category": meta.get("category", "MX"),
            "rank": meta.get("rank", "N"),
            "dblp": meta.get("dblp", ""),
            "years": sorted(conf_years_seen.get(conf_id, set())),
            "by_year": {str(y): dict(langs) for y, langs in sorted(year_data.items())},
            "total": dict(_sum_dicts(year_data.values())),
        }
        _write_json(STATS_DIR / "by_conference" / f"{conf_id}.json", conf_stats)

    # 4. by_category/{category}.json
    for cat, year_data in cat_data.items():
        cat_stats = {
            "category": cat,
            "conferences": [c["id"] for c in conferences if c.get("category") == cat],
            "by_year": {str(y): dict(langs) for y, langs in sorted(year_data.items())},
            "total": dict(_sum_dicts(year_data.values())),
        }
        _write_json(STATS_DIR / "by_category" / f"{cat}.json", cat_stats)

    # 5. by_rank/{rank}.json
    for rank, year_data in rank_data.items():
        rank_stats = {
            "rank": rank,
            "conferences": [c["id"] for c in conferences if c.get("rank") == rank],
            "by_year": {str(y): dict(langs) for y, langs in sorted(year_data.items())},
            "total": dict(_sum_dicts(year_data.values())),
        }
        _write_json(STATS_DIR / "by_rank" / f"{rank}.json", rank_stats)

    # 6. conferences_index.json — lightweight index for the website
    index = []
    for conf_id, year_data in conf_data.items():
        meta = conf_meta.get(conf_id, {})
        total = _sum_dicts(year_data.values())
        dominant = max(total, key=total.get) if total else "Other"
        total_sum = max(sum(total.values()), 1)
        lang_pcts = {lang: round(count / total_sum * 100, 1) for lang, count in total.items()}

        # Latest year data
        years_sorted = sorted(conf_years_seen.get(conf_id, set()))
        latest_year = years_sorted[-1] if years_sorted else 0
        latest_dist = dict(year_data.get(latest_year, {})) if latest_year else {}
        latest_total = max(sum(latest_dist.values()), 1)
        latest_lang = max(latest_dist, key=latest_dist.get) if latest_dist else dominant
        latest_pct = round(latest_dist.get(latest_lang, 0) / latest_total * 100, 1) if latest_dist else 0
        latest_lang_pcts = {lang: round(count / latest_total * 100, 1) for lang, count in latest_dist.items()}

        index.append({
            "id": conf_id,
            "title": meta.get("title", conf_id),
            "category": meta.get("category", "MX"),
            "rank": meta.get("rank", "N"),
            "total_papers": sum(total.values()),
            "dominant_language": dominant,
            "dominant_pct": round(total.get(dominant, 0) / total_sum * 100, 1),
            "lang_pcts": lang_pcts,
            "latest_year": latest_year,
            "latest_lang": latest_lang,
            "latest_pct": latest_pct,
            "latest_lang_pcts": latest_lang_pcts,
        })
    index.sort(key=lambda c: (-c["total_papers"],))
    _write_json(STATS_DIR / "conferences_index.json", index)

    print(f"Stats generated: {total_papers} papers across {len(conf_years_seen)} conferences → {STATS_DIR}")


def _sum_dicts(dicts) -> dict:
    """Sum multiple Counter-like dicts."""
    result = defaultdict(int)
    for d in dicts:
        for k, v in d.items():
            result[k] += v
    return dict(result)


def _write_json(path: Path, data):
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    run()
