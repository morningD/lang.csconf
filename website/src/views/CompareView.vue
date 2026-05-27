<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDataFetch } from '@/composables/useDataFetch'
import type { ConferenceIndex, ConferenceDetail, Meta, AffiliationIndex, CCFCategory } from '@/types'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
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
    initInstitutionsFromUrl()
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
let syncingUrl = false

// Sync institutions ↔ URL query param
watch(selectedInstitutions, (val) => {
  if (syncingUrl) return
  const q = { ...route.query }
  if (val.length > 0) q.inst = val.join(',')
  else delete q.inst
  router.replace({ query: q })
}, { deep: true })

function initInstitutionsFromUrl() {
  syncingUrl = true
  const raw = route.query.inst as string | undefined
  if (raw) {
    selectedInstitutions.value = raw.split(',').filter(Boolean)
  } else {
    selectedInstitutions.value = ['Tsinghua University']
  }
  syncingUrl = false
}
const instSearchQuery = ref('')
const showInstDropdown = ref(false)
const instDropdownRef = ref<HTMLElement | null>(null)
const instLatestOnly = ref(true)

// CCF-A only: filter conferences and recompute by_category
const affilIndexA = computed(() => {
  if (!affilIndex.value) return null
  const idx = affilIndex.value
  const aConfIds = new Set(
    Object.entries(idx.conferences).filter(([, v]) => v.rank === 'A').map(([k]) => k)
  )
  if (aConfIds.size === 0) return null

  const institutions: typeof idx.institutions = {}
  for (const [name, entry] of Object.entries(idx.institutions)) {
    const filteredConfs: typeof entry.conferences = {}
    for (const [cid, val] of Object.entries(entry.conferences)) {
      if (aConfIds.has(cid)) filteredConfs[cid] = val
    }
    if (Object.keys(filteredConfs).length === 0) continue
    const by_category: Record<string, number> = {}
    for (const [cid, val] of Object.entries(filteredConfs)) {
      const cat = idx.conferences[cid]?.category
      if (cat) by_category[cat] = (by_category[cat] || 0) + val.count
    }
    institutions[name] = { country: entry.country, by_category, conferences: filteredConfs }
  }

  return {
    conferences: Object.fromEntries(Object.entries(idx.conferences).filter(([, v]) => v.rank === 'A')),
    institutions,
    name_list: idx.name_list.filter(n => n in institutions),
    coverage: idx.coverage,
  }
})

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
const CAT_COLORS: Record<string, string> = {
  AI: '#60a5fa', DB: '#34d399', NW: '#fbbf24', SE: '#f87171',
  CG: '#a78bfa', CT: '#22d3ee', HI: '#f472b6', SC: '#fb923c',
  DS: '#2dd4bf', MX: '#94a3b8',
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
  'Microsoft': 'Microsoft',
  'Shanghai AI Lab': 'Shanghai AI Lab',
  // --- Universities (alphabetical) ---
  'Aalto University': 'Aalto',
  'Aarhus University': 'Aarhus',
  'Arizona State University': 'ASU',
  'Australian National University': 'ANU',
  'Bar-Ilan University': 'BIU',
  'Beihang University': 'Beihang',
  'Beijing Institute of Technology': 'BIT',
  'Beijing University of Posts and Telecommunications': 'BUPT',
  'Ben-Gurion University of the Negev': 'BGU',
  'Brno University of Technology': 'BUT',
  'Central South University': 'CSU',
  'Charles University': 'CUNI',
  'China University of Petroleum, Beijing': 'CUP',
  'City University of Hong Kong': 'CityU',
  'Clemson University': 'Clemson',
  'Czech Technical University in Prague': 'CTU',
  'Dalian University of Technology': 'DLUT',
  'Delft University of Technology': 'TU Delft',
  'Drexel University': 'Drexel',
  'Duke University': 'Duke',
  'East China Normal University': 'ECNU',
  'Eindhoven University of Technology': 'TU/e',
  'Florida International University': 'FIU',
  'Georgetown University': 'Georgetown',
  'Graz University of Technology': 'TU Graz',
  'Gwangju Institute of Science and Technology': 'GIST',
  'Harvard University': 'Harvard',
  'Hasso Plattner Institute': 'HPI',
  'Hong Kong Baptist University': 'HKBU',
  'Hong Kong Polytechnic University': 'PolyU',
  'Hunan University': 'HNU',
  'Indian Institute of Science': 'IISc',
  'Indian Institute of Technology Bombay': 'IITB',
  'Indian Institute of Technology Madras': 'IITM',
  'Indiana University Bloomington': 'IU',
  'Institute for Advanced Study': 'IAS',
  'Institute of Science and Technology Austria': 'ISTA',
  'Iowa State University': 'ISU',
  'Karlsruhe Institute of Technology': 'KIT',
  "King's College London": 'KCL',
  'Kyushu Institute of Technology': 'Kyutech',
  'KU Leuven': 'KU Leuven',
  'Lawrence Berkeley National Laboratory': 'LBNL',
  'Lawrence Livermore National Laboratory': 'LLNL',
  'Leiden University': 'Leiden',
  'Linköping University': 'LiU',
  'Louisiana State University': 'LSU',
  'Max Planck Institute for Informatics': 'MPI-INF',
  'Max Planck Institute for Intelligent Systems': 'MPI-IS',
  'Max Planck Institute for Software Systems': 'MPI-SWS',
  'Michigan State University': 'MSU',
  'Monash University': 'Monash',
  'Moscow Institute of Physics and Technology': 'MIPT',
  'Nagoya University': 'Nagoya',
  'Nanjing University of Aeronautics and Astronautics': 'NUAA',
  'Nanjing University of Science and Technology': 'NJUST',
  'Nankai University': 'Nankai',
  'National Institute of Informatics': 'NII',
  'National Taiwan University': 'NTU Taiwan',
  'National Tsing Hua University': 'NTHU',
  'National University of Defense Technology': 'NUDT',
  'National Yang Ming Chiao Tung University': 'NYCU',
  'North Carolina State University': 'NCSU',
  'Northeastern University': 'NEU',
  'Northwestern University': 'Northwestern',
  'Oak Ridge National Laboratory': 'ORNL',
  'Oregon State University': 'Oregon State',
  'Osaka University': 'Osaka',
  'Pennsylvania State University': 'PSU',
  'Purdue University West Lafayette': 'Purdue',
  'RWTH Aachen University': 'RWTH',
  'Radboud University Nijmegen': 'Radboud',
  'Renmin University of China': 'RUC',
  'Rochester Institute of Technology': 'RIT',
  'Ruhr University Bochum': 'RUB',
  'Rutgers, The State University of New Jersey': 'Rutgers',
  'Saarland University': 'Saarland',
  'Shandong University': 'SDU',
  'Shandong University of Science and Technology': 'SDUST',
  'ShanghaiTech University': 'ShanghaiTech',
  'Shenzhen University': 'SZU',
  'Simon Fraser University': 'SFU',
  'Singapore Management University': 'SMU',
  'Soochow University': 'Soochow',
  'Southeast University': 'SEU',
  'Southern University of Science and Technology': 'SUSTech',
  'Stevens Institute of Technology': 'Stevens',
  'Stony Brook University': 'Stony Brook',
  'Sun Yat-sen University': 'SYSU',
  'Sungkyunkwan University': 'SKKU',
  'TU Wien': 'TU Wien',
  'Tallinn University of Technology': 'TalTech',
  'Tampere University': 'Tampere',
  'Technical University of Darmstadt': 'TU Darmstadt',
  'Technische Universität Berlin': 'TU Berlin',
  'Technische Universität Darmstadt': 'TU Darmstadt',
  'Technology Innovation Institute': 'TII',
  'Tel Aviv University': 'TAU',
  'Texas A&M University': 'TAMU',
  'The University of Melbourne': 'Melbourne',
  'The University of Queensland': 'UQ',
  'Tianjin University': 'TJU',
  'Tokyo Institute of Technology': 'Tokyo Tech',
  'Tongji University': 'Tongji',
  'Toyota Technological Institute at Chicago': 'TTIC',
  'UCLouvain': 'UCLouvain',
  'UNSW Sydney': 'UNSW',
  'University of Amsterdam': 'UvA',
  'University of Bergen': 'UiB',
  'University of Birmingham': 'Birmingham',
  'University of Bordeaux': 'Bordeaux',
  'University of Calgary': 'UCalgary',
  'University of California, Irvine': 'UCI',
  'University of California, Merced': 'UCM',
  'University of California, Riverside': 'UCR',
  'University of California, Santa Barbara': 'UCSB',
  'University of Central Florida': 'UCF',
  'University of Colorado Boulder': 'CU Boulder',
  'University of Connecticut': 'UConn',
  'University of Delaware': 'UDel',
  'University of Edinburgh': 'Edinburgh',
  'University of Electronic Science and Technology of China': 'UESTC',
  'University of Exeter': 'Exeter',
  'University of Florida': 'UF',
  'University of Freiburg': 'Freiburg',
  'University of Glasgow': 'Glasgow',
  'University of Helsinki': 'Helsinki',
  'University of Houston': 'UH',
  'University of Iowa': 'UIowa',
  'University of Luxembourg': 'Uni.lu',
  'University of Massachusetts Amherst': 'UMass',
  'University of Minnesota': 'UMN',
  'University of North Carolina at Chapel Hill': 'UNC',
  'University of Notre Dame': 'Notre Dame',
  'University of Nottingham': 'UoN',
  'University of Pisa': 'UNIPI',
  'University of Pittsburgh': 'Pitt',
  'University of Sherbrooke': 'UdeS',
  'University of Siegen': 'Siegen',
  'University of Stuttgart': 'Stuttgart',
  'University of Sydney': 'Sydney',
  'University of Tennessee at Knoxville': 'UTK',
  'University of Twente': 'UT',
  'University of Tübingen': 'Tübingen',
  'University of Utah': 'U of U',
  'University of Virginia': 'UVA',
  'University of Warsaw': 'Warsaw',
  'University of Warwick': 'Warwick',
  'University of Waterloo': 'Waterloo',
  'University of Würzburg': 'JMU',
  'Virginia Tech': 'Virginia Tech',
  'Washington University in St. Louis': 'WashU',
  'Weizmann Institute of Science': 'Weizmann',
  'William & Mary': 'W&M',
  'Wuhan University': 'WHU',
  "Xi'an Jiaotong University": 'XJTU',
  'Xiamen University': 'XMU',
  'Xidian University': 'Xidian',
  'Yale University': 'Yale',
  'Yonsei University': 'Yonsei',
  'York University': 'York U',
  // --- Research Institutes ---
  'Argonne National Laboratory': 'ANL',
  'Barcelona Supercomputing Center': 'BSC',
  'Centre National de la Recherche Scientifique': 'CNRS',
  'Computer Network Information Center': 'CNIC',
  'Fondazione Bruno Kessler': 'FBK',
  'German Research Centre for Artificial Intelligence': 'DFKI',
  'Helmholtz Center for Information Security': 'CISPA',
  'INRIA': 'INRIA',
  'Leibniz Supercomputing Centre': 'LRZ',
  'NTT Social Informatics Laboratories': 'NTT',
  // --- Companies ---
  'Adobe': 'Adobe',
  'Alibaba': 'Alibaba',
  'Amazon': 'Amazon',
  'Ant Group': 'Ant Group',
  'Anthropic': 'Anthropic',
  'Criteo': 'Criteo',
  'Denso': 'Denso',
  'Huawei Technologies': 'Huawei',
  'Jingdong': 'JD',
  'Meta': 'Meta',
  'NVIDIA': 'NVIDIA',
  'Tableau Software': 'Tableau',
  // --- Others ---
  'U.S. National Science Foundation': 'NSF',
  'Defence Science and Technology Group': 'DSTG',
  'IMDEA Networks': 'IMDEA',
  'Sorbonne Université': 'Sorbonne',
  'École Pour l\'Informatique et les Techniques Avancées': 'EPITA',
  'Universitat Pompeu Fabra': 'UPF',
  'Università della Svizzera italiana': 'USI',
  'Universidad del Noreste': 'UNE',
  'Vassar College': 'Vassar',
  'Knoxville College': 'Knoxville',
  'Berkeley College': 'Berkeley College',
  'Saitama University': 'Saitama',
  'Ritsumeikan University': 'Ritsumeikan',
  'University Town of Shenzhen': 'UT Shenzhen',
  'LMU Klinikum': 'LMU',
  'IIT@MIT': 'IIT@MIT',
  'Moscow Institute of Thermal Technology': 'MITT',
  'Amsterdam University of the Arts': 'AHK',
  'Department of Computer Science': 'DCS',
  'HKUST': 'HKUST',
  'KAUST': 'KAUST',
  'EPFL': 'EPFL',
  'Technion': 'Technion',
  'Harvard University Press': 'Harvard Press',
  'Bauhaus-Universität Weimar': 'Bauhaus-Uni',
  'Carl von Ossietzky Universität Oldenburg': 'Uni Oldenburg',
  'Friedrich-Alexander-Universität Erlangen-Nürnberg': 'FAU',
  'IBM': 'IBM',
  'Institut national de recherche en sciences et technologies du numérique': 'Inria',
  'Instituto de Engenharia de Sistemas e Computadores Investigação e Desenvolvimento': 'INESC-ID',
  'Istituto di Scienza e Tecnologie dell\'Informazione "Alessandro Faedo"': 'ISTI',
  'Laboratoire d\'Informatique de l\'École Polytechnique': 'LIX',
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
  const matches = new Set<string>()
  for (const n of names) {
    if (n.toLowerCase().includes(q)) { matches.add(n); continue }
    const ab = INST_ABBREV[n]
    if (ab && ab.toLowerCase().includes(q)) { matches.add(n); continue }
  }
  return names.filter(n => matches.has(n)).slice(0, 20)
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
  if (!affilIndexA.value || selectedInstitutions.value.length === 0) return {}

  const institutions = affilIndexA.value.institutions
  const conferences = affilIndexA.value.conferences
  const seriesColors = ['#3498db', '#e74c3c', '#2ecc71']
  const latestOnly = instLatestOnly.value

  // Compute per-category sum for an institution (latest or all-time)
  function catSums(inst: typeof institutions[string]): number[] {
    const sums: Record<string, number> = {}
    for (const cat of CATEGORIES) sums[cat] = 0
    for (const [cid, val] of Object.entries(inst.conferences)) {
      const cat = conferences[cid]?.category
      if (!cat) continue
      sums[cat] = (sums[cat] || 0) + (latestOnly ? (val.latest?.count || 0) : val.count)
    }
    return CATEGORIES.map(cat => sums[cat] || 0)
  }

  // Normalize against global max across ALL institutions
  const catMax: Record<string, number> = {}
  for (const cat of CATEGORIES) {
    let max = 0
    for (const inst of Object.values(institutions)) {
      const sums = catSums(inst)
      const val = sums[CATEGORIES.indexOf(cat)]!
      if (val > max) max = val
    }
    catMax[cat] = max
  }

  const indicator = CATEGORIES.map(cat => ({
    name: `{${cat}|${cat}}`,
    max: 100,
  }))

  const axisNameRich: Record<string, { color: string; fontSize: number }> = {}
  for (const cat of CATEGORIES) {
    axisNameRich[cat] = { color: CAT_COLORS[cat] || '#aaa', fontSize: 11 }
  }

  const seriesData = selectedInstitutions.value.map((name, i) => {
    const inst = institutions[name]
    const flag = inst?.country ? countryFlag(inst.country) : ''
    const rawVals = inst ? catSums(inst) : CATEGORIES.map(() => 0)
    const displayName = flag
      ? `${abbreviateInst(name)} {flag|${flag}}`
      : abbreviateInst(name)
    return {
      value: rawVals.map((v, idx) => {
        const max = catMax[CATEGORIES[idx]!] || 0
        return max > 0 ? Math.round(v / max * 100) : 0
      }),
      rawValues: rawVals,
      name: displayName,
    }
  })

  return {
    tooltip: {
      trigger: 'item',
      position: 'right',
      formatter: (params: any) => {
        const name = selectedInstitutions.value[params.dataIndex] || (params.name as string)
        const rawVals = seriesData[params.dataIndex]?.rawValues || []
        let html = `<b>${abbreviateInst(name)}</b><br/>`
        CATEGORIES.forEach((cat, idx) => {
          if (rawVals[idx]! > 0) {
            const c = CAT_COLORS[cat] || '#aaa'
            html += `<span style="color:${c}">●</span> ${CATEGORY_FULL[cat]}: ${rawVals[idx]} papers<br/>`
          }
        })
        return html
      },
    },
    legend: {
      data: seriesData.map(s => s.name),
      textStyle: {
        color: '#aaa',
        fontSize: 11,
        rich: { flag: { fontSize: 16.5, lineHeight: 11 } },
      },
      top: 0,
    },
    radar: {
      indicator,
      shape: 'polygon',
      axisName: { rich: axisNameRich },
      splitLine: { lineStyle: { color: '#333' } },
      splitArea: { areaStyle: { color: ['transparent'] } },
      axisLine: { lineStyle: { color: '#444' } },
    },
    series: [{
      type: 'radar',
      data: seriesData.map((s, i) => ({
        value: s.value,
        name: s.name,
        areaStyle: { opacity: 0.15, color: seriesColors[i] },
        lineStyle: { color: seriesColors[i] },
        itemStyle: { color: seriesColors[i] },
      })),
    }],
  }
})

