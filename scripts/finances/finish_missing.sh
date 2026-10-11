#!/bin/bash
# 完成剩余 85 份缺失支出构成的提取（限流解除后运行）
set -e
cd /Users/momo/Documents/workspace/lang.csconf
echo "== step 1: batch extract (TEOS XML)"
python3 /tmp/zcode-finances/batch_extract.py > /tmp/zcode-finances/batch_final.log 2>&1
grep -cE "^OK " /tmp/zcode-finances/batch_final.log || true
echo "== step 2: generate deep JSONs"
python3 /tmp/zcode-finances/gen_deep_from_batch.py
echo "== step 3: rebuild stats + sync"
python3 -m pipeline.run_all --step 4 2>&1 | grep "Finances:"
rsync -a data/stats/finances.json website/public/data/stats/
echo "== done"
