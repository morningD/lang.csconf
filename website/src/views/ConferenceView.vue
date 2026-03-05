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
  // YoY trend for dominant language
  let trend: number | null = null
  let prevYear: string | null = null
  if (c.years.length >= 2) {
    prevYear = String(c.years[c.years.length - 2])
    const prevData = c.by_year[prevYear] || {}
    const prevTotal = Object.values(prevData).reduce((a: number, b: number) => a + b, 0)
    if (prevTotal > 0) {
      const prevPct = Math.round((prevData[topLang] || 0) / prevTotal * 100)
      trend = pct - prevPct
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
        interval: 0,
        formatter: (year: string) => {
          const venue = venues[year]
          if (venue?.country) {
            const isVirtual = venue.city === 'Virtual' || /Virtual|Online/i.test(venue.country)
            let label = venue.country
              .replace(/\s*\(Virtual.*?\)/gi, '')
              .replace(/\s*\(Online\)/gi, '')
              .replace(/\s*\(hybrid\)/gi, '')
            if (!label || label === 'None') label = isVirtual ? 'Virtual' : ''
            else if (isVirtual) label += '*'
            return `{year|${year}}\n{country|${label || venue.country}}`
          }
          return `{year|${year}}`
        },
        rich: {
          year: { color: '#bbb', fontSize: 12, lineHeight: 16 },
          country: { color: '#666', fontSize: 10, lineHeight: 14 },
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
        <div class="grid lg:grid-cols-3 items-start gap-6 mb-8">
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
                >↗ {{ latestAcceptRate.trend }}</span>
                <span
                  v-else-if="latestAcceptRate.trend != null && latestAcceptRate.trend < 0"
                  class="trend-down text-orange-400 text-xs font-medium"
                >↘ {{ Math.abs(latestAcceptRate.trend) }}</span>
                <span
                  v-else-if="latestAcceptRate.trend != null"
                  class="trend-flat text-gray-500 text-xs font-medium"
                >→ 0</span>
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
                >(<span :class="verdictGreeting.trend > 0 ? 'trend-up' : verdictGreeting.trend < 0 ? 'trend-down' : 'trend-flat'">{{ verdictGreeting.trend > 0 ? '↗' : verdictGreeting.trend < 0 ? '↘' : '→' }} {{ Math.abs(verdictGreeting.trend) }}pp</span> vs {{ verdictGreeting.prevYear }})</span>
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

