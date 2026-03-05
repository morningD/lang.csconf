<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { Meta, GlobalSummary, ConferenceIndex, CCFRank } from '@/types'

const { t } = useI18n()
const router = useRouter()
const { fetchMeta, fetchGlobalSummary, fetchConferencesIndex } = useDataFetch()

const meta = ref<Meta | null>(null)
const summary = ref<GlobalSummary | null>(null)
const conferences = ref<ConferenceIndex[]>([])
const loading = ref(true)
const searchQuery = ref('')
const activeRanks = ref<Set<CCFRank>>(new Set(['A']))
const activeCategory = ref('ALL')

const categories = ['ALL', 'AI', 'DB', 'NW', 'SE', 'CG', 'CT', 'HI', 'SC', 'DS', 'MX']
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
const ranks: CCFRank[] = ['A', 'B', 'C', 'N']
function toggleRank(rank: CCFRank) {
  const s = new Set(activeRanks.value)
  if (s.has(rank)) {
    if (s.size > 1) s.delete(rank)
  } else {
    s.add(rank)
  }
  activeRanks.value = s
}
const sortKey = ref('default')
const sortDir = ref<'desc' | 'asc'>('desc')
const sortOptions = [
  { value: 'default', label: 'Default' },
  { value: 'Chinese', label: 'Nihao' },
  { value: 'English', label: 'Hello' },
  { value: 'Korean', label: 'Annyeong' },
  { value: 'Indian', label: 'Namaste' },
  { value: 'papers', label: 'Papers' },
]
function toggleSort(value: string) {
  if (value === 'default') {
    sortKey.value = 'default'
    sortDir.value = 'desc'
  } else if (sortKey.value === value) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortKey.value = value
    sortDir.value = 'desc'
  }
}
function getSortLabel(opt: { value: string; label: string }) {
  if (opt.value === 'default') return opt.label
  const arrow = sortKey.value === opt.value ? (sortDir.value === 'desc' ? ' ↓' : ' ↑') : ''
  return opt.label + arrow
}
const trendMode = ref<'absolute' | 'ratio'>('absolute')

onMounted(async () => {
  document.addEventListener('click', onSearchClickOutside)
  try {
    const [m, s, c] = await Promise.all([
      fetchMeta(),
      fetchGlobalSummary(),
      fetchConferencesIndex(),
    ])
    meta.value = m
    summary.value = s
    conferences.value = c
  } catch (e) {
    console.error('Failed to load data:', e)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  document.removeEventListener('click', onSearchClickOutside)
})

const filteredConferences = computed(() => {
  let result = conferences.value
  if (activeRanks.value.size < 4) {
    result = result.filter(c => activeRanks.value.has(c.rank as CCFRank))
  }
  if (activeCategory.value !== 'ALL') {
    result = result.filter(c => c.category === activeCategory.value)
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(c => c.title.toLowerCase().includes(q) || c.id.toLowerCase().includes(q) || c.description.toLowerCase().includes(q))
  }
  if (sortKey.value !== 'default') {
    const dir = sortDir.value === 'desc' ? 1 : -1
    result = [...result].sort((a, b) => {
      let diff: number
      if (sortKey.value === 'papers') {
        diff = (Number(b.total_papers) || 0) - (Number(a.total_papers) || 0)
      } else {
        const lang = sortKey.value
        const aScore = a.latest_lang_pcts?.[lang] || a.lang_pcts?.[lang] || 0
        const bScore = b.latest_lang_pcts?.[lang] || b.lang_pcts?.[lang] || 0
        diff = bScore - aScore
      }
      return diff * dir
    })
  }
  return result
})

// Pie chart data
const pieOption = computed(() => {
  if (!summary.value || !meta.value) return {}
  const total = summary.value.total
  const colors = meta.value.language_colors
  const data = Object.entries(total)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }))

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#1a1a2e', borderWidth: 2 },
      label: { show: true, color: '#ccc', fontSize: 12 },
      data: data.map(d => ({ ...d, itemStyle: { color: colors[d.name] || '#95a5a6' } })),
    }],
  }
})

