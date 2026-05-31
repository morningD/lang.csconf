<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { Meta, GlobalSummary, CategoryStats, RankStats, CCFCategory, CCFRank, AffiliationTrends, AffiliationTrendSlice } from '@/types'

const { t } = useI18n()
const { fetchMeta, fetchGlobalSummary, fetchCategory, fetchRank, fetchAffiliationTrends } = useDataFetch()

const meta = ref<Meta | null>(null)
const loading = ref(true)
const activeCategory = ref<CCFCategory | 'ALL'>('ALL')
const activeRank = ref<CCFRank | 'ALL'>('ALL')

const globalData = ref<GlobalSummary | null>(null)
const categoryData = ref<CategoryStats | null>(null)
const rankData = ref<RankStats | null>(null)
const affilTrends = ref<AffiliationTrends | null>(null)

const categories: (CCFCategory | 'ALL')[] = ['ALL', 'AI', 'DB', 'NW', 'SE', 'CG', 'CT', 'HI', 'SC', 'DS', 'MX']
const categoryNames: Record<string, string> = {
  AI: 'Artificial Intelligence',
  DB: 'Database / Data Mining / Information Retrieval',
  NW: 'Computer Networking',
  SE: 'Software Engineering / System Software / PL',
  CG: 'Computer Graphics & Multimedia',
  CT: 'Theory of Computation',
  HI: 'Human-Computer Interaction & Ubiquittic Computing',
  SC: 'Network & Information Security',
  DS: 'Computer Architecture / Parallel & Distributed Computing / Storage',
  MX: 'Interdisciplinary & Emerging',
}
const ranks: (CCFRank | 'ALL')[] = ['ALL', 'A', 'B', 'C', 'N']

