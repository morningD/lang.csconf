"""Shared filters for cleaning DBLP paper data.

These filters are applied at the data entry point (step2/step2c) to ensure
raw data is clean from the start. Step4 does pure aggregation with no filtering.
"""

import re

# Proceedings volume titles are editor entries, not real papers.
# They appear in SPARQL results because DBLP indexes them alongside papers.
PROCEEDINGS_VOLUME_RE = re.compile(
    r"Proceedings\.?\s*$"                          # ends with "Proceedings"
    r"|Proceedings,?\s*Part\s+\w+\.?\s*$"          # "Proceedings, Part I"
    r"|Proceedings,?\s*Volume\s+\w+\.?\s*$"        # "Proceedings, Volume 1"
    r"|Revised Selected Papers"                    # Springer LNCS volumes
    r"|Revised (and Invited )?Contributions"       # Springer variant
    r"|Selected and Invited Papers"                # Springer variant
    r"|^Proceedings of the\s+(\d+|[A-Z]\w+th|First|Second|Third)"  # "Proceedings of the 15th/Thirteenth/First ..."
    r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d[^,]*,\s*\d{4}[^,]*Proceedings"  # date pattern + Proceedings
    r"|^\w+\s+\d{4}\s+[Pp]roceedings\.?$"         # "ISMB 2020 Proceedings"
    r"|^[A-Z]+ \d{4}:\s+Proceedings"              # "ECSCW 2015: Proceedings ..."
    r"|Lecture Notes in Computer Science"           # LNCS volume titles
    r"|Lecture Notes in Artificial Intelligence"    # LNAI volume titles
    r"|\bFrontmatter\b"                            # RTA-style frontmatter
    r"|Letter from the\b.*\bChair"                 # VLDB-style chair letters
    r"|^\w[\w\s,/&]+ - \d+\w{0,2} (International |Annual |IEEE )?Conference\b.*\d{4}\b"  # Springer LNCS book titles: "Topic - 22nd International Conference, PDCAT 2021, ..."
    r"|\bEditorial\s*$",                             # Journal editorials at end of title (POMACS, etc.)
    re.IGNORECASE,
)


def is_proceedings_volume(title: str) -> bool:
    """Check if a title is a proceedings volume entry (not a real paper)."""
    return bool(PROCEEDINGS_VOLUME_RE.search(title))
