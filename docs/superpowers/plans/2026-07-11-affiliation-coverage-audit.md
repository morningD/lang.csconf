# CCF-B Affiliation 覆盖率离线审计工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个完全离线、只读的命令行审计工具，诊断 CCF-B 会议第一作者 affiliation 覆盖率低下的阶段性原因，并写出稳定的结构化 JSON 报告。

**Architecture:** `scripts/audit_affiliation_coverage.py` 仅扫描 `data/raw/conferences.json`、`data/raw/authors/` 和 `data/raw/affiliations/`，以存在作者原始文件的 2010–2026 年 CCF-B conference-year 为唯一分母。脚本将 OpenAlex 条目分解为未匹配、已匹配但无机构、已有机构三阶段；其他来源只汇总已有覆盖结果，避免把其缺口归因给 OpenAlex。标准库 `unittest` 的夹具测试将构造最小 JSON 数据集，验证边界、汇总和确定性输出。

**Tech Stack:** Python 3 标准库（`argparse`、`json`、`pathlib`、`collections`、`unittest`）；无需新增依赖、网络请求或 API key。

## Global Constraints

- 只读取 `data/raw/conferences.json`、`data/raw/authors/`、`data/raw/affiliations/`；唯一允许的业务数据写入目标是新的 audit JSON 报告。
- 不调用 OpenAlex 或任何网络服务，不读取 `scripts/openalex_keys.txt`，不使用 API key。
- 不修改或删除既有 affiliation 文件，不执行 `--force`，不触发 pipeline 步骤。
- 目标范围固定为 `2010 <= year <= 2026`、`rank == "B"`、且存在 `data/raw/authors/{CONF}_{YEAR}.json` 的 conference-year。
- OpenAlex 分层必须满足 `with_institution <= matched <= total`；违背该不变量的文件必须保留在报告的完整性异常中，而不是静默修正。
- 非 `source == "openalex"` 的记录必须使用 `diagnosis: "non_openalex"`，不得依据 `matched` 字段对 OpenAlex 做归因。
- 输出不得包含运行时间戳或绝对路径；相同输入连续运行必须产生字节稳定的 JSON（缩进 2、`sort_keys=True`、末尾换行）。

---

### Task 1: 建立可测试的审计数据模型与纯函数

**Files:**
- Create: `scripts/audit_affiliation_coverage.py`
- Create: `tests/scripts/test_audit_affiliation_coverage.py`

**Interfaces:**
- Consumes: `dict` 格式 conference、raw author 和 affiliation JSON 数据。
- Produces:
  - `audit_affiliation_data(conferences: list[dict], authors_dir: Path, affiliations_dir: Path, year_floor: int = 2010, year_ceiling: int = 2026) -> dict`
  - `classify_coverage(total: int, with_institution: int) -> str`
  - `analyze_affiliation_file(conf_id: str, year: int, raw_total: int, payload: dict) -> dict`
- Record contract:
  ```python
  {
      "conference": "CONF",
      "year": 2024,
      "source": "openalex",
      "total": 3,
      "matched": 2,
      "with_institution": 1,
      "coverage_pct": 33.3,
      "coverage_band": "10_to_50",
      "diagnosis": "openalex_metadata_gap",
      "integrity_issues": [],
  }
  ```

- [ ] **Step 1: 创建测试目录和失败测试**

创建 `tests/scripts/test_audit_affiliation_coverage.py`，使用临时目录保存会议、原始作者与 affiliation fixture。测试应直接导入尚不存在的脚本模块：

```python
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audit_affiliation_coverage.py"
SPEC = importlib.util.spec_from_file_location("audit_affiliation_coverage", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class AuditAffiliationCoverageTests(unittest.TestCase):
    def test_openalex_record_separates_matching_and_metadata_gaps(self):
        payload = {
            "source": "openalex",
            "total_papers": 3,
            "total_matched": 2,
            "total_with_affiliation": 1,
            "papers": [
                {"matched": True, "institution": "Example University"},
                {"matched": True, "institution": None},
                {"matched": False, "institution": None},
            ],
        }

        result = audit.analyze_affiliation_file("CONF", 2024, 3, payload)

        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["with_institution"], 1)
        self.assertEqual(result["coverage_pct"], 33.3)
        self.assertEqual(result["coverage_band"], "10_to_50")
        self.assertEqual(result["diagnosis"], "openalex_metadata_gap")
        self.assertEqual(result["integrity_issues"], [])
```

