<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { Meta, GlobalSummary, CategoryStats, RankStats, CCFCategory, CCFRank } from '@/types'

const { t } = useI18n()
const { fetchMeta, fetchGlobalSummary, fetchCategory, fetchRank } = useDataFetch()

const meta = ref<Meta | null>(null)
const loading = ref(true)
const activeCategory = ref<CCFCategory | 'ALL'>('ALL')
const activeRank = ref<CCFRank | 'ALL'>('ALL')

const globalData = ref<GlobalSummary | null>(null)
const categoryData = ref<CategoryStats | null>(null)
const rankData = ref<RankStats | null>(null)

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
    const [m, g] = await Promise.all([fetchMeta(), fetchGlobalSummary()])
    meta.value = m
    globalData.value = g
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

// Active data source
const activeByYear = computed(() => {
  if (categoryData.value) return categoryData.value.by_year
  if (rankData.value) return rankData.value.by_year
  return globalData.value?.by_year || {}
})

const trendMode = ref<'absolute' | 'ratio' | 'cumulative'>('absolute')

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
        </div>
      </div>

      <div v-else class="text-center py-20">
        <div class="text-4xl mb-4 animate-bounce">🗣️</div>
        <p class="text-gray-400">{{ t('home.loading') }}</p>
      </div>
    </div>
  </div>
</template>
