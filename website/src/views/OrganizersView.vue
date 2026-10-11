<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSeo } from '@/composables/useSeo'
import { useDataFetch } from '@/composables/useDataFetch'

const { t } = useI18n()
const { fetchFinances } = useDataFetch()

interface OrganizerCard {
  id: string
  title: string
  orgName: string
  scope: string
  yearFrom: number | null
  yearTo: number | null
  yearCount: number
}
const organizers = ref<OrganizerCard[]>([])
const loading = ref(true)

const SCOPE_KEYS: Record<string, string> = {
  single_conference: 'finances.scope.single_conference',
  society: 'finances.scope.society',
  foundation: 'finances.scope.foundation',
}

onMounted(async () => {
  try {
    const data = await fetchFinances()
    organizers.value = Object.entries(data.conferences ?? {})
      .filter(([, e]) => (e as { usable?: boolean }).usable)
      .map(([id, e]) => {
        const entry = e as { title?: string; org_name?: string; scope?: string; years?: Record<string, unknown> }
        const years = Object.keys(entry.years ?? {}).map(Number).sort((a, b) => a - b)
        return {
          id,
          title: entry.title || id,
          orgName: entry.org_name || '',
          scope: entry.scope || 'society',
          yearFrom: years[0] ?? null,
          yearTo: years[years.length - 1] ?? null,
          yearCount: years.length,
        }
      })
      .sort((a, b) => a.title.localeCompare(b.title))
  } catch {
    // empty state shown below
  } finally {
    loading.value = false
  }
})

useSeo({
  title: 'Organizers',
  description: 'The foundations behind CCF-A conferences — explore revenue, expenses and expense composition of each organizing foundation (IRS Form 990, 2011–2024).',
  path: '/organizers',
})
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-5xl mx-auto">
      <h1 class="text-3xl font-bold text-white mb-3">{{ t('organizers.title') }}</h1>
      <p class="text-gray-400 mb-8 max-w-3xl">{{ t('organizers.subtitle') }}</p>

      <div v-if="loading" class="text-gray-400">{{ t('finances.title') }}…</div>
      <div v-else-if="!organizers.length" class="text-gray-400">{{ t('organizers.empty') }}</div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <router-link
          v-for="o in organizers"
          :key="o.id"
          :to="{ name: 'conference-finances', params: { id: o.id } }"
          class="card p-5 bg-gray-800/50 border-gray-700/50 hover:border-blue-500/50 hover:bg-gray-800/80 transition-colors group no-underline"
        >
          <div class="flex items-start justify-between gap-2 mb-1.5">
            <span class="text-lg font-semibold text-blue-400 group-hover:text-blue-300">{{ o.title }}</span>
            <span class="text-[11px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 whitespace-nowrap">{{ t(SCOPE_KEYS[o.scope] ?? 'finances.scope.society') }}</span>
          </div>
          <p class="text-gray-300 text-sm mb-3 no-underline">{{ o.orgName }}</p>
          <div class="flex items-center justify-between text-xs text-gray-500">
            <span v-if="o.yearFrom !== null">{{ o.yearFrom }}–{{ o.yearTo }} · {{ t('organizers.fiscal_years', { n: o.yearCount }) }}</span>
            <span class="text-blue-400/80 group-hover:text-blue-300">{{ t('organizers.view_finances') }} →</span>
          </div>
        </router-link>
      </div>
    </div>
  </div>
</template>
