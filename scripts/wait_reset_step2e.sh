#!/bin/bash
# Wait for the OpenAlex UTC-midnight budget reset, verify, then start watchdog_step2e.sh.
# Usage: nohup scripts/wait_reset_step2e.sh > /dev/null 2>&1 &

set -u
cd "$(dirname "$0")/.."
LOG_DIR="${TMPDIR:-/tmp}/langcsconf"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/step2e.log"
KEY=$(grep -v '^#' scripts/openalex_keys.txt | head -1)

WAIT=$(python3 -c "
import datetime
now = datetime.datetime.now(datetime.timezone.utc)
midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
print(int((midnight - now).total_seconds()))
")
echo "[waiter] sleeping ${WAIT}s until UTC midnight $(date '+%F %T')" >> "$LOG"
sleep "$WAIT"

CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
  "https://api.openalex.org/works?per_page=1&filter=title.search:robot,publication_year:2021&api_key=$KEY")
echo "[waiter] budget probe: HTTP $CODE $(date '+%F %T')" >> "$LOG"
if [ "$CODE" != "200" ]; then
  echo "[waiter] still rate-limited, aborting" >> "$LOG"
  exit 1
fi
echo "[waiter] budget reset confirmed, launching watchdog" >> "$LOG"
exec scripts/watchdog_step2e.sh
