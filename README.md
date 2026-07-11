# lang.csconf

**What language does your conference speak?**

Visualizing the linguistic diversity of first authors across CCF-rated CS conferences (2010–2026).

**Live demo**: [morningD.github.io/lang.csconf](https://morningD.github.io/lang.csconf/)

[English](#features) | [中文](#简介)

> Names are terrible predictors of language. We did it anyway.

## Data Coverage

| Metric | Value |
|--------|-------|
| **Conferences** | 416 (CCF A/B/C + non-ranked) |
| **Papers** | 909,106 |
| **Year range** | 2010–2026 |
| **Categories** | 10 (AI, DB, NW, SE, CG, CT, HI, SC, DS, MX) |
| **Languages tracked** | 17 |

## Open Data

The raw crawled dataset (909k+ first-author records from DBLP + OpenReview, 2010–2026) is available for download on the [Releases](https://github.com/morningD/lang.csconf/releases) page. The data has been extensively cleaned — see the [About page](https://morningD.github.io/lang.csconf/#/about) for details.

## Features

- **Global Overview** — Pie charts, trend lines, and animated counters showing the linguistic landscape of CS research
- **Conference Explorer** — Deep-dive into any CCF-rated conference with year-by-year language breakdowns
- **Compare Conferences** — Side-by-side radar charts for 2–4 conferences
- **Trends** — Filter by CCF category (AI/DB/SE...) and rank (A/B/C/N) to see how things change over time
- **CCF Rank History** — Track how conference rankings evolved across 6 CCF editions (2011–2026)
- **4 Languages** — UI available in English, 中文, 日本語, Deutsch

## Architecture

```
lang.csconf/
├── pipeline/          # Python: crawl DBLP + classify names → JSON stats
│   ├── conferences_base.json      # Single source of truth for 416 conferences
│   ├── step1_parse_conferences.py # Load base + apply CCF rank/category overrides
│   ├── step1b_parse_accept_rates.py # Merge acceptance rates from 7 sources
│   ├── step2_crawl_sparql.py      # Crawl DBLP via SPARQL for all authors
│   ├── step2b_crawl_venues.py     # Crawl DBLP for venue city/country
│   ├── step2c_fill_gaps.py        # Fill SPARQL indexing gaps via Search API
│   ├── step2d_crawl_openreview.py # Crawl OpenReview for AI/ML conferences
│   ├── step3_classify_names.py    # Predict language from names (fastText + rules)
│   ├── step4_generate_stats.py    # Aggregate statistics
│   └── run_all.py                 # Orchestrator
├── scripts/
│   └── extract_ccf_ranks.py       # Extract ranks + categories from CCF PDFs
├── website/           # Vue 3 + Vite: static site consuming JSON stats
│   └── src/
│       ├── views/     # 5 pages: Home, Conference, Compare, Trends, About
│       ├── components/# ECharts wrappers, layout, PixelRobots animation
│       └── i18n/      # 4 locale files (en/zh/ja/de)
├── data/              # Generated data (committed to repo)
│   ├── raw/           # Crawled author data + venue data
│   ├── classified/    # Author data with language predictions
│   ├── ccf-versions/  # CCF PDFs + extracted rank history
│   └── stats/         # Pre-computed JSON for website; maintenance-only audit reports remain here unless consumed by the frontend
│       └── affiliation_coverage_audit.json # Offline CCF-B affiliation-coverage diagnosis
└── .github/workflows/ # Deploy site + weekly data updates
```

## Quick Start

### Website Development

```bash
cd website
pnpm install
pnpm dev
```

### Data Pipeline

```bash
# Install Python dependencies
pip install -r pipeline/requirements.txt

# Run full pipeline (incremental, skips existing data)
python -m pipeline.run_all

# Run for specific conferences
python -m pipeline.run_all --conferences CVPR,AAAI,SIGMOD

# Run single step
python -m pipeline.run_all --step 1

# Force re-crawl
python -m pipeline.run_all --force
```

## Data Pipeline

| Step | What it does |
|------|-------------|
| 1. Parse conferences | Loads `conferences_base.json`, applies CCF rank/category from extracted PDFs |
| 1b. Accept rates | Merges acceptance rates from 7 upstream sources |
| 2. Crawl DBLP | Fetches all author names via DBLP SPARQL endpoint |
| 2b. Crawl venues | Scrapes DBLP HTML for conference city/country |
| 2c. Fill gaps | Fills SPARQL indexing gaps via DBLP Search API |
| 2d. OpenReview | Crawls OpenReview for AI/ML conferences (NeurIPS, ICLR, ICML, etc.) |
| 3. Classify names | Predicts language using fastText + rule-based surname ensemble |
| 4. Generate stats | Aggregates by conference, category, rank, year → JSON |

### Affiliation Coverage Audit

```bash
python3 scripts/audit_affiliation_coverage.py
```

The command is read-only with respect to crawled input: it reads CCF-B conference metadata, raw author files, and existing affiliation files, then deterministically writes `data/stats/affiliation_coverage_audit.json`. It makes no network requests, consumes no OpenAlex key, and never overwrites affiliation data. The report separates OpenAlex title-match gaps from matched-but-missing institution metadata, keeps non-OpenAlex sources out of OpenAlex attribution, and lists data-integrity exceptions. DBLP conference-metadata entries that have no corresponding affiliation record are excluded from the audit denominator and counted in `summary.excluded_conference_metadata`.

For an `openalex_match_gap`, first create a guarded, offline retry manifest rather than running a broad re-crawl:

```bash
python3 scripts/openalex_batch_crawl.py \
  --audit-report data/stats/affiliation_coverage_audit.json \
  --targets-file data/stats/affiliation_retry_plans/pilot_targets.json \
  --dry-run \
  --plan-output data/stats/affiliation_retry_plans/pilot_plan.json
```

The dry-run reads no API keys, makes no network request, and only accepts existing `source: "openalex"` files whose raw-paper total and matched count still agree with the audit snapshot. It rejects non-OpenAlex sources and audit drift. `openalex_metadata_gap` is not a title-retry candidate. A reviewed manifest is still **not** permission to overwrite data: each `--force --retry-unmatched-only` batch needs explicit approval, must preserve earlier matches, and is promoted only when matched and institution counts do not decline and at least one count improves.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Build | Vite 7 |
| Framework | Vue 3 (Composition API + TypeScript) |
| Charts | Apache ECharts 6 (via vue-echarts) |
| i18n | vue-i18n 9 |
| CSS | UnoCSS |
| Pipeline | Python 3.12 + fastText (fast-langdetect) |
| Deploy | GitHub Pages + Actions |

## Disclaimer

**Name-based language inference is inherently imprecise.** Many factors — immigration, marriage, cultural mixing, adopted names — make names unreliable indicators of linguistic background. This project is meant as a fun, light-hearted visualization, not a rigorous sociolinguistic study. No discrimination intended.

---

## 简介

**你的会议说什么语言？**

可视化 CCF 推荐计算机学术会议（2010–2026）第一作者的语言多样性。

**在线演示**: [morningD.github.io/lang.csconf](https://morningD.github.io/lang.csconf/)

> 基于姓名推断语言并不准确，但我们还是做了。

## 数据收录

| 指标 | 数值 |
|------|------|
| **会议数** | 416（CCF A/B/C + 未评级） |
| **论文数** | 909,106 |
| **年份范围** | 2010–2026 |
| **学科分类** | 10（AI、DB、NW、SE、CG、CT、HI、SC、DS、MX） |
| **追踪语言数** | 17 |

## 开放数据

原始爬取数据集（90 万余条第一作者记录，来自 DBLP + OpenReview，2010–2026）可在 [Releases](https://github.com/morningD/lang.csconf/releases) 页面下载。数据经过多轮清洗——详见[关于页面](https://morningD.github.io/lang.csconf/#/about)。

## 功能特点

- **全局总览** — 饼图、趋势线和动态计数器，展示 CS 研究的语言分布全貌
- **会议探索** — 深入查看任一 CCF 推荐会议的逐年语言分布
- **会议对比** — 2–4 个会议的雷达图并排对比
- **趋势分析** — 按 CCF 分类（AI/DB/SE...）和等级（A/B/C/N）筛选，观察历年变化
- **CCF 等级变迁** — 追踪 6 版 CCF 推荐列表（2011–2026）中会议等级的变化
- **4 种界面语言** — 支持 English、中文、日本語、Deutsch

## 数据管道

| 步骤 | 说明 |
|------|------|
| 1. 解析会议列表 | 加载 `conferences_base.json`，应用 CCF PDF 提取的等级和分类 |
| 1b. 接收率 | 合并 7 个上游来源的接收率数据 |
| 2. 爬取 DBLP | 通过 SPARQL 接口获取论文作者姓名 |
| 2b. 爬取会议地点 | 从 DBLP HTML 抓取城市/国家信息 |
| 2c. 补充缺失 | 通过 DBLP Search API 补充 SPARQL 索引空缺 |
| 2d. OpenReview | 爬取 AI/ML 会议数据（NeurIPS、ICLR、ICML 等） |
| 3. 姓名分类 | 使用 fastText + 规则姓氏匹配组合预测语言 |
| 4. 生成统计 | 按会议、分类、等级、年份聚合 → JSON |

### 增量更新

默认不加 `--force` 即为增量模式，只处理缺失的会议-年份数据：

```bash
# 增量运行全管道
python -m pipeline.run_all

# 同步统计数据到网站
rsync -av --delete data/stats/ website/public/data/stats/
```

如需重新爬取某个会议（例如 DBLP 后续新增了论文）：

```bash
rm data/raw/authors/CVPR_*.json data/classified/authors/CVPR_*.json
python -m pipeline.run_all --conferences CVPR
rsync -av --delete data/stats/ website/public/data/stats/
```

### Affiliation 覆盖率审计

```bash
python3 scripts/audit_affiliation_coverage.py
```

该命令对已爬取输入保持只读：读取 CCF-B 会议元数据、原始作者文件和现有 affiliation 文件，然后以确定性方式写入 `data/stats/affiliation_coverage_audit.json`。它不发起网络请求、不消耗 OpenAlex key，也不会覆盖 affiliation 数据。报告会区分 OpenAlex 标题未匹配与已匹配但机构元数据缺失；非 OpenAlex 来源不会被归因给 OpenAlex；数据完整性例外会单独列出。若 DBLP 收录了但 affiliation 文件中没有对应记录的会议元数据条目，审计会将其排除在分母外，并计入 `summary.excluded_conference_metadata`。

对于 `openalex_match_gap`，必须先生成受保护的离线重试 manifest，不能直接进行宽范围重爬：

```bash
python3 scripts/openalex_batch_crawl.py \
  --audit-report data/stats/affiliation_coverage_audit.json \
  --targets-file data/stats/affiliation_retry_plans/pilot_targets.json \
  --dry-run \
  --plan-output data/stats/affiliation_retry_plans/pilot_plan.json
```

该 dry-run 不读取 API key、不发起网络请求；仅接受当前仍为 `source: "openalex"`、且 raw 论文数与 matched 数仍和审计快照一致的文件。非 OpenAlex 来源和审计漂移都会被拒绝。`openalex_metadata_gap` 不属于标题重试候选。即使 manifest 已审阅，也不构成覆盖授权：每个 `--force --retry-unmatched-only` 批次必须单独获得明确确认；批次须保留旧匹配项，且仅当 matched 和机构计数都不下降、至少一项提升时才可替换。

## 免责声明

**基于姓名的语言推断本身存在很大局限性。** 移民、婚姻、文化融合、改名等因素都使得姓名无法可靠地反映语言背景。本项目旨在提供有趣的可视化探索，并非严谨的社会语言学研究，无任何歧视意图。

## License / 许可证

[Apache-2.0](LICENSE)
