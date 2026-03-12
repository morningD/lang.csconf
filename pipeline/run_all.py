"""Orchestrator: run all pipeline steps sequentially."""

import argparse
import re
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import step1_parse_conferences, step1b_parse_accept_rates, step2_crawl_sparql, step2b_crawl_venues, step2c_fill_gaps, step3_classify_names, step4_generate_stats


def main():
    parser = argparse.ArgumentParser(description="lang.csconf data pipeline")
    parser.add_argument("--force", action="store_true", help="Force re-crawl all data")
    parser.add_argument("--step", type=str, help="Run only a specific step (1, 1b, 2, 2b, 2c, 3, 4)")
    parser.add_argument("--conferences", type=str, help="Comma-separated conference IDs to process (e.g., CVPR,AAAI,SIGMOD)")

    args = parser.parse_args()
    conferences_filter = args.conferences.split(",") if args.conferences else None

    # Clean up macOS Finder duplicate files (" 2.json", " 3.json", etc.)
    # These are created when Finder copies/moves files and cause data corruption.
    data_dir = Path(__file__).parent.parent / "data"
    finder_dup_re = re.compile(r".+ \d+\.json$")
    cleaned = 0
    for subdir in ["raw/authors", "raw/venues", "classified/authors"]:
        d = data_dir / subdir
        if not d.exists():
            continue
        for f in d.iterdir():
            if finder_dup_re.match(f.name):
                f.unlink()
                cleaned += 1
    if cleaned:
        print(f"Cleaned {cleaned} macOS Finder duplicate file(s)\n")

    steps = [
        ("1", "Parse conferences", lambda: step1_parse_conferences.run(force=args.force)),
        ("1b", "Parse acceptance rates", lambda: step1b_parse_accept_rates.run(force=args.force, conferences_filter=conferences_filter)),
        ("2", "Crawl DBLP (SPARQL)", lambda: step2_crawl_sparql.run(force=args.force, conferences_filter=conferences_filter)),
        ("2b", "Crawl venues", lambda: step2b_crawl_venues.run(force=args.force, conferences_filter=conferences_filter)),
        ("2c", "Fill SPARQL gaps", lambda: step2c_fill_gaps.run(force=args.force, conferences_filter=conferences_filter)),
        ("3", "Classify names", lambda: step3_classify_names.run(force=args.force, conferences_filter=conferences_filter)),
        ("4", "Generate stats", lambda: step4_generate_stats.run(force=args.force)),
    ]

    if args.step:
        matched = [(s, n, f) for s, n, f in steps if s == args.step]
        if not matched:
            print(f"Unknown step: {args.step}. Available: {', '.join(s for s, _, _ in steps)}")
            sys.exit(1)
        step_id, name, func = matched[0]
        print(f"\n{'='*60}")
        print(f"Step {step_id}: {name}")
        print(f"{'='*60}\n")
        func()
    else:
        for step_id, name, func in steps:
            print(f"\n{'='*60}")
            print(f"Step {step_id}: {name}")
            print(f"{'='*60}\n")
            func()

    print("\nPipeline complete!")


if __name__ == "__main__":
    main()
