<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import { useSeo } from '@/composables/useSeo'
import type { FinancesIndex, FinancesData, FinanceYear } from '@/types'

const route = useRoute()
const { t, te, locale } = useI18n()
const { fetchFinances, fetchConference } = useDataFetch()

const confId = computed(() => route.params.id as string)

useSeo({
  title: 'Conference Financial Analysis',
  description: 'Financial analysis of CCF-A AI conferences: revenue and expense composition, board members and organizing committees, drawn from public IRS Form 990 filings (ProPublica Nonprofit Explorer).',
  path: `/conference/${confId.value}/finances`,
})

const financesIndex = ref<FinancesIndex | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const metric = ref<'ALL' | 'revenue' | 'expenses' | 'net_income' | 'net_assets' | 'revenue_mix' | 'expenses_mix'>('ALL')
const compareSelection = ref<string[]>([])
const compareMetric = ref<'revenue' | 'expenses' | 'net_income' | 'net_assets'>('revenue')

const METRIC_COLORS: Record<string, string> = {
  revenue: '#60a5fa',
  expenses: '#fb923c',
  net_income: '#34d399',
  net_assets: '#a78bfa',
}

const COMPARE_SERIES_COLORS = ['#60a5fa', '#34d399', '#f472b6', '#fbbf24', '#a78bfa', '#fb923c']

const REVENUE_MIX_COLORS: Record<string, string> = {
  contributions: '#818cf8',
  program: '#60a5fa',
  investment: '#34d399',
  royalties: '#fbbf24',
  misc: '#9ca3af',
}
// 20 distinguishable hues — expense categories exceed the old 10-color palette
const EXPENSE_MIX_PALETTE = [
  '#60a5fa', '#a78bfa', '#34d399', '#fbbf24', '#fb923c',
  '#f472b6', '#22d3ee', '#f87171', '#818cf8', '#a3e635',
  '#e879f9', '#2dd4bf', '#facc15', '#fb7185', '#38bdf8',
  '#c084fc', '#4ade80', '#fdba74', '#94a3b8', '#67e8f9',
]

onMounted(async () => {
  try {
    financesIndex.value = await fetchFinances()
    // Preselect a few major conferences for the compare section
    const usable = usableConfs.value
    compareSelection.value = [confId.value, ...usable.filter(c => c !== confId.value).slice(0, 2)]
      .filter(c => usable.includes(c))
  } catch (e) {
    error.value = 'Failed to load finances data'
  } finally {
    loading.value = false
  }
})

// ---- Venue labels under the year axis (from the conference page's venue data) ----
const venueMap = ref<Record<string, { city: string; country: string }>>({})
watch(confId, async (id) => {
  try {
    const detail = await fetchConference(id)
    venueMap.value = detail.venues ?? {}
  } catch {
    venueMap.value = {}
  }
}, { immediate: true })

/** Two-line axis label: year over host city (truncated), plain year when unknown. */
function venueAxisLabel(y: number): string {
  const v = venueMap.value[String(y)]
  if (!v?.city) return String(y)
  const city = v.city.length > 12 ? `${v.city.slice(0, 11)}…` : v.city
  return `{yr|${y}}\n{loc|${city}}`
}

const VENUE_AXIS_RICH = {
  yr: { color: '#9ca3af', fontSize: 10, lineHeight: 13, align: 'center' as const },
  loc: { color: '#6b7280', fontSize: 9, lineHeight: 11, align: 'center' as const },
}

const currentEntry = computed<FinancesData | null>(() => {
  return financesIndex.value?.conferences[confId.value] ?? null
})

/** Official display name (e.g. "NeurIPS"), falling back to the raw id. */
const displayName = computed(() => currentEntry.value?.title ?? confId.value)

const currentUsable = computed(() => currentEntry.value?.usable === true && Object.keys(currentEntry.value.years).length > 0)

const unavailableEntry = computed(() => {
  const e = financesIndex.value?.conferences[confId.value]
  return e && !e.usable ? e : null
})

const usableConfs = computed<string[]>(() => {
  const confs = financesIndex.value?.conferences ?? {}
  return Object.keys(confs).filter(c => confs[c]?.usable === true && Object.keys(confs[c]?.years ?? {}).length > 0)
})

function sortedYears(entry: FinancesData): number[] {
  return Object.keys(entry.years).map(Number).sort((a, b) => a - b)
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(abs >= 1e7 ? 1 : 2)}M`
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`
  return `${sign}$${abs}`
}

function valueOf(entry: FinancesData, year: number, key: keyof FinanceYear): number | null {
  return (entry.years[String(year)]?.[key] as number | null) ?? null
}

const latestStats = computed(() => {
  if (!currentEntry.value || !currentUsable.value) return null
  const entry = currentEntry.value
  const years = sortedYears(entry)
  if (!years.length) return null
  const latestYear = years[years.length - 1]!
  const latest = entry.years[String(latestYear)]
  if (!latest) return null
  const prevYear = years.length >= 2 ? years[years.length - 2]! : null
  let peakRevenue: { year: number; value: number } | null = null
  for (const y of years) {
    const v = valueOf(entry, y, 'revenue')
    if (v != null && (!peakRevenue || v > peakRevenue.value)) peakRevenue = { year: y, value: v }
  }
  return { latestYear, latest, prevYear, peakRevenue }
})

/** Year-over-year change of a metric vs the prior fiscal year. */
function yoyOf(key: 'revenue' | 'expenses' | 'net_income' | 'net_assets'): { pct: number; dir: 'up' | 'down' | 'flat' } | null {
  const s = latestStats.value
  if (!s || !s.prevYear) return null
  const cur = valueOf(currentEntry.value!, s.latestYear, key)
  const prev = valueOf(currentEntry.value!, s.prevYear, key)
  if (cur == null || prev == null || prev === 0) return null
  const pct = ((cur - prev) / Math.abs(prev)) * 100
  const dir = Math.abs(pct) < 0.05 ? 'flat' : pct > 0 ? 'up' : 'down'
  return { pct, dir }
}

/** Grow-green/shrink-orange for income metrics; inverted for expenses. */
function yoyClass(key: 'revenue' | 'expenses' | 'net_income' | 'net_assets'): string {
  const y = yoyOf(key)
  if (!y || y.dir === 'flat') return 'text-gray-500'
  const upIsGood = key !== 'expenses'
  if (y.dir === 'up') return upIsGood ? 'text-emerald-400' : 'text-orange-400'
  return upIsGood ? 'text-orange-400' : 'text-emerald-400'
}

function yoyArrow(key: 'revenue' | 'expenses' | 'net_income' | 'net_assets'): string {
  const y = yoyOf(key)
  return y ? (y.dir === 'up' ? '↗' : y.dir === 'down' ? '↘' : '→') : ''
}

const SCOPE_LABEL_KEYS: Record<string, string> = {
  single_conference: 'finances.scope.single_conference',
  society: 'finances.scope.society',
  foundation: 'finances.scope.foundation',
}

// ---- Filing rows, newest first (used by the annual breakdown and the archive) ----
interface FilingRow { year: number; data: FinanceYear }

