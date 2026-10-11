"""Batch-extract Part IX expense breakdowns from TEOS XML for all missing years."""
import json, struct, sys, time, urllib.request, zlib
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from teos3 import fetch_range, head_size

BASE = "https://apps.irs.gov/pub/epostcard/990/xml"
CACHE = Path('/tmp/zcode-finances/teos_cache')
CACHE.mkdir(exist_ok=True)

def year_cache(year):
    p = CACHE / f"zips_{year}.json"
    if p.exists():
        return json.load(open(p))
    zips = []
    miss = 0
    for seq in "AB":
        for i in range(1, 100):
            part = f"{i:02d}{seq}"
            name = f"{year}_TEOS_XML_{part}.zip"
            url = f"{BASE}/{year}/{name}"
            size = head_size(url)
            if size:
                zips.append({"url": url, "name": name, "size": size}); miss = 0
            else:
                miss += 1
                if zips and miss >= 20: break
                if not zips and seq == "B" and miss >= 6: break
    with open(p, 'w') as f: json.dump(zips, f, indent=1)
    return zips

def index_cache(year):
    p = CACHE / f"index_{year}.json"
    csv_pre = CACHE / f"index_{year}.csv"
    if not p.exists() and csv_pre.exists() and csv_pre.stat().st_size > 1000:
        data = csv_pre.read_text('utf-8', 'replace')
        idx = {}
        for line in data.split('\n'):
            parts = line.split(',')
            if len(parts) >= 9 and parts[8].strip():
                idx[(parts[2].lstrip('0'), parts[3].replace('-', ''))] = (parts[8].strip(), parts[1])
        with open(p, 'w') as f:
            json.dump(idx, f)
    if p.exists():
        return json.load(open(p))
    # IRS rate-limits aggressive clients; retry with backoff until non-empty
    import subprocess, time as _t
    csvp = CACHE / f"index_{year}.csv"
    for attempt, wait in enumerate([0, 30, 60, 120, 240]):
        if wait: _t.sleep(wait)
        subprocess.run(['curl', '-s', '--retry', '2', '--max-time', '600',
                        '-H', 'User-Agent: Mozilla/5.0', '-o', str(csvp),
                        f"{BASE}/{year}/index_{year}.csv"], check=False, timeout=700)
        if csvp.exists() and csvp.stat().st_size > 1000:
            break
        print(f"  index {year}: attempt {attempt+1} empty ({csvp.stat().st_size if csvp.exists() else 0}b), backoff {wait}s", flush=True)
    data = csvp.read_text('utf-8', 'replace') if csvp.exists() else ""
    idx = {}
    for line in data.split('\n'):
        parts = line.split(',')
        if len(parts) >= 9 and parts[8].strip():
            idx[f"{parts[2].lstrip('0')}|{parts[3].replace('-','')}"] = (parts[8].strip(), parts[1])
    with open(p, 'w') as f:
        json.dump(idx, f)
    return idx

def cd_cache(url, size, name):
    p = CACHE / (name.replace('.zip', '') + '_cd.json')
    if p.exists():
        return json.load(open(p))
    tail = fetch_range(url, f"bytes={max(0, size - 12_000_000)}-")
    loff = tail.rfind(b'PK\x05\x06')
    if loff < 0: return {"entries": {}}
    e = tail[loff:]
    cd_size, cd_off = struct.unpack('<II', e[12:20])
    if cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF:
        loff64 = tail.rfind(b'PK\x06\x07')
        cd64_off = struct.unpack('<Q', tail[loff64+8:loff64+16])[0]
        cd64 = fetch_range(url, f"bytes={cd64_off}-{cd64_off + 60}")
        cd_size = struct.unpack('<Q', cd64[44:52])[0]
        cd_off = struct.unpack('<Q', cd64[52:60])[0]
    cd_data = fetch_range(url, f"bytes={cd_off}-{cd_off + cd_size}")
    entries = {}
    idx = 0
    while idx < len(cd_data) - 46:
        if cd_data[idx:idx+4] == b'PK\x01\x02':
            (sig, ver, vneed, flags, method, mtime, mdate, crc, csize, usize,
             nlen, elen, clen, dsk, iattr, eattr, lho) = struct.unpack('<IHHHHHHIIIHHHHHII', cd_data[idx:idx+46])
            name = cd_data[idx+46:idx+46+nlen].decode('utf-8', 'replace')
            if object_id_like(name):
                entries[name] = {"lho": lho, "csize": csize, "method": method}
            idx += 46 + nlen + elen + clen
        else:
            idx += 1
    with open(p, 'w') as f: json.dump({"entries": entries, "cd_off": cd_off, "cd_size": cd_size}, f)
    return {"entries": entries, "cd_off": cd_off, "cd_size": cd_size}

def object_id_like(name):
    return '/public.xml' in name or name.endswith('_public.xml')

def prefix_of(url):
    head = fetch_range(url, "bytes=0-2047")
    return head.find(b'PK\x03\x04')

def extract_xml(year, ein, tax_period):
    idx = index_cache(year)
    hit = idx.get(f"{ein.lstrip('0')}|{tax_period}")
    if not hit: return None, f"not in index {year}"
    obj, ftype = hit
    zips = year_cache(year)
    for z in zips:
        cd = cd_cache(z['url'], z['size'], z['name'])
        entry = cd['entries'].get(f"Cycles")
        # find by object id in entries keys
        matches = [k for k in cd['entries'] if obj in k]
        if matches:
            k = matches[0]
            meta = cd['entries'][k]
            prefix = prefix_of(z['url'])
            lho = meta['lho'] + prefix
            blob = fetch_range(z['url'], f"bytes={lho}-{lho + meta['csize'] + 2048}")
            nlen2, elen2 = struct.unpack('<HH', blob[26:30])
            payload = blob[30 + nlen2 + elen2:30 + nlen2 + elen2 + meta['csize']]
            if meta['method'] == 8:
                try:
                    payload = zlib.decompress(payload, -15)
                except zlib.error:
                    # CD lho may be off for this non-standard archive; locate the
                    # local header signature inside the blob and parse from there
                    p2 = blob.find(b'PK\x03\x04')
                    if p2 < 0: raise
                    nlen3, elen3 = struct.unpack('<HH', blob[p2+26:p2+30])
                    payload = zlib.decompress(blob[p2+30+nlen3+elen3:p2+30+nlen3+elen3+meta['csize']+4096], -15)
            return payload.decode('utf-8', 'replace'), f"{z['name']}:{k}"
    return None, "not found in zips"

