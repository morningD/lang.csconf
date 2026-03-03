"""Step 3: Classify author names into language groups."""

import json
from pathlib import Path

from tqdm import tqdm

from pipeline.utils.name_classifier import classify_names_batch

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_AUTHORS_DIR = DATA_DIR / "raw" / "authors"
CLASSIFIED_DIR = DATA_DIR / "classified" / "authors"


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 3: classify author names."""
    CLASSIFIED_DIR.mkdir(parents=True, exist_ok=True)

    # Find all raw author files
    raw_files = sorted(RAW_AUTHORS_DIR.glob("*.json"))

    if conferences_filter:
        filter_set = {c.upper() for c in conferences_filter}
        raw_files = [f for f in raw_files
                     if any(f.stem.upper().startswith(c) for c in filter_set)]

    print(f"Classifying authors in {len(raw_files)} files...")

    for raw_file in tqdm(raw_files, desc="Classifying"):
        output_file = CLASSIFIED_DIR / raw_file.name

        # Skip if already classified (unless force)
        if not force and output_file.exists():
            continue

        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        authors = data.get("authors", [])
        if not authors:
            continue

        # Extract names for batch classification
        names = [a["name"] for a in authors]
        classifications = classify_names_batch(names)

        # Merge classifications with author data
        classified_authors = []
        for author, classification in zip(authors, classifications):
            classified_authors.append({
                **author,
                "nationality": classification["nationality"],
                "language": classification["language"],
                "confidence": classification["confidence"],
            })

        # Save classified data
        result = {
            "conference": data.get("conference", ""),
            "dblp": data.get("dblp", ""),
            "year": data.get("year", 0),
            "total_papers": data.get("total_papers", 0),
            "authors": classified_authors,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Classification complete. Results in {CLASSIFIED_DIR}")


if __name__ == "__main__":
    run()