const filings = computed<FilingRow[]>(() => {
  if (!currentEntry.value || !currentUsable.value) return []
  const entry = currentEntry.value
  return sortedYears(entry)
    .map(y => ({ year: y, data: entry.years[String(y)]! }))
    .reverse()
})

// ---- Composition bars / pies ----
interface MixSegment { key: string; label: string; value: number; pct: number; color: string }

/** Localized category label; falls back to a prettified key for unmapped categories. */
function mixLabel(key: string): string {
  const tk = `finances.mix_categories.${key}`
  if (te(tk)) return t(tk)
  return key.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

// ---- Stacked-view legend click = "show only this category" (click again to restore all) ----
// Selected maps must be EXPLICIT for every key: absent keys default to visible.
// Revenue Mix and Expense Mix keep separate solo states.
const revStackSelected = ref<Record<string, boolean> | null>(null)
const expStackSelected = ref<Record<string, boolean> | null>(null)

/** Localized legend names of a composition view, in series order. */
function mixViewKeys(row: FilingRow, id: 'rev' | 'exp'): string[] {
  return (yearMixes(row).find(m => m.id === id)?.segments ?? []).map(s => s.label)
}



/** Localized one-line definition of a category (Form 990 line-item meaning). */
function mixDesc(key: string): string {
  const tk = `finances.mix_desc.${key}`
  return te(tk) ? t(tk) : ''
}

/** Pick the current locale from a localized data field, falling back to English. */
function localizedText(v: Record<string, string> | string | null | undefined): string {
  if (!v) return ''
  if (typeof v === 'string') return v
  return v[locale.value] ?? v.en ?? ''
}

/** Localized fiscal-year note: templated when fiscal_end_month is known, else the raw string. */
function fiscalNoteOf(entry: FinancesData): string {
  const m = entry.fiscal_end_month
  if (m && m <= 6) return t('finances.fiscal_note_fy', { month: m })
  if (m) return t('finances.fiscal_note_calendar')
  return entry.fiscal_note
}

// Common officer titles seen in Form 990 Part VII → i18n keys
const TITLE_MAP: Record<string, string> = {
  president: 'president',
  'president-elect': 'president_elect',
  'president elect': 'president_elect',
  'past president': 'past_president',
  treasurer: 'treasurer',
  secretary: 'secretary',
  'secretary-treasurer': 'secretary_treasurer',
  'secretary/treasurer': 'secretary_treasurer',
  'executive director': 'executive_director',
  'executive di': 'executive_director',
  director: 'director',
  trustee: 'trustee',
  'vice president': 'vice_president',
  'vice president elect': 'vice_president_elect',
  'vice-president': 'vice_president',
  chair: 'chair',
  chairman: 'chair',
  chairperson: 'chair',
  'board member': 'board_member',
  member: 'member',
  'cl editor': 'cl_editor',
  counsel: 'counsel',
  'legal advisor': 'legal_advisor',
  'finance director': 'finance_director',
  'operations director': 'operations_director',
  'development director': 'development_director',
  'finance and hr director': 'finance_hr_director',
  'conference director': 'conference_director',
  'dev./grants manager': 'dev_grants_manager',
  'dev. / grants manager': 'dev_grants_manager',
  'former board member': 'former_board_member',
  'emeritus member': 'emeritus_member',
  'advisory board member': 'advisory_board_member',
}

// Conference-organizing role phrases (longest first) → i18n keys under finances.entity_roles.
// Applied as longest-match replacement so compound titles like
// "Mexico City Program Chair (NeurIPS 2025)" localize except proper nouns.
const ROLE_PHRASES: [string, string][] = [
  ['Senior Program Chair', 'senior_program_chair'],
  ['Program Chair Assistant', 'program_chair_assistant'],
  ['Position Paper Track Assistant Chair', 'assistant_chair'],
  ['Position Paper Track Chair', 'track_chair'],
  ['Ethics Review Chair', 'ethics_review_chair'],
  ['Scientific Integrity Chair', 'scientific_integrity_chair'],
  ['Communication and Next Generation Chair', 'communication_next_generation_chair'],
  ['Volunteer Chair', 'volunteer_chair'],
  ['Accessibility and Diversity & Inclusion Chair', 'accessibility_chair'],
  ['Next Generation and Accessibility Chair', 'accessibility_chair'],
  ['Datasets and Benchmarks Chair', 'track_chair'],
  ['Datasets & Benchmarks Track Chair', 'track_chair'],
  ['Creative AI Track Chair', 'track_chair'],
  ['Associate Chair', 'associate_chair'],
  ['Assistant Chair', 'assistant_chair'],
  ['General Chair', 'general_chair'],
  ['Chair of EACL', 'eacl_chair'],
  ['Program Chair', 'program_chair'],
  ['Workshop Chair', 'workshop_chair'],
  ['Tutorial Chair', 'tutorial_chair'],
  ['Social Chair', 'social_chair'],
  ['Publications Chair', 'publications_chair'],
  ['Publicity Chair', 'publicity_chair'],
  ['Local Chair', 'local_chair'],
  ['Press Chair', 'press_chair'],
  ['Ethics Chair', 'ethics_chair'],
  ['Communication Chair', 'communication_chair'],
  ['Communications Chair', 'communications_chair'],
  ['Education Chair', 'education_chair'],
  ['Competition Chair', 'competition_chair'],
  ['Journal Chair', 'journal_chair'],
  ['Accessibility Chair', 'accessibility_chair'],
  ['Affinity Chair', 'affinity_chair'],
  ['Workflow Chair', 'workflow_chair'],
  ['Experiment Chair', 'experiment_chair'],
  ['Workflow Manager', 'workflow_manager'],
  ['Advisory Board Member', 'advisory_board_member'],
  ['Former Board Member', 'former_board_member'],
  ['Emeritus Member', 'emeritus_member'],
  ['Track Chair', 'track_chair'],
  ['Board Member', 'board_member'],
  ['Legal Advisor', 'legal_advisor'],
  ['Chair', 'chair'],
  ['Member', 'member'],
]

/** Localized officer title: exact map first, then longest-match phrase replacement; trailing "(context)" kept verbatim. */
function officerTitleOf(title: string): string {
  const raw = title.trim()
  let core = raw
  let paren = ''
  const pm = raw.match(/^(.*?)\s*\(([^)]+)\)\s*$/)
  if (pm && pm[1]) {
    core = pm[1].trim()
    paren = ` (${pm[2]})`
  }
  const mapped = TITLE_MAP[core.toLowerCase()]
  if (mapped) {
    const tk = `finances.entity_titles.${mapped}`
    if (te(tk)) return t(tk) + paren
  }
  let out = core
  for (const [phrase, key] of ROLE_PHRASES) {
    const rk = `finances.entity_roles.${key}`
    if (!te(rk)) continue
    const rx = new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
    if (rx.test(out)) out = out.replace(rx, t(rk))
  }
  return out + paren
}

function countryLabel(code: string): string {
  const tk = `finances.country.${code}`
  return te(tk) ? t(tk) : code
}