MAPPING = {
  'AdvertisingGrp': 'advertising',
  'AllOtherExpensesGrp': 'other',
  'ConferencesMeetingsGrp': 'conferences',
  'ConferencesConventionsAndMeetingsGrp': 'conferences',
  'DepreciationDepletionGrp': 'depreciation',
  'DepreciationDepletionAndAmortizationGrp': 'depreciation',
  'FeesForServicesAccountingGrp': 'accounting_fees',
  'FeesForServicesLegalGrp': 'legal_fees',
  'FeesForServicesOtherGrp': 'other_fees',
  'FeesForSrvcInvstMgmntFeesGrp': 'investment_mgmt_fees',
  'InformationTechnologyGrp': 'information_technology',
  'InsuranceGrp': 'insurance',
  'OccupancyGrp': 'occupancy',
  'OfficeExpensesGrp': 'office_expenses',
  'OtherEmployeeBenefitsGrp': 'employee_benefits',
  'OtherSalariesAndWagesGrp': 'salaries_wages',
  'TravelGrp': 'travel',
  'LobbyingGrp': 'lobbying',
  'GrantsAndOtherAssistanceToOrganizationsGrp': 'grants_orgs',
  'GrantsAndOtherAssistanceToIndividualsGrp': 'grants_individuals',
  'GrantsAndOtherAssistanceToForeignOrganizationsGrp': 'grants_foreign',
  'PaymentsOfTravelOrEntertainmentExpensesGrp': 'travel_entertainment',
  'InterestGrp': 'interest',
  'PaymentsToAffiliatesGrp': 'affiliates',
  'CompensationOfOfficersDirectorsTrusteesKeyEmployeesGrp': 'officer_compensation',
  'FeesForServicesManagementGrp': 'management_fees',
  'ProfessionalFundraisingFeesGrp': 'fundraising_fees',
  'RltdOrgOfficerTrstKeyEmplGrp': 'related_org_payments',
  'SuppliesGrp': 'supplies',
  'PrintingGrp': 'printing',
  'TelephoneAndInternetGrp': 'telephone_internet',
  'PostageGrp': 'postage',
  'EquipmentRentalsGrp': 'equipment_rentals',
  'BadDebtGrp': 'bad_debt',
  'InvestmentManagementGrp': 'investment_mgmt',
}
SKIP = {'PrepaidExpensesDefrdChargesGrp', 'BusinessOfficerGrp', 'SigningOfficerGrp'}

def parse_part_ix(xml):
    root = ET.fromstring(xml)
    items = {}
    total = None
    for el in root.iter():
        tag = el.tag.split('}')[-1]
        if tag in ('TotalFunctionalExpensesGrp', 'TotalExpensesGrp'):
            for ch in el:
                ct = ch.tag.split('}')[-1]
                if ct == 'TotalAmt':
                    total = int(ch.text or 0)
        if tag in SKIP: continue
        if tag in MAPPING:
            for ch in el:
                ct = ch.tag.split('}')[-1]
                if ct == 'TotalAmt':
                    v = int(ch.text or 0)
                    if v > 0:
                        key = MAPPING[tag]
                        items[key] = items.get(key, 0) + v
    return items, total

def main():
    targets = json.load(open('/tmp/zcode-finances/missing_targets.json'))
    out = []
    for t in targets:
        conf, ein, tp = t['conf'], t['ein'], t['tax_period']
        # USENIX association: submission year = tax year + 1; database year = tax year + 1 generally
        xml = None; src = None
        for yr in (int(tp[:4]) + 1, int(tp[:4]), int(tp[:4]) + 2):
            try:
                xml, src = extract_xml(str(yr), ein, tp)
            except Exception as e:
                import traceback
                tb = ' | '.join(l.strip() for l in traceback.format_exc().splitlines() if l.strip())[:300]
                xml, src = None, f"ERR {tb}"
            if xml: break
        if not xml:
            out.append({"conf": conf, "tax_period": tp, "ok": False, "why": src})
            print(f"FAIL {conf} {tp}: {src}", flush=True)
            continue
        try:
            items, total = parse_part_ix(xml)
        except Exception as e:
            out.append({"conf": conf, "tax_period": tp, "ok": False, "why": f"parse: {e}"})
            print(f"PARSE FAIL {conf} {tp}: {e}", flush=True)
            continue
        ok = total is not None and abs(sum(items.values()) - total) <= 3
        out.append({"conf": conf, "tax_period": tp, "ok": ok, "total": total, "sum": sum(items.values()), "items": items})
        t_str = f"{total:,}" if total is not None else "None"
        print(f"{'OK ' if ok else 'MISMATCH'} {conf} {tp}: {len(items)} items, sum {sum(items.values()):,} vs {t_str}", flush=True)
    json.dump(out, open('/tmp/zcode-finances/batch_result.json', 'w'), indent=1)
    ok = sum(1 for r in out if r['ok'])
    print(f"=== done: {ok}/{len(out)}")

if __name__ == '__main__':
    main()
