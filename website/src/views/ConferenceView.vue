<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { ConferenceDetail, Meta } from '@/types'

const route = useRoute()
const { t } = useI18n()
const { fetchConference, fetchMeta } = useDataFetch()

const baseUrl = import.meta.env.BASE_URL
const conference = ref<ConferenceDetail | null>(null)
const meta = ref<Meta | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

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

const confId = computed(() => route.params.id as string)

const dblpLinks = computed(() => {
  if (!conference.value) return []
  const dblp = conference.value.dblp
  const keys = Array.isArray(dblp) ? dblp : dblp ? [dblp] : []
  return keys.map(k => ({ key: k, url: `https://dblp.org/db/conf/${k}/` }))
})
const areaMode = ref<'absolute' | 'ratio' | 'cumulative'>('absolute')

onMounted(async () => {
  try {
    const [c, m] = await Promise.all([
      fetchConference(confId.value),
      fetchMeta(),
    ])
    conference.value = c
    meta.value = m
  } catch (e) {
    error.value = `Conference "${confId.value}" not found`
  } finally {
    loading.value = false
  }
})

function getRankColor(rank: string) {
  const colors: Record<string, string> = { A: '#e74c3c', B: '#f39c12', C: '#3498db', N: '#95a5a6' }
  return colors[rank] || '#95a5a6'
}

const langGreetings: Record<string, string> = {
  Chinese: 'Nihao',
  English: 'Hello',
  Korean: 'Annyeong',
  German: 'Hallo',
  French: 'Bonjour',
  Indian: 'Namaste',
  Spanish: 'Hola',
  Italian: 'Ciao',
  Russian: 'Privet',
  Portuguese: 'Olá',
  Persian: 'Salaam',
  Arabic: 'Marhaba',
  Vietnamese: 'Xin chào',
  Turkish: 'Merhaba',
  Dutch: 'Hallo',
  Other: 'Hi',
}

const verdictGreeting = computed(() => {
  if (!conference.value) return null
  const c = conference.value
  const latestYear = String(c.years[c.years.length - 1])
  const latestData = c.by_year[latestYear] || {}
  const sorted = Object.entries(latestData).sort((a, b) => b[1] - a[1])
  if (sorted.length === 0) return null
  const topLang = sorted[0]![0]
  const total = Object.values(latestData).reduce((a: number, b: number) => a + b, 0)
  const pct = Math.round(sorted[0]![1] / total * 100)
  // YoY trend for dominant language (1 decimal precision)
  let trend: number | null = null
  let prevYear: string | null = null
  if (c.years.length >= 2) {
    prevYear = String(c.years[c.years.length - 2])
    const prevData = c.by_year[prevYear] || {}
    const prevTotal = Object.values(prevData).reduce((a: number, b: number) => a + b, 0)
    if (prevTotal > 0) {
      const latestPct1 = sorted[0]![1] / total * 100
      const prevPct1 = (prevData[topLang] || 0) / prevTotal * 100
      trend = Math.round((latestPct1 - prevPct1) * 10) / 10
    }
  }

  return {
    greeting: langGreetings[topLang] || topLang,
    lang: topLang,
    pct,
    year: latestYear,
    trend,
    prevYear,
    secondLang: sorted.length > 1 ? sorted[1]![0] : null,
    secondGreeting: sorted.length > 1 ? (langGreetings[sorted[1]![0]] || sorted[1]![0]) : null,
    secondPct: sorted.length > 1 ? Math.round(sorted[1]![1] / total * 100) : 0,
  }
})

// Compute rank change markers for the chart
const rankChangeMarkers = computed(() => {
  if (!conference.value?.rank_history) return []
  const rh = conference.value.rank_history
  const versions = ['2011', '2012', '2015', '2019', '2022', '2026']
  const markers: { year: number; from: string; to: string }[] = []

  for (let i = 1; i < versions.length; i++) {
    const prev = rh[versions[i - 1]!]
    const curr = rh[versions[i]!]
    if (prev && curr && prev !== curr) {
      markers.push({ year: parseInt(versions[i]!), from: prev, to: curr })
    } else if (!prev && curr) {
      markers.push({ year: parseInt(versions[i]!), from: '—', to: curr })
    }
  }
  return markers
})