/** Country distribution of board + officers' institutions (dedup by name, board takes precedence), largest first. */
const officerCountries = computed(() => {
  const entity = currentEntry.value?.entity
  if (!entity) return []
  const byName = new Map<string, { name: string; country?: string | null }>()
  for (const o of entity.officers ?? []) byName.set(o.name, o)
  for (const m of entity.board?.members ?? []) if (m.country !== undefined) byName.set(m.name, m)
  const counts = new Map<string, number>()
  for (const m of byName.values()) {
    if (!m.country) continue
    counts.set(m.country, (counts.get(m.country) ?? 0) + 1)
  }
  const total = [...counts.values()].reduce((a, b) => a + b, 0)
  if (!total) return []
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([code, n], i) => ({
      code,
      label: countryLabel(code),
      n,
      pct: Math.round((n / total) * 100),
      color: EXPENSE_MIX_PALETTE[i % EXPENSE_MIX_PALETTE.length] ?? '#9ca3af',
    }))
})

// ---- Committee year dropdown ----
const committeeYears = computed<string[]>(() =>
  Object.keys(currentEntry.value?.entity?.committee ?? {}).sort((a, b) => Number(b) - Number(a))
)
const committeeYear = ref<string | null>(null)
const committeeEntry = computed<{ members: { name: string; title: string; affiliation?: string | null; country?: string | null }[]; source?: string } | null>(() => {
  const c = currentEntry.value?.entity?.committee
  if (!c || !committeeYears.value.length) return null
  const y = committeeYear.value && c[committeeYear.value] ? committeeYear.value : committeeYears.value[0]!
  return c[y] ?? null
})
const committeeYearModel = computed({
  get: () => committeeYear.value ?? committeeYears.value[0] ?? '',
  set: (v: string) => { committeeYear.value = v },
})

/** Round up to a human-friendly axis bound. */
function niceCeil(v: number): number {
  if (v <= 0) return 0
  const exp = Math.floor(Math.log10(v))
  const f = v / 10 ** exp
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 4 ? 4 : f <= 8 ? 8 : 10) * 10 ** exp
}

/** Currently soloed category label in the stacked view (null = show all). */
function soloedMixName(isRevenue: boolean): string | null {
  const cur = isRevenue ? revStackSelected.value : expStackSelected.value
  if (!cur) return null
  const trues = Object.keys(cur).filter(k => cur[k] === true)
  return trues.length === 1 ? trues[0]! : null
}

/** Legend chips of the current stacked composition view (name + color from the series). */
const stackLegendItems = computed(() => {
  const series = (mixStackOption.value.series ?? []) as { name: string; itemStyle?: { color?: string } }[]
  return series.map(sr => ({ name: sr.name, color: sr.itemStyle?.color ?? '#9ca3af' }))
})

/** true when exactly this chip is soloed (others hidden). */
function isSoloChip(name: string): boolean {
  const cur = metric.value === 'revenue_mix' ? revStackSelected.value : expStackSelected.value
  if (!cur) return false
  const values = Object.values(cur)
  return cur[name] === true && values.filter(v => v).length === 1
}

/** Chip click: solo this category, or restore all if it was already soloed. */
function onStackChip(name: string) {
  const isRev = metric.value === 'revenue_mix'
  const names = stackLegendItems.value.map(i => i.name)
  const cur = isRev ? revStackSelected.value : expStackSelected.value
  const soloedOnName = !!cur && cur[name] === true && names.every(n => cur[n] === (n === name))
  const next = soloedOnName ? null : Object.fromEntries(names.map(n => [n, n === name]))
  if (isRev) revStackSelected.value = next
  else expStackSelected.value = next
}

/** Stable per-category color: one palette slot per expense key of this conference (union across years). */
const expenseColorMap = computed<Record<string, string>>(() => {
  const entry = currentEntry.value
  if (!entry) return {}
  const keys: string[] = []
  for (const y of Object.keys(entry.years)) {
    const mix = entry.years[y]?.expense_mix
    if (mix) for (const k of Object.keys(mix)) if ((mix[k] ?? 0) > 0 && !keys.includes(k)) keys.push(k)
  }
  const map: Record<string, string> = {}
  keys.forEach((k, i) => {
    map[k] = EXPENSE_MIX_PALETTE[i % EXPENSE_MIX_PALETTE.length] ?? '#9ca3af'
  })
  return map
})

function buildMix(mix: Record<string, number>, paletteMap: Record<string, string>): MixSegment[] {
  const entries = Object.entries(mix).filter(([, v]) => v != null && v > 0)
  const total = entries.reduce((s, [, v]) => s + v, 0)
  if (total <= 0) return []
  return entries.map(([k, v]) => ({
    key: k,
    label: mixLabel(k),
    value: v,
    pct: Math.round((v / total) * 100),
    color: paletteMap[k] ?? '#9ca3af',
  }))
}

function yearMixes(row: FilingRow): { id: 'rev' | 'exp'; label: string; segments: MixSegment[] }[] {
  const out: { id: 'rev' | 'exp'; label: string; segments: MixSegment[] }[] = []
  if (row.data.revenue_mix) {
    const s = buildMix(row.data.revenue_mix, REVENUE_MIX_COLORS)
    if (s.length) out.push({ id: 'rev', label: t('finances.mix_revenue'), segments: s })
  }
  if (row.data.expense_mix) {
    const s = buildMix(row.data.expense_mix, expenseColorMap.value)
    if (s.length) out.push({ id: 'exp', label: t('finances.mix_expenses'), segments: s })
  }
  return out
}

function mixTotal(segments: MixSegment[]): number {
  return segments.reduce((s, seg) => s + seg.value, 0)
}

function pieOption(segments: MixSegment[]) {
  return {
    backgroundColor: 'transparent',
    legend: {
      textStyle: { color: '#9ca3af', fontSize: 10 },
      bottom: 0,
      type: 'scroll',
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (p: { name: string; value: number; percent: number }) => {
        const seg = segments.find(s => s.label === p.name)
        const desc = seg ? mixDesc(seg.key) : ''
        return `${p.name}: ${fmtMoney(p.value)} (${p.percent}%)${desc ? `<br/><span style="color:#9ca3af">${desc}</span>` : ''}`
      },
    },
    series: [
      {
        type: 'pie',
        radius: '78%',
        center: ['50%', '46%'],
        data: segments.map(s => ({ name: s.label, value: s.value, itemStyle: { color: s.color } })),
        label: { color: '#9ca3af', fontSize: 11, formatter: '{b}\n{d}%' },
        labelLine: { lineStyle: { color: '#4b5563' }, length: 10, length2: 8 },
      },
    ],
  }
}

// Selected year for the Annual Breakdown section (defaults to the latest)
const selectedYear = ref<number | null>(null)
const selectedRow = computed<FilingRow | null>(() => {
  if (!filings.value.length) return null
  const y = selectedYear.value ?? filings.value[0]!.year
  return filings.value.find(r => r.year === y) ?? filings.value[0]!
})

/** String binding for the year <select>. */
const selectedYearModel = computed({
  get: () => String(selectedRow.value?.year ?? ''),
  set: (v: string) => {
    selectedYear.value = Number(v)
    // composition solo selection doesn't carry across years
    revStackSelected.value = null
    expStackSelected.value = null
  },
})

