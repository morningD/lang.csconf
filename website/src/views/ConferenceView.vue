<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { ConferenceDetail, Meta } from '@/types'

const route = useRoute()
const { t } = useI18n()
const { fetchConference, fetchMeta } = useDataFetch()

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
  const sorted = Object.entries(conference.value.total).sort((a, b) => b[1] - a[1])
  if (sorted.length === 0) return null
  const topLang = sorted[0]![0]
  const total = Object.values(conference.value.total).reduce((a, b) => a + b, 0)
  const pct = Math.round(sorted[0]![1] / total * 100)
  return {
    greeting: langGreetings[topLang] || topLang,
    lang: topLang,
    pct,
    secondLang: sorted.length > 1 ? sorted[1]![0] : null,
    secondGreeting: sorted.length > 1 ? (langGreetings[sorted[1]![0]] || sorted[1]![0]) : null,
    secondPct: sorted.length > 1 ? Math.round(sorted[1]![1] / total * 100) : 0,
  }
})

// Stacked area chart: language distribution over years
const areaOption = computed(() => {
  if (!conference.value || !meta.value) return {}
  const c = conference.value
  const years = c.years.map(String)
  const colors = meta.value.language_colors

  // Get top languages for this conference
  const topLangs = Object.entries(c.total)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([lang]) => lang)

  const mode = areaMode.value
  const showPct = mode === 'ratio'

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      valueFormatter: showPct ? (v: number) => v + '%' : undefined,
    },
    legend: { data: topLangs, textStyle: { color: '#aaa' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: years, boundaryGap: false, axisLabel: { color: '#aaa' }, axisLine: { lineStyle: { color: '#444' } } },
    yAxis: {
      type: 'value',
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
  }
})

const totalPapers = computed(() => {
  if (!conference.value) return 0
  return Object.values(conference.value.total).reduce((a, b) => a + b, 0)
})

// Fun facts
const funFacts = computed(() => {
  if (!conference.value) return []
  const c = conference.value
  const total = totalPapers.value
  const sorted = Object.entries(c.total).sort((a, b) => b[1] - a[1])
  const facts: string[] = []

  if (sorted.length > 0) {
    const first = sorted[0]!
    const topLang = first[0]
    const topCount = first[1]
    const pct = ((topCount / total) * 100).toFixed(1)
    facts.push(`${topLang} authors wrote ${pct}% of all first-authored papers.`)
  }

  // Growth trend
  const years = c.years.map(String)
  if (years.length >= 2 && sorted.length > 0) {
    const firstYear = years[0]!
    const lastYear = years[years.length - 1]!
    const topLang = sorted[0]![0]
    const sumValues = (obj: Record<string, number>) => Object.values(obj).reduce((a: number, b: number) => a + b, 0)
    const firstPct = (c.by_year[firstYear]?.[topLang] || 0) / Math.max(sumValues(c.by_year[firstYear] || {}), 1) * 100
    const lastPct = (c.by_year[lastYear]?.[topLang] || 0) / Math.max(sumValues(c.by_year[lastYear] || {}), 1) * 100
    const change = lastPct - firstPct
    if (Math.abs(change) > 2) {
      facts.push(`${topLang} representation ${change > 0 ? 'grew' : 'shrank'} by ${Math.abs(change).toFixed(1)}pp from ${firstYear} to ${lastYear}.`)
    }
  }

  if (sorted.length >= 3) {
    facts.push(`The top 3 language groups are: ${sorted.slice(0, 3).map(([l]) => l).join(', ')}.`)
  }

  return facts
})
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <!-- Back button -->
      <router-link to="/" class="inline-flex items-center gap-1 text-gray-400 hover:text-white mb-6 no-underline transition-colors">
        <span>←</span> {{ t('conference.back_to_home') }}
      </router-link>

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
        <div class="grid lg:grid-cols-3 gap-6 mb-8">
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
            <p class="text-gray-400">{{ conference.description }}</p>
            <div class="flex gap-6 mt-4 text-sm text-gray-500">
              <span>{{ t('conference.total_papers') }}: <strong class="text-white">{{ totalPapers.toLocaleString() }}</strong></span>
              <span>{{ t('conference.years_covered') }}: <strong class="text-white">{{ conference.years[0] }}–{{ conference.years[conference.years.length - 1] }}</strong></span>
            </div>
          </div>
          <div v-if="verdictGreeting" class="card px-4 py-3 bg-gradient-to-br from-indigo-900/40 to-purple-900/30 border-indigo-500/20 flex items-center gap-3 lg:flex-col lg:items-center lg:justify-center lg:text-center">
            <div class="text-3xl shrink-0 lg:text-4xl leading-none flex items-center">🗣️</div>
            <div>
              <p class="text-xl font-bold text-white lg:text-2xl lg:mb-1">
                Say <span class="text-indigo-300">{{ verdictGreeting.greeting }}</span>!
              </p>
              <p class="text-gray-400 text-xs leading-relaxed">
                {{ verdictGreeting.pct }}% speak {{ verdictGreeting.lang }}<template v-if="verdictGreeting.secondLang">, or try <span class="text-gray-300">{{ verdictGreeting.secondGreeting }}</span> ({{ verdictGreeting.secondPct }}%)</template>
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