// Conference ranking details for selected institutions (CCF-A only, flat list)
const instRankDetails = computed(() => {
  if (!affilIndexA.value || selectedInstitutions.value.length === 0) return []

  const conferences = affilIndexA.value.conferences
  const institutions = affilIndexA.value.institutions

  const confIds = new Set<string>()
  for (const name of selectedInstitutions.value) {
    const inst = institutions[name]
    if (inst) {
      for (const confId of Object.keys(inst.conferences)) {
        confIds.add(confId)
      }
    }
  }

  const rows: Array<{
    confId: string
    title: string
    category: string
    entries: Array<{ name: string; latestRank: number; latestYear: number; allTimeRank: number; fallback: boolean }>
  }> = []

  for (const confId of confIds) {
    const conf = conferences[confId]
    if (!conf) continue

    const entries = selectedInstitutions.value.map(name => {
      const instConf = institutions[name]?.conferences?.[confId]
      const hasLatest = instConf?.latest && instConf.latest.rank > 0
      return {
        name,
        latestRank: hasLatest ? instConf!.latest!.rank : (instConf?.rank || 0),
        latestYear: hasLatest ? instConf!.latest!.year : 0,
        allTimeRank: instConf?.rank || 0,
        fallback: !hasLatest,
      }
    })

    if (entries.some(e => e.latestRank > 0 || e.allTimeRank > 0)) {
      rows.push({ confId, title: conf.title, category: conf.category, entries })
    }
  }

  return rows.sort((a, b) => {
    const bestA = Math.min(...a.entries.map(e => e.latestRank || Infinity))
    const bestB = Math.min(...b.entries.map(e => e.latestRank || Infinity))
    return bestA - bestB
  })
})