/** Findings for the current UI locale, falling back to English. */
function findingsOf(row: FilingRow): string[] {
  const f = row.data.findings
  if (!f) return []
  if (Array.isArray(f)) return f
  return f[locale.value] ?? f.en ?? []
}

// ---- Composition-over-years: stacked bars (Rev Mix / Exp Mix views) ----
/** Whether every charted year has an expense composition on file. */
const expenseMixComplete = computed(() => {
  const entry = currentEntry.value
  if (!entry) return true
  return confChartYears.value.every(y => entry.years[String(y)]?.expense_mix)
})

const mixStackOption = computed(() => {
  const entry = currentEntry.value
  if (!entry || !confChartYears.value.length) return {}
  const isRevenue = metric.value === 'revenue_mix'
  const field = isRevenue ? 'revenue_mix' : 'expense_mix'
  const years = confChartYears.value

  // Series = union of category keys across years, revenue in canonical order, expenses by first appearance
  const keysOrder: string[] = []
  for (const y of years) {
    const mix = entry.years[String(y)]?.[field] as Record<string, number> | null | undefined
    if (mix) for (const k of Object.keys(mix)) if ((mix[k] ?? 0) > 0 && !keysOrder.includes(k)) keysOrder.push(k)
  }
  if (!keysOrder.length) return {}

  const canonical = ['contributions', 'program', 'investment', 'royalties', 'misc']
  if (isRevenue) keysOrder.sort((a, b) => {
    const ia = canonical.indexOf(a), ib = canonical.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  const colors = isRevenue ? REVENUE_MIX_COLORS : expenseColorMap.value
  const soloed = soloedMixName(isRevenue)
  const visibleKeys = soloed ? keysOrder.filter(k => mixLabel(k) === soloed) : keysOrder
  const series: Record<string, unknown>[] = visibleKeys.map((k) => ({
    name: mixLabel(k),
    type: 'bar',
    stack: 'mix',
    barMaxWidth: 28,
    itemStyle: { color: colors[k] ?? '#9ca3af' },
    emphasis: { focus: 'series' },
    data: years.map(y => (entry.years[String(y)]?.[field] as Record<string, number> | null | undefined)?.[k] ?? '-'),
  }))

  // Overlays: submissions (dashed, counts) + acceptance rate (%, % axis) — min 0 keeps zeros aligned
  const subs = entry.submissions ?? {}
  const hasSubs = Object.keys(subs).length > 0
  const submissionsName = t('finances.submissions')
  const accPct = entry.accept_rates_pct ?? {}
  const hasAcc = Object.keys(accPct).length > 0
  const acceptanceName = t('finances.acceptance')
  if (hasSubs) {
    series.push({
      name: submissionsName,
      type: 'line',
      yAxisIndex: 1,
      lineStyle: { width: 2, type: 'dashed', color: '#c084fc' },
      itemStyle: { color: '#c084fc' },
      symbolSize: 5,
      connectNulls: false,
      data: years.map(y => subs[String(y)] ?? '-'),
    })
  }
  if (hasAcc) {
    series.push({
      name: acceptanceName,
      type: 'line',
      yAxisIndex: 2,
      lineStyle: { width: 2, color: '#f472b6' },
      itemStyle: { color: '#f472b6' },
      symbolSize: 5,
      connectNulls: false,
      data: years.map(y => accPct[String(y)] ?? '-'),
    })
  }

  let stackMax = 0
  for (const y of years) {
    const mix = entry.years[String(y)]?.[field] as Record<string, number> | null | undefined
    if (!mix) continue
    const total = Object.values(mix).reduce((a, b) => a + (b ?? 0), 0)
    if (soloed) {
      const shown = Object.entries(mix).filter(([k]) => mixLabel(k) === soloed).reduce((a, [, b]) => a + (b ?? 0), 0)
      stackMax = Math.max(stackMax, shown)
    } else {
      stackMax = Math.max(stackMax, total, ...Object.values(mix).map(v => v ?? 0))
    }
  }
  let sMax = 1000
  for (const y of years) {
    const v = subs[String(y)]
    if (v != null) sMax = Math.max(sMax, v)
  }
  sMax = Math.max(Math.ceil(sMax / 1000) * 1000, 1000)
  let aMax = 10
  for (const y of years) {
    const v = accPct[String(y)]
    if (v != null) aMax = Math.max(aMax, v)
  }
  aMax = Math.ceil(aMax / 10) * 10

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (params: { seriesName: string; value: number | string; marker?: string }[]) => {
        const axisValue = (params[0] as unknown as { axisValue: unknown })?.axisValue
        const lines = params
          .filter(p => p.value !== '-')
          .map(p => {
            const v = p.seriesName === submissionsName
              ? Number(p.value).toLocaleString()
              : p.seriesName === acceptanceName ? `${Number(p.value).toFixed(1)}%` : fmtMoney(p.value as number)
            return `${p.marker ?? ''}${p.seriesName}: ${v}`
          })
        return lines.length ? `${axisValue}<br/>` + lines.join('<br/>') : ''
      },
    },
    grid: { left: 60, right: hasSubs && hasAcc ? 95 : hasSubs || hasAcc ? 50 : 20, top: 36, bottom: 44 },
    xAxis: {
      type: 'category',
      data: years,
      axisLabel: {
        color: '#9ca3af',
        interval: 0,
        formatter: (y: number) => venueAxisLabel(y),
        rich: VENUE_AXIS_RICH,
      },
      axisLine: { lineStyle: { color: '#4b5563' } },
    },
    yAxis: [
      {
        type: 'value',
        min: 0,
        max: niceCeil(stackMax),
        axisLabel: { color: '#9ca3af', formatter: (v: number) => fmtMoney(v) },
        splitLine: { lineStyle: { color: 'rgba(107,114,128,0.15)' } },
      },
      ...(hasSubs ? [{
        type: 'value',
        min: 0,
        max: sMax,
        position: 'right' as const,
        splitLine: { show: false },
        axisLabel: { color: '#9ca3af', formatter: (v: number) => `${Math.round(v / 1000)}k` },
      }] : []),
      ...(hasAcc ? [{
        type: 'value',
        min: 0,
        max: aMax,
        position: 'right' as const,
        offset: hasSubs ? 45 : 0,
        splitLine: { show: false },
        axisLabel: { color: '#9ca3af', formatter: (v: number) => `${Math.round(v)}%` },
      }] : []),
    ],
    series,
  }
})

// ---- Single-conference chart: Revenue/Expenses bars + Net Income line ----
const confChartYears = computed<number[]>(() => {
  if (!currentEntry.value || !currentUsable.value) return []
  return sortedYears(currentEntry.value)
})

