"""Extract conference ranks and categories from CCF PDF files and build ccf_rank_history.json."""

import json
import re
from pathlib import Path

import pdfplumber

DATA_DIR = Path(__file__).parent.parent / "data"
CCF_DIR = DATA_DIR / "ccf-versions"
BASE_CONFERENCES_FILE = Path(__file__).parent.parent / "pipeline" / "conferences_base.json"
OUTPUT_FILE = CCF_DIR / "ccf_rank_history.json"

# Category mapping: Chinese header keywords → category code
# Each key is a substring that uniquely identifies the category in the PDF header.
CATEGORY_MAPPING = {
    "体系结构": "DS",    # 计算机体系结构/并行与分布计算/存储系统
    "高性能计算": "DS",  # 计算机系统与高性能计算 (2012 variant)
    "计算机网络": "NW",
    "信息安全": "SC",    # 网络与信息安全
    "软件工程": "SE",    # 软件工程/系统软件/程序设计语言
    "数据库": "DB",      # 数据库/数据挖掘/内容检索
    "计算机科学理论": "CT",
    "图形学": "CG",      # 计算机图形学与多媒体
    "人工智能": "AI",
    "人机交互": "HI",    # 人机交互与普适计算
    "交叉": "MX",        # 交叉/综合/新兴
    "前沿": "MX",        # 前沿、交叉与综合 (2012 variant)
}

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
    "FSE-CRYPTO-DIRECT": "FSE-CRYPTO",
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
    "UbiComp": "UBICOMP",
    "CSCW": "CSCW",
    "IUI": "IUI",
    "UIST": "UIST",
    "WWW": "WWW",
    "PERCOM": "PERCOM",
    "MobileHCI": "MOBILEHCI",
    "ICWSM": "ICWSM",
    "DIS": "DIS",
    "ACM SIGOPS ATC\n（原 USENIX ATC）": "USENIXATC",
    "ACM SIGOPS ATC\n（原USENIX ATC）": "USENIXATC",
    "ACMSIGOPSATC\n（原USENIXATC）": "USENIXATC",
    "ACMSIGOPSATC （原USENIXATC）": "USENIXATC",
    "ACM SIGOPS ATC": "USENIXATC",
    "SIG-\nMETRICS": "SIGMETRICS",
    "SIG- METRICS": "SIGMETRICS",
    "INTER-\nSPEECH": "INTERSPEECH",
    "INTER- SPEECH": "INTERSPEECH",
    "FSCD\n（原RTA）": "RTA",
    "FSCD （原RTA）": "RTA",
    "VR": "IEEEVR",
    "IEEE BigData": "BIGDATA",
    "IEEE CLOUD": "CLOUD",
    "IEEEBigData": "BIGDATA",
    "IEEECLOUD": "CLOUD",
    # Old conference names → current IDs
    "NIPS": "NEURIPS",
    "FGR": "FG",
    "ICSM": "ICSME",
    "WCRE": "SANER",
    "Hot Interconnects": "HOTI",
    "ACM MM&SEC": "IH&MMSEC",
    "ACMMM&SEC": "IH&MMSEC",
    "EG": "EUROGRAPHICS",
    "SI3D": "I3D",
    "i3D": "I3D",
    "IEEECEC": "CEC",
    "IEEE CEC": "CEC",
    # Renamed conferences — map old name to current ID for rank history
    "SCC": "SSE",    # SCC renamed to SSE (IEEE Services → Software Services Engineering)
    "ITS": "ISS",    # ITS renamed to ISS (Interactive Tabletops → Interactive Surfaces)
    "QSIC": "QRS",   # QSIC renamed to QRS (Quality Software → Quality, Reliability, Security)
    # APWeb and WAIM were separate before ~2017; both map to the merged APWEB-WAIM
    "APWeb": "APWEB-WAIM",
    "APWEB": "APWEB-WAIM",
    "WAIM": "APWEB-WAIM",
    # Old abbreviations → current conference IDs
    "HPC": "HIPC",        # "HPC" in 2015 = HiPC (High Performance Computing)
    "ICB": "IJCB",        # ICB (Int'l Conf on Biometrics) merged into IJCB
    "CSOC": "ICSOC",      # PDF parsing error: "CSOC" = ICSOC (Service Oriented Computing)
    # PDF formatting quirks (newlines, spaces)
    "CADE/ IJCAR": "CADE",
    "CADE/\nIJCAR": "CADE",
    "FSE/ ESEC": "FSE",
    "FSE/\nESEC": "FSE",
    "ESEC/ FSE": "FSE",
    "ESEC/\nFSE": "FSE",
    "ESEC/FSE": "FSE",
    # Name variants
    "Hot Chips": "HOTCHIPS",
    "HotChips": "HOTCHIPS",
    "ISMAR": "ISMAR",
    "Mobiquitous": "MOBIQUITOUS",
    "HiPC": "HIPC",
    "HotNets": "HOTNETS",
    "NOSSDAV": "NOSSDAV",
    "WiSec": "WISEC",
    "WISEC": "WISEC",
    "CoNEXT": "CONEXT",
    # SIG-METRICS line-break variants
    "SIGMETRICS": "SIGMETRICS",
    # Mixed-case conferences
    "FAccT": "FACCT",
    "SaTML": "SATML",
    "SATML": "SATML",
    "SaT ML": "SATML",
    "SaT\nML": "SATML",
    # IH&MMSec variants
    "IH&MMSec": "IH&MMSEC",
    "IH&MMSEC": "IH&MMSEC",
    "IH&MM Sec": "IH&MMSEC",
    "IH&MM\nSec": "IH&MMSEC",
    # CODES+ISSS with space
    "CODES+ ISSS": "CODES+ISSS",
    "CODES+\nISSS": "CODES+ISSS",
    # 2026 PDF renamed conferences
    "ACMSIGOPSATC": "USENIXATC",
    "ACM SIGOPSATC": "USENIXATC",
    # 2012/2015 old names that differ from current
    "HotOS": "HOTOS",
    "HOTOS": "HOTOS",
    # Disambiguated entries (via full_name check in extract_conferences_from_pdf)
    "IFIPSEC-DIRECT": "IFIPSEC",
    # WHC has empty abbreviation column in 2026 PDF; recovered from full name
    "WHC": "WHC",
}


