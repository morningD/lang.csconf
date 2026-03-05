"""Extract conference ranks from CCF PDF files and build ccf_rank_history.json."""

import json
import re
from pathlib import Path

import pdfplumber

DATA_DIR = Path(__file__).parent.parent / "data"
CCF_DIR = DATA_DIR / "ccf-versions"
CONFERENCES_FILE = DATA_DIR / "raw" / "conferences.json"
OUTPUT_FILE = CCF_DIR / "ccf_rank_history.json"

# Known conference abbreviation aliases: PDF name -> our conference ID
# The PDFs use abbreviations that may differ from our conferences.json IDs
CONF_ALIASES = {
    "PPoPP": "PPOPP",
    "USENIX ATC": "USENIXATC",
    "EuroSys": "EUROSYS",
    "SoCC": "SOCC",
    "CODES+ISSS": "CODES+ISSS",
    "Euro-Par": "EURO-PAR",
    "VEE": "VEE",
    "CGO": "IEEE-ACMCGO",
    "ACM MM": "ACMMM",
    "SIGGRAPH": "ACMSIGGRAPH",
    # "SIGGRAPH Asia" not in CCF list - do not alias
    "IEEE VIS": "IEEEVIS",
    "SCA": "SCA",
    "SIGMOD": "SIGMOD",
    "KDD": "SIGKDD",
    "ICDE": "ICDE",
    "SIGIR": "SIGIR",
    "VLDB": "VLDB",
    "CCS": "CCS",
    "S&P": "S&P",
    "NDSS": "NDSS",
    "USENIX Security": "USENIXSECURITY",
    "CRYPTO": "CRYPTO",
    "EUROCRYPT": "EUROCRYPT",
    "ACSAC": "ACSAC",
    "ASIACRYPT": "ASIACRYPT",
    "ESORICS": "ESORICS",
    "FSE": "FSE-CRYPTO",
    "SOUPS": "SOUPS",
    "STOC": "STOC",
    "FOCS": "FOCS",
    "LICS": "LICS",
    "CAV": "CAV",
    "ICALP": "ICALP",
    "CADE/IJCAR": "CADE",
    "CCC": "CCC",
    "ESA": "ESA",
    "ISAAC": "ISAAC",
    "MFCS": "MFCS",
    "STACS": "STACS",
    "SIGCOMM": "SIGCOMM",
    "MobiCom": "MOBICOM",
    "INFOCOM": "INFOCOM",
    "NSDI": "NSDI",
    "IMC": "IMC",
    "IPSN": "IPSN",
    "MobiSys": "MOBISYS",
    "ICNP": "ICNP",
    "MobiHoc": "MOBIHOC",
    "SenSys": "SENSYS",
    "CoNEXT": "CONEXT",
    "OSDI": "OSDI",
    "PLDI": "PLDI",
    "POPL": "POPL",
    "FSE/ESEC": "FSE",
    "SOSP": "SOSP",
    "OOPSLA": "OOPSLA",
    "ASE": "ASE",
    "ICSE": "ICSE",
    "ISSTA": "ISSTA",
    "ECOOP": "ECOOP",
    "ETAPS": "ETAPS",
    "ISSRE": "ISSRE",
    "IJCAI": "IJCAI",
    "AAAI": "AAAI",
    "NeurIPS": "NEURIPS",
    "ACL": "ACL",
    "CVPR": "CVPR",
    "ICCV": "ICCV",
    "ICML": "ICML",
    "ECCV": "ECCV",
    "EMNLP": "EMNLP",
    "COLT": "COLT",
    "UAI": "UAI",
    "AAMAS": "AAMAS",
    "PRICAI": "PRICAI",
    "CHI": "CHI",
    "UbiComp": "UBICOMP-ISWC",
    "CSCW": "CSCW",
    "IUI": "IUI",
    "UIST": "UIST",
    "WWW": "WWW",
    "PERCOM": "PERCOM",
    "MobileHCI": "MOBILEHCI",
    "ICWSM": "ICWSM",
    "DIS": "DIS",
}