const confChartOption = computed(() => {
  if (metric.value === 'revenue_mix' || metric.value === 'expenses_mix') return mixStackOption.value
  const entry = currentEntry.value
  if (!entry || !confChartYears.value.length) return {}
  const years = confChartYears.value
  const showAll = metric.value === 'ALL'
  const mk = (key: 'revenue' | 'expenses' | 'net_income' | 'net_assets') =>
    years.map(y => valueOf(entry, y, key))

  // Overlays on right-side axes, shown in every money view:
  // submissions (counts, dashed) and acceptance rate (%, solid).
  const subs = entry.submissions ?? {}
  const acc = entry.accept_rates_pct ?? {}
  const hasSubs = Object.keys(subs).length > 0
  const hasAcc = Object.keys(acc).length > 0
  const submissionsName = t('finances.submissions')
  const acceptanceName = t('finances.acceptance')

  const series: Record<string, unknown>[] = []
  if (showAll || metric.value === 'revenue') {
    series.push({
      name: t('finances.metric.revenue'),
      type: 'bar', barMaxWidth: 28, itemStyle: { color: METRIC_COLORS.revenue, borderRadius: [3, 3, 0, 0] },
      data: mk('revenue'),
    })
  }
  if (showAll || metric.value === 'expenses') {
    series.push({
      name: t('finances.metric.expenses'),
      type: 'bar', barMaxWidth: 28, itemStyle: { color: METRIC_COLORS.expenses, borderRadius: [3, 3, 0, 0] },
      data: mk('expenses'),
    })
  }
  if (showAll || metric.value === 'net_income') {
    series.push({
      name: t('finances.metric.net_income'),
      type: showAll ? 'line' : 'bar', barMaxWidth: 28,
      lineStyle: { width: 2.5, color: METRIC_COLORS.net_income },
      itemStyle: { color: METRIC_COLORS.net_income },
      symbolSize: 6,
      data: mk('net_income'),
    })
  }
  if (metric.value === 'net_assets') {
    series.push({
      name: t('finances.metric.net_assets'),
      type: 'bar', barMaxWidth: 28, itemStyle: { color: METRIC_COLORS.net_assets, borderRadius: [3, 3, 0, 0] },
      data: mk('net_assets'),
    })
  }
  if (hasSubs) {
    series.push({
      name: submissionsName,
      type: 'line',
      yAxisIndex: 1,
      lineStyle: { width: 2, type: 'dashed', color: '#c084fc' },
      itemStyle: { color: '#c084fc' },
      symbolSize: 5,
      connectNulls: false,
      data: years.map(y => subs[String(y)] ?? '-'),
    })
  }
  if (hasAcc) {
    series.push({
      name: acceptanceName,
      type: 'line',
      yAxisIndex: hasSubs ? 2 : 1,
      lineStyle: { width: 2, color: '#f472b6' },
      itemStyle: { color: '#f472b6' },
      symbolSize: 5,
      connectNulls: false,
      data: years.map(y => acc[String(y)] ?? '-'),
    })
  }
  if (hasSubs) {
    series.push({
      name: submissionsName,
      type: 'line',
      yAxisIndex: 1,
      lineStyle: { width: 2, type: 'dashed', color: '#c084fc' },
      itemStyle: { color: '#c084fc' },
      symbolSize: 5,
      connectNulls: false,
      data: years.map(y => subs[String(y)] ?? '-'),
    })
  }

  const moneyAxis: Record<string, unknown> = {
    type: 'value' as const,
    axisLabel: { color: '#9ca3af', formatter: (v: number) => fmtMoney(v) },
    splitLine: { lineStyle: { color: 'rgba(107,114,128,0.15)' } },
  }
  const rightAxes: Record<string, unknown>[] = []
  if (hasSubs || hasAcc) {
    // Align the zero lines of every axis: explicit min/max chosen so that the
    // zero fraction from the bottom is identical on all sides.
    const visibleKeys: ('revenue' | 'expenses' | 'net_income' | 'net_assets')[] =
      metric.value === 'ALL' ? ['revenue', 'expenses', 'net_income'] : [metric.value]
    let mMin = 0, mMax = 0
    for (const y of years) {
      for (const k of visibleKeys) {
        const v = valueOf(entry, y, k)
        if (v != null) { mMin = Math.min(mMin, v); mMax = Math.max(mMax, v) }
      }
    }
    moneyAxis.min = mMin < 0 ? -niceCeil(-mMin) : 0
    moneyAxis.max = niceCeil(mMax)
    const lo = moneyAxis.min as number
    const r = lo < 0 ? -lo / ((moneyAxis.max as number) - lo) : 0
    const zeroAligned = (max: number) => (mMin < 0 ? Math.floor((-r * max) / (1 - r)) : 0)

    if (hasSubs) {
      let sMax = 1000
      for (const y of years) {
        const v = subs[String(y)]
        if (v != null) sMax = Math.max(sMax, v)
      }
      sMax = Math.max(Math.ceil(sMax / 1000) * 1000, 1000)
      rightAxes.push({
        type: 'value' as const,
        min: zeroAligned(sMax),
        max: sMax,
        position: 'right' as const,
        splitLine: { show: false },
        axisLabel: {
          color: '#9ca3af',
          // negative ticks only exist to keep the zero lines aligned; hide their labels
          formatter: (v: number) => (v < 0 ? '' : Math.abs(v) >= 1000 ? `${Math.round(v / 1000)}k` : String(v)),
        },
      })
    }
    if (hasAcc) {
      let aMax = 10
      for (const y of years) {
        const v = acc[String(y)]
        if (v != null) aMax = Math.max(aMax, v)
      }
      aMax = Math.ceil(aMax / 10) * 10
      rightAxes.push({
        type: 'value' as const,
        min: zeroAligned(aMax),
        max: aMax,
        position: 'right' as const,
        offset: hasSubs ? 45 : 0,
        splitLine: { show: false },
        axisLabel: {
          color: '#9ca3af',
          formatter: (v: number) => (v < 0 ? '' : `${Math.round(v)}%`),
        },
      })
    }
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (params: { marker?: string; seriesName: string; value: number | string }[]) => {
        const lines = params
          .filter(p => p.value !== '-')
          .map(p => {
            const v = p.seriesName === submissionsName
              ? `${Number(p.value).toLocaleString()}`
              : p.seriesName === acceptanceName ? `${Number(p.value).toFixed(1)}%` : fmtMoney(p.value as number)
            return `${p.marker ?? ''}${p.seriesName}: ${v}`
          })
        return lines.length ? lines.join('<br/>') : ''
      },
    },
    legend: { textStyle: { color: '#9ca3af' }, top: 0 },
    grid: { left: 60, right: rightAxes.length === 2 ? 95 : rightAxes.length === 1 ? 50 : 20, top: 36, bottom: 44 },
    xAxis: {
      type: 'category',
      data: years,
      axisLabel: {
        color: '#9ca3af',
        interval: 0,
        formatter: (y: number) => venueAxisLabel(y),
        rich: VENUE_AXIS_RICH,
      },
      axisLine: { lineStyle: { color: '#4b5563' } },
    },
    yAxis: [moneyAxis, ...rightAxes],
    series,
  }
})

// ---- Compare chart: one line per conference ----
const compareEntries = computed(() => {
  const confs = financesIndex.value?.conferences ?? {}
  return compareSelection.value
    .filter(c => usableConfs.value.includes(c) && confs[c])
    .map(c => ({ id: c, title: c, entry: confs[c]! }))
})

const compareYears = computed<number[]>(() => {
  const set = new Set<number>()
  for (const { entry } of compareEntries.value) {
    for (const y of sortedYears(entry)) set.add(y)
  }
  return [...set].sort((a, b) => a - b)
})

