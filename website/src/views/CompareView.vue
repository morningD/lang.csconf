<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { ConferenceIndex, ConferenceDetail, Meta } from '@/types'

const { t } = useI18n()
const { fetchConferencesIndex, fetchConference, fetchMeta } = useDataFetch()

const allConferences = ref<ConferenceIndex[]>([])
const meta = ref<Meta | null>(null)
const selectedIds = ref<string[]>([])
const selectedData = ref<ConferenceDetail[]>([])
const loading = ref(true)

onMounted(async () => {
  document.addEventListener('click', onClickOutside)
  try {
    const [confs, m] = await Promise.all([fetchConferencesIndex(), fetchMeta()])
    allConferences.value = confs
    meta.value = m
    // Default: pick two CCF-A conferences with contrasting language profiles
    selectedIds.value = ['ACMMM', 'LICS']
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})

watch(selectedIds, async (ids) => {
  const details = await Promise.all(ids.map(id => fetchConference(id)))
  selectedData.value = details
}, { deep: true })

function addConference(id: string) {
  if (id && !selectedIds.value.includes(id) && selectedIds.value.length < 4) {
    selectedIds.value.push(id)
  }
}

function removeConference(id: string) {
  selectedIds.value = selectedIds.value.filter(i => i !== id)
}

const searchQuery = ref('')
const showDropdown = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const availableConferences = computed(() =>
  allConferences.value
    .filter(c => !selectedIds.value.includes(c.id))
    .sort((a, b) => a.id.localeCompare(b.id))
)

const filteredConferences = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return availableConferences.value
  const matches = availableConferences.value.filter(c =>
    c.id.toLowerCase().includes(q) || c.title.toLowerCase().includes(q) || c.description.toLowerCase().includes(q)
  )
  matches.sort((a, b) => {
    const aId = a.id.toLowerCase().includes(q) ? 0 : a.title.toLowerCase().includes(q) ? 1 : 2
    const bId = b.id.toLowerCase().includes(q) ? 0 : b.title.toLowerCase().includes(q) ? 1 : 2
    return aId - bId || a.id.localeCompare(b.id)
  })
  return matches
})

function selectConference(id: string) {
  addConference(id)
  searchQuery.value = ''
  showDropdown.value = false
}

function getRankColor(rank: string) {
  const colors: Record<string, string> = { A: '#e74c3c', B: '#f39c12', C: '#3498db', N: '#95a5a6' }
  return colors[rank] || '#95a5a6'
}

function onClickOutside(e: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    showDropdown.value = false
  }
}


// Radar chart
const radarOption = computed(() => {
  if (selectedData.value.length < 2 || !meta.value) return {}
  const colors = meta.value.language_colors

  // Get union of top languages across selected conferences
  const langSet = new Set<string>()
  selectedData.value.forEach(c => {
    Object.entries(c.total).sort((a, b) => b[1] - a[1]).slice(0, 6).forEach(([l]) => langSet.add(l))
  })
  const langs = Array.from(langSet).slice(0, 8)

  // Normalize to percentages
  const indicator = langs.map(l => ({ name: l, max: 100 }))
  const series = selectedData.value.map((c, i) => {
    const total = Object.values(c.total).reduce((a, b) => a + b, 0)
    return {
      value: langs.map(l => Math.round(((c.total[l] || 0) / total) * 100)),
      name: c.title,
    }
  })

  const seriesColors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']

  return {
    tooltip: {},
    legend: {
      data: selectedData.value.map(c => c.title),
      textStyle: { color: '#aaa' },
      top: 0,
    },
    radar: {
      indicator,
      shape: 'polygon',
      axisName: { color: '#aaa' },
      splitLine: { lineStyle: { color: '#333' } },
      splitArea: { areaStyle: { color: ['transparent'] } },
      axisLine: { lineStyle: { color: '#444' } },
    },
    series: [{
      type: 'radar',
      data: series.map((s, i) => ({
        ...s,
        areaStyle: { opacity: 0.15, color: seriesColors[i] },
        lineStyle: { color: seriesColors[i] },
        itemStyle: { color: seriesColors[i] },
      })),
    }],
  }
})

