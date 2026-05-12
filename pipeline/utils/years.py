"""Shared year-range constants for the pipeline.

Single source of truth — all pipeline steps import from here
instead of hardcoding upper year bounds.
"""

from datetime import datetime

YEAR_FLOOR = 2010


def year_ceiling() -> int:
    """Upper bound for data years.

    +1 handles the publication-year lag where proceedings are
    published the year after the conference.
    """
    return datetime.now().year + 1


def expected_years_range() -> list[int]:
    """All candidate years from floor to ceiling (inclusive)."""
    return list(range(YEAR_FLOOR, year_ceiling() + 1))
