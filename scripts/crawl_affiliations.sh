#!/usr/bin/env bash
# Robust OpenReview affiliation crawler with auto-restart on stalls.
# Usage: bash scripts/crawl_affiliations.sh
#
# - Runs step2e for OpenReview conferences only (skips existing files)
# - Monitors progress: if no new output for STALL_TIMEOUT seconds, kills and restarts
# - MAX_RESTARTS controls how many times to retry before giving up
# - Each restart creates a new session (fresh SSL connection)
# - Set env vars to override: STALL_TIMEOUT=120 MAX_RESTARTS=50

set -euo pipefail
cd "$(dirname "$0")/.."

STALL_TIMEOUT=${STALL_TIMEOUT:-120}   # seconds without output before restart
MAX_RESTARTS=${MAX_RESTARTS:-50}       # max restart attempts
CHECK_INTERVAL=${CHECK_INTERVAL:-10}   # how often to check for stalls

restarts=0
output_file=""

cleanup() {
    if [[ -n "$output_file" ]] && [[ -f "$output_file" ]]; then
        # Check if crawl completed successfully
        if grep -q "ALL DONE" "$output_file" 2>/dev/null; then
            echo "[$(date '+%H:%M:%S')] Crawl completed successfully."
            # Show final summary
            echo ""
            echo "=== Completed affiliation files ==="
            for f in data/raw/affiliations/*.json; do
                [[ "$(basename "$f")" == _* ]] && continue
                python3 -c "import json; d=json.load(open('$f')); print(f\"{d['conference']} {d['year']}: {d['total_with_affiliation']}/{d['total_papers']} ({d['coverage_pct']}%)\")" 2>/dev/null || true
            done
            exit 0
        fi
    fi
    echo "[$(date '+%H:%M:%S')] Cleanup: killing crawl process..."
    jobs -p | xargs kill 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT

echo "[$(date '+%H:%M:%S')] Starting resilient affiliation crawler"
echo "  Stall timeout: ${STALL_TIMEOUT}s, Max restarts: ${MAX_RESTARTS}, Check interval: ${CHECK_INTERVAL}s"
echo ""

while [[ $restarts -lt $MAX_RESTARTS ]]; do
    restarts=$((restarts + 1))
    echo "[$(date '+%H:%M:%S')] === Attempt $restarts/$MAX_RESTARTS ==="

    # Create temp output file
    output_file=$(mktemp /tmp/affil_crawl_${RANDOM}_XXXXXX.log)

    # Start crawl in background
    PYTHONUNBUFFERED=1 PYTHONPATH=. python3 -c "
import sys
from pipeline.step2e_fetch_affiliations import _process_openreview
from pipeline.utils.openreview import _session, registered_conferences
from pathlib import Path
import time

s = _session()
or_confs = registered_conferences()

missing = []
for conf_id in or_confs:
    for f in sorted(Path('data/raw/authors').glob(f'{conf_id}_*.json')):
        year = int(f.stem.split('_')[1])
        if not (Path('data/raw/affiliations') / f'{conf_id}_{year}.json').exists():
            missing.append((conf_id, year))

print(f'Missing: {len(missing)} conference-years')
for c, y in missing:
    print(f'  {c} {y}')

for conf_id, year in missing:
    print(f'=== {conf_id} {year} ===', flush=True)
    try:
        result = _process_openreview(conf_id, year, s, force=False)
        if result is not None:
            print(f'  Done: {result} papers with affiliations', flush=True)
        else:
            print(f'  Skipped (no notes on OpenReview)', flush=True)
    except Exception as e:
        print(f'  Error: {type(e).__name__}: {e}', flush=True)
        time.sleep(2)
print('ALL DONE', flush=True)
" > "$output_file" 2>&1 &

    crawl_pid=$!
    last_size=0
    stall_count=0

    # Monitor for stalls
    while kill -0 "$crawl_pid" 2>/dev/null; do
        sleep "$CHECK_INTERVAL"
        current_size=$(wc -c < "$output_file" 2>/dev/null || echo 0)

        if [[ "$current_size" -eq "$last_size" ]]; then
            stall_count=$((stall_count + CHECK_INTERVAL))
            if [[ "$stall_count" -ge "$STALL_TIMEOUT" ]]; then
                echo "[$(date '+%H:%M:%S')] STALLED: no output for ${STALL_TIMEOUT}s, killing PID $crawl_pid"
                # Show last few lines for debugging
                echo "  Last output:"
                tail -3 "$output_file" | sed 's/^/    /'
                kill -9 "$crawl_pid" 2>/dev/null || true
                wait "$crawl_pid" 2>/dev/null || true
                break
            fi
        else
            stall_count=0
            last_size=$current_size
            # Show latest progress
            tail -1 "$output_file" | sed 's/^/  /' || true
        fi
    done

    # Check if process exited naturally
    if ! kill -0 "$crawl_pid" 2>/dev/null; then
        wait "$crawl_pid" 2>/dev/null || true
        if grep -q "ALL DONE" "$output_file" 2>/dev/null; then
            echo "[$(date '+%H:%M:%S')] Crawl completed!"
            cat "$output_file"
            rm -f "$output_file"
            exit 0
        fi
    fi

    echo "[$(date '+%H:%M:%S')] Process died or was killed. Waiting 5s before restart..."
    rm -f "$output_file"
    sleep 5
done

echo "[$(date '+%H:%M:%S')] Exceeded max restarts ($MAX_RESTARTS). Giving up."
exit 1
