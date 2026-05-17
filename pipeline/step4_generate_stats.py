"""Step 4: Generate aggregated statistics from classified author data."""

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pipeline.utils.nationality_to_lang import LANGUAGE_COLORS, LANGUAGE_GROUPS
from pipeline.utils.years import YEAR_FLOOR, year_ceiling

# Valid author filename: {CONFID}_{YEAR}.json (no spaces, year must be 4 digits)
_VALID_AUTHOR_FILENAME = re.compile(r"^[A-Za-z0-9+&.\-]+_\d{4}\.json$")

DATA_DIR = Path(__file__).parent.parent / "data"
CLASSIFIED_DIR = DATA_DIR / "classified" / "authors"
RAW_DIR = DATA_DIR / "raw"
STATS_DIR = DATA_DIR / "stats"
VENUES_DIR = RAW_DIR / "venues"
CCF_RANK_HISTORY_FILE = DATA_DIR / "ccf-versions" / "ccf_rank_history.json"
ACCEPT_RATES_FILE = RAW_DIR / "accept_rates.json"
YEAR_NOTES_FILE = Path(__file__).parent / "conference_year_notes.json"


def load_conferences() -> list[dict]:
    """Load conference metadata."""
    conf_file = RAW_DIR / "conferences.json"
    if not conf_file.exists():
        return []
    with open(conf_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_classified() -> list[dict]:
    """Load all classified author files, skipping files with invalid names."""
    all_data = []
    skipped = 0
    for f in sorted(CLASSIFIED_DIR.glob("*.json")):
        if not _VALID_AUTHOR_FILENAME.match(f.name):
            skipped += 1
            continue
        with open(f, "r", encoding="utf-8") as fh:
            all_data.append(json.load(fh))
    if skipped:
        print(f"  Warning: skipped {skipped} file(s) with invalid names in {CLASSIFIED_DIR}")
    return all_data


def load_venues() -> dict[str, dict]:
    """Load venue data per conference. Returns {conf_id: {year: {city, country}}}."""
    venues = {}
    if not VENUES_DIR.exists():
        return venues
    for f in VENUES_DIR.glob("*.json"):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        conf_id = data.get("conference", "")
        raw_venues = data.get("venues", {})
        # Simplify: only keep city and country
        venues[conf_id] = {
            year: {"city": v.get("city", ""), "country": v.get("country", "")}
            for year, v in raw_venues.items()
        }
    return venues


def load_rank_history() -> dict[str, dict]:
    """Load CCF rank history. Returns {conf_id: {version: rank}}.

    Handles both old format ({version: rank_string}) and new format
    ({version: {"rank": rank_string, "category": cat_string}}).
    """
    if not CCF_RANK_HISTORY_FILE.exists():
        return {}
    with open(CCF_RANK_HISTORY_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Normalize to {conf_id: {version: rank_string}} for website compatibility
    result = {}
    for conf_id, versions in raw.items():
        result[conf_id] = {}
        for ver, val in versions.items():
            if isinstance(val, dict):
                result[conf_id][ver] = val["rank"]
            else:
                result[conf_id][ver] = val
    return result


def load_accept_rates() -> dict[str, list[dict]]:
    """Load acceptance rates. Returns {conf_id: [{year, submitted, accepted}]}."""
    if not ACCEPT_RATES_FILE.exists():
        return {}
    with open(ACCEPT_RATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_year_notes() -> dict[str, dict[str, dict]]:
    """Load per-conference-year notes. Returns {conf_id: {year_str: {note fields}}}."""
    if not YEAR_NOTES_FILE.exists():
        return {}
    with open(YEAR_NOTES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    result: dict[str, dict[str, dict]] = {}
    for key, entry in raw.items():
        if key.startswith("_"):
            continue
        parts = key.rsplit("_", 1)
        if len(parts) != 2:
            continue
        conf_id, year_str = parts
        result.setdefault(conf_id, {})[year_str] = entry
    return result


def compute_language_distribution(authors: list[dict]) -> dict[str, int]:
    """Count authors by language group."""
    counts = defaultdict(int)
    for a in authors:
        lang = a.get("language", "Other")
        counts[lang] += 1
    return dict(counts)


def load_affiliations() -> dict[str, dict[int, dict]]:
    """Load affiliation data from step2e.

    Returns: {conf_id: {year: affiliation_data}}
    """
    affil_dir = Path(__file__).parent.parent / "data" / "raw" / "affiliations"
    if not affil_dir.exists():
        return {}

    result: dict[str, dict[int, dict]] = {}
    for f in sorted(affil_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            conf_id = data.get("conference", "").replace("/", "-")
            year = data.get("year", 0)
            if conf_id and year:
                result.setdefault(conf_id, {})[year] = data
        except (json.JSONDecodeError, KeyError):
            continue
    return result


# Canonical institution mapping: raw_name → (canonical_name, country_code)
# Covers all institutions appearing in any conference's top-10.
# For entries with long addresses (papercopilot), we strip to the core institution.
_INST_MAP: dict[str, tuple[str, str]] = {
    # --- US Universities ---
    "Stanford University": ("Stanford University", "US"),
    "Carnegie Mellon University": ("Carnegie Mellon University", "US"),
    "Massachusetts Institute of Technology": ("Massachusetts Institute of Technology", "US"),
    "MIT": ("Massachusetts Institute of Technology", "US"),
    "Princeton University": ("Princeton University", "US"),
    "UC Berkeley": ("University of California, Berkeley", "US"),
    "University of California, Berkeley": ("University of California, Berkeley", "US"),
    "University of Southern California": ("University of Southern California", "US"),
    "Georgia Institute of Technology": ("Georgia Institute of Technology", "US"),
    "Harvard University": ("Harvard University", "US"),
    "Cornell University": ("Cornell University", "US"),
    "University of Washington": ("University of Washington", "US"),
    "Duke University": ("Duke University", "US"),
    "Columbia University": ("Columbia University", "US"),
    "University of Pennsylvania": ("University of Pennsylvania", "US"),
    "Johns Hopkins University": ("Johns Hopkins University", "US"),
    "University of Maryland, College Park": ("University of Maryland, College Park", "US"),
    "University of California, San Diego": ("University of California, San Diego", "US"),
    "University of California San Diego": ("University of California, San Diego", "US"),
    "University of California, Irvine": ("University of California, Irvine", "US"),
    "University of Texas at Austin": ("University of Texas at Austin", "US"),
    "University of Illinois at Urbana-Champaign": ("University of Illinois at Urbana-Champaign", "US"),
    "University of Illinois, Urbana Champaign": ("University of Illinois at Urbana-Champaign", "US"),
    "Purdue University": ("Purdue University", "US"),
    "UNC Chapel Hill": ("University of North Carolina at Chapel Hill", "US"),
    "Arizona State University": ("Arizona State University", "US"),
    "University of Michigan - Ann Arbor": ("University of Michigan", "US"),
    "Yale University": ("Yale University", "US"),
    "Toyota Technological Institute at Chicago": ("Toyota Technological Institute at Chicago", "US"),
    "Department of Computer Science": ("Department of Computer Science", "US"),
    # CMU sub-units (papercopilot long addresses)
    "Robotics Institute, Carnegie Mellon University, Pittsburgh, PA, USA": ("Carnegie Mellon University", "US"),
    "The Robotics Institute, Carnegie Mellon University, Pittsburgh, PA, USA": ("Carnegie Mellon University", "US"),
    "The Robotics Institute, Carnegie Mellon University": ("Carnegie Mellon University", "US"),
    "Robotics Institute, Carnegie Mellon University": ("Carnegie Mellon University", "US"),
    "Language Technologies Institute, Carnegie Mellon University": ("Carnegie Mellon University", "US"),
    "Mechanical Engineering, Carnegie Mellon University, Pittsburgh, PA, USA": ("Carnegie Mellon University", "US"),
    # MIT sub-units
    "Computer Science and Artificial Intelligence Laboratory, Massachusetts Institute of Technology, Cambridge, MA, USA": ("Massachusetts Institute of Technology", "US"),
    "Mechanical Engineering, Massachusetts Institute of Technology, Cambridge, MA, USA": ("Massachusetts Institute of Technology", "US"),
    # Other US sub-units
    "Mechanical Engineering, Johns Hopkins University, Baltimore, MD, USA": ("Johns Hopkins University", "US"),
    "Mechanical Engineering, University of California, Berkeley, CA, USA": ("University of California, Berkeley", "US"),
    "GRASP Laboratory, University of Pennsylvania, Philadelphia, PA, USA": ("University of Pennsylvania", "US"),
    "GRASP Laboratory, University of Pennsylvania": ("University of Pennsylvania", "US"),
    "Electrical and Computer Engineering, Georgia Institute of Technology, Atlanta, GA, USA": ("Georgia Institute of Technology", "US"),
    # --- US Companies ---
    "Google": ("Google", "US"),
    "Google Research": ("Google", "US"),
    "Amazon": ("Amazon", "US"),
    "NVIDIA": ("NVIDIA", "US"),
    "Microsoft Research": ("Microsoft Research", "US"),
    "IBM Research": ("IBM Research", "US"),
    "Adobe Research": ("Adobe", "US"),
    "Adobe": ("Adobe", "US"),
    # --- China Universities ---
    "Tsinghua University": ("Tsinghua University", "CN"),
    "Peking University": ("Peking University", "CN"),
    "Zhejiang University": ("Zhejiang University", "CN"),
    "University of Science and Technology of China": ("University of Science and Technology of China", "CN"),
    "Shanghai Jiao Tong University": ("Shanghai Jiao Tong University", "CN"),
    "Shanghai Jiaotong University": ("Shanghai Jiao Tong University", "CN"),
    "Fudan University": ("Fudan University", "CN"),
    "Harbin Institute of Technology": ("Harbin Institute of Technology", "CN"),
    "Beijing University of Posts and Telecommunications": ("Beijing University of Posts and Telecommunications", "CN"),
    "University of Electronic Science and Technology of China": ("University of Electronic Science and Technology of China", "CN"),
    "Huazhong University of Science and Technology": ("Huazhong University of Science and Technology", "CN"),
    "Renmin University of China": ("Renmin University of China", "CN"),
    "Beihang University": ("Beihang University", "CN"),
    "Shandong University": ("Shandong University", "CN"),
    "Beijing Institute of Technology": ("Beijing Institute of Technology", "CN"),
    "University of Chinese Academy of Sciences": ("University of Chinese Academy of Sciences", "CN"),
    "University of Chinese Academy of Sciences, Beijing, China": ("University of Chinese Academy of Sciences", "CN"),
    "Nanjing University": ("Nanjing University", "CN"),
    # China sub-units
    "College of Computer Science and Technology, Zhejiang University": ("Zhejiang University", "CN"),
    "Gaoling School of Artificial Intelligence, Renmin University of China": ("Renmin University of China", "CN"),
    "Wangxuan Institute of Computer Technology, Peking University": ("Peking University", "CN"),
    "Computer Science, Fudan University": ("Fudan University", "CN"),
    "College of Information Science and Electronic Engineering, Zhejiang University, Hangzhou, China": ("Zhejiang University", "CN"),
    "National Key Laboratory for Novel Software Technology, Nanjing University, Nanjing 210023, China": ("Nanjing University", "CN"),
    "Institute of Information Engineering, Chinese Academy of Sciences, Beijing, China": ("Institute of Information Engineering, CAS", "CN"),
    "College of Intelligence and Computing, Tianjin University, Tianjin, China": ("Tianjin University", "CN"),
    "Computer Science and Technology, Soochow University, Suzhou, China": ("Soochow University", "CN"),
    "Computer Science and Technology, Soochow University, China": ("Soochow University", "CN"),
    "Computer Science and Information Engineering, National Taiwan University": ("National Taiwan University", "TW"),
    # --- Hong Kong ---
    "The Chinese University of Hong Kong": ("Chinese University of Hong Kong", "HK"),
    "Chinese University of Hong Kong": ("Chinese University of Hong Kong", "HK"),
    "The University of Hong Kong": ("University of Hong Kong", "HK"),
    "University of Hong Kong": ("University of Hong Kong", "HK"),
    "City University of Hong Kong": ("City University of Hong Kong", "HK"),
    "Computer Science, Hong Kong Baptist University, Hong Kong SAR, China": ("Hong Kong Baptist University", "HK"),
    # --- UK ---
    "University of Oxford": ("University of Oxford", "GB"),
    "University of Cambridge": ("University of Cambridge", "GB"),
    # --- Germany ---
    "Technical University of Munich": ("Technical University of Munich", "DE"),
    "Computer Science, University of Freiburg, Germany": ("University of Freiburg", "DE"),
    "Eberhard-Karls-Universität Tübingen": ("University of Tübingen", "DE"),
    "Institute for Anthropomatics and Robotics, Karlsruhe Institute of Technology, Karlsruhe, Germany": ("Karlsruhe Institute of Technology", "DE"),
    "Institute of Robotics and Mechatronics, German Aerospace Center (DLR), Wessling, Germany": ("German Aerospace Center (DLR)", "DE"),
    "Technische Universität Wien": ("TU Wien", "AT"),
    # --- Switzerland ---
    "ETH Zürich": ("ETH Zurich", "CH"),
    "ETHZ - ETH Zurich": ("ETH Zurich", "CH"),
    # --- Canada ---
    "University of Toronto": ("University of Toronto", "CA"),
    # --- Singapore ---
    "National University of Singapore": ("National University of Singapore", "SG"),
    "Electrical and Electronic Engineering, Nanyang Technological University, Singapore": ("Nanyang Technological University", "SG"),
    # --- Japan ---
    "The University of Tokyo": ("University of Tokyo", "JP"),
    "Graduate School of System Informatics, Kobe University": ("Kobe University", "JP"),
    "Graduate School of Informatics, Kyoto University": ("Kyoto University", "JP"),
    "Graduate School of Systems Engineering, Wakayama University": ("Wakayama University", "JP"),
    # --- Korea ---
    "KAIST": ("KAIST", "KR"),
    "Seoul National University": ("Seoul National University", "KR"),
    # --- Israel ---
    "Tel Aviv University": ("Tel Aviv University", "IL"),
    "Weizmann Institute of Science": ("Weizmann Institute of Science", "IL"),
    # --- Australia ---
    "Australian National University": ("Australian National University", "AU"),
    # --- Italy ---
    "Department of Advanced Robotics, Istituto Italiano di Tecnologia, Genova, Italy": ("Istituto Italiano di Tecnologia", "IT"),
    # --- Netherlands ---
    "University of Amsterdam": ("University of Amsterdam", "NL"),
    # --- Finland ---
    "University of Helsinki": ("University of Helsinki", "FI"),
    "Tampere University": ("Tampere University", "FI"),
    # --- Spain ---
    "Universitat Pompeu Fabra": ("Universitat Pompeu Fabra", "ES"),
    # --- UAE ---
    "Mohamed bin Zayed University of Artificial Intelligence": ("MBZUAI", "AE"),
    # Additional papercopilot variants (with/without address)
    "Computer Science and Artificial Intelligence Laboratory, Massachusetts Institute of Technology": ("Massachusetts Institute of Technology", "US"),
    "GRASP Lab, University of Pennsylvania": ("University of Pennsylvania", "US"),
    "Mechanical Engineering, Stanford University, Stanford, CA, USA": ("Stanford University", "US"),
    "University of Bonn, Germany": ("University of Bonn", "DE"),
    # --- Major universities not in initial top-110 but common in raw data ---
    "Nanyang Technological University": ("Nanyang Technological University", "SG"),
    "New York University": ("New York University", "US"),
    "University of California, Los Angeles": ("University of California, Los Angeles", "US"),
    "ETH Zurich": ("ETH Zurich", "CH"),
    "DeepMind": ("Google DeepMind", "GB"),
    "Google DeepMind": ("Google DeepMind", "GB"),
    "Google Brain": ("Google DeepMind", "GB"),
    "Korea Advanced Institute of Science & Technology": ("KAIST", "KR"),
    "Korea Advanced Institute of Science and Technology": ("KAIST", "KR"),
    "Korea Advanced Institute of Science and Technology (KAIST)": ("KAIST", "KR"),
    "Microsoft": ("Microsoft", "US"),
    "Northeastern University": ("Northeastern University", "US"),
    "Imperial College London": ("Imperial College London", "GB"),
    "University of Michigan": ("University of Michigan", "US"),
    "University of Michigan, Ann Arbor": ("University of Michigan", "US"),
    "University of Michigan - Ann Arbor": ("University of Michigan", "US"),
    "Hong Kong University of Science and Technology": ("HKUST", "HK"),
    "The Hong Kong University of Science and Technology": ("HKUST", "HK"),
    "HKUST": ("HKUST", "HK"),
    "Alibaba Group": ("Alibaba", "CN"),
    "EPFL": ("EPFL", "CH"),
    "EPFL - EPF Lausanne": ("EPFL", "CH"),
    "Apple": ("Apple", "US"),
    "South China University of Technology": ("South China University of Technology", "CN"),
    "Yonsei University": ("Yonsei University", "KR"),
    "University of Illinois Urbana-Champaign": ("University of Illinois at Urbana-Champaign", "US"),
    "UIUC": ("University of Illinois at Urbana-Champaign", "US"),
    "University of British Columbia": ("University of British Columbia", "CA"),
    "INRIA": ("INRIA", "FR"),
    "Inria": ("INRIA", "FR"),
    "University of Edinburgh": ("University of Edinburgh", "GB"),
    "Boston University": ("Boston University", "US"),
    "The University of Texas at Austin": ("University of Texas at Austin", "US"),
    "University of Texas, Austin": ("University of Texas at Austin", "US"),
    "UT Austin": ("University of Texas at Austin", "US"),
    "University of Alberta": ("University of Alberta", "CA"),
    "University of Chicago": ("University of Chicago", "US"),
    "Rutgers University": ("Rutgers University", "US"),
    "Wuhan University": ("Wuhan University", "CN"),
    "Rice University": ("Rice University", "US"),
    "Michigan State University": ("Michigan State University", "US"),
    "University College London": ("University College London", "GB"),
    "UCLA": ("University of California, Los Angeles", "US"),
    "Xidian University": ("Xidian University", "CN"),
    "ShanghaiTech University": ("ShanghaiTech University", "CN"),
    "University of Waterloo": ("University of Waterloo", "CA"),
    "University of Wisconsin-Madison": ("University of Wisconsin-Madison", "US"),
    "University of Wisconsin - Madison": ("University of Wisconsin-Madison", "US"),
    "Korea University": ("Korea University", "KR"),
    "Southeast University": ("Southeast University", "CN"),
    "Tianjin University": ("Tianjin University", "CN"),
    "East China Normal University": ("East China Normal University", "CN"),
    "Northwestern University": ("Northwestern University", "US"),
    "ByteDance Inc.": ("ByteDance", "CN"),
    "Pennsylvania State University": ("Pennsylvania State University", "US"),
    "Brown University": ("Brown University", "US"),
    "University of Maryland": ("University of Maryland, College Park", "US"),
    "Facebook": ("Meta", "US"),
    "Facebook AI Research": ("Meta", "US"),
    "Meta": ("Meta", "US"),
    "Meta AI": ("Meta", "US"),
    "Institute of Automation, Chinese Academy of Sciences": ("Institute of Automation, CAS", "CN"),
    "Nanjing University of Science and Technology": ("Nanjing University of Science and Technology", "CN"),
    "Technion": ("Technion", "IL"),
    "Technion - Israel Institute of Technology": ("Technion", "IL"),
    "McGill University": ("McGill University", "CA"),
    "Dalian University of Technology": ("Dalian University of Technology", "CN"),
    "National University of Defense Technology": ("National University of Defense Technology", "CN"),
    "University of California, Santa Barbara": ("University of California, Santa Barbara", "US"),
    "Xi'an Jiaotong University": ("Xi'an Jiaotong University", "CN"),
    "Xi'an Jiaotong University": ("Xi'an Jiaotong University", "CN"),
    "Tongji University": ("Tongji University", "CN"),
    "Sun Yat-sen University": ("Sun Yat-sen University", "CN"),
    "SUN YAT-SEN UNIVERSITY": ("Sun Yat-sen University", "CN"),
    "University of Virginia": ("University of Virginia", "US"),
    "UC San Diego": ("University of California, San Diego", "US"),
    "Texas A&M University": ("Texas A&M University", "US"),
    "Texas A&M University - College Station": ("Texas A&M University", "US"),
    "Xiamen University": ("Xiamen University", "CN"),
    "University of Massachusetts Amherst": ("University of Massachusetts Amherst", "US"),
    "Simon Fraser University": ("Simon Fraser University", "CA"),
    "University of California Berkeley": ("University of California, Berkeley", "US"),
    "The Chinese University of Hong Kong, Shenzhen": ("Chinese University of Hong Kong, Shenzhen", "CN"),
    "The Ohio State University": ("Ohio State University", "US"),
    "Ohio State University, Columbus": ("Ohio State University", "US"),
    "National Taiwan University": ("National Taiwan University", "TW"),
    "Aalto University": ("Aalto University", "FI"),
    "Monash University": ("Monash University", "AU"),
    "University of Sydney": ("University of Sydney", "AU"),
    "The University of Sydney": ("University of Sydney", "AU"),
    "California Institute of Technology": ("California Institute of Technology", "US"),
    "Caltech": ("California Institute of Technology", "US"),
    "The Hong Kong Polytechnic University": ("Hong Kong Polytechnic University", "HK"),
    "Hong Kong Polytechnic University": ("Hong Kong Polytechnic University", "HK"),
    "Shanghai Artificial Intelligence Laboratory": ("Shanghai AI Lab", "CN"),
    "Shanghai AI Laboratory": ("Shanghai AI Lab", "CN"),
    "Singapore Management University": ("Singapore Management University", "SG"),
    "University of Tübingen": ("University of Tübingen", "DE"),
    "Technische Universität München": ("Technical University of Munich", "DE"),
    "Stony Brook University": ("Stony Brook University", "US"),
    "University of Notre Dame": ("University of Notre Dame", "US"),
    "OpenAI": ("OpenAI", "US"),
    "Sichuan University": ("Sichuan University", "CN"),
    "CMU": ("Carnegie Mellon University", "US"),
    "CMU, Carnegie Mellon University": ("Carnegie Mellon University", "US"),
    "Georgia Tech": ("Georgia Institute of Technology", "US"),
    "University of Minnesota": ("University of Minnesota", "US"),
    "University of Technology Sydney": ("University of Technology Sydney", "AU"),
    "University of California, Davis": ("University of California, Davis", "US"),
    "University of Copenhagen": ("University of Copenhagen", "DK"),
    "Tencent AI Lab": ("Tencent", "CN"),
    "Tencent": ("Tencent", "CN"),
    "KAUST": ("KAUST", "SA"),
    "King Abdullah University of Science and Technology": ("KAUST", "SA"),
    "Delft University of Technology": ("Delft University of Technology", "NL"),
    "MIT CSAIL": ("Massachusetts Institute of Technology", "US"),
    "Stanford": ("Stanford University", "US"),
    "University of Rochester": ("University of Rochester", "US"),
    "Westlake University": ("Westlake University", "CN"),
    "Rensselaer Polytechnic Institute": ("Rensselaer Polytechnic Institute", "US"),
    "Nankai University": ("Nankai University", "CN"),
    "Shenzhen University": ("Shenzhen University", "CN"),
    "University of Utah": ("University of Utah", "US"),
    "Politecnico di Milano": ("Politecnico di Milano", "IT"),
    "University of Central Florida": ("University of Central Florida", "US"),
    "Beijing Jiaotong University": ("Beijing Jiaotong University", "CN"),
    "Oregon State University": ("Oregon State University", "US"),
    "Huawei Noah's Ark Lab": ("Huawei", "CN"),
    "Huawei Technologies Ltd.": ("Huawei", "CN"),
    "KTH Royal Institute of Technology": ("KTH Royal Institute of Technology", "SE"),
    "Virginia Tech": ("Virginia Tech", "US"),
    "POSTECH": ("POSTECH", "KR"),
    "Hong Kong Baptist University": ("Hong Kong Baptist University", "HK"),
    "State Key Laboratory for Novel Software Technology, Nanjing University, China": ("Nanjing University", "CN"),
    "State Key Lab of CAD&CG, Zhejiang University": ("Zhejiang University", "CN"),
    "University of the Chinese Academy of Sciences": ("University of Chinese Academy of Sciences", "CN"),
    "Southern University of Science and Technology": ("Southern University of Science and Technology", "CN"),
    "Nanjing University of Aeronautics and Astronautics": ("Nanjing University of Aeronautics and Astronautics", "CN"),
    "Bar-Ilan University": ("Bar-Ilan University", "IL"),
    "Indian Institute of Science": ("Indian Institute of Science", "IN"),
    "Sungkyunkwan University": ("Sungkyunkwan University", "KR"),
    "Jilin University": ("Jilin University", "CN"),
    "Washington University in St. Louis": ("Washington University in St. Louis", "US"),
    "Northwestern Polytechnical University": ("Northwestern Polytechnical University", "CN"),
    "Tokyo Institute of Technology": ("Tokyo Institute of Technology", "JP"),
    "Osaka University": ("Osaka University", "JP"),
    "Ohio State University": ("Ohio State University", "US"),
    "University of Melbourne": ("University of Melbourne", "AU"),
    "George Mason University": ("George Mason University", "US"),
    "University of California, Santa Cruz": ("University of California, Santa Cruz", "US"),
    "National Yang Ming Chiao Tung University": ("National Yang Ming Chiao Tung University", "TW"),
    "École Polytechnique": ("École Polytechnique", "FR"),
    "University of California, Riverside": ("University of California, Riverside", "US"),
    "Max Planck Institute for Informatics": ("Max Planck Institute for Informatics", "DE"),
    "Max Planck Institute for Intelligent Systems": ("Max Planck Institute for Intelligent Systems", "DE"),
    "Microsoft Research Asia": ("Microsoft Research Asia", "CN"),
    "AWS AI Labs": ("Amazon", "US"),
    "CISPA Helmholtz Center for Information Security": ("CISPA", "DE"),
    "Harbin Institute of Technology, Shenzhen": ("Harbin Institute of Technology, Shenzhen", "CN"),
    "Université de Montréal": ("Université de Montréal", "CA"),
    "University of Bristol": ("University of Bristol", "GB"),
    "North Carolina State University": ("North Carolina State University", "US"),
    "Rochester Institute of Technology": ("Rochester Institute of Technology", "US"),
    "Dartmouth College": ("Dartmouth College", "US"),
    "University of Pittsburgh": ("University of Pittsburgh", "US"),
    "Eindhoven University of Technology": ("Eindhoven University of Technology", "NL"),
    "University of North Carolina at Chapel Hill": ("University of North Carolina at Chapel Hill", "US"),
    "Queen Mary University of London": ("Queen Mary University of London", "GB"),
    "Delft University of Technology": ("Delft University of Technology", "NL"),
    "Ludwig-Maximilians-Universität München": ("LMU Munich", "DE"),
    "University of Trento": ("University of Trento", "IT"),
    "Ant Group": ("Ant Group", "CN"),
    "SenseTime Research": ("SenseTime", "CN"),
    "Soochow University": ("Soochow University", "CN"),
    "University of Freiburg": ("University of Freiburg", "DE"),
    "Istituto Italiano di Tecnologia": ("Istituto Italiano di Tecnologia", "IT"),
    "Karlsruhe Institute of Technology": ("Karlsruhe Institute of Technology", "DE"),
    "German Aerospace Center (DLR)": ("German Aerospace Center (DLR)", "DE"),
    "German Aerospace Center": ("German Aerospace Center (DLR)", "DE"),
    "Kobe University": ("Kobe University", "JP"),
    "Kyoto University": ("Kyoto University", "JP"),
    "Wakayama University": ("Wakayama University", "JP"),
    "Nanjing University": ("Nanjing University", "CN"),
    "Tianjin University": ("Tianjin University", "CN"),
    "DAMO Academy, Alibaba Group": ("Alibaba", "CN"),
    # Remaining variants found in top-20s
    "Criteo": ("Criteo", "FR"),
    "York University": ("York University", "CA"),
    "Stevens Institute of Technology": ("Stevens Institute of Technology", "US"),
    "Moscow Institute of Physics and Technology": ("Moscow Institute of Physics and Technology", "RU"),
    "Courant Institute of Mathematical Sciences, NYU": ("New York University", "US"),
    "Institue for Advanced Study, Princeton": ("Institute for Advanced Study", "US"),
    "Saarland Informatics Campus, Max-Planck Institute": ("Max Planck Institute for Informatics", "DE"),
    "Sorbonne Université - Faculté des Sciences (Paris VI)": ("Sorbonne Université", "FR"),
    "Sorbonne Université - Faculté des Sciences": ("Sorbonne Université", "FR"),
}


def _normalize_institution(name: str) -> tuple[str, str]:
    """Normalize institution name → (canonical_name, country_code).

    Strategy:
    1. Exact lookup in _INST_MAP
    2. Pattern-based extraction: strip dept/school/lab prefixes, country/address suffixes
    3. Match extracted core against known institution names
    """
    if not name:
        return "", ""

    name = name.strip()

    # Strip trailing parenthetical content: "(MIT)", "(Guangzhou)", "(Shenzhen)" etc.
    name = re.sub(r'\s*\([^)]+\)\s*$', '', name)

    # Direct lookup
    if name in _INST_MAP:
        return _INST_MAP[name]

    # Case-insensitive lookup
    name_lower = name.lower()
    for key, val in _INST_MAP.items():
        if key.lower() == name_lower:
            return val

    # Strip trailing ", Same Name" pattern (OpenReview artifact)
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 2 and parts[0].lower() == parts[1].lower():
        name = parts[0]

    # --- Pattern-based extraction ---
    # Extract the likely core institution from "Dept/Lab/School, University, City, State, Country" patterns
    # Strategy: find the part that contains "University", "Institute", "College", etc.
    comma_parts = [p.strip() for p in name.split(",")]

    # Try to find a comma-separated segment that looks like a known institution
    core_candidates = []
    for part in comma_parts:
        pl = part.lower()
        if any(kw in pl for kw in ("university", "institute", "college", "technol")):
            core_candidates.append(part)

    # If we found institution-like segments, try matching them
    if core_candidates:
        for candidate in core_candidates:
            if candidate in _INST_MAP:
                return _INST_MAP[candidate]
            # Case-insensitive
            cl = candidate.lower()
            for key, val in _INST_MAP.items():
                if key.lower() == cl:
                    return val

    # Try stripping known prefixes and re-matching
    prefixes_to_strip = [
        "Department of ", "Dept. of ", "School of ", "Faculty of ",
        "College of ", "Graduate School of ",
    ]
    stripped = name
    for prefix in prefixes_to_strip:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):]
            break

    if stripped in _INST_MAP:
        return _INST_MAP[stripped]
    sl = stripped.lower()
    for key, val in _INST_MAP.items():
        if key.lower() == sl:
            return val

    # Strip address suffixes: ", City, ST, USA" / ", Country" / ", Country Code"
    # Find the university/institute part and strip everything after the last university-like segment
    address_suffixes = [
        r",\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2},\s*USA$",
        r",\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}$",
        r",\s*(?:China|Germany|France|Italy|UK|Japan|Korea|Singapore|Canada|Australia|India|Brazil|Spain|Netherlands|Switzerland|Austria|Sweden|Finland|Israel)$",
        r",\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*(?:China|Germany|France|Italy|UK|Japan|Korea|Singapore)$",
        r",\s*(?:China|Germany|France|Italy|UK|Japan|Korea|Singapore|Canada|Australia)$",
        r",\s*HK SAR,\s*China$",
        r",\s*Hong Kong SAR,\s*China$",
    ]
    import re as _re
    for suffix_re in address_suffixes:
        cleaned = _re.sub(suffix_re, "", stripped)
        if cleaned != stripped and cleaned in _INST_MAP:
            return _INST_MAP[cleaned]
        if cleaned != stripped:
            cl2 = cleaned.lower()
            for key, val in _INST_MAP.items():
                if key.lower() == cl2:
                    return val
            stripped = cleaned

    # Special: "X, Same X" → X (OpenReview duplication)
    if len(comma_parts) == 2 and comma_parts[0].lower() == comma_parts[1].lower():
        stripped = comma_parts[0]

    return stripped, ""


def compute_affiliation_top(affil_data: dict, top_n: int = 20) -> dict:
    """Compute top-N affiliation distribution from step2e data.

    Returns: {"total_covered": int, "total_papers": int, "coverage_pct": float,
              "top": [{"name": str, "count": int, "pct": float, "country": str}, ...]}
    """
    papers = affil_data.get("papers", [])
    total = affil_data.get("total_papers", len(papers))
    covered = sum(1 for p in papers if p.get("institution"))

    inst_counts: dict[str, int] = defaultdict(int)
    inst_countries: dict[str, str] = {}
    for p in papers:
        raw_inst = p.get("institution")
        if raw_inst:
            canon, country = _normalize_institution(raw_inst)
            inst_counts[canon] += 1
            # Prefer mapping country, fall back to raw data country
            if country:
                inst_countries[canon] = country
            else:
                raw_country = p.get("institution_country", "")
                if raw_country and canon not in inst_countries:
                    inst_countries[canon] = raw_country

    # Sort by count descending, take top-N
    sorted_insts = sorted(inst_counts.items(), key=lambda x: -x[1])[:top_n]

    top = [
        {
            "name": name,
            "count": count,
            "pct": round(100 * count / max(total, 1), 2),
            "country": inst_countries.get(name, ""),
        }
        for name, count in sorted_insts
    ]

    return {
        "total_covered": covered,
        "total_papers": total,
        "coverage_pct": round(100 * covered / max(total, 1), 1),
        "top": top,
    }


def validate_paper_counts(
    all_data: list[dict],
    all_venues: dict[str, dict],
    year_notes: dict[str, dict[str, dict]] | None = None,
) -> tuple[list[str], list[str]]:
    """Detect anomalies in paper counts.

    Checks:
    1. Papers exist for a year with no venue data (conference hasn't happened)
    2. Paper count drops sharply vs recent years (excluding COVID 2020-2021)
    3. Paper count spikes (>2x recent trend), suggesting workshop contamination

    Anomalies documented in year_notes are separated as "known".
    Conference-years with skip=true in year_notes are excluded entirely.

    Returns (new_warnings, known_warnings).
    """
    COVID_YEARS = {2020, 2021}
    if year_notes is None:
        year_notes = {}
    new_warnings = []
    known_warnings = []

    def _is_known(conf_id: str, year: int) -> bool:
        return str(year) in year_notes.get(conf_id, {})

    def _is_skipped(conf_id: str, year: int) -> bool:
        yn = year_notes.get(conf_id, {}).get(str(year), {})
        return bool(yn.get("skip"))

    def _add(msg: str, conf_id: str, year: int):
        if _is_known(conf_id, year):
            known_warnings.append(msg)
        else:
            new_warnings.append(msg)

    # Build {conf_id: {year: paper_count}} from raw data
    conf_year_papers: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for entry in all_data:
        conf_id = entry.get("conference", "").replace("/", "-")
        year = entry.get("year", 0)
        if not conf_id or not year or year < YEAR_FLOOR or year > year_ceiling():
            continue
        if _is_skipped(conf_id, year):
            continue
        first_authors = [a for a in entry.get("authors", []) if a.get("ordinal", 1) == 1]
        conf_year_papers[conf_id][year] = len(first_authors)

    # Build venue year sets
    venue_years: dict[str, set[int]] = {}
    for conf_id, year_map in all_venues.items():
        venue_years[conf_id] = {int(y) for y in year_map}

    for conf_id, year_counts in sorted(conf_year_papers.items()):
        vy = venue_years.get(conf_id, set())

        # Check 1: papers exist for a year with no venue data
        # (conference likely hasn't happened yet, or data is from workshops)
        for year, count in sorted(year_counts.items()):
            if count > 0 and vy and year not in vy:
                _add(
                    f"  {conf_id} {year}: {count} papers but NO venue data "
                    f"(conference may not have happened yet)",
                    conf_id, year,
                )

        # Build sorted yearly data for trend analysis
        sorted_years = sorted(year_counts.keys())
        if len(sorted_years) < 3:
            continue

        for i, year in enumerate(sorted_years):
            count = year_counts[year]
            if count < 30:
                continue

            # Get recent prior years for comparison (up to 3, excluding COVID)
            prior = []
            for j in range(i - 1, -1, -1):
                py = sorted_years[j]
                if py not in COVID_YEARS:
                    prior.append(year_counts[py])
                if len(prior) >= 3:
                    break

            if not prior:
                continue
            recent_max = max(prior)
            recent_avg = sum(prior) / len(prior)

            # Check 2: sharp drop (< 40% of recent average, not a COVID year)
            if year not in COVID_YEARS and recent_avg >= 30:
                if count < recent_avg * 0.4:
                    _add(
                        f"  {conf_id} {year}: {count} papers, "
                        f"recent avg {recent_avg:.0f} (sharp drop)",
                        conf_id, year,
                    )

            # Check 3: spike detection
            # If prior years show a consistent upward trend (each year >= previous),
            # use a relaxed 3x threshold — the conference is genuinely growing.
            # Otherwise use 2x for sudden jumps that suggest workshop contamination.
            if recent_max >= 30 and count - recent_max > 100:
                growing = len(prior) >= 2 and all(
                    prior[k] >= prior[k + 1] for k in range(len(prior) - 1)
                )
                threshold = 3 if growing else 2
                if count > recent_max * threshold:
                    _add(
                        f"  {conf_id} {year}: {count} papers, "
                        f"recent max {recent_max} (>{threshold}x spike)",
                        conf_id, year,
                    )

    return new_warnings, known_warnings


def run(force: bool = False):
    """Run step 4: generate aggregated statistics."""
    conferences = load_conferences()
    conf_meta = {c["id"]: c for c in conferences}
    all_data = load_all_classified()
    all_venues = load_venues()
    rank_history = load_rank_history()
    accept_rates = load_accept_rates()
    year_notes = load_year_notes()
    all_affiliations = load_affiliations()

    if not all_data:
        print("No classified data found. Run step 3 first.")
        return

    # Validate data before generating stats
    new_anomalies, known_anomalies = validate_paper_counts(all_data, all_venues, year_notes)
    if new_anomalies:
        print(f"WARNING: {len(new_anomalies)} NEW anomalies detected (not yet in conference_year_notes.json):")
        for w in new_anomalies:
            print(w)
        print()
    if known_anomalies:
        print(f"  ({len(known_anomalies)} known anomalies documented in notes, suppressed)")
        print()

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

    # Build venue-year sets for correcting publication year → conference year.
    # DBLP yearOfPublication can be 1 year later than the actual conference year
    # (e.g., FM 2024 proceedings published in 2025). Venue data from DBLP index
    # pages uses the real conference year, so we use it as ground truth.
    venue_years: dict[str, set[int]] = {}
    for conf_id_v, year_map in all_venues.items():
        venue_years[conf_id_v] = {int(y) for y in year_map}

    for entry in all_data:
        conf_id = entry.get("conference", "").replace("/", "-")
        year = entry.get("year", 0)

        if not conf_id or not year:
            continue

        # Fix publication year offset: DBLP yearOfPublication can lag the real
        # conference year by 1. Only applies to SPARQL-sourced data where the
        # year field may be the publication year rather than the conference year.
        # OpenReview and other manual crawls already use the correct conference year.
        if conf_id in venue_years and entry.get("_source", "sparql") == "sparql":
            vy = venue_years[conf_id]
            if year not in vy and (year - 1) in vy and (year - 1) >= 2010:
                year = year - 1

        # Skip papers with out-of-range years (DBLP data errors, e.g. 2089)
        if year < YEAR_FLOOR or year > year_ceiling():
            continue

        # Skip conference-years marked as "skip" in year notes
        # (e.g., joint conferences where papers are already counted elsewhere)
        yn = year_notes.get(conf_id, {}).get(str(year), {})
        if yn.get("skip"):
            continue

        # Count first authors only
        authors = [a for a in entry.get("authors", []) if a.get("ordinal", 1) == 1]

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
        "year_range": [min(global_by_year), max(global_by_year)] if global_by_year else [YEAR_FLOOR, year_ceiling()],
        "languages": LANGUAGE_GROUPS,
        "language_colors": LANGUAGE_COLORS,
        "ccf_versions": {
            "2011": {"name": "2nd Edition (2011)", "partial": True, "note": "Partial: DS, NW, SC, CG(C-only). Source: .doc file, may be inaccurate."},
            "2012": {"name": "3rd Edition (2012)", "partial": False},
            "2015": {"name": "4th Edition (2015)", "partial": False},
            "2019": {"name": "5th Edition (2019)", "partial": False},
            "2022": {"name": "6th Edition (2022)", "partial": False},
            "2026": {"name": "7th Edition (2026)", "partial": False},
        },
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
        # Add venue data if available
        if conf_id in all_venues:
            conf_stats["venues"] = all_venues[conf_id]
        # Add rank history if available
        if conf_id in rank_history:
            conf_stats["rank_history"] = rank_history[conf_id]
        # Add acceptance rates if available
        if conf_id in accept_rates:
            conf_stats["accept_rates"] = accept_rates[conf_id]
        # Add note if available (conference-level)
        if meta.get("note"):
            conf_stats["note"] = meta["note"]
        # Add per-year notes if available
        if conf_id in year_notes:
            conf_stats["year_notes"] = year_notes[conf_id]
        # Add affiliation data if available
        if conf_id in all_affiliations:
            conf_affils = all_affiliations[conf_id]
            years_with_data = [y for y in conf_years_seen.get(conf_id, set()) if y in conf_affils]

            if years_with_data:
                # Aggregate all years for overall top
                all_papers = [p for y in years_with_data for p in conf_affils[y].get("papers", [])]
                total_papers = sum(conf_affils[y].get("total_papers", 0) for y in years_with_data)

                affil_top = compute_affiliation_top({
                    "total_papers": total_papers,
                    "papers": all_papers,
                })

                if affil_top["total_covered"] > 0:
                    # Add per-year breakdown
                    by_year = {}
                    sources = set()
                    for y in years_with_data:
                        year_top = compute_affiliation_top(conf_affils[y])
                        if year_top["total_covered"] > 0:
                            by_year[str(y)] = year_top
                        src = conf_affils[y].get("source", "")
                        if src:
                            sources.add(src)

                    affil_top["by_year"] = by_year
                    affil_top["sources"] = sorted(sources)
                    conf_stats["affiliations"] = affil_top
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

        # YoY trend for dominant language
        latest_trend = None
        if latest_year and len(years_sorted) >= 2:
            prev_year = years_sorted[-2]
            prev_dist = dict(year_data.get(prev_year, {}))
            prev_total = max(sum(prev_dist.values()), 1)
            prev_pct = round(prev_dist.get(latest_lang, 0) / prev_total * 100, 1)
            latest_trend = round(latest_pct - prev_pct, 1)

        index.append({
            "id": conf_id,
            "title": meta.get("title", conf_id),
            "description": meta.get("description", ""),
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
            "latest_trend": latest_trend,
        })
    index.sort(key=lambda c: (-c["total_papers"],))
    _write_json(STATS_DIR / "conferences_index.json", index)

    # 7. affiliation_trends.json — institution trends for the Trends page
    generate_affiliation_trends(all_affiliations, conf_meta)

    print(f"Stats generated: {total_papers} papers across {len(conf_years_seen)} conferences → {STATS_DIR}")


def generate_affiliation_trends(
    all_affiliations: dict[str, dict[int, dict]],
    conf_meta_map: dict[str, dict],
) -> None:
    """Generate affiliation_trends.json for the Trends page.

    Aggregates institution counts by year across all conferences,
    broken down by category and rank (A only).
    """
    # Accumulators: {slice_key: {year: {institution: count}}}
    global_inst: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    cat_inst: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    rank_inst: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    inst_countries: dict[str, str] = {}

    # Coverage tracking: {slice_key: {year: {covered, total}}}
    global_cov: dict[int, dict[str, int]] = defaultdict(lambda: {"covered": 0, "total": 0})
    cat_cov: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"covered": 0, "total": 0}))
    rank_cov: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"covered": 0, "total": 0}))

    # Conference-years per year per slice
    global_conf_years: dict[int, set[str]] = defaultdict(set)
    cat_conf_years: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    rank_conf_years: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))

    for conf_id, years_data in all_affiliations.items():
        meta = conf_meta_map.get(conf_id, {})
        category = meta.get("category", "MX")
        rank = meta.get("rank", "N")

        for year, affil_data in years_data.items():
            if year < YEAR_FLOOR or year > year_ceiling():
                continue

            papers = affil_data.get("papers", [])
            total_papers = affil_data.get("total_papers", len(papers))
            covered = sum(1 for p in papers if p.get("institution"))

            # Update coverage
            global_cov[year]["covered"] += covered
            global_cov[year]["total"] += total_papers
            cat_cov[category][year]["covered"] += covered
            cat_cov[category][year]["total"] += total_papers
            rank_cov[rank][year]["covered"] += covered
            rank_cov[rank][year]["total"] += total_papers

            global_conf_years[year].add(conf_id)
            cat_conf_years[category][year].add(conf_id)
            rank_conf_years[rank][year].add(conf_id)

            for p in papers:
                raw_inst = p.get("institution")
                if not raw_inst:
                    continue
                canon, country = _normalize_institution(raw_inst)
                if not canon:
                    continue
                if country:
                    inst_countries[canon] = country
                global_inst[year][canon] += 1
                cat_inst[category][year][canon] += 1
                rank_inst[rank][year][canon] += 1

    def _build_slice(
        inst_data: dict[int, dict[str, int]],
        cov_data: dict[int, dict[str, int]],
        conf_yrs: dict[int, set[str]],
    ) -> dict:
        if not inst_data:
            return None
        years = sorted(inst_data.keys())
        # Aggregate total per institution across all years
        totals: dict[str, int] = defaultdict(int)
        for yr_data in inst_data.values():
            for inst, cnt in yr_data.items():
                totals[inst] += cnt
        institutions = {}
        for inst in totals:
            institutions[inst] = {
                "country": inst_countries.get(inst, ""),
                "by_year": {str(y): inst_data[y].get(inst, 0) for y in years},
            }
        return {
            "years": [str(y) for y in years],
            "institutions": institutions,
            "total_by_year": {str(y): sum(inst_data[y].values()) for y in years},
            "coverage_by_year": {
                str(y): {"covered": cov_data[y]["covered"], "total": cov_data[y]["total"]}
                for y in years
            },
            "conferences_by_year": {str(y): sorted(conf_yrs[y]) for y in years},
        }

    result = {}
    g = _build_slice(global_inst, global_cov, global_conf_years)
    if g:
        result["global"] = g

    # by_category: only categories with data
    by_cat = {}
    for cat in sorted(cat_inst):
        s = _build_slice(cat_inst[cat], cat_cov[cat], cat_conf_years[cat])
        if s:
            by_cat[cat] = s
    if by_cat:
        result["by_category"] = by_cat

    # by_rank: only rank A for now
    if "A" in rank_inst:
        s = _build_slice(rank_inst["A"], rank_cov["A"], rank_conf_years["A"])
        if s:
            result["by_rank"] = {"A": s}

    _write_json(STATS_DIR / "affiliation_trends.json", result)
    total_insts = len(result.get("global", {}).get("institutions", {}))
    total_years = len(result.get("global", {}).get("years", []))
    print(f"Affiliation trends: {total_insts} institutions across {total_years} years")


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
