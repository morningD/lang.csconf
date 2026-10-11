"""Generate deep JSON files from batch_extract results (USENIX entries replicated per conference)."""
import json
from pathlib import Path

DEEP = Path('/Users/momo/Documents/workspace/lang.csconf/data/raw/finances/deep')
RAW = Path('/Users/momo/Documents/workspace/lang.csconf/data/raw/finances')
USENIX_CONFS = ['OSDI', 'NSDI', 'FAST', 'USENIXSECURITY', 'USENIXATC']

result = json.load(open('/tmp/zcode-finances/batch_result.json'))
ok = fail = dup = 0
for r in result:
    if not r.get('ok'): fail += 1; continue
    conf, tp = r['conf'], r['tax_period']
    confs = USENIX_CONFS if conf == 'USENIX' else [conf]
    # revenue_mix from the API data (already per-year in raw finances)
    try:
        raw = json.load(open(RAW / f'{conf}.json'))
        rmix = raw['years'][str(r.get('year', tp[:4] if int(tp[:4]) <= int(max(raw['years'])) else tp[:4]))].get('revenue_mix')
    except Exception:
        rmix = None
    for c in confs:
        if conf == 'USENIX' and c != conf and tp != r['tax_period']: pass
        out = DEEP / f'{c}_{tp}.json'
        if out.exists():
            dup += 1
            # merge expense_mix into existing file if it lacks one
            ex = json.load(open(out))
            if not ex.get('expense_mix'):
                ex['expense_mix'] = r['items']
                ex['total_expenses'] = r['total']
                json.dump(ex, open(out, 'w'), ensure_ascii=False, indent=2)
            continue
        d = {
            "conf_id": c, "tax_period": tp,
            "total_expenses": r['total'],
            "revenue_mix": rmix,
            "expense_mix": r['items'],
            "notes": "expense composition parsed from IRS TEOS e-file XML; line items cross-checked to Part IX total",
        }
        json.dump(d, open(out, 'w'), ensure_ascii=False, indent=2)
print(f"ok={ok} fail={fail} dup-merged={dup}")