- [ ] **Step 2: 运行测试，确认其因模块缺失失败**

运行：

```bash
python3 -m unittest tests.scripts.test_audit_affiliation_coverage.AuditAffiliationCoverageTests.test_openalex_record_separates_matching_and_metadata_gaps -v
```

预期：失败，错误包含 `No such file or directory` 或 `audit_affiliation_coverage.py` 不存在。

- [ ] **Step 3: 实现纯函数与 OpenAlex 分层逻辑**

创建 `scripts/audit_affiliation_coverage.py`，先加入以下代码；此阶段不实现 CLI 和完整扫描：

```python
#!/usr/bin/env python3
"""Audit existing CCF-B affiliation coverage without network access."""

from __future__ import annotations

from pathlib import Path
from typing import Any


COVERAGE_BANDS = (
    (0.0, "zero"),
    (10.0, "under_10"),
    (50.0, "10_to_50"),
)


def classify_coverage(total: int, with_institution: int) -> str:
    """Return the priority band for a conference-year's coverage."""
    pct = 100 * with_institution / total if total else 0.0
    if pct == 0:
        return "zero"
    if pct < 10:
        return "under_10"
    if pct < 50:
        return "10_to_50"
    return "50_or_more"


def _count_papers(papers: list[dict[str, Any]]) -> tuple[int, int]:
    matched = sum(bool(paper.get("matched")) for paper in papers)
    with_institution = sum(bool(paper.get("institution")) for paper in papers)
    return matched, with_institution


def analyze_affiliation_file(
    conf_id: str, year: int, raw_total: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """Analyze one existing affiliation payload without mutating it."""
    source = str(payload.get("source") or "unknown")
    papers = payload.get("papers")
    integrity_issues: list[str] = []
    if not isinstance(papers, list):
        papers = []
        integrity_issues.append("papers_not_list")

    file_total = payload.get("total_papers")
    if not isinstance(file_total, int):
        file_total = len(papers)
        integrity_issues.append("total_papers_missing_or_invalid")
    if file_total != raw_total:
        integrity_issues.append("raw_total_mismatch")

    if source == "openalex":
        matched, with_institution = _count_papers(papers)
        declared_matched = payload.get("total_matched")
        declared_with_institution = payload.get("total_with_affiliation")
        if declared_matched != matched:
            integrity_issues.append("total_matched_mismatch")
        if declared_with_institution != with_institution:
            integrity_issues.append("total_with_affiliation_mismatch")
        if with_institution > matched:
            integrity_issues.append("institution_exceeds_matched")
        if matched > raw_total:
            integrity_issues.append("matched_exceeds_raw_total")
        if matched < raw_total:
            diagnosis = "openalex_match_gap"
        elif with_institution < matched:
            diagnosis = "openalex_metadata_gap"
        else:
            diagnosis = "openalex_complete"
    else:
        matched = _count_papers(papers)[0]
        with_institution = _count_papers(papers)[1]
        diagnosis = "non_openalex"

    coverage_pct = round(100 * with_institution / raw_total, 1) if raw_total else 0.0
    return {
        "conference": conf_id,
        "year": year,
        "source": source,
        "total": raw_total,
        "matched": matched,
        "with_institution": with_institution,
        "coverage_pct": coverage_pct,
        "coverage_band": classify_coverage(raw_total, with_institution),
        "diagnosis": diagnosis,
        "integrity_issues": sorted(integrity_issues),
    }
```

- [ ] **Step 4: 运行单测，确认 OpenAlex 分层通过**

运行：

```bash
python3 -m unittest tests.scripts.test_audit_affiliation_coverage.AuditAffiliationCoverageTests.test_openalex_record_separates_matching_and_metadata_gaps -v
```

预期：`OK`，1 个测试通过。

- [ ] **Step 5: 提交纯函数与测试**

```bash
git add scripts/audit_affiliation_coverage.py tests/scripts/test_audit_affiliation_coverage.py
git commit -m "feat: add affiliation coverage audit core"
```


### Task 2: 扫描真实目录、报告完整性异常并汇总数据

