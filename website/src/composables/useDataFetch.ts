import { ref } from 'vue'
import type { Meta, GlobalSummary, ConferenceIndex, ConferenceDetail, CategoryStats, RankStats } from '@/types'

const BASE_URL = import.meta.env.BASE_URL + 'data/stats/'
const cache = new Map<string, unknown>()

async function fetchJson<T>(path: string): Promise<T> {
  const url = BASE_URL + path
  if (cache.has(url)) {
    return cache.get(url) as T
  }
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`Failed to fetch ${url}: ${resp.status}`)
  const data = await resp.json()
  cache.set(url, data)
  return data as T
}

export function useDataFetch() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchMeta(): Promise<Meta> {
    return fetchJson<Meta>('meta.json')
  }

  async function fetchGlobalSummary(): Promise<GlobalSummary> {
    return fetchJson<GlobalSummary>('global_summary.json')
  }

  async function fetchConferencesIndex(): Promise<ConferenceIndex[]> {
    return fetchJson<ConferenceIndex[]>('conferences_index.json')
  }

  async function fetchConference(id: string): Promise<ConferenceDetail> {
    return fetchJson<ConferenceDetail>(`by_conference/${id}.json`)
  }

  async function fetchCategory(cat: string): Promise<CategoryStats> {
    return fetchJson<CategoryStats>(`by_category/${cat}.json`)
  }

  async function fetchRank(rank: string): Promise<RankStats> {
    return fetchJson<RankStats>(`by_rank/${rank}.json`)
  }

  return {
    loading,
    error,
    fetchMeta,
    fetchGlobalSummary,
    fetchConferencesIndex,
    fetchConference,
    fetchCategory,
    fetchRank,
  }
}
