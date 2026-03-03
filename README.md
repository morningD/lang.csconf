# 🗣️ lang.csconf

**What language does your conference speak?**

Visualizing the linguistic diversity of first authors across CCF-rated CS conferences (2010–2025).

🌐 **Live demo**: [morningD.github.io/lang.csconf](https://morningD.github.io/lang.csconf/)

[English](#features) | [中文](#简介)

> We analyzed 800,000+ papers so you don't have to. Names are terrible predictors of language. We did it anyway.

## Features

- **Global Overview** — Pie charts, trend lines, and animated counters showing the linguistic landscape of CS research
- **Conference Explorer** — Deep-dive into any CCF-rated conference with year-by-year language breakdowns
- **Compare Conferences** — Side-by-side radar charts for 2–4 conferences
- **Trends** — Filter by CCF category (AI/DB/SE...) and rank (A/B/C/N) to see how things change over time
- **CCF Classification** — Browse by rank (A/B/C/N) and category, inspired by [ccfddl](https://ccfddl.github.io)
- **4 Languages** — UI available in English, 中文, 日本語, Deutsch
- **Pixel Art Footer** — Rabbits, mushrooms, and weather animations (borrowed with love from [ModelGo](https://www.modelgo.li))

## Architecture

```
lang.csconf/
├── pipeline/          # Python: crawl DBLP + classify names → JSON stats
│   ├── step1_parse_conferences.py   # Parse CCF conference list
│   ├── step2_crawl_sparql.py        # Crawl DBLP via SPARQL for first authors
│   ├── step3_classify_names.py      # Predict language from names
│   ├── step4_generate_stats.py      # Aggregate statistics
│   └── run_all.py                   # Orchestrator
├── website/           # Vue 3 + Vite: static site consuming JSON stats
│   └── src/
│       ├── views/     # 5 pages: Home, Conference, Compare, Trends, About
│       ├── components/# ECharts wrappers, layout, PixelRobots animation
│       └── i18n/      # 4 locale files (en/zh/ja/de)
├── data/              # Generated data (committed to repo)
│   ├── raw/           # Crawled author data
│   ├── classified/    # Author data with language predictions
│   └── stats/         # Pre-computed JSON for website
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
| 1. Parse conferences | Clones [ccf-deadlines](https://github.com/ccfddl/ccf-deadlines), extracts conference metadata |
| 2. Crawl DBLP | Fetches first author names via DBLP SPARQL endpoint with rate limiting |
| 3. Classify names | Predicts nationality/language using [name2nat](https://github.com/Kyubyong/name2nat) |
| 4. Generate stats | Aggregates by conference, category, rank, year → JSON |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Build | Vite 7 |
| Framework | Vue 3 (Composition API + TypeScript) |
| Charts | Apache ECharts 6 (via vue-echarts) |
| i18n | vue-i18n 9 |
| CSS | UnoCSS |
| Pipeline | Python 3.12 + name2nat |
| Deploy | GitHub Pages + Actions |

## Disclaimer

**Name-based language inference is inherently imprecise.** Many factors — immigration, marriage, cultural mixing, adopted names — make names unreliable indicators of linguistic background. This project is meant as a fun, light-hearted visualization, not a rigorous sociolinguistic study. No discrimination intended.

---

## 简介

**你的会议说什么语言？**

可视化 CCF 推荐计算机学术会议（2010–2025）第一作者的语言多样性。

🌐 **在线演示**: [morningD.github.io/lang.csconf](https://morningD.github.io/lang.csconf/)

> 我们分析了 80 万+ 篇论文。基于姓名推断语言并不准确，但我们还是做了。

## 功能特点

- **全局总览** — 饼图、趋势线和动态计数器，展示 CS 研究的语言分布全貌
- **会议探索** — 深入查看任一 CCF 推荐会议的逐年语言分布
- **会议对比** — 2–4 个会议的雷达图并排对比
- **趋势分析** — 按 CCF 分类（AI/DB/SE...）和等级（A/B/C/N）筛选，观察历年变化
- **CCF 分类体系** — 按等级和类别浏览，灵感来自 [ccfddl](https://ccfddl.github.io)
- **4 种界面语言** — 支持 English、中文、日本語、Deutsch
- **像素风页脚** — 兔子、蘑菇和天气动画（来自 [ModelGo](https://www.modelgo.li)）

## 数据管道

| 步骤 | 说明 |
|------|------|
| 1. 解析会议列表 | 从 [ccf-deadlines](https://github.com/ccfddl/ccf-deadlines) 提取会议元数据 |
| 2. 爬取 DBLP | 通过 SPARQL 接口获取每篇论文的第一作者姓名 |
| 3. 姓名分类 | 使用 [name2nat](https://github.com/Kyubyong/name2nat) 预测国籍/语言 |
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

## 免责声明

**基于姓名的语言推断本身存在很大局限性。** 移民、婚姻、文化融合、改名等因素都使得姓名无法可靠地反映语言背景。本项目旨在提供有趣的可视化探索，并非严谨的社会语言学研究，无任何歧视意图。

## 许可证

[Apache-2.0](LICENSE)