**Files:**
- Modify: `scripts/audit_affiliation_coverage.py`
- Modify: `tests/scripts/test_audit_affiliation_coverage.py`

**Interfaces:**
- Consumes: `data/raw/conferences.json` 中 `id` 与 `rank`，以及 filename 为 `{CONF}_{YYYY}.json` 的作者/affiliation 文件。
- Produces: `audit_affiliation_data(...)` 返回的 report：
  ```python
  {
      "scope": {"rank": "B", "year_floor": 2010, "year_ceiling": 2026},
      "summary": {
          "eligible_conference_years": 2,
          "affiliation_files_found": 1,
          "missing_affiliation_files": 1,
          "invalid_affiliation_files": 0,
      },
      "by_source": {"openalex": {"conference_years": 1, "total": 3, ...}},
      "records": [...],
      "priority": {"zero": [...], "under_10": [...], "10_to_50": [...]},
      "integrity_issues": [...],
  }
  ```

- [ ] **Step 1: 添加失败测试，覆盖范围筛选、缺失文件与非 OpenAlex 数据**

在测试文件追加：

```python
    def test_audit_uses_raw_author_files_as_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            conferences = [
                {"id": "BCONF", "rank": "B"},
                {"id": "ACONF", "rank": "A"},
            ]
            write_json(authors_dir / "BCONF_2024.json", {
                "authors": [
                    {"title": "One", "ordinal": 1},
                    {"title": "One", "ordinal": 2},
                    {"title": "Two", "ordinal": 1},
                ],
            })
            write_json(authors_dir / "BCONF_2025.json", {
                "authors": [{"title": "Three", "ordinal": 1}],
            })
            write_json(authors_dir / "ACONF_2024.json", {
                "authors": [{"title": "Ignored", "ordinal": 1}],
            })
            write_json(affiliations_dir / "BCONF_2024.json", {
                "source": "papercopilot",
                "total_papers": 2,
                "total_matched": 2,
                "total_with_affiliation": 1,
                "papers": [
                    {"matched": True, "institution": "Example University"},
                    {"matched": True, "institution": None},
                ],
            })

            report = audit.audit_affiliation_data(
                conferences, authors_dir, affiliations_dir
            )

        self.assertEqual(report["summary"]["eligible_conference_years"], 2)
        self.assertEqual(report["summary"]["affiliation_files_found"], 1)
        self.assertEqual(report["summary"]["missing_affiliation_files"], 1)
        self.assertEqual(report["records"][0]["diagnosis"], "non_openalex")
        self.assertEqual(report["priority"]["zero"], [{"conference": "BCONF", "year": 2025}])
        self.assertEqual(report["integrity_issues"], [
            {"conference": "BCONF", "year": 2025, "issue": "missing_affiliation_file"},
        ])
```

- [ ] **Step 2: 运行测试，确认扫描函数尚未定义**

运行：

```bash
python3 -m unittest tests.scripts.test_audit_affiliation_coverage.AuditAffiliationCoverageTests.test_audit_uses_raw_author_files_as_denominator -v
```

预期：失败，错误包含 `AttributeError: module ... has no attribute 'audit_affiliation_data'`。

- [ ] **Step 3: 实现原始作者分母识别、文件读取和稳定汇总**

在 `scripts/audit_affiliation_coverage.py` 的已有函数之后加入以下实现。只把 `ordinal == 1` 的作者按 `title` 去重；空标题的第一作者记录保留为单独论文，以避免无标题数据被错误合并：

