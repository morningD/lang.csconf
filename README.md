# 🗣️ lang.csconf

**What language does your conference speak?**

Visualizing the linguistic diversity of first authors across CCF-rated CS conferences (2016–2025).

🌐 **Live demo**: [morningD.github.io/lang.csconf](https://morningD.github.io/lang.csconf/)

> We analyzed 125,000+ papers so you don't have to. Names are terrible predictors of language. We did it anyway.

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
│   ├── step2_crawl_sparql.py         # Crawl DBLP via SPARQL for first authors
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

# Run full pipeline
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
| Build | Vite 6 |
| Framework | Vue 3 (Composition API + TypeScript) |
| Charts | Apache ECharts 5 (via vue-echarts) |
| i18n | vue-i18n 9 |
| CSS | UnoCSS |
| Pipeline | Python 3.11 + name2nat |
| Deploy | GitHub Pages + Actions |

## Disclaimer

**Name-based language inference is inherently imprecise.** Many factors — immigration, marriage, cultural mixing, adopted names — make names unreliable indicators of linguistic background. This project is meant as a fun, light-hearted visualization, not a rigorous sociolinguistic study. No discrimination intended.

## License

[Apache-2.0](LICENSE)