// Trend line chart
const trendOption = computed(() => {
  if (!summary.value || !meta.value) return {}
  const byYear = summary.value.by_year
  const years = Object.keys(byYear).sort()
  const colors = meta.value.language_colors
  const topLangs = Object.entries(summary.value.total)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([lang]) => lang)

  const isRatio = trendMode.value === 'ratio'

  return {
    tooltip: {
      trigger: 'axis',
      valueFormatter: isRatio ? (v: number) => v + '%' : undefined,
    },
    legend: { data: topLangs, textStyle: { color: '#aaa' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: years, axisLabel: { color: '#aaa' }, axisLine: { lineStyle: { color: '#444' } } },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#aaa', formatter: isRatio ? '{value}%' : '{value}' },
      splitLine: { lineStyle: { color: '#333' } },
    },
    series: topLangs.map(lang => ({
      name: lang,
      type: 'line',
      smooth: true,
      data: years.map(y => {
        const val = byYear[y]?.[lang] || 0
        if (!isRatio) return val
        const yearTotal = Object.values(byYear[y] || {}).reduce((a: number, b: number) => a + b, 0)
        return yearTotal > 0 ? Math.round(val / yearTotal * 1000) / 10 : 0
      }),
      itemStyle: { color: colors[lang] || '#95a5a6' },
      areaStyle: { opacity: 0.1 },
    })),
  }
})

function getRankColor(rank: string) {
  const colors: Record<string, string> = { A: '#e74c3c', B: '#f39c12', C: '#3498db', N: '#95a5a6' }
  return colors[rank] || '#95a5a6'
}

function getLangColor(lang: string) {
  return meta.value?.language_colors[lang] || '#95a5a6'
}

const showSearchSuggestions = ref(false)
const searchDropdownRef = ref<HTMLElement | null>(null)

const searchSuggestions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  const matches = conferences.value
    .filter(c => c.id.toLowerCase().includes(q) || c.title.toLowerCase().includes(q) || c.description.toLowerCase().includes(q))
  // Sort: ID matches first, then title matches, then description-only matches
  matches.sort((a, b) => {
    const aId = a.id.toLowerCase().includes(q) ? 0 : a.title.toLowerCase().includes(q) ? 1 : 2
    const bId = b.id.toLowerCase().includes(q) ? 0 : b.title.toLowerCase().includes(q) ? 1 : 2
    return aId - bId || a.id.localeCompare(b.id)
  })
  return matches
})

function goToConference(id: string) {
  searchQuery.value = ''
  showSearchSuggestions.value = false
  router.push(`/conference/${id}`)
}

function onSearchClickOutside(e: MouseEvent) {
  if (searchDropdownRef.value && !searchDropdownRef.value.contains(e.target as Node)) {
    showSearchSuggestions.value = false
  }
}

</script>