// Stacked area chart: language distribution over years
const hasVirtualYears = computed(() => {
  if (!conference.value) return false
  const venues = conference.value.venues || {}
  return Object.values(venues).some((v: any) =>
    v?.city === 'Virtual' || /Virtual|Online/i.test(v?.country || '')
  )
})

const areaOption = computed(() => {
  if (!conference.value || !meta.value) return {}
  const c = conference.value
  const years = c.years.map(String)
  const colors = meta.value.language_colors
  const venues = c.venues || {}

  // Get top languages for this conference
  const topLangs = Object.entries(c.total)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([lang]) => lang)

  const mode = areaMode.value
  const showPct = mode === 'ratio'

  // Build rank change lookup for x-axis labels
  const rankOrder: Record<string, number> = { A: 3, B: 2, C: 1 }
  const rankChangeByYear: Record<string, { from: string; to: string; isUpgrade: boolean }> = {}
  for (const m of rankChangeMarkers.value) {
    if (years.includes(String(m.year))) {
      rankChangeByYear[String(m.year)] = {
        from: m.from,
        to: m.to,
        isUpgrade: (rankOrder[m.to] || 0) > (rankOrder[m.from] || 0),
      }
    }
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const year = params[0].axisValue
        const lines = params
          .filter((p: any) => p.value != null && p.value !== 0)
          .map((p: any) => {
            const val = showPct ? p.value + '%' : p.value
            return `${p.marker} ${p.seriesName}: <b>${val}</b>`
          })
        // Always show actual paper count as total
        const yearTotal = Object.values(c.by_year[year] || {}).reduce((a: number, b: number) => a + b, 0)
        lines.push(`<b>Total: ${yearTotal} papers</b>`)
        // Show venue if available
        const venue = venues[year]
        if (venue?.city) {
          lines.push(`📍 ${venue.city}, ${venue.country}`)
        }
        return `<b>${year}</b><br>` + lines.join('<br>')
      },
    },
    legend: { data: topLangs, textStyle: { color: '#aaa' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: {
      type: 'category',
      data: years,
      boundaryGap: false,
      axisLabel: {
        interval: (index: number) => {
          const isMobile = window.innerWidth < 640
          if (!isMobile) return true
          // On mobile, show every 2nd or 3rd label depending on data density
          const step = years.length > 12 ? 2 : 1
          return index % (step + 1) === 0
        },
        rotate: window.innerWidth < 640 ? 45 : 0,
        formatter: (year: string) => {
          const venue = venues[year]
          if (venue?.country || venue?.city) {
            const isVirtual = venue.city === 'Virtual' || /Virtual|Online/i.test(venue.country || '')
            let label = (venue.country || '')
              .replace(/\s*\(Virtual.*?\)/gi, '')
              .replace(/\s*\(Online\)/gi, '')
              .replace(/\s*\(hybrid\)/gi, '')
            if (!label || label === 'None') label = isVirtual ? '*' : ''
            else if (isVirtual) label += '*'
            if (label) return `{year|${year}}\n{country|${label}}`
          }
          return `{year|${year}}`
        },
        rich: {
          year: { color: '#bbb', fontSize: window.innerWidth < 640 ? 10 : 12, lineHeight: window.innerWidth < 640 ? 14 : 16 },
          country: { color: '#666', fontSize: window.innerWidth < 640 ? 8 : 10, lineHeight: window.innerWidth < 640 ? 12 : 14 },
        },
      },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#aaa', formatter: showPct ? '{value}%' : '{value}' },
      splitLine: { lineStyle: { color: '#333' } },
    },
    series: [
      ...topLangs.map((lang) => {
        const cumSum: number[] = []
        return {
          name: lang,
          type: 'line' as const,
          stack: 'total',
          areaStyle: { opacity: 0.6 },
          emphasis: { focus: 'series' },
          smooth: true,
          data: years.map((y, i) => {
            const val = c.by_year[y]?.[lang] || 0
            if (mode === 'ratio') {
              const yearTotal = Object.values(c.by_year[y] || {}).reduce((a: number, b: number) => a + b, 0)
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
      // Custom series to draw vertical dashed lines at CCF rank change years
      ...(Object.keys(rankChangeByYear).length > 0 ? [{
        type: 'custom' as const,
        name: '',
        silent: true,
        z: 10,
        tooltip: { show: false },
        renderItem: (params: any, api: any) => {
          const x = api.coord([api.value(0), 0])[0]
          const isUpgrade = api.value(1) === 1
          const color = isUpgrade ? '#22c55e' : '#ef4444'
          const label = api.value(2) as string
          const top = params.coordSys.y
          const bottom = params.coordSys.y + params.coordSys.height
          return {
            type: 'group' as const,
            children: [
              {
                type: 'line' as const,
                shape: { x1: x, y1: top, x2: x, y2: bottom },
                style: { stroke: color, lineDash: [4, 4], lineWidth: 1.5 },
              },
              {
                type: 'text' as const,
                x, y: top - 4,
                style: {
                  text: label,
                  fill: color,
                  fontSize: 10,
                  fontWeight: 'bold',
                  align: 'center' as const,
                  verticalAlign: 'bottom' as const,
                  backgroundColor: 'rgba(0,0,0,0.7)',
                  padding: [2, 4],
                  borderRadius: 2,
                },
              },
            ],
          }
        },
        encode: { x: 0 },
        data: Object.entries(rankChangeByYear).map(([year, rc]) => [
          years.indexOf(year),
          rc.isUpgrade ? 1 : 0,
          `CCF ${rc.from}→${rc.to}`,
        ]),
      }] : []),
    ],
  }
})

const totalPapers = computed(() => {
  if (!conference.value) return 0
  return Object.values(conference.value.total).reduce((a, b) => a + b, 0)
})

const latestAcceptRate = computed(() => {
  if (!conference.value?.accept_rates?.length) return null
  const entry = conference.value.accept_rates[0]!
  const rate = Math.round(entry.accepted / entry.submitted * 1000) / 10
  let trend: number | null = null
  if (conference.value.accept_rates.length >= 2) {
    const prev = conference.value.accept_rates[1]!
    const prevRate = Math.round(prev.accepted / prev.submitted * 1000) / 10
    trend = Math.round((rate - prevRate) * 10) / 10
  }
  return { year: entry.year, rate, trend }
})

const showAcceptRateChart = ref(false)

const acceptRateChartOption = computed(() => {
  if (!conference.value?.accept_rates?.length) return {}
  const entries = [...conference.value.accept_rates].sort((a, b) => a.year - b.year)
  const years = entries.map(e => String(e.year))
  const rates = entries.map(e => Math.round(e.accepted / e.submitted * 1000) / 10)

  return {
    grid: { left: 36, right: 12, top: 8, bottom: 24 },
    xAxis: {
      type: 'category',
      data: years,
      axisLabel: { color: '#aaa', fontSize: 10 },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#aaa', fontSize: 10, formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#333' } },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        const entry = entries[p.dataIndex]!
        return `<b>${p.axisValue}</b><br>Rate: ${p.value}%<br>${entry.accepted} / ${entry.submitted}`
      },
    },
    series: [{
      type: 'line',
      data: rates,
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { color: '#818cf8', width: 2 },
      itemStyle: { color: '#818cf8' },
      areaStyle: { color: 'rgba(129,140,248,0.15)' },
    }],
  }
})

// Fun facts
const funFacts = computed(() => {
  if (!conference.value) return []
  const c = conference.value
  const years = c.years.map(String)
  const facts: string[] = []
  const sumValues = (obj: Record<string, number>) => Object.values(obj).reduce((a: number, b: number) => a + b, 0)

  // Use latest year data for primary facts
  const latestYear = years[years.length - 1]!
  const latestData = c.by_year[latestYear] || {}
  const latestTotal = sumValues(latestData)
  const latestSorted = Object.entries(latestData).sort((a, b) => b[1] - a[1])

  if (latestSorted.length > 0 && latestTotal > 0) {
    const topLang = latestSorted[0]![0]
    const pct = ((latestSorted[0]![1] / latestTotal) * 100).toFixed(1)
    facts.push(`In ${latestYear}, ${topLang} authors wrote ${pct}% of first-authored papers.`)
  }

  // Growth trend of the overall top language
  if (years.length >= 2 && latestSorted.length > 0) {
    const firstYear = years[0]!
    const topLang = latestSorted[0]![0]
    const firstTotal = sumValues(c.by_year[firstYear] || {})
    const firstPct = (c.by_year[firstYear]?.[topLang] || 0) / Math.max(firstTotal, 1) * 100
    const lastPct = (latestSorted[0]![1] / Math.max(latestTotal, 1)) * 100
    const change = lastPct - firstPct
    if (Math.abs(change) > 2) {
      facts.push(`${topLang} representation ${change > 0 ? 'grew' : 'shrank'} by ${Math.abs(change).toFixed(1)}pp from ${firstYear} to ${latestYear}.`)
    }
  }

  if (latestSorted.length >= 3) {
    facts.push(`Top 3 in ${latestYear}: ${latestSorted.slice(0, 3).map(([l]) => l).join(', ')}.`)
  }

  return facts
})

// Affiliation horizontal bar chart
const INST_ABBREV: Record<string, string> = {
  'Chinese Academy of Sciences': 'CAS',
  'University of California, Berkeley': 'UC Berkeley',
  'University of California, Los Angeles': 'UCLA',
  'University of California, San Diego': 'UC San Diego',
  'University of California, Santa Barbara': 'UC Santa Barbara',
  'University of California, Irvine': 'UC Irvine',
  'University of California, Davis': 'UC Davis',
  'University of California, Santa Cruz': 'UC Santa Cruz',
  'University of California, Riverside': 'UC Riverside',
  'University of Illinois at Urbana-Champaign': 'UIUC',
  'Georgia Institute of Technology': 'Georgia Tech',
  'University of Texas at Austin': 'UT Austin',
  'University of Massachusetts Amherst': 'UMass',
  'University of Maryland, College Park': 'UMD',
  'Hong Kong University of Science and Technology': 'HKUST',
  'Chinese University of Hong Kong': 'CUHK',
  'Chinese University of Hong Kong, Shenzhen': 'CUHK-Shenzhen',
  'University of Hong Kong': 'HKU',
  'Pohang University of Science and Technology': 'POSTECH',
  'Nanyang Technological University': 'NTU',
  'National University of Singapore': 'NUS',
  'University of Science and Technology of China': 'USTC',
  'National Chiao Tung University': 'NYCU',
  'National Yang Ming Chiao Tung University': 'NYCU',
  'National Taiwan University': 'NTU Taiwan',
  'Shanghai Jiao Tong University': 'SJTU',
  'Harbin Institute of Technology': 'HIT',
  'Harbin Institute of Technology, Shenzhen': 'HIT Shenzhen',
  'University of British Columbia': 'UBC',
  'University of New South Wales': 'UNSW',
  'Technical University of Munich': 'TUM',
  'TU Munich': 'TUM',
  'LMU Munich': 'LMU Munich',
  'Ludwig Maximilian University of Munich': 'LMU Munich',
  'Humboldt University of Berlin': 'HU Berlin',
  'Friedrich-Alexander-Universität Erlangen-Nürnberg': 'FAU',
  'Tel Aviv University': 'TAU',
  'Indian Institute of Technology Bombay': 'IIT Bombay',
  'Indian Institute of Science': 'IISc',
  'Pierre and Marie Curie University': 'UPMC',
  'Polytechnic University of Milan': 'PoliMi',
  'Politecnico di Milano': 'PoliMi',
  'Sapienza University of Rome': 'Sapienza',
  'KTH Royal Institute of Technology': 'KTH',
  'Tokyo Institute of Technology': 'Tokyo Tech',
  'University of Pennsylvania': 'UPenn',
  'Carnegie Mellon University': 'CMU',
  'Massachusetts Institute of Technology': 'MIT',
  'California Institute of Technology': 'Caltech',
  'University of Electronic Science and Technology of China': 'UESTC',
  'Beijing University of Posts and Telecommunications': 'BUPT',
  'Huazhong University of Science and Technology': 'HUST',
  'Renmin University of China': 'RUC',
  'Hong Kong Polytechnic University': 'PolyU',
  'Hong Kong Baptist University': 'HKBU',
  'Beihang University': 'Beihang',
  'Xi\'an Jiaotong University': 'XJTU',
  'Nanjing University of Aeronautics and Astronautics': 'NUAA',
  'Northwestern Polytechnical University': 'NWPU',
  'National University of Defense Technology': 'NUDT',
  'Ohio State University': 'OSU',
  'University of Michigan': 'UMich',
  'University of North Carolina at Chapel Hill': 'UNC',
  'Pennsylvania State University': 'Penn State',
  'University of Waterloo': 'UWaterloo',
  'University of Edinburgh': 'Edinburgh',
  'University College London': 'UCL',
  'Imperial College London': 'Imperial',
  'University of Toronto': 'UofT',
  'Université de Montréal': 'UdeM',
  'King Abdullah University of Science and Technology': 'KAUST',
  'Mohamed bin Zayed University of Artificial Intelligence': 'MBZUAI',
  'Max Planck Institute for Informatics': 'MPI Informatics',
  'Max Planck Institute for Intelligent Systems': 'MPI-IS',
  'Shanghai AI Lab': 'Shanghai AI Lab',
  'German Aerospace Center (DLR)': 'DLR',
  'Istituto Italiano di Tecnologia': 'IIT Genova',
  'Universitat Pompeu Fabra': 'UPF',
  'University of Bonn': 'U Bonn',
  'University of Freiburg': 'U Freiburg',
  'University of Tübingen': 'U Tübingen',
  'Karlsruhe Institute of Technology': 'KIT',
  'Rensselaer Polytechnic Institute': 'RPI',
  'Virginia Tech': 'Virginia Tech',
  'Texas A&M University': 'TAMU',
  'Rutgers University': 'Rutgers',
  'Stony Brook University': 'Stony Brook',
  'Dartmouth College': 'Dartmouth',
}
const abbreviateInst = (name: string) => INST_ABBREV[name] || name

const COUNTRY_OVERRIDES: Record<string, string> = { TW: 'CN' }
const countryFlag = (code: string) => {
  const c = COUNTRY_OVERRIDES[code] || code
  return String.fromCodePoint(...[...c.toUpperCase()].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65))
}

const SOURCE_NAMES: Record<string, { label: string; url: string }> = {
  openreview: { label: 'OpenReview', url: 'https://openreview.net' },
  openalex: { label: 'OpenAlex', url: 'https://openalex.org' },
  martenlienen: { label: 'Marten Lienen et al.', url: 'https://github.com/martenlienen/icml-neurips-iclr-dataset' },
  papercopilot: { label: 'PaperCopilot', url: 'https://github.com/papercopilot/paperlists' },
}
const sourceLinks = (sources: string[]) =>
  (sources || [])
    .map(s => {
      const info = SOURCE_NAMES[s]
      return info
        ? `<a href="${info.url}" target="_blank" rel="noopener" class="text-blue-400 hover:text-blue-300">${info.label}</a>`
        : s
    })
    .join(' + ')

interface ActiveAffil {
  total_papers: number
  total_covered: number
  coverage_pct: number
  top: { name: string; count: number; pct: number; country?: string; rank?: number }[]
  sources?: string[]
  year?: string
}

const affilLatestOnly = ref(true)

const activeAffilData = computed<ActiveAffil | null>(() => {
  const affil = conference.value?.affiliations
  if (!affil) return null
  if (!affilLatestOnly.value) return affil as ActiveAffil
  const byYear = affil.by_year
  if (!byYear) return affil as ActiveAffil
  const years = Object.keys(byYear).filter(y => byYear[y]?.top?.length)
  if (years.length <= 1) return affil as ActiveAffil
  const latestYear = years.sort().pop()!
  const yd = byYear[latestYear]!
  return {
    total_papers: yd.total_papers,
    total_covered: yd.total_covered,
    coverage_pct: yd.total_papers > 0 ? Math.round(100 * yd.total_covered / yd.total_papers * 10) / 10 : 0,
    top: yd.top,
    sources: affil.sources,
    year: latestYear,
  }
})

const affiliationChartOption = computed(() => {
  const affil = activeAffilData.value
  if (!affil) return {}
  const top = affil.top.slice(0, 20)
  if (!top.length) return {}

  // Build prev-year rank map for comparison when showing single year
  let prevRankMap: Map<string, number> | null = null
  if (affil.year && conference.value?.affiliations?.by_year) {
    const byYear = conference.value.affiliations.by_year
    const years = Object.keys(byYear).filter(y => byYear[y]?.top?.length).sort()
    const idx = years.indexOf(affil.year)
    if (idx > 0) {
      const prevYear = years[idx - 1]!
      const prevData = byYear[prevYear]!
      // Use rank field from data (handles ties); fallback to index+1
      prevRankMap = new Map(prevData.top.map((e: any, i: number) => [e.name, e.rank ?? (i + 1)]))
    }
  }

  const items = top.slice().reverse()
  const prevMaxRank = prevRankMap ? Math.max(...prevRankMap.values()) : 100
  const labels = items.map((e) => {
    const flag = e.country ? countryFlag(e.country) : ''
    const short = abbreviateInst(e.name)
    const curRank = e.rank ?? (top.indexOf(e) + 1)
    let badge = ''
    if (prevRankMap) {
      const prevRank = prevRankMap.get(e.name) ?? (prevMaxRank + 1)
      const diff = prevRank - curRank
      if (diff > 0) badge = ` {rank_up|↑${diff}}`
      else if (diff < 0) badge = ` {rank_down|↓${Math.abs(diff)}}`
      else badge = ` {rank_same|—}`
    }
    return flag ? `${short}${badge} {flag|${flag}}` : `${short}${badge}`
  })
  const counts = items.map(e => e.count)
  const pcts = items.map(e => e.pct)
  const cleanNames = items.map(e => e.name)

  // gradient: bottom bar (top institution) = soft lavender, top bar = vivid violet
  const n = labels.length
  const barColors = labels.map((_: any, i: number) => {
    const t = n > 1 ? i / (n - 1) : 0
    const r = Math.round(159 - t * 50)
    const g = Math.round(180 - t * 140)
    const b = Math.round(252 - t * 35)
    return `rgb(${r},${g},${b})`
  })

  return {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: any) => {
        const p = params[0]
        return `${cleanNames[p.dataIndex]}<br/>${p.value} papers (${pcts[p.dataIndex]?.toFixed(1)}%)`
      },
    },
    grid: { left: 220, right: 60, top: 10, bottom: 20 },
    xAxis: {
      type: 'value' as const,
      axisLabel: { color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'category' as const,
      data: labels,
      axisLabel: {
        color: '#d1d5db',
        fontSize: 12,
        rich: {
          flag: { fontSize: 18, align: 'center' },
          rank_up: { fontSize: 11, color: '#34d399', padding: [0, 0, 0, 4] },
          rank_down: { fontSize: 11, color: '#f87171', padding: [0, 0, 0, 4] },
          rank_same: { fontSize: 11, color: '#6b7280', padding: [0, 0, 0, 4] },
        },
      },
    },
    series: [{
      type: 'bar' as const,
      data: counts.map((v, i) => ({
        value: v,
        itemStyle: { color: barColors[i], borderRadius: [0, 4, 4, 0] },
      })),
      barMaxWidth: 24,
      label: {
        show: true,
        position: 'right' as const,
        formatter: (p: any) => `${p.value}`,
        color: '#9ca3af',
        fontSize: 11,
      },
    }],
  }
})
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <!-- Loading -->
      <div v-if="loading" class="text-center py-20">
        <div class="text-4xl mb-4 animate-bounce">🗣️</div>
        <p class="text-gray-400">{{ t('home.loading') }}</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center py-20">
        <p class="text-red-400 text-lg">{{ error }}</p>
        <router-link to="/" class="text-blue-400 mt-4 inline-block no-underline">{{ t('conference.back_to_home') }}</router-link>
      </div>

      <!-- Conference Detail -->
      <template v-else-if="conference">
        <!-- Header + Verdict -->
        <div class="grid lg:grid-cols-3 items-stretch gap-6 mb-8">
          <div class="lg:col-span-2">
            <div class="flex items-center gap-3 mb-2">
              <h1 class="text-3xl md:text-4xl font-bold text-white">{{ conference.title }}</h1>
              <span
                class="text-sm font-bold px-3 py-1 rounded"
                :style="{ backgroundColor: getRankColor(conference.rank) + '22', color: getRankColor(conference.rank) }"
              >
                CCF {{ conference.rank }}
              </span>
              <span class="text-sm px-3 py-1 rounded bg-gray-700 text-gray-300">{{ categoryNames[conference.category] || conference.category }}</span>
            </div>
            <span class="text-gray-400">{{ conference.description }}</span>
            <span v-if="conference.note" class="block text-xs text-gray-500 mt-1 italic">{{ conference.note }}</span>
            <a
              v-for="link in dblpLinks"
              :key="link.key"
              :href="link.url"
              target="_blank"
              rel="noopener"
              class="inline-block ml-1.5 align-middle opacity-50 hover:opacity-100 transition-opacity"
              :title="`DBLP: ${link.key}`"
            ><img :src="`${baseUrl}dblp-logo.png`" class="w-4 h-4" alt="DBLP"></a>
            <div class="flex gap-6 mt-4 text-sm text-gray-500">
              <span>{{ t('conference.total_papers') }}: <strong class="text-white">{{ totalPapers.toLocaleString() }}</strong></span>
              <span>{{ t('conference.years_covered') }}: <strong class="text-white">{{ conference.years[0] }}–{{ conference.years[conference.years.length - 1] }}</strong></span>
              <span
                v-if="latestAcceptRate"
                class="relative cursor-default"
                @mouseenter="showAcceptRateChart = true"
                @mouseleave="showAcceptRateChart = false"
              >
                {{ t('conference.accept_rate') }}: <strong class="text-white">{{ latestAcceptRate.rate }}%</strong>
                <span class="text-gray-600"> ({{ latestAcceptRate.year }}) </span>
                <span
                  v-if="latestAcceptRate.trend != null && latestAcceptRate.trend > 0"
                  class="trend-up text-emerald-400 text-xs font-medium"
                >↗ {{ latestAcceptRate.trend.toFixed(1) }}</span>
                <span
                  v-else-if="latestAcceptRate.trend != null && latestAcceptRate.trend < 0"
                  class="trend-down text-orange-400 text-xs font-medium"
                >↘ {{ Math.abs(latestAcceptRate.trend).toFixed(1) }}</span>
                <span
                  v-else-if="latestAcceptRate.trend != null"
                  class="trend-flat text-gray-500 text-xs font-medium"
                >→ 0.0</span>
                <Transition name="fade">
                  <div
                    v-if="showAcceptRateChart && conference!.accept_rates!.length > 1"
                    class="absolute left-0 top-full mt-2 z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-3"
                    style="width: 340px"
                  >
                    <p class="text-xs text-gray-400 mb-1">{{ t('conference.accept_rate_history') }}</p>
                    <v-chart :option="acceptRateChartOption" style="height: 160px" autoresize />
                  </div>
                </Transition>
              </span>
            </div>
          </div>
          <div v-if="verdictGreeting" class="card px-5 py-4 bg-gradient-to-br from-indigo-900/40 to-purple-900/30 border-indigo-500/20 flex flex-col justify-center">
            <div>
              <p class="text-xl font-bold text-white lg:text-2xl">
                <span class="text-xl">🗣️</span>
                Say <span class="greeting-pop">{{ verdictGreeting.greeting }}</span>!
              </p>
              <p class="text-gray-400 text-xs leading-relaxed">
                In {{ verdictGreeting.year }}, {{ verdictGreeting.pct }}% speak {{ verdictGreeting.lang }}
                <span v-if="verdictGreeting.trend != null" :class="verdictGreeting.trend > 0 ? 'text-emerald-400' : verdictGreeting.trend < 0 ? 'text-orange-400' : 'text-gray-500'"
                >(<span :class="verdictGreeting.trend > 0 ? 'trend-up' : verdictGreeting.trend < 0 ? 'trend-down' : 'trend-flat'">{{ verdictGreeting.trend > 0 ? '↗' : verdictGreeting.trend < 0 ? '↘' : '→' }} {{ Math.abs(verdictGreeting.trend).toFixed(1) }}pp</span> vs {{ verdictGreeting.prevYear }})</span>
                <template v-if="verdictGreeting.secondLang">, or try <span class="text-gray-300">{{ verdictGreeting.secondGreeting }}</span> ({{ verdictGreeting.secondPct }}%)</template>
              </p>
            </div>
          </div>
        </div>

        <!-- Chart -->
        <div class="mb-8">
          <div class="card p-6 bg-gray-800/50 border-gray-700/50">
            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-4">
              <h3 class="text-lg font-semibold text-white">{{ t('conference.language_over_years') }}</h3>
              <div class="inline-flex rounded-lg overflow-hidden border border-gray-600 shrink-0">
                <button
                  @click="areaMode = 'absolute'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="areaMode === 'absolute' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  Count
                </button>
                <button
                  @click="areaMode = 'ratio'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="areaMode === 'ratio' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  Ratio %
                </button>
                <button
                  @click="areaMode = 'cumulative'"
                  class="px-3 py-1 text-xs font-medium transition-colors"
                  :class="areaMode === 'cumulative' ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
                >
                  Cumulative
                </button>
              </div>
            </div>
            <v-chart :option="areaOption" style="height: 400px" autoresize />
            <p v-if="hasVirtualYears" class="text-xs text-gray-500 mt-1 text-right">* Virtual / Online</p>
          </div>
        </div>

        <!-- Fun Facts -->
        <div v-if="funFacts.length" class="card p-6 bg-gray-800/50 border-gray-700/50 mb-8">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('conference.fun_facts') }}</h3>
          <ul class="space-y-2">
            <li v-for="(fact, i) in funFacts" :key="i" class="text-gray-300 flex items-start gap-2">
              <span class="text-yellow-400 mt-0.5">•</span>
              {{ fact }}
            </li>
          </ul>
        </div>

        <!-- Top Affiliations -->
        <div v-if="conference.affiliations && conference.affiliations.coverage_pct >= 50" class="card p-6 bg-gray-800/50 border-gray-700/50 mb-8">
          <div class="flex items-center justify-between mb-1">
            <h3 class="text-lg font-semibold text-white"><span class="text-violet-400 mr-1">{{ conference.id }}</span>{{ t('conference.top_affiliations') }}</h3>
            <label v-if="conference!.affiliations!.by_year && Object.keys(conference!.affiliations!.by_year).filter(y => conference!.affiliations!.by_year?.[y]?.top?.length).length > 1" class="flex items-center gap-2 text-sm text-gray-400 cursor-pointer select-none">
              <input type="checkbox" v-model="affilLatestOnly" class="accent-violet-500" />
              {{ t('conference.affiliation_latest_only') }}
            </label>
          </div>
          <p class="text-xs text-gray-500 mb-4">
            <template v-if="activeAffilData?.year">
              {{ t('conference.affiliation_coverage_year', {
                year: activeAffilData.year,
                covered: `${activeAffilData.total_covered} (${activeAffilData.coverage_pct}%)`,
                total: activeAffilData.total_papers
              }) }}
            </template>
            <template v-else>
              {{ t('conference.affiliation_coverage', {
                covered: `${conference.affiliations.total_covered} (${conference.affiliations.coverage_pct}%)`,
                total: conference.affiliations.total_papers
              }) }}
            </template>
            · <span v-html="sourceLinks(conference.affiliations.sources ?? [])" />
            <span class="text-gray-600 ml-1">{{ t('conference.affiliation_top_note') }}</span>
          </p>
          <v-chart :option="affiliationChartOption" style="height: 480px" autoresize />
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.trend-up {
  display: inline-block;
  animation: slideUp 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), glowGreen 2s ease-in-out 0.5s infinite;
}