const compareChartOption = computed(() => {
  if (compareEntries.value.length < 2) return {}
  const years = compareYears.value
  const series = compareEntries.value.map(({ id, entry }, i) => ({
    name: id,
    type: 'line' as const,
    connectNulls: true,
    lineStyle: { width: 2.5 },
    itemStyle: { color: COMPARE_SERIES_COLORS[i % COMPARE_SERIES_COLORS.length] },
    symbolSize: 5,
    data: years.map(y => valueOf(entry, y, compareMetric.value)),
  }))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      valueFormatter: (v: unknown) => fmtMoney(typeof v === 'number' ? v : null),
    },
    legend: { textStyle: { color: '#9ca3af' }, top: 0 },
    grid: { left: 60, right: 20, top: 36, bottom: 30 },
    xAxis: {
      type: 'category',
      data: years,
      axisLabel: { color: '#9ca3af' },
      axisLine: { lineStyle: { color: '#4b5563' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', formatter: (v: number) => fmtMoney(v) },
      splitLine: { lineStyle: { color: 'rgba(107,114,128,0.15)' } },
    },
    series,
  }
})
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <!-- Loading -->
      <div v-if="loading" class="text-center py-20">
        <div class="text-4xl mb-4 animate-bounce">💰</div>
        <p class="text-gray-400">{{ t('finances.title') }}…</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center py-20">
        <p class="text-red-400 text-lg">{{ error }}</p>
        <router-link :to="{ name: 'conference', params: { id: confId } }" class="text-blue-400 mt-4 inline-block no-underline">{{ t('finances.back_to_conference') }}</router-link>
      </div>

      <template v-else>
        <!-- Header -->
        <div class="mb-6">
          <router-link
            :to="{ name: 'conference', params: { id: confId } }"
            class="text-sm text-gray-500 hover:text-gray-300 no-underline"
          >← {{ t('finances.back_to_conference') }}</router-link>
          <h1 class="text-3xl md:text-4xl font-bold text-white mt-2">
            <span class="text-blue-400">{{ displayName }}</span> {{ t('finances.title') }}
          </h1>
          <p v-if="currentEntry" class="text-gray-400 mt-1">
            {{ currentEntry.org_name }}
            <span class="ml-2 text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 align-middle">{{ t(SCOPE_LABEL_KEYS[currentEntry.scope] ?? 'finances.scope.society') }}</span>
          </p>
        </div>

        <!-- Unavailable (CVPR/ICCV) -->
        <div v-if="unavailableEntry" class="card p-6 bg-gray-800/50 border-orange-500/30 mb-8">
          <h3 class="text-lg font-semibold text-white mb-2">💰 {{ t('finances.not_public') }}</h3>
          <p class="text-gray-400 text-sm leading-relaxed">{{ t('finances.unavailable_note') }}</p>
          <p class="text-gray-500 text-xs mt-2">{{ unavailableEntry.org_name }} — {{ localizedText(unavailableEntry.scope_note) }}</p>
          <p class="text-gray-500 text-xs mt-3">{{ t('finances.compare_hint') }}</p>
        </div>

        <!-- Single conference chart -->
        <div v-if="currentEntry && currentUsable" class="card p-6 bg-gray-800/50 border-gray-700/50 mb-8">
          <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
            <h3 class="text-lg font-semibold text-white">{{ t('finances.title') }} · <span class="text-blue-400">{{ displayName }}</span></h3>
            <div class="inline-flex rounded-lg overflow-hidden border border-gray-600 shrink-0 flex-wrap">
              <button
                v-for="m in ['ALL', 'revenue', 'expenses', 'net_income', 'net_assets', 'revenue_mix', 'expenses_mix']"
                :key="m"
                @click="metric = m as typeof metric"
                class="px-3 py-1 text-xs font-medium transition-colors"
                :class="metric === m ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
              >
                <template v-if="m === 'ALL'">All</template>
                <template v-else-if="m === 'revenue_mix'">{{ t('finances.mix_view_revenue') }}</template>
                <template v-else-if="m === 'expenses_mix'">{{ t('finances.mix_view_expenses') }}</template>
                <template v-else>{{ t(`finances.metric.${m}`) }}</template>
              </button>
            </div>
          </div>
          <!-- HTML legend chips for the stacked composition views (click = solo) -->
          <div v-if="metric === 'revenue_mix' || metric === 'expenses_mix'" class="flex flex-wrap gap-1.5 mb-3">
            <button
              v-for="item in stackLegendItems"
              :key="item.name"
              @click="onStackChip(item.name)"
              class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors"
              :class="isSoloChip(item.name)
                ? 'border-transparent text-white'
                : 'bg-gray-800 border-gray-600 text-gray-400 hover:bg-gray-700'"
              :style="isSoloChip(item.name) ? { backgroundColor: item.color, borderColor: item.color } : {}"
            >
              <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: item.color }" />
              {{ item.name }}
            </button>
          </div>
          <v-chart
            :option="confChartOption"
            :update-options="{ notMerge: true }"
            style="height: 380px"
            autoresize
          />
          <p v-if="metric === 'expenses_mix' && !expenseMixComplete" class="text-xs text-gray-500 mt-2">{{ t('finances.mix_expense_coverage') }}</p>

          <!-- Latest stats with YoY change (inline, same line as the value) -->
          <div v-if="latestStats" class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
            <div class="rounded-lg bg-gray-900/60 border border-gray-700/50 px-4 py-3">
              <p class="text-xs text-gray-500">{{ t('finances.metric.revenue') }} ({{ latestStats.latestYear }})</p>
              <p class="text-xl font-bold" :style="{ color: METRIC_COLORS.revenue }">
                {{ fmtMoney(latestStats.latest.revenue) }}
                <span v-if="yoyOf('revenue')" class="text-xs font-medium align-middle" :class="yoyClass('revenue')">
                  {{ yoyArrow('revenue') }} {{ Math.abs(yoyOf('revenue')!.pct).toFixed(1) }}%
                  <span class="text-gray-500 font-normal">{{ t('finances.yoy_vs', { year: latestStats.prevYear }) }}</span>
                </span>
              </p>
            </div>
            <div class="rounded-lg bg-gray-900/60 border border-gray-700/50 px-4 py-3">
              <p class="text-xs text-gray-500">{{ t('finances.metric.expenses') }} ({{ latestStats.latestYear }})</p>
              <p class="text-xl font-bold" :style="{ color: METRIC_COLORS.expenses }">
                {{ fmtMoney(latestStats.latest.expenses) }}
                <span v-if="yoyOf('expenses')" class="text-xs font-medium align-middle" :class="yoyClass('expenses')">
                  {{ yoyArrow('expenses') }} {{ Math.abs(yoyOf('expenses')!.pct).toFixed(1) }}%
                  <span class="text-gray-500 font-normal">{{ t('finances.yoy_vs', { year: latestStats.prevYear }) }}</span>
                </span>
              </p>
            </div>
            <div class="rounded-lg bg-gray-900/60 border border-gray-700/50 px-4 py-3">
              <p class="text-xs text-gray-500">{{ t('finances.metric.net_income') }} ({{ latestStats.latestYear }})</p>
              <p class="text-xl font-bold" :style="{ color: METRIC_COLORS.net_income }">
                {{ fmtMoney(latestStats.latest.net_income) }}
                <span v-if="yoyOf('net_income')" class="text-xs font-medium align-middle" :class="yoyClass('net_income')">
                  {{ yoyArrow('net_income') }} {{ Math.abs(yoyOf('net_income')!.pct).toFixed(1) }}%
                  <span class="text-gray-500 font-normal">{{ t('finances.yoy_vs', { year: latestStats.prevYear }) }}</span>
                </span>
              </p>
            </div>
            <div class="rounded-lg bg-gray-900/60 border border-gray-700/50 px-4 py-3">
              <p class="text-xs text-gray-500">{{ t('finances.metric.net_assets') }} ({{ latestStats.latestYear }})</p>
              <p class="text-xl font-bold" :style="{ color: METRIC_COLORS.net_assets }">
                {{ fmtMoney(latestStats.latest.net_assets) }}
                <span v-if="yoyOf('net_assets')" class="text-xs font-medium align-middle" :class="yoyClass('net_assets')">
                  {{ yoyArrow('net_assets') }} {{ Math.abs(yoyOf('net_assets')!.pct).toFixed(1) }}%
                  <span class="text-gray-500 font-normal">{{ t('finances.yoy_vs', { year: latestStats.prevYear }) }}</span>
                </span>
              </p>
            </div>
          </div>

          <!-- Provenance -->
          <div class="mt-5 pt-4 border-t border-gray-700/50 text-xs text-gray-500 space-y-1">
            <p>
              📄 <a :href="currentEntry.propublica_url" target="_blank" rel="noopener" class="text-blue-400 hover:text-blue-300">{{ t('finances.source_note') }}</a>
              <template v-if="latestStats?.latest.pdf_url">
                · <a :href="latestStats.latest.pdf_url" target="_blank" rel="noopener" class="text-blue-400 hover:text-blue-300">Form 990 PDF ({{ latestStats.latestYear }})</a>
              </template>
            </p>
            <p>{{ t('finances.fiscal_note_label') }}: {{ fiscalNoteOf(currentEntry) }}</p>
            <p class="text-gray-600">{{ localizedText(currentEntry.scope_note) }}</p>
            <p class="text-gray-600">{{ t('finances.unit_note') }}</p>
          </div>
        </div>

        <!-- Annual breakdown: year dropdown, pies side by side, findings below -->
        <div v-if="filings.length && selectedRow" class="card p-6 bg-gray-800/50 border-gray-700/50 mb-8">
          <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
            <div>
              <h3 class="text-lg font-semibold text-white">📊 {{ t('finances.annual_title') }}</h3>
              <p class="text-xs text-gray-500 mt-0.5">{{ t('finances.annual_hint') }}</p>
            </div>
            <label class="inline-flex items-center gap-2 text-sm text-gray-400 shrink-0">
              <span class="text-xs">{{ t('finances.fiscal_note_label') }}</span>
              <select
                v-model="selectedYearModel"
                class="bg-gray-800 border border-gray-600 rounded-lg text-gray-200 text-sm px-3 py-1.5 cursor-pointer focus:outline-none focus:border-blue-500"
              >
                <option v-for="row in filings" :key="row.year" :value="String(row.year)">
                  {{ row.year }}
                </option>
              </select>
            </label>
          </div>

          <!-- Pies side by side -->
          <div v-if="yearMixes(selectedRow).length" class="grid sm:grid-cols-2 gap-4">
            <div v-for="mix in yearMixes(selectedRow)" :key="mix.id">
              <p class="text-[11px] uppercase tracking-wide text-gray-500 mb-1">
                {{ mix.label }} · {{ fmtMoney(mixTotal(mix.segments)) }}
              </p>
              <v-chart :option="pieOption(mix.segments)" style="height: 250px" autoresize />
            </div>
          </div>
          <p v-else class="text-sm text-gray-500 py-12 text-center">{{ t('finances.mix_none') }}</p>

          <!-- Findings below -->
          <ul v-if="findingsOf(selectedRow).length" class="mt-5 pt-4 border-t border-gray-700/50 space-y-2.5">
            <li v-for="(f, i) in findingsOf(selectedRow)" :key="i" class="text-sm text-gray-300 leading-relaxed flex gap-2">
              <span class="text-blue-400 mt-0.5 shrink-0">•</span>
              <span>{{ f }}</span>
            </li>
          </ul>
        </div>

        <!-- Host organization -->
        <div v-if="currentEntry?.entity" class="card p-6 bg-gray-800/50 border-gray-700/50 mb-8">
          <h3 class="text-lg font-semibold text-white mb-1">🏛️ {{ t('finances.entity_title') }}</h3>

          <!-- Country distribution of board members' institutions -->
          <div v-if="officerCountries.length" class="mb-5">
            <p class="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{{ t('finances.entity_country_title') }}</p>
            <div class="flex h-2.5 rounded-full overflow-hidden bg-gray-900/80">
              <div
                v-for="seg in officerCountries"
                :key="seg.code"
                :style="{ width: seg.pct + '%', backgroundColor: seg.color }"
                :title="`${seg.label} ${seg.n} (${seg.pct}%)`"
              />
            </div>
            <div class="flex flex-wrap gap-x-4 gap-y-0.5 mt-1.5">
              <span v-for="seg in officerCountries" :key="seg.code" class="inline-flex items-center gap-1 text-[11px] text-gray-400">
                <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: seg.color }" />
                {{ seg.label }} <span class="text-gray-500">{{ seg.n }} ({{ seg.pct }}%)</span>
              </span>
            </div>
          </div>

          <!-- Statutory officers from Form 990 -->
          <div v-if="currentEntry.entity.officers?.length">
            <p class="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{{ t('finances.entity_officers_title') }}</p>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-left text-xs text-gray-500 border-b border-gray-700/60">
                    <th class="py-2 pr-4 font-medium">{{ t('finances.entity_name') }}</th>
                    <th class="py-2 pr-4 font-medium">{{ t('finances.entity_role') }}</th>
                    <th class="py-2 pr-4 font-medium">{{ t('finances.entity_affiliation') }}</th>
                    <th class="py-2 font-medium text-right">{{ t('finances.entity_comp') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="o in currentEntry.entity.officers" :key="o.name" class="border-b border-gray-700/30">
                    <td class="py-2 pr-4 text-gray-200 whitespace-nowrap">{{ o.name }}</td>
                    <td class="py-2 pr-4 text-gray-400 whitespace-nowrap">{{ officerTitleOf(o.title) }}</td>
                    <td class="py-2 pr-4 text-gray-400">{{ o.affiliation ?? '—' }}</td>
                    <td class="py-2 text-right text-gray-400 whitespace-nowrap">{{ o.compensation ? fmtMoney(o.compensation) : '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Official foundation board & advisors (conference website) — collapsed by default -->
          <details v-if="currentEntry.entity.board?.members?.length" class="mt-5 pt-4 border-t border-gray-700/50 group/board">
            <summary class="cursor-pointer select-none flex items-center gap-2 text-sm text-gray-300 font-medium">
              <span class="text-blue-400 inline-block transition-transform group-open/board:rotate-90">▸</span>
              {{ t('finances.entity_board_title') }}
              <span class="text-xs text-gray-500 font-normal">({{ currentEntry.entity.board.members.length }})</span>
              <a
                v-if="currentEntry.entity.board.source"
                :href="currentEntry.entity.board.source"
                target="_blank"
                rel="noopener"
                class="ml-auto text-[11px] text-blue-400 hover:text-blue-300"
                @click.stop
              >{{ t('finances.entity_source') }} ↗</a>
            </summary>
            <div class="grid sm:grid-cols-2 gap-x-6 gap-y-1.5 mt-3">
              <div v-for="m in currentEntry.entity.board.members" :key="m.name + m.title" class="text-sm text-gray-300 flex flex-wrap gap-x-1.5 items-baseline min-w-0">
                <span class="text-gray-200">{{ m.name }}</span>
                <span class="text-gray-500 text-xs">{{ officerTitleOf(m.title) }}</span>
                <span v-if="m.affiliation" class="text-gray-500 text-xs">{{ m.affiliation }}</span>
                <span v-if="m.country" class="text-[10px] px-1 rounded bg-gray-700/60 text-gray-400">{{ countryLabel(m.country) }}</span>
              </div>
            </div>
          </details>

          <!-- Disclosed paid staff & contractors (Part VII) -->
          <div v-if="currentEntry.entity.top_employees?.length || currentEntry.entity.contractors?.length" class="mt-5 pt-4 border-t border-gray-700/50">
            <p class="text-[11px] uppercase tracking-wide text-gray-500 mb-2">{{ t('finances.entity_payroll_title') }}</p>
            <ul class="list-none space-y-1">
              <li v-for="e in currentEntry.entity.top_employees" :key="'e' + e.name" class="text-sm text-gray-300">
                • {{ e.name }} <span class="text-gray-500">— {{ officerTitleOf(e.title ?? '') }}</span>
                <span class="text-gray-400 ml-1">{{ e.compensation ? fmtMoney(e.compensation) : '' }}</span>
              </li>
              <li v-for="c in currentEntry.entity.contractors" :key="'c' + c.name" class="text-sm text-gray-300">
                • {{ c.name }} <span class="text-gray-500">— {{ c.description }}</span>
                <span class="text-gray-400 ml-1">{{ fmtMoney(c.compensation) }}</span>
              </li>
            </ul>
          </div>

          <!-- Conference organizing committees by year — collapsed by default -->
          <details v-if="committeeEntry" class="mt-5 pt-4 border-t border-gray-700/50 group/cmt">
            <summary class="cursor-pointer select-none flex items-center gap-2 text-sm text-gray-300 font-medium">
              <span class="text-blue-400 inline-block transition-transform group-open/cmt:rotate-90">▸</span>
              {{ t('finances.entity_committee_title') }}
              <span class="text-xs text-gray-500 font-normal">({{ committeeEntry.members.length }})</span>
              <a
                v-if="committeeEntry.source"
                :href="committeeEntry.source"
                target="_blank"
                rel="noopener"
                class="ml-auto text-[11px] text-blue-400 hover:text-blue-300"
                @click.stop
              >{{ t('finances.entity_source') }} ↗</a>
            </summary>
            <div class="mt-3">
              <div class="flex items-center gap-2 mb-3">
                <label class="text-xs text-gray-500">{{ t('finances.fiscal_note_label') }}</label>
                <select
                  v-model="committeeYearModel"
                  class="bg-gray-800 border border-gray-600 rounded-lg text-gray-200 text-xs px-2 py-1 cursor-pointer focus:outline-none focus:border-blue-500"
                >
                  <option v-for="y in committeeYears" :key="y" :value="y">{{ y }}</option>
                </select>
              </div>
              <div class="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
                <div v-for="m in committeeEntry.members" :key="m.name + m.title" class="text-sm text-gray-300 flex flex-wrap gap-x-1.5 items-baseline min-w-0">
                  <span class="text-gray-200">{{ m.name }}</span>
                  <span class="text-gray-500 text-xs">{{ officerTitleOf(m.title) }}</span>
                  <span v-if="m.affiliation" class="text-gray-500 text-xs">{{ m.affiliation }}</span>
                  <span v-if="m.country" class="text-[10px] px-1 rounded bg-gray-700/60 text-gray-400">{{ countryLabel(m.country) }}</span>
                </div>
              </div>
            </div>
          </details>
        </div>

        <!-- Compare -->
        <div class="card p-6 bg-gray-800/50 border-gray-700/50 mb-8">
          <h3 class="text-lg font-semibold text-white mb-1">{{ t('finances.compare_title') }}</h3>
          <p class="text-xs text-gray-500 mb-4">{{ t('finances.compare_hint') }}</p>

          <div class="flex flex-wrap gap-2 mb-4">
            <label
              v-for="c in usableConfs"
              :key="c"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm cursor-pointer select-none transition-colors"
              :class="compareSelection.includes(c)
                ? 'bg-blue-500/10 border-blue-500/50 text-blue-300'
                : 'bg-gray-800 border-gray-600 text-gray-400 hover:border-gray-500'"
            >
              <input v-model="compareSelection" type="checkbox" :value="c" class="accent-blue-500" />
              {{ c }}
            </label>
          </div>

          <div class="inline-flex rounded-lg overflow-hidden border border-gray-600 mb-4">
            <button
              v-for="m in ['revenue', 'expenses', 'net_income', 'net_assets']"
              :key="m"
              @click="compareMetric = m as typeof compareMetric"
              class="px-3 py-1 text-xs font-medium transition-colors"
              :class="compareMetric === m ? 'bg-blue-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
            >
              {{ t(`finances.metric.${m}`) }}
            </button>
          </div>

          <p v-if="compareEntries.length < 2" class="text-sm text-gray-500 py-8 text-center">{{ t('finances.compare_empty') }}</p>
          <v-chart v-else :option="compareChartOption" style="height: 360px" autoresize />
        </div>

        <!-- Annual filings: collapsed by default, compact year links -->
        <details v-if="filings.length" class="card px-6 py-4 bg-gray-800/50 border-gray-700/50 mb-8 group/files">
          <summary class="cursor-pointer select-none flex items-center gap-2 text-sm text-gray-300 font-medium">
            <span class="text-blue-400 inline-block transition-transform group-open/files:rotate-90">▸</span>
            🗂️ {{ t('finances.filing_archive') }}
            <span class="text-xs text-gray-500 font-normal">({{ filings.length }})</span>
          </summary>
          <div class="flex flex-wrap gap-2 mt-3">
            <a
              v-for="row in filings"
              :key="row.year"
              :href="row.data.pdf_url ?? '#'"
              target="_blank"
              rel="noopener"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-gray-600 bg-gray-800 text-xs text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
              :title="t('finances.filing_original')"
            >{{ row.year }}</a>
          </div>
        </details>
      </template>
    </div>
  </div>
</template>

<style scoped>
</style>