def _detect_category(line: str) -> str | None:
    """Detect CCF category from a line of text. Returns category code or None."""
    # Strip parentheses (both half-width and full-width)
    s = line.strip().strip("（）()")
    for keyword, category in CATEGORY_MAPPING.items():
        if keyword in s:
            return category
    return None


def extract_conferences_from_pdf(pdf_path: str) -> list[tuple[str, str, str]]:
    """Extract conference abbreviations with their ranks and categories from a CCF PDF.

    Returns: list of (abbreviation, rank, category) tuples
    """
    conferences = []
    current_section = None  # 'journals' or 'conferences'
    current_rank = None  # 'A', 'B', 'C'
    current_category = None  # 'AI', 'DB', etc.

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            text = page.extract_text() or ""

            # Detect section headers - line by line to avoid footer false-positives.
            # The 2019 PDF has footer "Academic Periodicals\nand Conferences Recommended"
            # on every page, so page-level "Academic Periodicals" matching fails.
            # The 2012 PDF uses "学术刊物" instead of "学术期刊" for journals.
            # The 2015 PDF has "学术 期刊" with space.
            for line in text.split("\n"):
                # Conference section headers (line-level, not footer)
                if re.search(r"Academic Conferences\s+Recommended", line):
                    current_section = "conferences"
                    current_rank = None
                elif re.search(r"推荐国际学术会议(?!和期刊)", line):
                    current_section = "conferences"
                    current_rank = None
                # Journal section headers
                if re.search(r"Academic Periodicals\s+Recommended", line):
                    current_section = "journals"
                    current_rank = None
                elif re.search(r"推荐国际学术\s*期刊", line):
                    current_section = "journals"
                    current_rank = None
                elif "学术刊物" in line:
                    current_section = "journals"
                    current_rank = None

                # Detect category headers — parenthesized lines or bare category lines
                # Examples: （计算机网络）, (数据库/数据挖掘/内容检索),
                #           计算机体系结构/并行与分布计算/存储系统 (bare, 2015 conference section)
                cat = _detect_category(line)
                if cat is not None:
                    current_category = cat

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
                        # Filter pseudo-entries from PDF table parsing errors
                        if abbrev.lower() in ("joint", "on", "刊物简号称",
                                               "刊物简称", "会议简称", "none",
                                               "of", "and", "for", "the",
                                               "abbr", "abbr.", "no."):
                            continue
                        # Skip entries that look like partial table headers
                        if len(abbrev) <= 1:
                            continue
                        full_name = str(row[2] or "")
                        # Disambiguate: "FSE" appears for both Fast Software Encryption
                        # (crypto) and Foundations of Software Engineering (SE)
                        if abbrev == "FSE" and "Encryption" in full_name:
                            abbrev = "FSE-CRYPTO-DIRECT"
                        # Disambiguate: "SEC" appears for both IFIP Information Security
                        # and ACM/IEEE Edge Computing
                        if abbrev == "SEC" and "IFIP" in full_name:
                            abbrev = "IFIPSEC-DIRECT"
                        conferences.append((abbrev, current_rank, current_category or "MX"))
                    elif not abbrev or abbrev == "None":
                        # Some PDF entries have empty abbreviation column
                        # but the full name is in column 2, try to recover
                        full_name = str(row[2] or "")
                        if "Haptics" in full_name or "HapticsConference" in full_name:
                            conferences.append(("WHC", current_rank, current_category or "MX"))

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
    with open(BASE_CONFERENCES_FILE, "r") as f:
        our_confs = json.load(f)
    our_ids = {c["id"] for c in our_confs}

    # Extract from each available PDF
    # New format: conf_id -> {version: {"rank": "A", "category": "AI"}}
    results = {}
    unmatched = {}  # version -> list of unmatched abbreviations

    for version in ["2012", "2015", "2019", "2022", "2026"]:
        pdf_path = CCF_DIR / f"ccf-{version}.pdf"
        if not pdf_path.exists():
            print(f"Skipping {version} (not found)")
            continue

        print(f"\n--- Extracting from CCF {version} ---")
        confs = extract_conferences_from_pdf(str(pdf_path))
        print(f"  Found {len(confs)} conference entries")

        unmatched[version] = []
        matched = 0
        for abbrev, rank, category in confs:
            norm_id = normalize_abbrev(abbrev)
            if norm_id in our_ids:
                results.setdefault(norm_id, {})[version] = {
                    "rank": rank,
                    "category": category,
                }
                matched += 1
            else:
                unmatched[version].append((abbrev, rank, category, norm_id))

        print(f"  Matched: {matched}, Unmatched: {len(unmatched[version])}")
        if unmatched[version]:
            print(f"  Unmatched: {[u[0] for u in unmatched[version][:20]]}")

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\nWrote {len(results)} conferences to {OUTPUT_FILE}")

    # Print rank changes
    changes = 0
    for conf_id, versions in results.items():
        ranks = [v["rank"] for v in versions.values()]
        if len(set(ranks)) > 1:
            changes += 1
            rank_str = {ver: v["rank"] for ver, v in versions.items()}
            print(f"  RANK CHANGED: {conf_id}: {rank_str}")

    print(f"\n{changes} conferences with rank changes")

    # Print category changes
    cat_changes = 0
    for conf_id, versions in results.items():
        cats = [v["category"] for v in versions.values()]
        if len(set(cats)) > 1:
            cat_changes += 1
            cat_str = {ver: v["category"] for ver, v in versions.items()}
            print(f"  CATEGORY CHANGED: {conf_id}: {cat_str}")

    print(f"{cat_changes} conferences with category changes")


if __name__ == "__main__":
    main()
