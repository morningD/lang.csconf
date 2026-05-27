<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { ConferenceIndex, ConferenceDetail, Meta, AffiliationIndex, CCFCategory } from '@/types'

const { t } = useI18n()
const { fetchConferencesIndex, fetchConference, fetchMeta, fetchAffiliationIndex } = useDataFetch()

const allConferences = ref<ConferenceIndex[]>([])
const meta = ref<Meta | null>(null)
const selectedIds = ref<string[]>([])
const selectedData = ref<ConferenceDetail[]>([])
const loading = ref(true)

onMounted(async () => {
  document.addEventListener('click', onClickOutside)
  try {
    const [confs, m, idx] = await Promise.all([
      fetchConferencesIndex(), fetchMeta(), fetchAffiliationIndex(),
    ])
    allConferences.value = confs
    meta.value = m
    affilIndex.value = idx
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
  const rankOrder: Record<string, number> = { A: 0, B: 1, C: 2, N: 3 }
  matches.sort((a, b) => {
    const aId = a.id.toLowerCase().includes(q) ? 0 : a.title.toLowerCase().includes(q) ? 1 : 2
    const bId = b.id.toLowerCase().includes(q) ? 0 : b.title.toLowerCase().includes(q) ? 1 : 2
    return aId - bId || (rankOrder[a.rank] ?? 3) - (rankOrder[b.rank] ?? 3) || a.id.localeCompare(b.id)
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

// ============================================================
// Institution Comparison
// ============================================================

const affilIndex = ref<AffiliationIndex | null>(null)
const selectedInstitutions = ref<string[]>([])
const instSearchQuery = ref('')
const showInstDropdown = ref(false)
const instDropdownRef = ref<HTMLElement | null>(null)

const CATEGORIES: CCFCategory[] = ['AI', 'DB', 'NW', 'SE', 'CG', 'CT', 'HI', 'SC', 'DS', 'MX']
const CATEGORY_FULL: Record<string, string> = {
  AI: 'Artificial Intelligence',
  DB: 'Database / Data Mining',
  NW: 'Computer Networking',
  SE: 'Software Engineering / PL',
  CG: 'Computer Graphics & Multimedia',
  CT: 'Theory of Computation',
  HI: 'Human-Computer Interaction',
  SC: 'Network & Information Security',
  DS: 'Computer Architecture',
  MX: 'Interdisciplinary & Emerging',
}

const INST_ABBREV: Record<string, string> = {
  'Carnegie Mellon University': 'CMU',
  'Massachusetts Institute of Technology': 'MIT',
  'Stanford University': 'Stanford',
  'University of California, Berkeley': 'UCB',
  'University of California, Los Angeles': 'UCLA',
  'University of California, San Diego': 'UCSD',
  'University of Illinois at Urbana-Champaign': 'UIUC',
  'Georgia Institute of Technology': 'GT',
  'University of Texas at Austin': 'UT Austin',
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
  'New York University': 'NYU',
  'University of Chicago': 'UChicago',
  'Johns Hopkins University': 'JHU',
  'Tsinghua University': 'THU',
  'Peking University': 'PKU',
  'Zhejiang University': 'ZJU',
  'Shanghai Jiao Tong University': 'SJTU',
  'University of Science and Technology of China': 'USTC',
  'Chinese Academy of Sciences': 'CAS',
  'Chinese University of Hong Kong': 'CUHK',
  'University of Hong Kong': 'HKU',
  'Hong Kong University of Science and Technology': 'HKUST',
  'Fudan University': 'Fudan',
  'Nanjing University': 'NJU',
  'Harbin Institute of Technology': 'HIT',
  'Huazhong University of Science and Technology': 'HUST',
  'University of Oxford': 'Oxford',
  'University of Cambridge': 'Cambridge',
  'University College London': 'UCL',
  'Imperial College London': 'Imperial',
  'ETH Zurich': 'ETH',
  'École Polytechnique Fédérale de Lausanne': 'EPFL',
  'Technical University of Munich': 'TUM',
  'University of Toronto': 'UofT',
  'University of British Columbia': 'UBC',
  'National University of Singapore': 'NUS',
  'Nanyang Technological University': 'NTU',
  'Seoul National University': 'SNU',
  'KAIST': 'KAIST',
  'University of Tokyo': 'UTokyo',
  'Google': 'Google',
  'Google DeepMind': 'DeepMind',
  'Microsoft Research': 'MSR',
  'Shanghai AI Lab': 'Shanghai AI Lab',
}

const COUNTRY_OVERRIDES: Record<string, string> = { TW: 'CN' }
const countryFlag = (code: string) => {
  const c = COUNTRY_OVERRIDES[code] || code
  return String.fromCodePoint(...[...c.toUpperCase()].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65))
}

function abbreviateInst(name: string) {
  if (INST_ABBREV[name]) return INST_ABBREV[name]
  const SKIP = new Set(['of', 'at', 'the', 'and', 'for', 'in', 'de', 'la', 'le', 'du', 'di'])
  const words = name.split(/[\s,]+/).filter(w => w && !SKIP.has(w.toLowerCase()))
  const initials = words.map(w => w[0]?.toUpperCase()).filter(Boolean).join('')
  return initials || name
}

const filteredInstitutions = computed(() => {
  if (!affilIndex.value) return []
  const q = instSearchQuery.value.trim().toLowerCase()
  if (!q) return []
  const names = affilIndex.value.name_list
  return names.filter(n => n.toLowerCase().includes(q)).slice(0, 20)
})

function addInstitution(name: string) {
  if (name && !selectedInstitutions.value.includes(name) && selectedInstitutions.value.length < 3) {
    selectedInstitutions.value.push(name)
  }
}

function removeInstitution(name: string) {
  selectedInstitutions.value = selectedInstitutions.value.filter(n => n !== name)
}

function selectInstitution(name: string) {
  addInstitution(name)
  instSearchQuery.value = ''
  showInstDropdown.value = false
}

function onClickOutsideInst(e: MouseEvent) {
  if (instDropdownRef.value && !instDropdownRef.value.contains(e.target as Node)) {
    showInstDropdown.value = false
  }
}

// Category radar chart for selected institutions
const instRadarOption = computed(() => {
  if (!affilIndex.value || selectedInstitutions.value.length === 0) return {}

  const institutions = affilIndex.value.institutions
  const seriesColors = ['#3498db', '#e74c3c', '#2ecc71']

  // Find max value across all selected institutions for each category
  const maxValues: Record<string, number> = {}
  for (const cat of CATEGORIES) {
    maxValues[cat] = 0
    for (const name of selectedInstitutions.value) {
      const val = institutions[name]?.by_category?.[cat] || 0
      if (val > maxValues[cat]) maxValues[cat] = val
    }
  }

  const indicator = CATEGORIES.map(cat => ({
    name: cat,
    max: Math.max((maxValues[cat] || 0) * 1.2, 1),
  }))

  const seriesData = selectedInstitutions.value.map((name, i) => {
    const inst = institutions[name]
    const flag = inst?.country ? countryFlag(inst.country) : ''
    return {
      value: CATEGORIES.map(cat => inst?.by_category?.[cat] || 0),
      name: `${abbreviateInst(name)} ${flag}`,
    }
  })

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const name = selectedInstitutions.value[params.dataIndex] || (params.name as string)
        const inst = institutions[name]
        const vals = params.value as number[]
        let html = `<b>${abbreviateInst(name)}</b><br/>`
        CATEGORIES.forEach((cat, idx) => {
          if (vals[idx]! > 0) {
            html += `${CATEGORY_FULL[cat]}: ${vals[idx]} papers<br/>`
          }
        })
        return html
      },
    },
    legend: {
      data: seriesData.map(s => s.name),
      textStyle: { color: '#aaa', fontSize: 11 },
      top: 0,
    },
    radar: {
      indicator,
      shape: 'polygon',
      axisName: { color: '#aaa', fontSize: 11 },
      splitLine: { lineStyle: { color: '#333' } },
      splitArea: { areaStyle: { color: ['transparent'] } },
      axisLine: { lineStyle: { color: '#444' } },
    },
    series: [{
      type: 'radar',
      data: seriesData.map((s, i) => ({
        ...s,
        areaStyle: { opacity: 0.15, color: seriesColors[i] },
        lineStyle: { color: seriesColors[i] },
        itemStyle: { color: seriesColors[i] },
      })),
    }],
  }
})

// Conference ranking details for selected institutions
const instRankDetails = computed(() => {
  if (!affilIndex.value || selectedInstitutions.value.length === 0) return {} as Record<string, Array<{
    confId: string
    title: string
    rank: string
    confRank: string
    entries: Array<{ name: string; count: number; rank: number; latest?: { rank: number; count: number; year: number } }>
  }>>

  const conferences = affilIndex.value.conferences
  const institutions = affilIndex.value.institutions

  // Collect all conferences that at least one selected institution appears in
  const confIds = new Set<string>()
  for (const name of selectedInstitutions.value) {
    const inst = institutions[name]
    if (inst) {
      for (const confId of Object.keys(inst.conferences)) {
        confIds.add(confId)
      }
    }
  }

  // Group by category
  const byCategory: Record<string, Array<{
    confId: string
    title: string
    rank: string
    confRank: string
    entries: Array<{ name: string; count: number; rank: number; latest?: { rank: number; count: number; year: number } }>
  }>> = {}

  for (const confId of confIds) {
    const conf = conferences[confId]
    if (!conf) continue
    const cat = conf.category || 'Other'

    const entries = selectedInstitutions.value.map(name => {
      const instConf = institutions[name]?.conferences?.[confId]
      return {
        name,
        count: instConf?.count || 0,
        rank: instConf?.rank || 0,
        latest: instConf?.latest,
      }
    })

    // Only include if at least one institution has data
    if (entries.some(e => e.count > 0)) {
      if (!byCategory[cat]) byCategory[cat] = []
      byCategory[cat].push({
        confId,
        title: conf.title,
        rank: conf.rank,
        confRank: conf.rank,
        entries,
      })
    }
  }

  // Sort each category by total papers (sum across institutions) descending
  for (const cat of Object.keys(byCategory)) {
    byCategory[cat]!.sort((a, b) => {
      const totalA = a.entries.reduce((s, e) => s + e.count, 0)
      const totalB = b.entries.reduce((s, e) => s + e.count, 0)
      return totalB - totalA
    })
  }

  return byCategory
})

const hasInstData = computed(() => selectedInstitutions.value.length > 0 && Object.keys(instRankDetails.value).length > 0)
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
          <span class="text-white font-medium">{{ allConferences.find(c => c.id === id)?.title || id }}</span>
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
                <span class="text-white font-medium">{{ conf.title }}</span>
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

      <!-- Institution Comparison -->
      <div v-if="affilIndex" class="mt-10">
        <h2 class="text-2xl font-bold text-white mb-1">{{ t('compare.institution_title') }}</h2>
        <p class="text-gray-400 mb-6">{{ t('compare.institution_subtitle') }}</p>

        <!-- Institution Selector -->
        <div class="flex flex-wrap gap-3 mb-6">
          <div
            v-for="name in selectedInstitutions"
            :key="name"
            class="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-1.5 text-sm"
          >
            <span class="text-white font-medium">{{ abbreviateInst(name) }}</span>
            <span v-if="affilIndex.institutions[name]?.country" class="text-base">{{ countryFlag(affilIndex.institutions[name].country) }}</span>
            <button @click="removeInstitution(name)" class="text-gray-400 hover:text-red-400">×</button>
          </div>

          <div v-if="selectedInstitutions.length < 3" ref="instDropdownRef" class="relative">
            <input
              v-model="instSearchQuery"
              @focus="showInstDropdown = true"
              :placeholder="t('compare.institution_search')"
              class="bg-gray-800 text-gray-300 text-sm rounded-lg px-3 py-1.5 border border-gray-600 w-64 outline-none focus:border-blue-500"
            >
            <ul
              v-show="showInstDropdown && filteredInstitutions.length > 0"
              class="absolute left-0 top-full mt-1 z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl max-h-64 overflow-y-auto w-96 p-0 list-none"
            >
              <li
                v-for="instName in filteredInstitutions"
                :key="instName"
                @mousedown.prevent="selectInstitution(instName)"
                class="px-3 py-1.5 text-sm hover:bg-gray-700 cursor-pointer flex items-center gap-2"
              >
                <span v-if="affilIndex.institutions[instName]?.country" class="text-base">{{ countryFlag(affilIndex.institutions[instName].country) }}</span>
                <span class="text-white">{{ abbreviateInst(instName) }}</span>
                <span class="text-gray-500 text-xs truncate">{{ instName }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- Category Radar Chart -->
        <div v-if="selectedInstitutions.length > 0" class="card p-6 bg-gray-800/50 border-gray-700/50 mb-6">
          <v-chart :option="instRadarOption" style="height: 450px" autoresize />
          <p class="text-xs text-gray-500 mt-2">
            {{ t('compare.institution_coverage', {
              conferences: affilIndex.coverage.conferences,
              categories: affilIndex.coverage.categories,
              pct: affilIndex.coverage.coverage_pct
            }) }}
          </p>
        </div>

        <!-- Ranking Details by Category -->
        <div v-if="hasInstData">
          <div v-for="cat in Object.keys(instRankDetails).sort()" :key="cat" class="mb-6">
            <h3 class="text-lg font-semibold text-white mb-3">
              {{ cat }} <span class="text-gray-500 text-sm font-normal">— {{ CATEGORY_FULL[cat] || cat }}</span>
            </h3>
            <div class="card bg-gray-800/50 border-gray-700/50 overflow-hidden">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-gray-700">
                    <th class="text-left px-4 py-2 text-gray-400 font-medium">Conference</th>
                    <th v-for="name in selectedInstitutions" :key="name" class="text-center px-4 py-2 text-gray-400 font-medium">
                      {{ abbreviateInst(name) }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in instRankDetails[cat]"
                    :key="row.confId"
                    class="border-b border-gray-700/50 hover:bg-gray-700/30"
                  >
                    <td class="px-4 py-2">
                      <span class="text-white">{{ row.title }}</span>
                      <span
                        class="ml-1.5 text-xs font-bold px-1 py-0.5 rounded"
                        :style="{ backgroundColor: getRankColor(row.confRank) + '22', color: getRankColor(row.confRank) }"
                      >{{ row.confRank }}</span>
                    </td>
                    <td v-for="entry in row.entries" :key="entry.name" class="text-center px-4 py-2">
                      <template v-if="entry.count > 0">
                        <span class="text-white font-medium">#{{ entry.rank }}</span>
                        <span class="text-gray-500 text-xs ml-1">({{ entry.count }})</span>
                        <div v-if="entry.latest" class="text-xs text-gray-500">
                          {{ entry.latest.year }}: #{{ entry.latest.rank }} ({{ entry.latest.count }})
                        </div>
                      </template>
                      <span v-else class="text-gray-600">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- No institution selected -->
        <div v-else class="text-center py-12">
          <div class="text-5xl mb-3 opacity-20">🏛️</div>
          <p class="text-gray-500">{{ t('compare.institution_subtitle') }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