<template>
  <div class="min-h-screen">
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center min-h-[60vh]">
      <div class="text-center">
        <div class="text-4xl mb-4 animate-bounce">🗣️</div>
        <p class="text-gray-400 text-lg">{{ t('home.loading') }}</p>
      </div>
    </div>

    <template v-else>
      <!-- Browse Conferences -->
      <section class="pt-8 pb-12 px-4">
        <div class="max-w-7xl mx-auto">
          <h2 class="section-title text-center mb-8">{{ t('home.browse_conferences') }}</h2>

          <!-- Search & Filters -->
          <div class="flex flex-col md:flex-row gap-4 mb-6 items-center justify-center">
            <div ref="searchDropdownRef" class="relative w-full md:w-96">
              <input
                v-model="searchQuery"
                @focus="showSearchSuggestions = true"
                :placeholder="t('home.search_placeholder')"
                class="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
              <ul
                v-show="showSearchSuggestions && searchSuggestions.length > 0"
                class="absolute left-0 right-0 top-full mt-1 z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl max-h-72 overflow-y-auto p-0 list-none"
              >
                <li
                  v-for="conf in searchSuggestions"
                  :key="conf.id"
                  @mousedown.prevent="goToConference(conf.id)"
                  class="px-4 py-2 text-sm hover:bg-gray-700 cursor-pointer flex items-center justify-between"
                >
                  <span class="truncate">
                    <span class="text-white font-medium">{{ conf.id }}</span>
                    <span class="text-gray-500 ml-2 text-xs">{{ conf.description }}</span>
                  </span>
                  <span
                    class="text-xs font-bold px-1.5 py-0.5 rounded ml-2 shrink-0"
                    :style="{ backgroundColor: getRankColor(conf.rank) + '22', color: getRankColor(conf.rank) }"
                  >{{ conf.rank }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- Rank Tabs (multi-select) -->
          <div class="flex justify-center gap-2 mb-4">
            <button
              v-for="rank in ranks"
              :key="rank"
              @click="toggleRank(rank)"
              class="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
              :class="activeRanks.has(rank)
                ? 'bg-blue-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
            >
              CCF {{ rank }}
            </button>
          </div>

          <!-- Category Filter -->
          <div class="flex justify-center gap-2 mb-8 flex-wrap">
            <button
              v-for="cat in categories"
              :key="cat"
              @click="activeCategory = cat"
              class="px-3 py-1 rounded-full text-xs font-medium transition-all relative group/cat"
              :class="activeCategory === cat
                ? 'bg-gray-600 text-white'
                : 'bg-gray-800 text-gray-500 hover:bg-gray-700'"
            >
              {{ cat === 'ALL' ? t('home.all_categories') : cat }}
              <span
                v-if="categoryNames[cat]"
                class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 text-xs text-white bg-gray-900 rounded shadow-lg whitespace-nowrap opacity-0 pointer-events-none group-hover/cat:opacity-100 transition-opacity z-10"
              >
                {{ categoryNames[cat] }}
              </span>
            </button>
          </div>

          <!-- Sort -->
          <div class="flex justify-center items-center gap-2 mb-6 flex-wrap">
            <span class="text-gray-500 text-xs mr-1">Sort:</span>
            <button
              v-for="opt in sortOptions"
              :key="opt.value"
              @click="toggleSort(opt.value)"
              class="px-3 py-1 rounded-full text-xs font-medium transition-all"
              :class="sortKey === opt.value
                ? 'bg-indigo-500 text-white'
                : 'bg-gray-800 text-gray-500 hover:bg-gray-700'"
            >
              {{ getSortLabel(opt) }}
            </button>
          </div>

          <!-- Conference Cards Grid -->
          <div class="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            <router-link
              v-for="conf in filteredConferences"
              :key="conf.id"
              :to="`/conference/${conf.id}`"
              class="conf-card card p-4 bg-gray-800/50 border-gray-700/50 no-underline group"
            >
              <div class="flex items-start justify-between mb-2">
                <h3 class="font-bold text-white group-hover:text-blue-400 transition-colors">{{ conf.title }}</h3>
                <span
                  class="text-xs font-bold px-2 py-0.5 rounded"
                  :style="{ backgroundColor: getRankColor(conf.rank) + '22', color: getRankColor(conf.rank) }"
                >
                  CCF {{ conf.rank }}
                </span>
              </div>
              <div class="flex items-center gap-2 mb-2">
                <span class="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300" :title="categoryNames[conf.category] || ''">{{ conf.category }}</span>
                <span class="text-xs text-gray-500">{{ t('home.papers_count', { n: conf.total_papers.toLocaleString() }) }}</span>
              </div>
              <div class="flex items-center gap-2">
                <div
                  class="w-2 h-2 rounded-full"
                  :style="{ backgroundColor: getLangColor(conf.latest_lang || conf.dominant_language) }"
                ></div>
                <span class="text-sm text-gray-400" :title="conf.latest_lang || conf.dominant_language">
                  {{ langGreetings[conf.latest_lang || conf.dominant_language] || conf.dominant_language }} ({{ conf.latest_pct || conf.dominant_pct }}%) · {{ conf.latest_year }}
                </span>
              </div>
              <!-- Mini progress bar -->
              <div class="mt-3 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :style="{ width: (conf.latest_pct || conf.dominant_pct) + '%', backgroundColor: getLangColor(conf.latest_lang || conf.dominant_language) }"
                ></div>
              </div>
            </router-link>
          </div>

          <div v-if="filteredConferences.length === 0" class="text-center text-gray-500 py-12">
            No conferences found matching your filters.
          </div>
        </div>
      </section>

      <!-- Global Distribution -->
      <section class="py-12 px-4">
        <div class="max-w-7xl mx-auto">
          <h2 class="section-title text-center mb-8">{{ t('home.global_distribution') }}</h2>
          <div class="grid md:grid-cols-2 gap-8">
            <div class="card p-6 bg-gray-800/50 border-gray-700/50">
              <v-chart :option="pieOption" style="height: 400px" autoresize />
            </div>
            <div class="card p-6 bg-gray-800/50 border-gray-700/50">
              <div class="flex justify-end mb-2">
                <div class="inline-flex rounded-lg overflow-hidden border border-gray-600">
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
                </div>
              </div>
              <v-chart :option="trendOption" style="height: 370px" autoresize />
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.conf-card {
  position: relative;
  background: rgba(30, 30, 40, 0.5);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2),
              inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 0.3s ease,
              border-color 0.3s ease,
              background 0.3s ease;
}

/* Top accent line */
.conf-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 2px;
  border-radius: 0 0 2px 2px;
  background: linear-gradient(90deg, transparent, #7c3aed, transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}

/* Anti-flicker zone */
.conf-card::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -6px;
  height: 6px;
}

.conf-card:hover {
  transform: translateY(-4px);
  background: rgba(40, 38, 55, 0.65);
  border-color: rgba(124, 58, 237, 0.4);
  box-shadow: 0 4px 20px rgba(124, 58, 237, 0.12),
              0 12px 40px rgba(0, 0, 0, 0.15),
              inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.conf-card:hover::before {
  opacity: 1;
}
</style>