const hasInstData = computed(() => selectedInstitutions.value.length > 0 && instRankDetails.value.length > 0)
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <h1 class="text-3xl font-bold text-white mb-8">{{ t('compare.title') }}</h1>

      <!-- Institution Comparison -->
      <div v-if="affilIndexA" class="mb-10">
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
            <span v-if="affilIndex?.institutions[name]?.country" class="text-base">{{ countryFlag(affilIndex.institutions[name].country) }}</span>
            <button @click="removeInstitution(name)" class="text-gray-400 hover:text-red-400">×</button>
          </div>

          <div v-if="selectedInstitutions.length < 2" ref="instDropdownRef" class="relative">
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
                <span v-if="affilIndex?.institutions[instName]?.country" class="text-base">{{ countryFlag(affilIndex.institutions[instName].country) }}</span>
                <span class="text-white">{{ abbreviateInst(instName) }}</span>
                <span class="text-gray-500 text-xs truncate">{{ instName }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- Radar + Rankings side by side -->
        <div v-if="selectedInstitutions.length > 0" class="grid lg:grid-cols-[380px_1fr] gap-6 mb-6">
          <!-- Category Radar Chart (compact) -->
          <div class="card p-4 bg-gray-800/50 border-gray-700/50">
            <div class="flex items-center justify-between mb-1">
              <label class="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none">
                <input type="checkbox" v-model="instLatestOnly" class="accent-violet-500" />
                {{ t('compare.institution_latest') }}
              </label>
            </div>
            <v-chart :option="instRadarOption" style="height: 340px" autoresize />
            <p class="text-xs text-gray-500 mt-2">
              {{ t('compare.institution_coverage', {
                conferences: Object.keys(affilIndexA.conferences).length,
                pct: affilIndexA.coverage.coverage_pct
              }) }}
            </p>
          </div>

          <!-- Ranking Details (flat, styled like venue boxes) -->
          <div v-if="hasInstData" class="flex flex-wrap gap-1.5 content-start max-h-[410px] overflow-y-auto">
            <router-link
              v-for="row in instRankDetails"
              :key="row.confId"
              :to="`/conference/${row.confId}`"
              class="rank-box relative text-center no-underline"
            >
              <div class="absolute top-0 left-2 right-2 h-0.5 rounded-b opacity-60" :style="{ backgroundColor: CAT_COLORS[row.category] || '#666' }"></div>
              <div class="text-white text-xs font-bold leading-tight py-1">{{ row.title }}</div>
              <template v-for="(entry, ei) in row.entries" :key="entry.name">
                <div v-if="entry.latestRank > 0 || entry.allTimeRank > 0" class="flex flex-col items-center gap-0 pb-1">
                  <span v-if="selectedInstitutions.length > 1" class="text-xs font-medium leading-tight" :style="{ color: ['#3498db', '#e74c3c'][ei] || '#aaa' }">
                    {{ abbreviateInst(entry.name) }}
                  </span>
                  <div class="text-sm font-bold leading-tight" :style="{ color: CAT_COLORS[row.category] || '#aaa' }">
                    #{{ entry.latestRank }}<span v-if="entry.latestYear && !entry.fallback" class="text-gray-500 text-[10px] font-normal">'{{ String(entry.latestYear).slice(2) }}</span>
                  </div>
                  <div class="text-gray-500 text-[10px] leading-tight">
                    #{{ entry.allTimeRank }}<span v-if="!entry.fallback"> Σ</span>
                  </div>
                </div>
                <div v-else class="text-gray-600 text-xs pb-1">—</div>
              </template>
            </router-link>
          </div>
          <div v-else class="flex items-center justify-center text-gray-500">—</div>
        </div>

        <!-- No institution selected -->
        <div v-else class="text-center py-12">
          <div class="text-5xl mb-3 opacity-20">🏛️</div>
          <p class="text-gray-500">{{ t('compare.institution_subtitle') }}</p>
        </div>
      </div>

      <!-- Conference Selector -->
      <h2 class="text-2xl font-bold text-white mb-1">{{ t('compare.language_title') }}</h2>
      <p class="text-gray-400 mb-6">{{ t('compare.subtitle') }}</p>
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
    </div>
  </div>
</template>

<style scoped>
.rank-box {
  background: rgba(30, 30, 40, 0.5);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2),
              inset 0 1px 0 rgba(255, 255, 255, 0.05);
  padding: 0 6px;
  min-width: 72px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.rank-box:hover {
  transform: translateY(-2px);
  border-color: rgba(124, 58, 237, 0.3);
  box-shadow: 0 4px 16px rgba(124, 58, 237, 0.1),
              0 8px 24px rgba(0, 0, 0, 0.12),
              inset 0 1px 0 rgba(255, 255, 255, 0.06);
}
</style>
