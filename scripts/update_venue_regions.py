"""Batch update venue data to apply political sensitivity mapping."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
VENUES_DIR = DATA_DIR / "raw" / "venues"

REGION_TO_COUNTRY = {
    "Taiwan": "Taiwan, CN",
    "Hong Kong": "Hong Kong, CN",
    "Macau": "Macau, CN",
}


def update_venues():
    """Update all venue JSON files to apply region mapping."""
    if not VENUES_DIR.exists():
        print(f"Venues directory not found: {VENUES_DIR}")
        return

    updated_files = 0
    updated_entries = 0

    for venue_file in VENUES_DIR.glob("*.json"):
        with open(venue_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        modified = False
        venues = data.get("venues", {})

        for year, venue_info in venues.items():
            country = venue_info.get("country")
            if country in REGION_TO_COUNTRY:
                venue_info["country"] = REGION_TO_COUNTRY[country]
                modified = True
                updated_entries += 1
                print(f"  {data['conference']} {year}: {country} → {venue_info['country']}")

        if modified:
            with open(venue_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            updated_files += 1

    print(f"\nDone: {updated_files} files updated, {updated_entries} entries modified")


if __name__ == "__main__":
    update_venues()
