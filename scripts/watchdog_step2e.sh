#!/bin/bash
# Watchdog for `pipeline.run_all --step 2e` (OpenAlex affiliations crawl).
#
# Restarts the crawler when its log stalls. Rationale: the local proxy's
# fake-IP mapping can reset at runtime, blackholing a long-lived process's
# connections. A fresh process gets fresh DNS and runs fast again.
#
# Usage:
#   nohup scripts/watchdog_step2e.sh > /dev/null 2>&1 &
#
# Env:
#   OPENALEX_NO_KEY=1  use polite pool (when daily key budget is exhausted)
#   STALL_SECS         log stall threshold before restart (default 180)

set -u
cd "$(dirname "$0")/.."

STALL_SECS="${STALL_SECS:-180}"
LOG_DIR="${TMPDIR:-/tmp}/langcsconf"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/step2e.log"

echo "[watchdog] start $(date '+%F %T')" >> "$LOG"
while true; do
  python3 -u -m pipeline.run_all --step 2e >> "$LOG" 2>&1 &
  PID=$!
  echo "[watchdog] started PID $PID $(date '+%T')" >> "$LOG"
  while kill -0 $PID 2>/dev/null; do
    sleep 30
    AGE=$(( $(date +%s) - $(stat -f %m "$LOG") ))
    if [ "$AGE" -gt "$STALL_SECS" ]; then
      echo "[watchdog] log stalled ${AGE}s, restarting PID $PID $(date '+%T')" >> "$LOG"
      kill -9 $PID 2>/dev/null
      sleep 2
      break
    fi
  done
  wait $PID 2>/dev/null
  grep -q "Step 2e complete" "$LOG" && { echo "[watchdog] finished $(date '+%F %T')" >> "$LOG"; break; }
  sleep 5
done