.trend-down {
  display: inline-block;
  animation: slideDown 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), glowOrange 2s ease-in-out 0.5s infinite;
}

.trend-flat {
  display: inline-block;
  animation: fadeIn 0.4s ease;
}

@keyframes slideUp {
  0% { transform: translate(-4px, 4px); opacity: 0; }
  60% { transform: translate(1px, -1px); opacity: 1; }
  100% { transform: translate(0, 0); }
}

@keyframes slideDown {
  0% { transform: translate(-4px, -4px); opacity: 0; }
  60% { transform: translate(1px, 1px); opacity: 1; }
  100% { transform: translate(0, 0); }
}

@keyframes glowGreen {
  0%, 100% { text-shadow: 0 0 2px transparent; }
  50% { text-shadow: 0 0 6px rgba(52, 211, 153, 0.6); }
}

@keyframes glowOrange {
  0%, 100% { text-shadow: 0 0 2px transparent; }
  50% { text-shadow: 0 0 6px rgba(251, 146, 60, 0.6); }
}

@keyframes fadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

.greeting-pop {
  background: linear-gradient(90deg, #a5b4fc 0%, #a5b4fc 40%, #e0e7ff 50%, #a5b4fc 60%, #a5b4fc 100%);
  background-size: 200% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer 2s ease-in-out 0.3s 1;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>

<style>
/* Make ECharts SVG text selectable (for copying institution names) */
.echarts svg text {
  user-select: text !important;
  -webkit-user-select: text !important;
  cursor: text;
}
</style>

