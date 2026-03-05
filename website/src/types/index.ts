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