onMounted(async () => {
  try {
    const [m, g, a] = await Promise.all([fetchMeta(), fetchGlobalSummary(), fetchAffiliationTrends()])
    meta.value = m
    globalData.value = g
    affilTrends.value = a
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

watch(activeCategory, async (cat) => {
  if (cat !== 'ALL') {
    try {
      categoryData.value = await fetchCategory(cat)
    } catch { categoryData.value = null }
  } else {
    categoryData.value = null
  }
})

watch(activeRank, async (rank) => {
  if (rank !== 'ALL') {
    try {
      rankData.value = await fetchRank(rank)
    } catch { rankData.value = null }
  } else {
    rankData.value = null
  }
})

// Active data source for language trends
const activeByYear = computed(() => {
  if (categoryData.value) return categoryData.value.by_year
  if (rankData.value) return rankData.value.by_year
  return globalData.value?.by_year || {}
})

const trendMode = ref<'absolute' | 'ratio' | 'cumulative'>('ratio')

const chartOption = computed(() => {
  if (!meta.value || !Object.keys(activeByYear.value).length) return {}
  const byYear = activeByYear.value
  const years = Object.keys(byYear).sort()
  const colors = meta.value.language_colors
  const mode = trendMode.value
  const showPct = mode === 'ratio'

  const totals: Record<string, number> = {}
  for (const yearData of Object.values(byYear)) {
    for (const [lang, count] of Object.entries(yearData)) {
      totals[lang] = (totals[lang] || 0) + count
    }
  }
  const topLangs = Object.entries(totals).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([l]) => l)

  return {
    tooltip: {
      trigger: 'axis',
      valueFormatter: showPct ? (v: number) => v + '%' : undefined,
    },
    legend: { data: topLangs, textStyle: { color: '#aaa' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: years, boundaryGap: false, axisLabel: { color: '#aaa' }, axisLine: { lineStyle: { color: '#444' } } },
    yAxis: {
      type: 'value',
      max: showPct ? 100 : undefined,
      axisLabel: { color: '#aaa', formatter: showPct ? '{value}%' : '{value}' },
      splitLine: { lineStyle: { color: '#333' } },
    },
    series: topLangs.map(lang => {
      const cumSum: number[] = []
      return {
        name: lang,
        type: 'line',
        stack: 'total',
        areaStyle: { opacity: 0.6 },
        emphasis: { focus: 'series' },
        smooth: true,
        data: years.map((y, i) => {
          const val = byYear[y]?.[lang] || 0
          if (mode === 'ratio') {
            const yearTotal = Object.values(byYear[y] || {}).reduce((a: number, b: unknown) => a + (b as number), 0)
            return yearTotal > 0 ? Math.round(val / yearTotal * 1000) / 10 : 0
          }
          if (mode === 'cumulative') {
            const prev = i > 0 ? cumSum[i - 1]! : 0
            cumSum.push(prev + val)
            return cumSum[i]
          }
          return val
        }),
        itemStyle: { color: colors[lang] || '#95a5a6' },
      }
    }),
  }
})

// --- Affiliation trends ---
const INST_ABBREV: Record<string, string> = {
  // --- US Universities ---
  'Carnegie Mellon University': 'CMU',
  'Massachusetts Institute of Technology': 'MIT',
  'Stanford University': 'Stanford',
  'University of California, Berkeley': 'UCB',
  'University of California, Los Angeles': 'UCLA',
  'University of California, San Diego': 'UCSD',
  'University of California, Santa Barbara': 'UCSB',
  'University of California, Irvine': 'UCI',
  'University of California, Davis': 'UCD',
  'University of California, Santa Cruz': 'UCSC',
  'University of California, Riverside': 'UCR',
  'University of Illinois at Urbana-Champaign': 'UIUC',
  'Georgia Institute of Technology': 'GT',
  'University of Texas at Austin': 'UT Austin',
  'University of Massachusetts Amherst': 'UMass',
  'University of Maryland, College Park': 'UMD',
  'University of Pennsylvania': 'UPenn',
  'California Institute of Technology': 'Caltech',
  'Princeton University': 'Princeton',
  'Cornell University': 'Cornell',
  'Columbia University': 'Columbia',
  'University of Washington': 'UW',
  'University of Wisconsin-Madison': 'UW-Madison',
  'Purdue University': 'Purdue',
  'University of Southern California': 'USC',
  'University of Michigan': 'UMich',
  'Ohio State University': 'OSU',
  'Pennsylvania State University': 'Penn State',
  'New York University': 'NYU',
  'University of Chicago': 'UChicago',
  'Johns Hopkins University': 'JHU',
  'Northwestern University': 'NU',
  'University of Minnesota': 'UMN',
  'University of Pittsburgh': 'Pitt',
  'Rutgers University': 'Rutgers',
  'Stony Brook University': 'Stony Brook',
  'Dartmouth College': 'Dartmouth',
  'Texas A&M University': 'TAMU',
  'Rensselaer Polytechnic Institute': 'RPI',
  'Virginia Tech': 'VT',
  'University of North Carolina at Chapel Hill': 'UNC',
  // --- Chinese Universities ---
  'Tsinghua University': 'THU',
  'Peking University': 'PKU',
  'Zhejiang University': 'ZJU',
  'Shanghai Jiao Tong University': 'SJTU',
  'University of Science and Technology of China': 'USTC',
  'Chinese Academy of Sciences': 'CAS',
  'Chinese University of Hong Kong': 'CUHK',
  'University of Hong Kong': 'HKU',
  'Hong Kong University of Science and Technology': 'HKUST',
  'Hong Kong Polytechnic University': 'PolyU',
  'Hong Kong Baptist University': 'HKBU',
  'City University of Hong Kong': 'CityU',
  'Fudan University': 'Fudan',
  'Nanjing University': 'NJU',
  'Harbin Institute of Technology': 'HIT',
  'University of Electronic Science and Technology of China': 'UESTC',
  'Beijing University of Posts and Telecommunications': 'BUPT',
  'Huazhong University of Science and Technology': 'HUST',
  'Renmin University of China': 'RUC',
  'University of Chinese Academy of Sciences': 'UCAS',
  'Beihang University': 'BUAA',
  "Xi'an Jiaotong University": 'XJTU',
  'Nanjing University of Aeronautics and Astronautics': 'NUAA',
  'Northwestern Polytechnical University': 'NWPU',
  'National University of Defense Technology': 'NUDT',
  'Sun Yat-sen University': 'SYSU',
  'Wuhan University': 'WHU',
  'Tongji University': 'Tongji',
  'Xiamen University': 'XMU',
  'South China University of Technology': 'SCUT',
  'Beijing Institute of Technology': 'BIT',
  'Central South University': 'CSU',
  'Dalian University of Technology': 'DUT',
  'Southeast University': 'SEU',
  'Tianjin University': 'TJU',
  'Shandong University': 'SDU',
  'University of Macau': 'UM',
  'National Cheng Kung University': 'NCKU',
  'National Chiao Tung University': 'NYCU',
  'National Yang Ming Chiao Tung University': 'NYCU',
  'National Taiwan University': 'NTU',
  // --- UK/Europe ---
  'University of Oxford': 'Oxford',
  'University of Cambridge': 'Cambridge',
  'University College London': 'UCL',
  'Imperial College London': 'Imperial',
  'University of Edinburgh': 'Edinburgh',
  'ETH Zurich': 'ETH',
  'École Polytechnique Fédérale de Lausanne': 'EPFL',
  'Technical University of Munich': 'TUM',
  'TU Munich': 'TUM',
  'LMU Munich': 'LMU',
  'Ludwig Maximilian University of Munich': 'LMU',
  'Humboldt University of Berlin': 'HU Berlin',
  'Friedrich-Alexander-Universität Erlangen-Nürnberg': 'FAU',
  'University of Bonn': 'U Bonn',
  'University of Freiburg': 'U Freiburg',
  'University of Tübingen': 'U Tübingen',
  'Karlsruhe Institute of Technology': 'KIT',
  'Pierre and Marie Curie University': 'UPMC',
  'Polytechnic University of Milan': 'PoliMi',
  'Politecnico di Milano': 'PoliMi',
  'Sapienza University of Rome': 'Sapienza',
  'KTH Royal Institute of Technology': 'KTH',
  'Universitat Pompeu Fabra': 'UPF',
  'German Aerospace Center (DLR)': 'DLR',
  // --- Canada ---
  'University of Toronto': 'UofT',
  'University of British Columbia': 'UBC',
  'University of Waterloo': 'Waterloo',
  'Université de Montréal': 'UdeM',
  // --- Asia-Pacific ---
  'National University of Singapore': 'NUS',
  'Nanyang Technological University': 'NTU',
  'Pohang University of Science and Technology': 'POSTECH',
  'Seoul National University': 'SNU',
  'Korea University': 'KU',
  'Yonsei University': 'Yonsei',
  'KAIST': 'KAIST',
  'University of New South Wales': 'UNSW',
  'University of Tokyo': 'UTokyo',
  'Tokyo Institute of Technology': 'Tokyo Tech',
  'Kyoto University': 'Kyoto',
  'Osaka University': 'Osaka',
  'Tel Aviv University': 'TAU',
  'King Abdullah University of Science and Technology': 'KAUST',
  'Mohamed bin Zayed University of Artificial Intelligence': 'MBZUAI',
  'Indian Institute of Technology Bombay': 'IITB',
  'Indian Institute of Science': 'IISc',
  // --- Companies/Institutes ---
  'Google': 'Google',
  'Google DeepMind': 'DeepMind',
  'Microsoft Research': 'MSR',
  'Nokia Bell Labs': 'Bell Labs',
  'Max Planck Institute for Informatics': 'MPI',
  'Max Planck Institute for Intelligent Systems': 'MPI-IS',
  'Shanghai AI Lab': 'Shanghai AI Lab',
  'Istituto Italiano di Tecnologia': 'IIT',
  'Chongqing University': 'CQU',
  'Alibaba': 'Alibaba',
  'HKUST': 'HKUST',
  'Helmholtz Center for Information Security': 'CISPA',
  'Northeastern University': 'NEU',
  'Purdue University West Lafayette': 'Purdue',
  'Ruhr University Bochum': 'RUB',
}

const SKIP_WORDS = new Set(['of', 'at', 'the', 'and', 'for', 'in', 'de', 'la', 'le', 'du', 'di', 'da', 'del'])
const abbreviateInst = (name: string) => {
  if (INST_ABBREV[name]) return INST_ABBREV[name]
  // Fallback: take uppercase initials, skip common particles
  const words = name.split(/[\s,]+/).filter(w => w && !SKIP_WORDS.has(w.toLowerCase()))
  const initials = words.map(w => w[0]?.toUpperCase()).filter(Boolean).join('')
  return initials || name
}

const COUNTRY_OVERRIDES: Record<string, string> = { TW: 'CN' }
const countryFlag = (code: string) => {
  const c = COUNTRY_OVERRIDES[code] || code
  return String.fromCodePoint(...[...c.toUpperCase()].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65))
}

// Affiliation rank filter: 'ALL' or 'A'
const affilRank = ref<'ALL' | 'A'>('A')

// Active affiliation slice based on category + rank filters
const activeAffilSlice = computed<AffiliationTrendSlice | null>(() => {
  if (!affilTrends.value) return null
  if (affilRank.value === 'A') {
    return affilTrends.value.by_rank?.A ?? null
  }
  if (activeCategory.value !== 'ALL') {
    return affilTrends.value.by_category?.[activeCategory.value] ?? null
  }
  return affilTrends.value.global ?? null
})

const affilMode = ref<'absolute' | 'ratio' | 'cumulative'>('ratio')

// 10 hand-picked colors: max visual distinction, bright enough for dark bg
const PALETTE = [
  '#e06c75', // red
  '#61afef', // blue
  '#98c379', // green
  '#e5c07b', // yellow
  '#c678dd', // purple
  '#56b6c2', // cyan
  '#d19a66', // orange
  '#be5046', // dark red
  '#7ec8e3', // sky blue
  '#c3a6ff', // lavender
]

// Assign colors to a set of institution names deterministically:
// sort names alphabetically, assign palette by position, return map
function assignColors(names: string[]): Map<string, string> {
  const sorted = [...names].sort()
  const map = new Map<string, string>()
  sorted.forEach((name, i) => map.set(name, PALETTE[i % PALETTE.length]!))
  return map
}

const affilChartOption = computed(() => {
  const slice = activeAffilSlice.value
  if (!slice || !slice.years.length) return {}

  const years = slice.years
  const institutions = slice.institutions
  const mode = affilMode.value

  // Find top 10 institutions by total count across all years
  const totals: [string, number][] = []
  for (const [name, data] of Object.entries(institutions)) {
    const total = Object.values(data.by_year).reduce((a, b) => a + b, 0)
    totals.push([name, total])
  }
  totals.sort((a, b) => b[1] - a[1])
  const top10 = totals.slice(0, 10).map(([name]) => name)

  // Assign stable colors to this set of institutions
  const colorMap = assignColors(top10)

  const showPct = mode === 'ratio'

  // Helper to compute chart value for a given institution/year
  const chartVal = (name: string, y: string, idx: number) => {
    const val = institutions[name]?.by_year?.[y] || 0
    if (mode === 'ratio') {
      const totalYear = slice.total_by_year[y] || 1
      return totalYear > 0 ? Math.round(val / totalYear * 10000) / 100 : 0
    }
    if (mode === 'cumulative') {
      let sum = 0
      for (let j = 0; j <= idx; j++) {
        sum += institutions[name]?.by_year?.[years[j]!] || 0
      }
      return sum
    }
    return val
  }

  // Sort top10 by last-year value DESC; tiebreak by previous year DESC
  const lastY = years[years.length - 1]!
  const prevY = years.length >= 2 ? years[years.length - 2]! : lastY
  top10.sort((a, b) => {
    const va = chartVal(a, lastY, years.length - 1)
    const vb = chartVal(b, lastY, years.length - 1)
    if (va !== vb) return vb - va
    return chartVal(b, prevY, years.length - 2) - chartVal(a, prevY, years.length - 2)
  })

  // Pre-compute endLabel.offset dy to prevent overlap (data NOT modified)
  const lastVals = top10.map(name => chartVal(name, lastY, years.length - 1))
  // Full data range across ALL years (ECharts Y axis uses full range, not just last year)
  const allVals: number[] = []
  for (const name of top10) {
    for (let idx = 0; idx < years.length; idx++) {
      allVals.push(chartVal(name, years[idx]!, idx))
    }
  }
  const dataMax = Math.max(...allVals, 1)
  // Estimate ECharts' yMax using nice-number rounding
  const niceSteps = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
  let yMax = dataMax
  for (const step of niceSteps) {
    const intervals = Math.ceil(dataMax / step)
    if (intervals >= 3 && intervals <= 7) {
      yMax = step * intervals
      break
    }
  }
  const gridTop = 10
  const gridBottom = Math.round(450 * 0.03)
  const gridHeight = 450 - gridTop - gridBottom
  const toPixelY = (v: number) => gridTop + gridHeight * (1 - v / yMax)
  const minLabelGap = 18

  const labelPixelY = lastVals.map(toPixelY)
  const labelDy: number[] = new Array(top10.length).fill(0)
  for (let i = 1; i < top10.length; i++) {
    const prevEffectiveY = labelPixelY[i - 1]! + labelDy[i - 1]!
    if (labelPixelY[i]! - prevEffectiveY < minLabelGap) {
      labelDy[i] = prevEffectiveY + minLabelGap - labelPixelY[i]!
    }
  }

  return {
    tooltip: {
      trigger: 'axis',
      valueFormatter: showPct ? (v: number) => `${Math.round(v * 100) / 100}%` : undefined,
      formatter: (params: any) => {
        if (!Array.isArray(params)) return ''
        const year = params[0]?.axisValue ?? ''
        const lines = params
          .filter((p: any) => p.value != null)
          .sort((a: any, b: any) => (b.value ?? 0) - (a.value ?? 0))
          .map((p: any) => {
            const name = p.seriesName as string
            const flag = institutions[name]?.country ? countryFlag(institutions[name].country) : ''
            const val = showPct ? `${Math.round(p.value * 100) / 100}%` : p.value
            const flagHtml = flag ? `<span style="font-size:1.5em;vertical-align:middle;margin-left:4px">${flag}</span>` : ''
            return `${p.marker} ${name}${flagHtml}  <b>${val}</b>`
          })
        return `<div style="font-weight:600;margin-bottom:4px">${year}</div>${lines.join('<br>')}`
      },
    },
    grid: { left: '3%', right: 140, bottom: '3%', top: 10, containLabel: false },
    xAxis: {
      type: 'category',
      data: years,
      boundaryGap: false,
      axisLabel: { color: '#aaa' },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#aaa', formatter: showPct ? '{value}%' : '{value}' },
      splitLine: { lineStyle: { color: '#333' } },
    },
    series: top10.map((name, i) => {
      const color = colorMap.get(name)!
      const flag = institutions[name]?.country ? countryFlag(institutions[name].country) : ''
      const label = flag ? `${abbreviateInst(name)} ${flag}` : abbreviateInst(name)
      return {
        name,
        type: 'line',
        emphasis: { focus: 'series' },
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        data: years.map((y, idx) => chartVal(name, y, idx)),
        itemStyle: { color },
        lineStyle: { width: 2 },
        endLabel: {
          show: true,
          formatter: () => label,
          color,
          fontSize: 11,
          offset: [4, labelDy[i]],
        },
      }
    }),
  }
})

// Coverage info for affiliation data
const affilCoverage = computed(() => {
  const slice = activeAffilSlice.value
  if (!slice) return null
  const totalCovered = Object.values(slice.coverage_by_year).reduce((a, c) => a + c.covered, 0)
  const totalPapers = Object.values(slice.coverage_by_year).reduce((a, c) => a + c.total, 0)
  const confYears = new Set<string>()
  for (const cfs of Object.values(slice.conferences_by_year || {})) {
    for (const c of cfs) confYears.add(c)
  }
  return {
    confYears: Object.keys(slice.coverage_by_year).length,
    coveragePct: totalPapers > 0 ? (totalCovered / totalPapers * 100).toFixed(1) : '0',
    conferences: confYears.size,
    years: slice.years.length,
  }
})

// Which categories have affiliation data?
const affilCategories = computed(() => {
  if (!affilTrends.value?.by_category) return []
  return Object.keys(affilTrends.value.by_category)
})
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <h1 class="text-3xl font-bold text-white mb-2">{{ t('trends.title') }}</h1>
      <p class="text-gray-400 mb-8">{{ t('trends.subtitle') }}</p>

      <!-- Filters -->
      <div class="flex flex-col sm:flex-row gap-4 mb-8">
        <div>
          <label class="text-sm text-gray-500 block mb-1">{{ t('trends.filter_by_category') }}</label>
          <div class="flex gap-1 flex-wrap">
            <button
              v-for="cat in categories"
              :key="cat"
              @click="activeCategory = cat; if (cat !== 'ALL') activeRank = 'ALL'"
              class="px-3 py-1 rounded-full text-xs font-medium transition-all relative group/cat"
              :class="activeCategory === cat
                ? 'bg-gray-600 text-white'
                : 'bg-gray-800 text-gray-500 hover:bg-gray-700'"
            >
              {{ cat }}
              <span
                v-if="categoryNames[cat]"
                class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 text-xs text-white bg-gray-900 rounded shadow-lg whitespace-nowrap opacity-0 pointer-events-none group-hover/cat:opacity-100 transition-opacity z-10"
              >
                {{ categoryNames[cat] }}
              </span>
            </button>
          </div>
        </div>
        <div>
          <label class="text-sm text-gray-500 block mb-1">{{ t('trends.filter_by_rank') }}</label>
          <div class="flex gap-1">
            <button
              v-for="rank in ranks"
              :key="rank"
              @click="activeRank = rank; if (rank !== 'ALL') activeCategory = 'ALL'"
              class="px-3 py-1 rounded-full text-xs font-medium transition-all"
              :class="activeRank === rank ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
            >
              {{ rank === 'ALL' ? 'ALL' : `CCF ${rank}` }}
            </button>
          </div>
        </div>
      </div>

      <!-- Chart -->
      <div v-if="!loading">
        <div class="card p-6 bg-gray-800/50 border-gray-700/50">
          <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-4">
            <h3 class="text-lg font-semibold text-white">{{ t('trends.year_over_year') }}</h3>
            <div class="inline-flex rounded-lg overflow-hidden border border-gray-600 shrink-0">
              <button
                @click="trendMode = 'absolute'"
                class="px-3 py-1 text-xs font-medium transition-colors"
                :class="trendMode === 'absolute' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
              >
                Count
              </button>
              <button
                @click="trendMode = 'ratio'"
                class="px-3 py-1 text-xs font-medium transition-colors"
                :class="trendMode === 'ratio' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
              >
                Ratio %
              </button>
              <button
                @click="trendMode = 'cumulative'"
                class="px-3 py-1 text-xs font-medium transition-colors"
                :class="trendMode === 'cumulative' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
              >
                Cumulative
              </button>
            </div>
          </div>
          <v-chart :option="chartOption" style="height: 450px" autoresize />
          <p class="text-xs text-gray-500 mt-2 text-right">{{ t('home.data_lag_note', { year: meta?.year_range?.[1] ?? 2025 }) }}</p>
        </div>

        <!-- Affiliation Trends -->
        <div v-if="affilTrends" class="card p-6 bg-gray-800/50 border-gray-700/50 mt-8">
          <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-4">
            <h3 class="text-lg font-semibold text-white">{{ t('trends.affiliation_title') }}</h3>
            <div class="flex gap-2 items-center flex-wrap">
              <!-- Category filter for affiliations (only categories with data) -->
              <div class="inline-flex rounded-lg overflow-hidden border border-gray-600 shrink-0">
                <button
                  v-for="ac in ['ALL', ...affilCategories]"
                  :key="ac"
                  @click="activeCategory = ac as any; if (ac !== 'ALL') activeRank = 'ALL'; affilRank = 'ALL'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="activeCategory === ac && affilRank === 'ALL' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  {{ ac === 'ALL' ? 'ALL' : ac }}
                </button>
              </div>
              <!-- CCF-A toggle -->
              <div class="inline-flex rounded-lg overflow-hidden border border-gray-600 shrink-0">
                <button
                  @click="affilRank = 'ALL'; activeCategory = 'ALL'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="affilRank === 'ALL' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  {{ t('trends.affiliation_all') }}
                </button>
                <button
                  @click="affilRank = 'A'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="affilRank === 'A' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  CCF-A
                </button>
              </div>
              <!-- Count / Ratio / Cumulative toggle -->
              <div class="inline-flex rounded-lg overflow-hidden border border-gray-600 shrink-0">
                <button
                  @click="affilMode = 'absolute'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="affilMode === 'absolute' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  Count
                </button>
                <button
                  @click="affilMode = 'ratio'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="affilMode === 'ratio' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  Ratio %
                </button>
                <button
                  @click="affilMode = 'cumulative'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="affilMode === 'cumulative' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  Cumulative
                </button>
              </div>
            </div>
          </div>

          <v-chart v-if="activeAffilSlice" :option="affilChartOption" style="height: 450px" autoresize />
          <div v-else class="text-center py-12 text-gray-500">
            {{ t('trends.affiliation_no_data') }}
          </div>

          <div v-if="affilCoverage" class="flex justify-between items-start mt-2">
            <span class="text-xs text-gray-500">{{ t('trends.affiliation_coverage', {
              conferences: affilCoverage.conferences,
              years: affilCoverage.years,
              pct: affilCoverage.coveragePct
            }) }}</span>
            <span class="text-xs text-gray-500">{{ t('trends.affiliation_lag_note', { year: meta?.year_range?.[1] ?? 2026 }) }}</span>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-20">
        <div class="text-4xl mb-4 animate-bounce">🗣️</div>
        <p class="text-gray-400">{{ t('home.loading') }}</p>
      </div>
    </div>
  </div>
</template>