```python
import json
import re
from collections import defaultdict


AUTHOR_FILENAME = re.compile(r"^(?P<conference>[A-Za-z0-9+&.\-]+)_(?P<year>\d{4})\.json$")


def _raw_paper_total(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    authors = payload.get("authors") if isinstance(payload, dict) else payload
    if not isinstance(authors, list):
        raise ValueError("authors_not_list")
    seen_titles: set[str] = set()
    untitled_count = 0
    for author in authors:
        if not isinstance(author, dict) or author.get("ordinal") != 1:
            continue
        title = author.get("title")
        if isinstance(title, str) and title.strip():
            seen_titles.add(title.strip())
        else:
            untitled_count += 1
    return len(seen_titles) + untitled_count


def _eligible_raw_files(
    conferences: list[dict[str, Any]], authors_dir: Path, year_floor: int, year_ceiling: int
) -> list[tuple[str, int, Path]]:
    ccf_b_ids = {str(item.get("id")) for item in conferences if item.get("rank") == "B"}
    eligible: list[tuple[str, int, Path]] = []
    for path in sorted(authors_dir.glob("*.json")):
        match = AUTHOR_FILENAME.fullmatch(path.name)
        if not match:
            continue
        conf_id = match.group("conference")
        year = int(match.group("year"))
        if conf_id in ccf_b_ids and year_floor <= year <= year_ceiling:
            eligible.append((conf_id, year, path))
    return eligible


def _source_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = defaultdict(lambda: {
        "conference_years": 0, "total": 0, "matched": 0, "with_institution": 0,
    })
    for record in records:
        source = record["source"]
        summary[source]["conference_years"] += 1
        for key in ("total", "matched", "with_institution"):
            summary[source][key] += record[key]
    return {source: summary[source] for source in sorted(summary)}


def audit_affiliation_data(
    conferences: list[dict[str, Any]],
    authors_dir: Path,
    affiliations_dir: Path,
    year_floor: int = 2010,
    year_ceiling: int = 2026,
) -> dict[str, Any]:
    """Return a deterministic offline audit for eligible CCF-B conference-years."""
    records: list[dict[str, Any]] = []
    integrity_issues: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    invalid = 0
    for conf_id, year, raw_path in _eligible_raw_files(
        conferences, authors_dir, year_floor, year_ceiling
    ):
        try:
            raw_total = _raw_paper_total(raw_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            integrity_issues.append({
                "conference": conf_id, "year": year, "issue": f"invalid_raw_file:{error}",
            })
            continue
        affiliation_path = affiliations_dir / f"{conf_id}_{year}.json"
        if not affiliation_path.exists():
            item = {"conference": conf_id, "year": year}
            missing.append(item)
            integrity_issues.append({**item, "issue": "missing_affiliation_file"})
            continue
        try:
            payload = json.loads(affiliation_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload_not_object")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            invalid += 1
            integrity_issues.append({
                "conference": conf_id, "year": year, "issue": f"invalid_affiliation_file:{error}",
            })
            continue
        record = analyze_affiliation_file(conf_id, year, raw_total, payload)
        records.append(record)
        integrity_issues.extend(
            {"conference": conf_id, "year": year, "issue": issue}
            for issue in record["integrity_issues"]
        )

    records.sort(key=lambda item: (item["conference"], item["year"]))
    integrity_issues.sort(key=lambda item: (item["conference"], item["year"], item["issue"]))
    priority = {
        band: [
            {"conference": item["conference"], "year": item["year"]}
            for item in records if item["coverage_band"] == band
        ]
        for band in ("zero", "under_10", "10_to_50")
    }
    return {
        "scope": {"rank": "B", "year_floor": year_floor, "year_ceiling": year_ceiling},
        "summary": {
            "eligible_conference_years": len(records) + len(missing) + invalid,
            "affiliation_files_found": len(records),
            "missing_affiliation_files": len(missing),
            "invalid_affiliation_files": invalid,
        },
        "by_source": _source_summary(records),
        "records": records,
        "priority": priority,
        "integrity_issues": integrity_issues,
    }
```

同时将文件顶部的 import 合并为：

```python
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
```

- [ ] **Step 4: 运行所有单元测试，确认分母和异常语义正确**

运行：

```bash
python3 -m unittest tests.scripts.test_audit_affiliation_coverage -v
```

预期：`OK`，两个测试通过。

- [ ] **Step 5: 提交扫描和汇总逻辑**

```bash
git add scripts/audit_affiliation_coverage.py tests/scripts/test_audit_affiliation_coverage.py
git commit -m "feat: audit CCF-B affiliation coverage"
```


### Task 3: 添加 CLI、写出报告并验证真实 CCF-B 数据

**Files:**
- Modify: `scripts/audit_affiliation_coverage.py`
- Modify: `tests/scripts/test_audit_affiliation_coverage.py`
- Create (generated, do not hand-edit): `data/stats/affiliation_coverage_audit.json`

**Interfaces:**
- Consumes:
  ```bash
  python3 scripts/audit_affiliation_coverage.py \
    --conferences data/raw/conferences.json \
    --authors-dir data/raw/authors \
    --affiliations-dir data/raw/affiliations \
    --output data/stats/affiliation_coverage_audit.json
  ```