def extract_conferences_from_pdf(pdf_path: str) -> list[tuple[str, str]]:
    """Extract conference abbreviations with their ranks from a CCF PDF.

    Returns: list of (abbreviation, rank) tuples
    """
    conferences = []
    current_section = None  # 'journals' or 'conferences'
    current_rank = None  # 'A', 'B', 'C'

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            text = page.extract_text() or ""

            # Detect section headers - handle both Chinese (2015/2022) and English (2019)
            if "推荐国际学术会议" in text or "Academic Conferences" in text:
                current_section = "conferences"
                current_rank = None  # Reset rank when entering new section
            elif "推荐国际学术期刊" in text or "Academic Periodicals" in text:
                current_section = "journals"
                current_rank = None

            # Detect rank headers - both Chinese and English formats
            if ("一、A 类" in text or "一、A类" in text
                    or "1. Class A" in text or "1.Class A" in text):
                current_rank = "A"
            if ("二、B 类" in text or "二、B类" in text
                    or "2. Class B" in text or "2.Class B" in text):
                current_rank = "B"
            if ("三、C 类" in text or "三、C类" in text
                    or "3. Class C" in text or "3.Class C" in text):
                current_rank = "C"

            if current_section != "conferences" or current_rank is None:
                continue

            for table in tables:
                if not table:
                    continue
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    # Skip header rows
                    first = str(row[0] or "")
                    second = str(row[1] or "")
                    if any(h in first for h in ["序号", "No."]):
                        continue
                    if any(h in second for h in ["会议简称", "Abbr", "刊物简称"]):
                        continue
                    # The abbreviation is typically in column 1 (index 1)
                    abbrev = second.strip()
                    if abbrev and abbrev != "None" and not abbrev.isdigit():
                        # Clean up newlines within abbreviation
                        abbrev = abbrev.replace("\n", " ").strip()
                        conferences.append((abbrev, current_rank))

    return conferences


def normalize_abbrev(abbrev: str) -> str:
    """Normalize a conference abbreviation to match our conference IDs."""
    # Check alias first
    if abbrev in CONF_ALIASES:
        return CONF_ALIASES[abbrev]
    # Default: uppercase and remove spaces
    return abbrev.upper().replace(" ", "").replace("/", "-")


def main():
    # Load our conference list
    with open(CONFERENCES_FILE, "r") as f:
        our_confs = json.load(f)
    our_ids = {c["id"] for c in our_confs}

    # Extract from each available PDF
    results = {}  # conf_id -> {version: rank}
    unmatched = {}  # version -> list of unmatched abbreviations

    for version in ["2012", "2015", "2019", "2022"]:
        pdf_path = CCF_DIR / f"ccf-{version}.pdf"
        if not pdf_path.exists():
            print(f"Skipping {version} (not found)")
            continue

        print(f"\n--- Extracting from CCF {version} ---")
        confs = extract_conferences_from_pdf(str(pdf_path))
        print(f"  Found {len(confs)} conference entries")

        unmatched[version] = []
        matched = 0
        for abbrev, rank in confs:
            norm_id = normalize_abbrev(abbrev)
            if norm_id in our_ids:
                results.setdefault(norm_id, {})[version] = rank
                matched += 1
            else:
                unmatched[version].append((abbrev, rank, norm_id))

        print(f"  Matched: {matched}, Unmatched: {len(unmatched[version])}")
        if unmatched[version]:
            print(f"  Unmatched: {[u[0] for u in unmatched[version][:20]]}")

    # Also use current conferences.json ranks as 2022 baseline
    # (since conferences.json already reflects 2022 CCF list)
    for conf in our_confs:
        conf_id = conf["id"]
        rank = conf.get("rank", "N")
        if rank in ("A", "B", "C"):
            results.setdefault(conf_id, {})["2022"] = rank

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\nWrote {len(results)} conferences to {OUTPUT_FILE}")

    # Print some stats
    changes = 0
    for conf_id, versions in results.items():
        ranks = list(versions.values())
        if len(set(ranks)) > 1:
            changes += 1
            print(f"  CHANGED: {conf_id}: {versions}")

    print(f"\n{changes} conferences with rank changes")


if __name__ == "__main__":
    main()
