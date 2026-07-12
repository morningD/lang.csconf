"""Pure parsing boundaries for HiPEAC activity records.

This module intentionally accepts only explicit structured title fields.  It never
infers a title boundary from free-form description text, which avoids appending
presenter or affiliation display tails to paper titles.
"""

from __future__ import annotations

from typing import Any


def parse_activity(activity: dict[str, Any]) -> dict[str, Any]:
    """Return a structured paper candidate or an unresolved diagnostic without guessing."""
    title = activity.get("title")
    if not isinstance(title, str) or not title:
        return {
            "status": "unresolved",
            "reason": "missing_explicit_title",
            "title": None,
            "authors": [],
            "display_tail": None,
        }

    authors = activity.get("authors")
    if not isinstance(authors, list) or not all(isinstance(author, str) and author for author in authors):
        return {
            "status": "unresolved",
            "reason": "missing_explicit_authors",
            "title": None,
            "authors": [],
            "display_tail": None,
        }

    display_tail = activity.get("description")
    return {
        "status": "resolved",
        "title": title,
        "authors": authors,
        "display_tail": display_tail if isinstance(display_tail, str) else None,
    }