- Produces: `main(argv: list[str] | None = None) -> int`，成功写入后返回 `0`；输出路径的父目录不存在时创建它。

- [ ] **Step 1: 添加 CLI 输出确定性的失败测试**

在测试文件追加：

```python
    def test_main_writes_stable_sorted_json_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conferences_path = root / "conferences.json"
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            output_path = root / "stats" / "audit.json"
            write_json(conferences_path, [{"id": "BCONF", "rank": "B"}])
            write_json(authors_dir / "BCONF_2024.json", {
                "authors": [{"title": "One", "ordinal": 1}],
            })
            write_json(affiliations_dir / "BCONF_2024.json", {
                "source": "openalex",
                "total_papers": 1,
                "total_matched": 1,
                "total_with_affiliation": 1,
                "papers": [{"matched": True, "institution": "Example University"}],
            })
            argv = [
                "--conferences", str(conferences_path),
                "--authors-dir", str(authors_dir),
                "--affiliations-dir", str(affiliations_dir),
                "--output", str(output_path),
            ]

            self.assertEqual(audit.main(argv), 0)
            first = output_path.read_bytes()
            self.assertEqual(audit.main(argv), 0)
            self.assertEqual(output_path.read_bytes(), first)
            report = json.loads(first)

        self.assertEqual(report["records"][0]["diagnosis"], "openalex_complete")
        self.assertTrue(first.endswith(b"\n"))
```

- [ ] **Step 2: 运行测试，确认 `main` 尚未定义**

运行：

```bash
python3 -m unittest tests.scripts.test_audit_affiliation_coverage.AuditAffiliationCoverageTests.test_main_writes_stable_sorted_json_report -v
```

预期：失败，错误包含 `AttributeError: module ... has no attribute 'main'`。

- [ ] **Step 3: 实现 CLI 与原子化 JSON 写出**

在 `scripts/audit_affiliation_coverage.py` 中增加 `argparse`、`os` import，并在末尾加入：

```python
import argparse
import os


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFERENCES = ROOT / "data" / "raw" / "conferences.json"
DEFAULT_AUTHORS_DIR = ROOT / "data" / "raw" / "authors"
DEFAULT_AFFILIATIONS_DIR = ROOT / "data" / "raw" / "affiliations"
DEFAULT_OUTPUT = ROOT / "data" / "stats" / "affiliation_coverage_audit.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline audit for CCF-B first-author affiliation coverage"
    )
    parser.add_argument("--conferences", type=Path, default=DEFAULT_CONFERENCES)
    parser.add_argument("--authors-dir", type=Path, default=DEFAULT_AUTHORS_DIR)
    parser.add_argument("--affiliations-dir", type=Path, default=DEFAULT_AFFILIATIONS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--year-floor", type=int, default=2010)
    parser.add_argument("--year-ceiling", type=int, default=2026)
    args = parser.parse_args(argv)

    conferences = json.loads(args.conferences.read_text(encoding="utf-8"))
    if not isinstance(conferences, list):
        raise ValueError("conferences JSON must be an array")
    report = audit_affiliation_data(
        conferences,
        args.authors_dir,
        args.affiliations_dir,
        args.year_floor,
        args.year_ceiling,
    )
    _write_json(args.output, report)
    summary = report["summary"]
    print(
        "CCF-B affiliation audit: "
        f"eligible={summary['eligible_conference_years']}, "
        f"files={summary['affiliation_files_found']}, "
        f"missing={summary['missing_affiliation_files']}, "
        f"invalid={summary['invalid_affiliation_files']}"
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行单元测试，确认 CLI 输出稳定**

运行：

```bash
python3 -m unittest tests.scripts.test_audit_affiliation_coverage -v
```

预期：`OK`，三个测试通过。

- [ ] **Step 5: 用真实输入生成报告并验证既定完整性不变量**

运行：

```bash
python3 scripts/audit_affiliation_coverage.py
python3 - <<'PY'
import json
from pathlib import Path
path = Path("data/stats/affiliation_coverage_audit.json")
report = json.loads(path.read_text(encoding="utf-8"))
assert report["summary"]["eligible_conference_years"] == 1978
assert report["summary"]["missing_affiliation_files"] == 0
assert report["summary"]["invalid_affiliation_files"] == 0
for record in report["records"]:
    if record["source"] == "openalex":
        assert record["with_institution"] <= record["matched"] <= record["total"], record
