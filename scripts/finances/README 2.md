# Finances TEOS extraction tools

批量提取 IRS TEOS e-file XML 中的 Part IX 支出构成（用于补齐历史年份的
expense_mix）。适用对象：电子申报的 501(c)(3) 主体（USENIX/IJCAI/VLDB 等）。

## 一键收尾（限流解除后运行）

    /tmp/zcode-finances/finish_missing.sh

或手动分步：

    python3 scripts/finances/batch_extract.py    # 批量提取 → /tmp/zcode-finances/batch_result.json
    python3 scripts/finances/gen_deep_from_batch.py  # 生成 deep JSON（USENIX ×5 会议复制）
    python3 -m pipeline.run_all --step 4         # 重建 stats
    rsync -a data/stats/finances.json website/public/data/stats/

## 已知限制

- IRS 对频繁请求限流（小时级窗口）：index CSV 下载需间隔/退避（脚本已内置）
- TEOS zip 为非标准封装：开头 76 字节前缀 + zip64 EOCD，teos3.py 已处理
- 纸质申报（如 ICML 2018）无 XML/PDF 电子副本，结构性缺失

## 文件

- teos3.py: EOCD/zip64/前缀三重修复的远程 zip 定位与提取
- batch_extract.py: 批量驱动（index 查找 → 定位 zip → 提取 → 解析 Part IX）
- gen_deep_from_batch.py: batch 结果 → deep JSON（USENIX 条目复制到 5 个会议）
