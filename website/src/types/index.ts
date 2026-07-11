export interface ConferenceIndex {
  id: string
  title: string
  description: string
  category: string
  rank: string
  total_papers: number
  dominant_language: string
  dominant_pct: number
  lang_pcts: Record<string, number>
  latest_year: number
  latest_lang: string
  latest_pct: number
  latest_lang_pcts: Record<string, number>
  latest_trend: number | null
}

export interface ConferenceDetail {
  id: string
  title: string
  description: string
  category: string
  rank: string
  dblp: string | string[]
  years: number[]
  by_year: Record<string, Record<string, number>>
  total: Record<string, number>
  venues?: Record<string, { city: string; country: string }>
  rank_history?: Record<string, string>
  accept_rates?: Array<{ year: number; submitted: number; accepted: number }>
  note?: string
  affiliations?: AffiliationData
}

export interface GlobalSummary {
  total: Record<string, number>
  by_year: Record<string, Record<string, number>>
}

export interface Meta {
  last_updated: string
  total_papers: number
  total_conferences: number
  year_range: [number, number]
  languages: string[]
  language_colors: Record<string, string>
}

export interface CategoryStats {
  category: string
  conferences: string[]
  by_year: Record<string, Record<string, number>>
  total: Record<string, number>
}

export interface RankStats {
  rank: string
  conferences: string[]
  by_year: Record<string, Record<string, number>>
  total: Record<string, number>
}

export type CCFRank = 'A' | 'B' | 'C' | 'N'
export type CCFCategory = 'AI' | 'DB' | 'NW' | 'SE' | 'CG' | 'CT' | 'HI' | 'SC' | 'DS' | 'MX'

export interface AffiliationData {
  total_covered: number
  total_papers: number
  coverage_pct: number
  top: AffiliationEntry[]
  by_year?: Record<string, AffiliationYearData>
  sources?: string[]
}

export interface AffiliationEntry {
  name: string
  count: number
  pct: number
  country?: string
}

export interface AffiliationYearData {
  total_covered: number
  total_papers: number
  coverage_pct: number
  top: AffiliationEntry[]
}

export interface AffiliationTrendManifestEntry {
  url: string
  candidate_count: number
  total_institution_count: number
  years: string[]
}

export interface AffiliationTrendManifest {
  schema_version: number
  generated_at: string
  top_n: number
  slices: Record<string, AffiliationTrendManifestEntry>
}

export interface AffiliationTrendChunk extends AffiliationTrendSlice {
  schema_version: number
  slice_id: string
  candidate_limit: number
  candidate_count: number
  total_institution_count: number
}


export interface AffiliationTrendSlice {
  years: string[]
  institutions: Record<string, { country: string; by_year: Record<string, number> }>
  total_by_year: Record<string, number>
  coverage_by_year: Record<string, { covered: number; total: number }>
  conferences_by_year?: Record<string, string[]>
}

export interface AffiliationIndex {
  conferences: Record<string, { title: string; category: string; rank: string }>
  institutions: Record<string, AffiliationIndexEntry>
  name_list: string[]
  coverage: { conferences: number; categories: number; coverage_pct: number }
}

export interface AffiliationIndexEntry {
  country: string
  by_category: Record<string, number>
  conferences: Record<string, {
    rank: number
    count: number
    pct: number
    latest?: { rank: number; count: number; year: number }
  }>
}
