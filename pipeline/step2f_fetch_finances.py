"""Step 2f: Fetch conference finances from ProPublica Nonprofit Explorer API.

CCF-A AI conferences are run by US 501(c)(3) nonprofits whose IRS Form 990
filings are public. ProPublica Nonprofit Explorer exposes structured filing
data via a free JSON API (no key required).

Scope is organizational ("foundation scope"): stored per conference with a
scope_note explaining what the numbers actually cover (see
pipeline/finances_sources.json).

Output: data/raw/finances/{CONF}.json
{
  "org_name", "ein", "scope", "scope_note", "propublica_url",
  "source": "propublica",
  "fiscal_note": "IRS tax year (tax_prd YYYYMM)",
  "years": {
    "2024": {"tax_period": "202405", "revenue": ..., "expenses": ...,
              "net_income": ..., "net_assets": ..., "pdf_url": ...}
  },
  "fetched_at": "ISO date"
}

Manual overrides: pipeline/finances_overrides.json
{"CONF": {"years": {"2024": {...override fields...}}, "note": "..."}}
merged on top of fetched data (set a year's value to null to hide it).
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
FINANCES_DIR = RAW_DIR / "finances"
SOURCES_FILE = Path(__file__).parent / "finances_sources.json"
OVERRIDES_FILE = Path(__file__).parent / "finances_overrides.json"

API_URL = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
REQUEST_DELAY = 1.0


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fetch_org(ein: str, session: requests.Session) -> dict:
    resp = session.get(API_URL.format(ein=ein), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _parse_filings(payload: dict, fiscal_end_month: int) -> dict:
    """filings_with_data -> {str(conference_year): metrics}.

    tax_prd YYYYMM: IRS tax year = YYYY. For calendar-year filers the tax
    year equals the conference year. Conferences held in December (NeurIPS)
    with a FY ending early the next year land in tax_year+1, so map
    tax_year-1 -> conference_year when fiscal_end_month <= 6.

    Also extracts the revenue composition (Form 990 Part VIII lines the
    IRS e-file schema exposes: contributions / program service /
    investment+gains / royalties / miscellaneous) and the partial expense
    detail the schema carries (officer & staff compensation, fundraising).
    """
    years: dict[str, dict] = {}
    for f in payload.get("filings_with_data", []):
        tax_prd = f.get("tax_prd")
        if not tax_prd:
            continue
        tax_year = int(str(tax_prd)[:4])
        year = tax_year - 1 if fiscal_end_month <= 6 else tax_year
        revenue = f.get("totrevenue")
        expenses = f.get("totfuncexpns")

        def _nz(*vals) -> int | None:
            """Sum non-None values; None if every component is missing."""
            present = [v for v in vals if v is not None]
            return sum(present) if present else None

        revenue_mix: dict[str, int | None] = {
            "contributions": f.get("totcntrbgfts"),
            "program": f.get("totprgmrevnue"),
            "investment": _nz(f.get("invstmntinc"), f.get("netgnls")),
            "royalties": f.get("royaltsinc"),
            "misc": f.get("miscrevtot11e"),
        }
        if all(v is None for v in revenue_mix.values()):
            revenue_mix = None
        expense_partial: dict[str, int | None] = {
            "officer_comp": f.get("compnsatncurrofcr"),
            "salaries": f.get("othrsalwages"),
            "payroll_tax": f.get("payrolltx"),
            "fundraising": f.get("profndraising"),
        }
        if all(v is None for v in expense_partial.values()):
            expense_partial = None

        entry = {
            "tax_period": str(tax_prd),
            "tax_year": tax_year,
            "conference_year": year,
            "revenue": revenue,
            "expenses": expenses,
            "net_income": (revenue - expenses) if (revenue is not None and expenses is not None) else None,
            "net_assets": f.get("totnetassetend"),
            "pdf_url": f.get("pdf_url"),
            "revenue_mix": revenue_mix,
            "expense_partial": expense_partial,
        }
        # Keep the latest filing if multiple tax periods map to the same conference year
        prev = years.get(str(year))
        if prev is None or str(tax_prd) > prev["tax_period"]:
            years[str(year)] = entry
    return years


def _apply_overrides(data: dict, conf_id: str) -> dict:
    overrides = _load_json(OVERRIDES_FILE, {})
    conf_ovr = overrides.get(conf_id)
    if not conf_ovr:
        return data
    for key, val in conf_ovr.items():
        if key == "years":
            for yr, fields in val.items():
                yr_entry = data["years"].setdefault(str(yr), {"tax_period": "override"})
                for fk, fv in fields.items():
                    yr_entry[fk] = fv
        else:
            data[key] = val
    data["overridden"] = True
    return data


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Fetch Form 990 financials for all conferences registered in finances_sources.json."""
    sources = _load_json(SOURCES_FILE, {})
    sources = {k: v for k, v in sources.items() if not k.startswith("_")}
    if conferences_filter:
        sources = {k: v for k, v in sources.items() if k in conferences_filter}
    if not sources:
        print("No finance sources registered.")
        return

    FINANCES_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "lang.csconf pipeline (academic research)"})

    fetched = skipped = 0
    for conf_id, meta in sorted(sources.items()):
        out_file = FINANCES_DIR / f"{conf_id}.json"
        if out_file.exists() and not force:
            skipped += 1
            continue
        ein = meta["ein"]
        if not ein:
            print(f"{conf_id}: skipped (no EIN — no US filing)")
            skipped += 1
            continue
        fiscal_end_month = int(meta.get("fiscal_end_month", 12))
        print(f"{conf_id}: fetching EIN {ein} ({meta['org_name']})...")
        try:
            payload = _fetch_org(ein, session)
        except requests.RequestException as e:
            print(f"  ERROR: {e}")
            continue
        years = _parse_filings(payload, fiscal_end_month)
        if not years:
            print("  WARNING: no filings with data")
            continue
        data = {
            "org_name": meta["org_name"],
            "ein": ein,
            "scope": meta["scope"],
            "scope_note": meta["scope_note"],
            "usable": meta.get("usable", True),
            "propublica_url": meta.get("propublica_url") or (f"https://projects.propublica.org/nonprofits/organizations/{ein}" if ein else ""),
            "source": "propublica",
            "fiscal_end_month": fiscal_end_month,
            "fiscal_note": (
                f"IRS tax year ending month {fiscal_end_month:02d}; "
                + ("conference_year = tax_year - 1 (Dec conference, FY ends next year)"
                   if fiscal_end_month <= 6 else
                   "conference_year = tax_year (calendar year)")
            ),
            "years": years,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        data = _apply_overrides(data, conf_id)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        span = f"{min(years)}-{max(years)}"
        print(f"  saved {len(years)} fiscal years ({span}) -> {out_file.name}")
        fetched += 1
        time.sleep(REQUEST_DELAY)

    print(f"Done: {fetched} fetched, {skipped} skipped (use --force to re-fetch).")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch conference finances (step 2f)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--conferences", type=str, help="Comma-separated conference IDs")
    args = parser.parse_args()
    run(force=args.force, conferences_filter=args.conferences.split(",") if args.conferences else None)
