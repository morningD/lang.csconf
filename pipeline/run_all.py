"""Orchestrator: run all pipeline steps sequentially."""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import step1_parse_conferences, step2_crawl_sparql, step3_classify_names, step4_generate_stats


def main():
    parser = argparse.ArgumentParser(description="lang.csconf data pipeline")
    parser.add_argument("--force", action="store_true", help="Force re-crawl all data")
    parser.add_argument("--step", type=int, choices=[1, 2, 3, 4], help="Run only a specific step")
    parser.add_argument("--conferences", type=str, help="Comma-separated conference IDs to process (e.g., CVPR,AAAI,SIGMOD)")

    args = parser.parse_args()
    conferences_filter = args.conferences.split(",") if args.conferences else None

    steps = {
        1: ("Parse conferences", lambda: step1_parse_conferences.run(force=args.force)),
        2: ("Crawl DBLP (SPARQL)", lambda: step2_crawl_sparql.run(force=args.force, conferences_filter=conferences_filter)),
        3: ("Classify names", lambda: step3_classify_names.run(force=args.force, conferences_filter=conferences_filter)),
        4: ("Generate stats", lambda: step4_generate_stats.run(force=args.force)),
    }

    if args.step:
        step_num = args.step
        name, func = steps[step_num]
        print(f"\n{'='*60}")
        print(f"Step {step_num}: {name}")
        print(f"{'='*60}\n")
        func()
    else:
        for step_num, (name, func) in steps.items():
            print(f"\n{'='*60}")
            print(f"Step {step_num}: {name}")
            print(f"{'='*60}\n")
            func()

    print("\nPipeline complete!")


if __name__ == "__main__":
    main()
