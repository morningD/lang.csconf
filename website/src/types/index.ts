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
  finances?: FinancesData
  finances_unavailable?: FinancesUnavailable
}

export interface FinanceYear {
  tax_period: string
  tax_year: number
  conference_year: number
  revenue: number | null
  expenses: number | null
  net_income: number | null
  net_assets: number | null
  pdf_url: string | null
  transcript?: string
  manual?: boolean
  revenue_mix?: Record<string, number> | null
  expense_mix?: Record<string, number> | null
  expense_partial?: Record<string, number | null> | null
  /** Per-locale findings ({en,zh,ja,de}); legacy years may hold a plain string[]. */
  findings?: Record<string, string[]> | string[]
}

export interface EntityOfficer {
  name: string
  title: string
  hours?: number | null
  compensation?: number | null
  affiliation?: string | null
  /** ISO country code of the affiliation's institution. */
  country?: string | null
}

export interface EntityCommitteeMember {
  name: string
  title: string
  affiliation?: string | null
  country?: string | null
}

export interface EntityContractor {
  name: string
  description?: string | null
  compensation: number
}

export interface EntityInsight {
  formation_year?: number | null
  state?: string | null
  officers?: EntityOfficer[]
  /** Official foundation board & advisors from the conference website (beyond the 990 officers). */
  board?: { members: EntityCommitteeMember[]; source?: string }
  /** Conference organizing committees by edition year, each with its source URL. */
  committee?: Record<string, { members: EntityCommitteeMember[]; source?: string }>
  /** Independent contractors ≥$100K disclosed in Part VII Section B. */
  contractors?: EntityContractor[]
  /** Highest compensated employees disclosed in Part VII Section A. */
  top_employees?: EntityOfficer[]
  findings?: string[]
  /** Localized explanation {en,zh,ja,de} (older data: plain string). */
  notes?: Record<string, string> | string | null
  tax_period?: string | null
}

export interface FinancesData {
  /** Official display name (e.g. "NeurIPS"), from the conference registry. */
  title?: string
  org_name: string
  ein: string
  scope: 'single_conference' | 'society' | 'foundation'
  /** Localized scope explanation {en,zh,ja,de} (older data: plain string). */
  scope_note: Record<string, string> | string
  usable: boolean
  propublica_url: string
  source: string
  fiscal_note: string
  /** Fiscal-year end month; drives the localized fiscal-note template. */
  fiscal_end_month?: number
  years: Record<string, FinanceYear>
  /** Per-year submission counts (accept_rates), for the chart overlay. */
  submissions?: Record<string, number>
  /** Per-year acceptance rate in percent (accepted/submitted), for the chart overlay. */
  accept_rates_pct?: Record<string, number>
  entity?: EntityInsight
}

export interface FinancesUnavailable {
  org_name: string
  scope_note: string
  source: string
}

export interface FinancesIndex {
  last_updated: string
  conferences: Record<string, FinancesData>
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
