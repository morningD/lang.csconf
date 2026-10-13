#!/bin/bash
# Traffic-guarded download: HEAD pre-check + hard size cap + usage ledger + daily budget.
#
# Usage: safe_fetch.sh <url> <out_path> [max_mb=50]
#   NET_BUDGET_MB  daily download budget, default 300 (set lower on metered links)
#   NETLOG         ledger path, default ~/.zcode-netlog
#
# Exit codes: 0 ok | 2 daily budget exhausted | 3 file larger than cap | 4 download failed
set -u

url="$1"; out="$2"; max_mb="${3:-50}"
budget_mb="${NET_BUDGET_MB:-300}"
log="${NETLOG:-$HOME/.zcode-netlog}"
touch "$log"
today=$(date +%F)

used=$(awk -F'\t' -v d="$today" '$1 ~ "^"d && $2 ~ /^[0-9]+$/ {s+=$2} END {print s+0}' "$log")
budget_bytes=$((budget_mb * 1024 * 1024))
if [ "$used" -ge "$budget_bytes" ]; then
  echo "NET BUDGET EXHAUSTED: ${used} bytes downloaded today (budget ${budget_mb}MB). Raise NET_BUDGET_MB only with the user's consent." >&2
  exit 2
fi

# HEAD pre-check: reject oversized targets before pulling a single byte.
head_json=$(curl -sIL --max-time 30 -H 'User-Agent: Mozilla/5.0' -w '%{http_code} %{size_download}' -o /dev/null "$url")
size=$(curl -sIL --max-time 30 -H 'User-Agent: Mozilla/5.0' "$url" | tr -d '\r' | awk 'tolower($1)=="content-length:" {v=$2} END {print v+0}')
if [ "$size" -gt $((max_mb * 1024 * 1024)) ]; then
  echo "REFUSED: $url is $((size / 1024 / 1024))MB > cap ${max_mb}MB. Fetch only the byte range you need (curl -r)." >&2
  printf '%s\t0\t%s\tHEAD-refused (%s bytes avoided)\n' "$(date -u +%FT%TZ)" "$url" "$size" >> "$log"
  exit 3
fi

mkdir -p "$(dirname "$out")"
if ! curl -fsSL --retry 2 --max-time 900 --max-filesize $((max_mb * 1024 * 1024)) \
       -H 'User-Agent: Mozilla/5.0' -o "$out" "$url"; then
  echo "DOWNLOAD FAILED: $url" >&2
  exit 4
fi

bytes=$(stat -f%z "$out" 2>/dev/null || stat -c%s "$out" 2>/dev/null || echo 0)
printf '%s\t%s\t%s\tok\n' "$(date -u +%FT%TZ)" "$bytes" "$url" >> "$log"
echo "downloaded $bytes bytes (today: $((used + bytes)) / ${budget_mb}MB) -> $out"