print("validated", report["summary"])
PY
cp data/stats/affiliation_coverage_audit.json /tmp/affiliation_coverage_audit.first.json
python3 scripts/audit_affiliation_coverage.py
cmp /tmp/affiliation_coverage_audit.first.json data/stats/affiliation_coverage_audit.json
```

预期：审计摘要显示 `eligible=1978`、`missing=0`、`invalid=0`；Python 验证输出 `validated`；`cmp` 无输出且退出状态为 0。

- [ ] **Step 6: 提交 CLI、测试与生成报告**

```bash
git add scripts/audit_affiliation_coverage.py tests/scripts/test_audit_affiliation_coverage.py data/stats/affiliation_coverage_audit.json
git commit -m "feat: generate CCF-B affiliation coverage audit"
```


### Task 4: 抽查报告语义与项目数据镜像策略

**Files:**
- Modify: `data/stats/affiliation_coverage_audit.json`（由脚本重新生成）
- Optional create: `website/public/data/stats/affiliation_coverage_audit.json`（仅当产品决定在前端消费该审计报告时）

**Interfaces:**
- Consumes: Task 3 输出的 audit report。
- Produces: 经确认的数据质量结论；本任务不改变前端代码，也不引入报告同步，除非已有消费者明确需要。

- [ ] **Step 1: 检查 0%、<10%、10–<50% 三个优先级的代表记录**

运行：

```bash
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("data/stats/affiliation_coverage_audit.json").read_text())
records = {(item["conference"], item["year"]): item for item in report["records"]}
for band in ("zero", "under_10", "10_to_50"):
    items = report["priority"][band]
    print(band, len(items), items[:3])
    for item in items[:3]:
        record = records[(item["conference"], item["year"])]
        print(" ", record["conference"], record["year"], record["source"], record["diagnosis"], record["matched"], record["with_institution"], record["total"])
PY
```

预期：每个优先级仅列出对应覆盖区间的 conference-year；`source != "openalex"` 的记录始终显示 `diagnosis=non_openalex`。

- [ ] **Step 2: 确认报告不应自动同步到网站公开数据目录**

检查 `website` 中是否存在实际读取 `affiliation_coverage_audit.json` 的代码：

```bash
rg "affiliation_coverage_audit" website || true
```

预期：无匹配。该报告是维护诊断资产，不是前端数据契约；因此不执行 `rsync`，也不创建 `website/public/data/stats/affiliation_coverage_audit.json`。

- [ ] **Step 3: 最终回归测试**

运行：

```bash
python3 -m unittest tests.scripts.test_audit_affiliation_coverage -v
python3 scripts/audit_affiliation_coverage.py
```

预期：所有单元测试通过；报告被确定性重建且没有网络请求、key 使用或 affiliation 文件改动。

- [ ] **Step 4: 提交最终验证产生的报告（若 Task 3 后报告发生变化）**

```bash
git status --short
git add data/stats/affiliation_coverage_audit.json
git commit -m "chore: refresh affiliation coverage audit"
```

只有当 `git status --short` 显示 `data/stats/affiliation_coverage_audit.json` 有变化时才创建此提交；否则跳过本步骤。

---

## Plan Self-Review

- **Spec coverage:** Task 1 实现 OpenAlex 的未匹配/元数据缺失/完整分层；Task 2 将正确的 CCF-B raw-author 分母、非 OpenAlex 隔离、缺失与无效文件异常、来源汇总和三档优先级写入报告；Task 3 提供只读 CLI、稳定 JSON、真实 1,978 条范围和不变量验证；Task 4 抽查报告语义并避免无消费者的前端同步。
- **Placeholder scan:** 计划没有待定标记、未定义接口或“适当处理”之类模糊步骤。唯一 Optional 条目有明确条件（出现真实前端消费者）且默认不执行。
- **Type consistency:** 测试、纯函数和 CLI 均使用 `dict[str, Any]` 报告结构；`records` 的键名 `total`、`matched`、`with_institution` 在所有后续任务一致；`priority` 只使用 `zero`、`under_10`、`10_to_50` 三个约定键。