// Grouped bar chart
const barOption = computed(() => {
  if (selectedData.value.length < 2 || !meta.value) return {}
  const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']

  // Top 8 languages across all selected
  const langSet = new Set<string>()
  selectedData.value.forEach(c => {
    Object.entries(c.total).sort((a, b) => b[1] - a[1]).slice(0, 5).forEach(([l]) => langSet.add(l))
  })
  const langs = Array.from(langSet).slice(0, 8)

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: selectedData.value.map(c => c.title), textStyle: { color: '#aaa' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: langs,
      axisLabel: { color: '#aaa', rotate: 15 },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: { type: 'value', axisLabel: { color: '#aaa', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#333' } } },
    series: selectedData.value.map((c, i) => {
      const total = Object.values(c.total).reduce((a, b) => a + b, 0)
      return {
        name: c.title,
        type: 'bar',
        data: langs.map(l => Math.round(((c.total[l] || 0) / total) * 100)),
        itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] },
      }
    }),
  }
})
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <h1 class="text-3xl font-bold text-white mb-2">{{ t('compare.title') }}</h1>
      <p class="text-gray-400 mb-8">{{ t('compare.subtitle') }}</p>

      <!-- Conference Selector -->
      <div class="flex flex-wrap gap-3 mb-8">
        <div
          v-for="id in selectedIds"
          :key="id"
          class="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-1.5 text-sm"
        >
          <span class="text-white font-medium">{{ id }}</span>
          <button @click="removeConference(id)" class="text-gray-400 hover:text-red-400">×</button>
        </div>

        <div v-if="selectedIds.length < 4" ref="dropdownRef" class="relative">
          <input
            v-model="searchQuery"
            @focus="showDropdown = true"
            :placeholder="`${t('compare.add_conference')}...`"
            class="bg-gray-800 text-gray-300 text-sm rounded-lg px-3 py-1.5 border border-gray-600 w-56 outline-none focus:border-blue-500"
          >
          <ul
            v-show="showDropdown"
            class="absolute left-0 top-full mt-1 z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl max-h-64 overflow-y-auto w-96 p-0 list-none"
          >
            <li
              v-for="conf in filteredConferences"
              :key="conf.id"
              @mousedown.prevent="selectConference(conf.id)"
              class="px-3 py-1.5 text-sm hover:bg-gray-700 cursor-pointer flex items-center justify-between gap-2"
            >
              <span class="truncate">
                <span class="text-white font-medium">{{ conf.id }}</span>
                <span class="text-gray-500 ml-1 text-xs">{{ conf.description }}</span>
              </span>
              <span
                class="text-xs font-bold px-1.5 py-0.5 rounded shrink-0"
                :style="{ backgroundColor: getRankColor(conf.rank) + '22', color: getRankColor(conf.rank) }"
              >{{ conf.rank }}</span>
            </li>
            <li v-if="filteredConferences.length === 0" class="px-3 py-2 text-sm text-gray-500">No matches</li>
          </ul>
        </div>
      </div>

      <!-- Charts -->
      <div v-if="selectedData.length >= 2" class="grid lg:grid-cols-2 gap-8">
        <div class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('compare.radar_chart') }}</h3>
          <v-chart :option="radarOption" style="height: 450px" autoresize />
        </div>
        <div class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('compare.title') }}</h3>
          <v-chart :option="barOption" style="height: 450px" autoresize />
        </div>
      </div>

      <!-- Placeholder -->
      <div v-else class="text-center py-20">
        <div class="text-6xl mb-4 opacity-30">📊</div>
        <p class="text-gray-500 text-lg">{{ t('compare.no_selection') }}</p>
      </div>
    </div>
  </div>
</template>
