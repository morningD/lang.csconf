<script setup>
import { ref, shallowRef, triggerRef, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { rabbitPalettes, mushroomPalettes, butterflyPalettes, snailPalettes, sporeColors, grassShades, flowerColors } from './pixel-palettes'
import { rabbitThoughts, snakeHisses } from './rabbit-thoughts'
import { getActiveHolidays } from './holiday-calendar'

const { locale } = useI18n()
const lang = computed(() => locale.value)
const isDark = ref(false)

const container = ref(null)
const rabbits = shallowRef([])
const mushrooms = shallowRef([])
const grasses = shallowRef([])
const butterflies = shallowRef([])
const snails = shallowRef([])
const rainbows = shallowRef([])
const spores = shallowRef([])
const snakeGrasses = shallowRef([])
const holidayDecorations = shallowRef([])
const holidayParticles = shallowRef([])
const activeHolidays = ref([])
const groundY = ref(48)
function getLunarPhase() {
  // Known new moon: Jan 6, 2000 18:14 UTC
  const ref = Date.UTC(2000, 0, 6, 18, 14)
  const now = Date.now()
  const cycle = 29.53059
  const days = (now - ref) / 86400000
  return ((days % cycle) + cycle) % cycle / cycle // 0–1: 0=new, 0.5=full
}

function moonPhasePath(cx, cy, r, lunarPhase) {
  // lunarPhase: 0=new, 0.5=full, 1=new
  const k = Math.cos(lunarPhase * 2 * Math.PI) // 1 at new, -1 at full
  const rx = Math.abs(k) * r
  const sweep = k >= 0 ? 0 : 1
  if (lunarPhase <= 0.5) {
    // Waxing — right side lit
    return `M${cx} ${cy - r} A${r} ${r} 0 0 1 ${cx} ${cy + r} A${rx} ${r} 0 0 ${sweep} ${cx} ${cy - r} Z`
  } else {
    // Waning — left side lit
    return `M${cx} ${cy - r} A${r} ${r} 0 0 0 ${cx} ${cy + r} A${rx} ${r} 0 0 ${1 - sweep} ${cx} ${cy - r} Z`
  }
}

function computeSky(w) {
  const now = new Date()
  const h = now.getHours() + now.getMinutes() / 60
  const isSun = h >= 6 && h < 18
  let timePhase
  if (isSun) {
    timePhase = (h - 6) / 12
  } else {
    timePhase = ((h - 18 + 24) % 24) / 12
  }
  return {
    isSun,
    x: 30 + timePhase * (w - 60),
    arcY: Math.sin(timePhase * Math.PI) * 45,
    timePhase,
    lunarPhase: getLunarPhase()
  }
}
const sky = ref(computeSky(800))
let animFrame = 0
let lastTime = 0
let resizeObs = null
let visibilityObs = null
let isVisible = false
let lightboxOpen = false
let sceneReady = false
let nextSpawn = 0
let skyFrame = 0
const SKY_UPDATE_INTERVAL = 60 // update sky every 60 frames

// Physics
const GRAVITY = 0.25
const GROUND = 0
const BOUNCE = 0.45
const WALK_SPEED_MIN = 0.35
const WALK_SPEED_MAX = 0.7
const RABBIT_W = 30
const RABBIT_H = 30
const COLLISION_DIST = 28
const MUSHROOM_EAT_DIST = 16
const MUSHROOM_EDIBLE = 0.35
const MAX_MUSHROOMS = 8
const MAX_SPORES = 80


// Weather system
const clouds = shallowRef([])
const wxParticles = shallowRef([])
const stars = shallowRef([])
const weather = ref({ type: 'clear', wind: 0 })
const stripH = ref(200)

function pickWeather() {
  const month = new Date().getMonth()
  const r = Math.random()
  const isWinter = month >= 11 || month <= 1
  const isSpring = month >= 2 && month <= 4
  if (isWinter) {
    if (r < 0.20) return { type: 'clear', wind: 0.1 + Math.random() * 0.2 }
    if (r < 0.38) return { type: 'partly-cloudy', wind: 0.2 + Math.random() * 0.3 }
    if (r < 0.52) return { type: 'cloudy', wind: 0.3 + Math.random() * 0.4 }
    if (r < 0.72) return { type: 'rainy', wind: 0.4 + Math.random() * 0.5 }
    return { type: 'snowy', wind: 0.1 + Math.random() * 0.3 }
  }
  if (isSpring) {
    if (r < 0.28) return { type: 'clear', wind: Math.random() * 0.3 }
    if (r < 0.48) return { type: 'partly-cloudy', wind: 0.15 + Math.random() * 0.3 }
    if (r < 0.62) return { type: 'cloudy', wind: 0.25 + Math.random() * 0.4 }
    if (r < 0.92) return { type: 'rainy', wind: 0.3 + Math.random() * 0.5 }
    return { type: 'snowy', wind: 0.1 + Math.random() * 0.2 }
  }
  // Summer & Autumn
  if (r < 0.40) return { type: 'clear', wind: Math.random() * 0.2 }
  if (r < 0.62) return { type: 'partly-cloudy', wind: 0.1 + Math.random() * 0.3 }
  if (r < 0.78) return { type: 'cloudy', wind: 0.2 + Math.random() * 0.4 }
  if (r < 0.95) return { type: 'rainy', wind: 0.3 + Math.random() * 0.5 }
  return { type: 'snowy', wind: 0.1 + Math.random() * 0.2 }
}

// Multiple cloud palette families per time-of-day for variety
const dayCloudFamilies = [
  { top: '#ffffff', mid: '#eef0f4', base: '#d8dce4', shadow: '#b8c0cc', edge: '#c4cad4' },  // classic white
  { top: '#fff8f0', mid: '#f0e0d0', base: '#e8d0c0', shadow: '#c8a898', edge: '#d4b8a8' },  // warm cream
  { top: '#f0f4ff', mid: '#d8e0f8', base: '#c0cce8', shadow: '#98a8cc', edge: '#b0b8d8' },  // cool blue
  { top: '#fff4f8', mid: '#f0dce4', base: '#e0c8d4', shadow: '#c0a0b4', edge: '#d0b0c0' },  // pink tint
  { top: '#f8fff0', mid: '#e4f0d8', base: '#d0e0c4', shadow: '#a8c098', edge: '#b8d0a8' },  // soft green
]
const dayStormFamilies = [
  { top: '#c8ccd4', mid: '#a8aeb8', base: '#909498', shadow: '#70767e', edge: '#8a9098' },
  { top: '#c4c8d8', mid: '#a0a8b8', base: '#8890a0', shadow: '#687080', edge: '#808898' },
  { top: '#d0c8c8', mid: '#b0a8a8', base: '#989090', shadow: '#787070', edge: '#908888' },
]

function cPal(ci = 0) {
  const h = new Date().getHours() + new Date().getMinutes() / 60
  const s = weather.value.type === 'rainy' || weather.value.type === 'snowy'
  // Per-cloud brightness + warm/cool tint for variety
  const sh = ((ci * 7 + 3) % 11 - 5) * 4
  const tint = ((ci * 13 + 5) % 9 - 4) * 3
  function adj(hex) {
    const rv = Math.max(0, Math.min(255, parseInt(hex.slice(1, 3), 16) + sh + tint))
    const gv = Math.max(0, Math.min(255, parseInt(hex.slice(3, 5), 16) + sh))
    const bv = Math.max(0, Math.min(255, parseInt(hex.slice(5, 7), 16) + sh - tint))
    return '#' + [rv, gv, bv].map(v => v.toString(16).padStart(2, '0')).join('')
  }
  let p
  if (h >= 5 && h < 7) {
    // Dawn — warm pink/orange
    p = s
      ? { top: '#d0b8b0', mid: '#b09898', base: '#988080', shadow: '#786060', edge: '#887070' }
      : { top: '#fff0e0', mid: '#f0d0b0', base: '#e8b898', shadow: '#c89878', edge: '#d8a888' }
  } else if (h >= 7 && h < 17) {
    // Day — pick from multiple families per cloud index
    p = s
      ? dayStormFamilies[ci % dayStormFamilies.length]
      : dayCloudFamilies[ci % dayCloudFamilies.length]
  } else if (h >= 17 && h < 19) {
    // Dusk — warm orange/peach
    p = s
      ? { top: '#b8a098', mid: '#988078', base: '#887068', shadow: '#685050', edge: '#786060' }
      : { top: '#f8e0d0', mid: '#e8b8a0', base: '#d8a090', shadow: '#b87868', edge: '#c88878' }
  } else {
    // Night — moonlit blue-grey
    p = s
      ? { top: '#484c60', mid: '#343848', base: '#282e3c', shadow: '#181c28', edge: '#222838' }
      : { top: '#606880', mid: '#485068', base: '#384058', shadow: '#202838', edge: '#303850' }
  }
  return { top: adj(p.top), mid: adj(p.mid), base: adj(p.base), shadow: adj(p.shadow), edge: adj(p.edge) }
}

function measureGround() {
  const footer = document.querySelector('.app-footer')
  if (footer && container.value) {
    const h = footer.offsetHeight
    const sh = h + 160
    container.value.style.height = sh + 'px'
    container.value.style.marginTop = -sh + 'px'
    groundY.value = h
    stripH.value = sh
  }
}

function makeMushroom(x, time, stagger) {
  const pal = mushroomPalettes[Math.floor(Math.random() * mushroomPalettes.length)]
  return {
    x, targetScale: 3, currentScale: 0,
    colors: pal, type: pal.type,
    spawnTime: time - (stagger || 0),
    eaten: false, eatenTime: 0, scaleAtEat: 0,
    maxedAt: 0, lastSporeTime: 0
  }
}

function initScene() {
  const w = container.value?.offsetWidth || 800
  const now = performance.now()

  const isMobile = w < 640
  rabbits.value = (isMobile ? rabbitPalettes.slice(0, 2) : rabbitPalettes).map((colors, i) => ({
    x: (w / (isMobile ? 3 : 4)) * (i + 1), y: 0,
    vx: (Math.random() > 0.5 ? 1 : -1) * (WALK_SPEED_MIN + Math.random() * (WALK_SPEED_MAX - WALK_SPEED_MIN)),
    vy: 0, colors, grabbed: false, glowing: false,
    earPhase: Math.random() * Math.PI * 2,
    // Hop system
    hopping: false, hopTimer: Math.random() * 15, hopInterval: 20 + Math.random() * 15,
    squash: 0,
    // Trip
    tripping: false, tripTimer: 0, tripPhase: 0, tripType: null,
    // Growth from eating mushrooms
    sizeBoost: 1,
    mushroomsEaten: 0,
    isBaby: false,
    bubble: null,
    bubbleCooldown: 0
  }))

  const mc = isMobile ? 2 + Math.floor(Math.random() * 2) : 4 + Math.floor(Math.random() * 3)
  const segW = (w - 40) / mc
  mushrooms.value = Array.from({ length: mc }, (_, i) =>
    makeMushroom(20 + segW * i + Math.random() * segW, now, Math.random() * 5000)
  )

  // Grass — varied clusters with different styles
  const gc = isMobile ? 10 + Math.floor(Math.random() * 5) : 22 + Math.floor(Math.random() * 10)
  grasses.value = Array.from({ length: gc }, () => {
    // Different cluster styles: 0=normal, 1=bushy-short, 2=tall-thin, 3=wild-mixed
    const style = Math.floor(Math.random() * 4)
    let bc, blades
    if (style === 0) {
      // Normal cluster
      bc = 4 + Math.floor(Math.random() * 4)
      blades = Array.from({ length: bc }, (_, b) => ({
        x: b * 3.5 + 2,
        h: 7 + Math.random() * 10,
        lean: (Math.random() - 0.5) * 5,
        curve: (Math.random() - 0.5) * 3,
        width: 1.5 + Math.random() * 1.2,
        color: grassShades[Math.floor(Math.random() * grassShades.length)],
        opacity: 0.55 + Math.random() * 0.4,
        flower: null
      }))
    } else if (style === 1) {
      // Bushy short cluster — many short wide blades
      bc = 6 + Math.floor(Math.random() * 5)
      blades = Array.from({ length: bc }, (_, b) => ({
        x: b * 2.5 + 1,
        h: 4 + Math.random() * 6,
        lean: (Math.random() - 0.5) * 8,
        curve: (Math.random() - 0.5) * 4,
        width: 2 + Math.random() * 1.5,
        color: grassShades[Math.floor(Math.random() * grassShades.length)],
        opacity: 0.5 + Math.random() * 0.4,
        flower: null
      }))
    } else if (style === 2) {
      // Tall thin cluster — few tall narrow blades
      bc = 2 + Math.floor(Math.random() * 3)
      blades = Array.from({ length: bc }, (_, b) => ({
        x: b * 4 + 2,
        h: 14 + Math.random() * 8,
        lean: (Math.random() - 0.5) * 7,
        curve: (Math.random() - 0.5) * 5,
        width: 1 + Math.random() * 0.6,
        color: grassShades[Math.floor(Math.random() * grassShades.length)],
        opacity: 0.5 + Math.random() * 0.45,
        flower: null
      }))
    } else {
      // Wild mixed with possible tiny flower
      bc = 3 + Math.floor(Math.random() * 5)
      blades = Array.from({ length: bc }, (_, b) => ({
        x: b * 3 + 1.5,
        h: 5 + Math.random() * 14,
        lean: (Math.random() - 0.5) * 10,
        curve: (Math.random() - 0.5) * 6,
        width: 0.8 + Math.random() * 2,
        color: grassShades[Math.floor(Math.random() * grassShades.length)],
        opacity: 0.5 + Math.random() * 0.45,
        flower: (b === bc - 1 && Math.random() < 0.5)
          ? { color: flowerColors[Math.floor(Math.random() * flowerColors.length)], r: 1.2 + Math.random() * 1 }
          : null
      }))
    }
    const spacing = style === 1 ? 2.5 : style === 2 ? 4 : style === 3 ? 3 : 3.5
    return {
      x: Math.random() * w,
      blades,
      maxH: Math.max(...blades.map(b => b.h)) + (blades.some(b => b.flower) ? 6 : 2),
      totalW: bc * spacing + 6,
      bend: 0,
      style
    }
  })

  snails.value = (isMobile ? snailPalettes.slice(0, 1) : snailPalettes).map((colors, i) => ({
    x: w * 0.2 + Math.random() * w * 0.6,
    dir: Math.random() > 0.5 ? 1 : -1,
    speed: 0.06 + Math.random() * 0.04,
    colors,
    antennaPhase: Math.random() * Math.PI * 2,
    bodyStretch: 0
  }))

  const bfc = isMobile ? 1 + Math.floor(Math.random() * 2) : 3 + Math.floor(Math.random() * 3)
  butterflies.value = Array.from({ length: bfc }, (_, i) => ({
    x: Math.random() * w, baseY: 15 + Math.random() * 25,
    phase: Math.random() * Math.PI * 2, wingPhase: Math.random() * Math.PI * 2,
    speed: 0.15 + Math.random() * 0.35, dir: Math.random() > 0.5 ? 1 : -1,
    colors: butterflyPalettes[i % butterflyPalettes.length],
    fleeing: false, fleeTimer: 0,
    rainbowHue: 0,
    bobAmp: 6 + Math.random() * 12,
    bobSpeed: 0.015 + Math.random() * 0.015,
    driftY: 0, driftTarget: 0, driftTimer: 0
  }))

  // Weather
  weather.value = pickWeather()
  const wt = weather.value.type

  // Clouds
  const clCount = isMobile
    ? (wt === 'clear' ? 2 + Math.floor(Math.random() * 2) : wt === 'partly-cloudy' ? 3 + Math.floor(Math.random() * 2) : 5 + Math.floor(Math.random() * 3))
    : (wt === 'clear' ? 4 + Math.floor(Math.random() * 3) : wt === 'partly-cloudy' ? 7 + Math.floor(Math.random() * 4) : 10 + Math.floor(Math.random() * 5))
  clouds.value = Array.from({ length: clCount }, (_, ci) => ({
    x: Math.random() * (w + 60) - 30,
    y: 45 + Math.random() * 50,
    speed: 0.04 + Math.random() * 0.08,
    scale: 0.55 + Math.random() * 0.65,
    opacity: wt === 'clear' ? 0.25 + Math.random() * 0.15
      : wt === 'partly-cloudy' ? 0.4 + Math.random() * 0.2
      : 0.55 + Math.random() * 0.3,
    variant: Math.floor(Math.random() * 6),
    rainbowHue: 0,
    rainbowPhase: 0,
    pal: cPal(ci)
  }))

  // Stars — depth-based brightness, slight color variation
  stars.value = Array.from({ length: 20 + Math.floor(Math.random() * 15) }, () => {
    const bright = Math.random()
    return {
      x: Math.random() * w,
      y: 50 + Math.random() * 105,
      r: 0.3 + bright * 0.9,
      delay: Math.random() * 5,
      duration: 1.8 + Math.random() * 3,
      glow: bright > 0.7, // bright stars get a glow halo
      warm: Math.random() < 0.3 // some stars are warm-toned
    }
  })

  // Rain / Snow particles — depth-based parallax
  const sh = stripH.value
  if (wt === 'rainy') {
    wxParticles.value = Array.from({ length: 55 + Math.floor(Math.random() * 25) }, () => {
      const depth = Math.random() // 0=far, 1=near
      return {
        x: Math.random() * w,
        y: Math.random() * sh,
        speed: 2 + depth * 4,
        len: 3 + depth * 8,
        w: 0.3 + depth * 0.9,
        op: 0.04 + depth * 0.22,
        depth
      }
    })
  } else if (wt === 'snowy') {
    wxParticles.value = Array.from({ length: 30 + Math.floor(Math.random() * 20) }, () => {
      const depth = Math.random()
      return {
        x: Math.random() * w,
        y: Math.random() * sh,
        speed: 0.15 + depth * 0.6,
        r: 0.5 + depth * 2.2,
        swayPh: Math.random() * Math.PI * 2,
        swaySp: 0.01 + Math.random() * 0.02,
        op: 0.15 + depth * 0.55,
        depth
      }
    })
  } else {
    wxParticles.value = []
  }

  // Snake nests — pick 1-2 non-short grasses to hide snakes
  const snakeCandidates = grasses.value
    .map((g, i) => ({ g, i }))
    .filter(({ g }) => g.style !== 1)
    .sort(() => Math.random() - 0.5)
    .slice(0, 1 + Math.floor(Math.random() * 2))
  snakeGrasses.value = snakeCandidates.map(({ g, i }) => ({
    grassIdx: i,
    x: g.x,
    tailReveal: 0,
    rustlePhase: Math.random() * Math.PI * 2,
    rustleTimer: 60 + Math.random() * 180,
    rustling: false,
    rustleAmount: 0,
    hovered: false,
    hissBubble: null,
    hissCooldown: 0,
    snakePhase: Math.random() * Math.PI * 2,
    swayX: 0,
    swayRot: 0
  }))

  // ── Holidays ──
  const locale = lang.value?.replace(/\/.*/, '') || 'en'
  activeHolidays.value = getActiveHolidays(locale)

  // Merge decorations from active holidays (max 6 desktop / 4 mobile, dedup by type)
  const decos = []
  const decoTypeSeen = new Set()
  const maxDecos = w < 640 ? 4 : 6
  for (const h of activeHolidays.value) {
    if (!h.visuals.decorations) continue
    const decoList = Array.isArray(h.visuals.decorations) ? h.visuals.decorations : [h.visuals.decorations]
    for (const deco of decoList) {
      const dt = deco.type
      if (decoTypeSeen.has(dt)) continue
      decoTypeSeen.add(dt)
      for (let di = 0; di < deco.count && decos.length < maxDecos; di++) {
        decos.push({
          type: dt,
          label: deco.label || '',
          x: 40 + Math.random() * (w - 80),
          wobblePhase: Math.random() * Math.PI * 2,
          wobbleSpeed: 0.01 + Math.random() * 0.01,
          scale: 0.9 + Math.random() * 0.2
        })
      }
    }
  }
  holidayDecorations.value = decos

  // Merge particles from active holidays (max 50 desktop / 25 mobile, dedup by type)
  const maxParts = w < 640 ? 25 : 50
  const parts = []
  const partTypeSeen = new Set()
  for (const h of activeHolidays.value) {
    if (!h.visuals.particles) continue
    const pt = h.visuals.particles.type
    if (partTypeSeen.has(pt)) continue
    partTypeSeen.add(pt)
    const count = Math.min(h.visuals.particles.count, maxParts - parts.length)
    const colors = h.visuals.particles.colors
    for (let pi = 0; pi < count && parts.length < maxParts; pi++) {
      parts.push({
        type: pt,
        x: Math.random() * w,
        y: Math.random() * sh,
        vx: (Math.random() - 0.5) * 0.3,
        vy: pt === 'firework-spark' ? -(0.5 + Math.random() * 1.5) : (0.2 + Math.random() * 0.5),
        color: colors[Math.floor(Math.random() * colors.length)],
        size: pt === 'sakura' ? (5 + Math.random() * 4) : pt === 'heart' ? (6 + Math.random() * 4) : pt === 'lantern-glow' ? (4 + Math.random() * 4) : pt === 'snowflake-special' ? (5 + Math.random() * 4) : pt === 'maple-leaf' ? (5 + Math.random() * 3) : pt === 'confetti' ? (4 + Math.random() * 3) : (3 + Math.random() * 3),
        rotation: Math.random() * 360,
        rotSpeed: (Math.random() - 0.5) * 2,
        swayPhase: Math.random() * Math.PI * 2,
        swaySpeed: 0.01 + Math.random() * 0.02,
        opacity: 0.4 + Math.random() * 0.4,
        life: pt === 'firework-spark' ? (60 + Math.random() * 60) : 9999,
        maxLife: pt === 'firework-spark' ? 120 : 9999
      })
    }
  }
  holidayParticles.value = parts

  // Weather hint: 60% chance to override weather if any active holiday has weatherHint
  for (const h of activeHolidays.value) {
    if (h.visuals.weatherHint && Math.random() < 0.6) {
      weather.value = { type: h.visuals.weatherHint, wind: weather.value.wind }
      break
    }
  }
}

function startLoop() {
  if (animFrame) return
  lastTime = 0 // reset to prevent dt explosion
  animFrame = requestAnimationFrame(tick)
}
function stopLoop() {
  if (animFrame) { cancelAnimationFrame(animFrame); animFrame = 0 }
}
function onLightboxChange(e) {
  lightboxOpen = e.detail.open
  if (!lightboxOpen && isVisible) startLoop()
}
function tick(time) {
  animFrame = 0
  if (!isVisible || lightboxOpen) return
  const dt = lastTime ? Math.min((time - lastTime) / 16, 3) : 1
  lastTime = time
  const w = container.value?.offsetWidth || 800

  // ── Mushroom lifecycle ──
  mushrooms.value.forEach(m => {
    if (m.eaten) {
      const t = Math.min(1, (time - m.eatenTime) / 400)
      m.currentScale = m.scaleAtEat * (1 - t)
    } else {
      const gt = Math.min(1, (time - m.spawnTime) / 25000)
      m.currentScale = m.targetScale * (1 - Math.pow(1 - gt, 3))
      // Track when mushroom reaches max size
      if (gt >= 0.99 && !m.maxedAt) m.maxedAt = time
      // Continuously release spores after 3s at max (every 1.5–2.5s)
      if (m.maxedAt && time - m.maxedAt >= 3000 && spores.value.length < MAX_SPORES) {
        if (!m.lastSporeTime || time - m.lastSporeTime >= 1500 + Math.random() * 1000) {
          m.lastSporeTime = time
          const count = 2 + Math.floor(Math.random() * 3)
          const capH = m.currentScale * 13
          for (let si = 0; si < count; si++) {
            spores.value.push({
              x: m.x + (Math.random() - 0.5) * m.currentScale * 10,
              y: -capH + (Math.random() - 0.5) * m.currentScale * 4,
              vx: (Math.random() - 0.5) * 0.5,
              vy: -(0.2 + Math.random() * 0.4),
              color: sporeColors[Math.floor(Math.random() * sporeColors.length)],
              size: 2 + Math.random() * 3,
              opacity: 0.6,
              spawnTime: time
            })
          }
        }
      }
    }
  })
  mushrooms.value = mushrooms.value.filter(m => !(m.eaten && time - m.eatenTime > 450))
  if (nextSpawn === 0) nextSpawn = time + 5000
  if (time > nextSpawn && mushrooms.value.filter(m => !m.eaten).length < MAX_MUSHROOMS) {
    let x, tries = 0
    do { x = Math.random() * (w - 40) + 20; tries++ }
    while (tries < 10 && mushrooms.value.some(m => !m.eaten && Math.abs(m.x - x) < 30))
    mushrooms.value.push(makeMushroom(x, time))
    nextSpawn = time + 6000 + Math.random() * 9000
  }

  // ── Rabbits ──
  rabbits.value.forEach(r => {
    if (r.grabbed) { r.earPhase += 0.15 * dt; return }

    // Trip tick
    if (r.tripping) {
      r.tripTimer -= dt
      r.tripPhase += 0.08 * dt
      if (r.tripTimer <= 0) { r.tripping = false; r.tripType = null }
      const flipChance = r.tripType === 'dizzy' ? 0.02 : r.tripType === 'sparkle' ? 0.006 : 0.012
      if (Math.random() < flipChance * dt) r.vx = -r.vx
    }

    // Gravity
    r.vy += GRAVITY * dt
    r.y += r.vy * dt

    // Ground
    if (r.y >= GROUND) {
      if (r.vy > 0.5) r.squash = Math.min(0.12, r.vy * 0.04)
      r.y = GROUND
      r.vy = Math.abs(r.vy) > 2 ? -r.vy * BOUNCE : 0
      if (r.hopping) r.hopping = false
      // Restore minimum speed on landing
      if (Math.abs(r.vx) < WALK_SPEED_MIN) {
        r.vx = Math.sign(r.vx || 1) * (WALK_SPEED_MIN + Math.random() * (WALK_SPEED_MAX - WALK_SPEED_MIN))
      }
    }

    // Squash decay
    if (r.squash > 0) r.squash *= (1 - 0.15 * dt)
    if (r.squash < 0.003) r.squash = 0

    // ─ Hop system ─
    const isTripping = r.tripping
    if (r.y >= GROUND - 0.1 && r.vy >= -0.1) {
      // On ground
      if (!r.hopping) {
        r.hopTimer += dt
        const interval = isTripping ? (8 + Math.random() * 8) : r.hopInterval
        if (r.hopTimer >= interval) {
          r.hopping = true
          r.hopTimer = 0
          // Speech bubble — ~15% chance per hop, with cooldown
          if (!r.bubble && r.bubbleCooldown <= 0 && Math.random() < 0.15) {
            const locale = lang.value?.replace(/\/.*/, '') || 'en'
            // 25% chance holiday thought when holidays are active
            let text = null
            if (activeHolidays.value.length > 0 && !r.isBaby && !r.tripping && Math.random() < 0.25) {
              const hol = activeHolidays.value[Math.floor(Math.random() * activeHolidays.value.length)]
              const holPool = hol.thoughts[locale] || hol.thoughts['en']
              if (holPool && holPool.length) text = holPool[Math.floor(Math.random() * holPool.length)]
            }
            // Snake awareness — only when rabbit faces toward and is near a snake grass
            // Babies are more sensitive: wider detection range and higher trigger chance
            if (!text && !r.tripping && snakeGrasses.value.length > 0) {
              const facingDir = r.vx < 0 ? -1 : 1
              const baseProximity = w < 640 ? w * 0.25 : 150
              const proximity = r.isBaby ? baseProximity * 1.4 : baseProximity
              const nearSnake = snakeGrasses.value.some(sg => {
                const dx = sg.x - r.x
                return Math.abs(dx) < proximity && (dx < 0 ? -1 : 1) === facingDir
              })
              if (nearSnake && Math.random() < (r.isBaby ? 0.3 : 0.1)) {
                const thoughts = rabbitThoughts[locale] || rabbitThoughts['en']
                if (thoughts.snake?.length) {
                  text = thoughts.snake[Math.floor(Math.random() * thoughts.snake.length)]
                }
              }
            }
            if (!text) {
              const thoughts = rabbitThoughts[locale] || rabbitThoughts['en']
              const pool = r.isBaby ? thoughts.baby
                : r.tripping ? thoughts.trip
                : thoughts.idle
              text = pool[Math.floor(Math.random() * pool.length)]
            }
            r.bubble = { text, timer: 120 }
            r.bubbleCooldown = 300
          }
          // Hop height
          if (isTripping && r.tripType === 'dizzy') {
            r.vy = -(2.5 + Math.random() * 2)
          } else if (isTripping && r.tripType === 'sparkle') {
            r.vy = -(3 + Math.random() * 1.5)
          } else if (isTripping) {
            r.vy = -(2 + Math.random() * 1.2)
          } else {
            r.vy = -(1.5 + Math.random() * 0.8)
          }
          r.hopInterval = 20 + Math.random() * 15
        }
      }
      // No horizontal movement while sitting on ground
    } else {
      // In air → move horizontally
      const speed = isTripping ? 1.6 : 1.3
      r.x += r.vx * speed * dt
      // Very gentle air drag (only for high-speed throws)
      if (Math.abs(r.vx) > WALK_SPEED_MAX * 1.5) r.vx *= 0.997
    }

    // Ear animation
    r.earPhase += (r.y < -0.5 ? 0.12 : 0.04) * dt

    // Bubble timer
    if (r.bubble) { r.bubble.timer -= dt; if (r.bubble.timer <= 0) r.bubble = null }
    if (r.bubbleCooldown > 0) r.bubbleCooldown -= dt

    // Wall bounce
    if (r.x < RABBIT_W / 2) { r.x = RABBIT_W / 2; r.vx = Math.abs(r.vx) || WALK_SPEED_MIN }
    if (r.x > w - RABBIT_W / 2) { r.x = w - RABBIT_W / 2; r.vx = -(Math.abs(r.vx) || WALK_SPEED_MIN) }
  })

  // Rabbit–rabbit collision
  for (let i = 0; i < rabbits.value.length; i++) {
    for (let j = i + 1; j < rabbits.value.length; j++) {
      const a = rabbits.value[i], b = rabbits.value[j]
      if (a.grabbed || b.grabbed) continue
      const dx = b.x - a.x, dy = b.y - a.y
      const distSq = dx * dx + dy * dy
      if (distSq < COLLISION_DIST * COLLISION_DIST && distSq > 0) {
        const dist = Math.sqrt(distSq)
        const nx = dx / dist, ny = dy / dist
        const ov = (COLLISION_DIST - dist) / 2
        a.x -= nx * ov; a.y -= ny * ov
        b.x += nx * ov; b.y += ny * ov
        const dvx = a.vx - b.vx, dvy = a.vy - b.vy
        const dot = dvx * nx + dvy * ny
        if (dot > 0) {
          a.vx -= dot * nx * 0.5; a.vy -= dot * ny * 0.5
          b.vx += dot * nx * 0.5; b.vy += dot * ny * 0.5
        }
      }
    }
  }

  // Rabbit eats mushroom
  rabbits.value.forEach(r => {
    if (r.grabbed) return
    mushrooms.value.forEach(m => {
      if (m.eaten || m.currentScale < MUSHROOM_EDIBLE) return
      if (Math.abs(r.x - m.x) < MUSHROOM_EAT_DIST * m.currentScale + 8 && r.y >= GROUND - 2) {
        const wasMaxed = !!m.maxedAt
        m.eaten = true; m.eatenTime = time; m.scaleAtEat = m.currentScale
        if (!r.tripping) {
          r.tripping = true; r.tripTimer = 280; r.tripPhase = 0; r.tripType = m.type
        } else {
          r.tripTimer += 150
          if (r.tripType !== m.type) r.tripType = m.type
        }
        r.vy = -2.5
        r.sizeBoost = Math.min(1.5, r.sizeBoost + 0.06)
        // Rainbow only when eating a fully grown mushroom
        if (wasMaxed) {
          rainbows.value.push({ x: r.x, spawnTime: time, opacity: 0, phase: 0 })
        }
        // Breeding: babies must grow to adult size first, then eat 5 mushrooms like adults
        r.mushroomsEaten = (r.mushroomsEaten || 0) + 1
        let shouldBreed = false
        if (r.isBaby) {
          // Graduate to adult when reaching adult size
          if (r.sizeBoost >= 1) {
            r.isBaby = false
            r.mushroomsEaten = 0
          }
        } else if (r.mushroomsEaten >= 5) {
          shouldBreed = true
          r.mushroomsEaten = 0
        }
        if (shouldBreed) {
          const babyColors = rabbitPalettes[Math.floor(Math.random() * rabbitPalettes.length)]
          rabbits.value.push({
            x: r.x + (Math.random() > 0.5 ? 15 : -15), y: 0,
            vx: (Math.random() > 0.5 ? 1 : -1) * (WALK_SPEED_MIN + Math.random() * (WALK_SPEED_MAX - WALK_SPEED_MIN)),
            vy: -3, colors: babyColors, grabbed: false, glowing: false,
            earPhase: Math.random() * Math.PI * 2,
            hopping: false, hopTimer: Math.random() * 10, hopInterval: 12 + Math.random() * 10,
            squash: 0,
            tripping: false, tripTimer: 0, tripPhase: 0, tripType: null,
            sizeBoost: 0.5, mushroomsEaten: 0, isBaby: true,
            bubble: null, bubbleCooldown: 0
          })
        }
      }
    })
  })

  // ── Butterflies ──
  butterflies.value.forEach(b => {
    b.phase += b.bobSpeed * dt; b.wingPhase += (0.08 + Math.random() * 0.04) * dt
    // Slow vertical drift — change target every few seconds
    b.driftTimer -= dt
    if (b.driftTimer <= 0) {
      b.driftTarget = (Math.random() - 0.5) * 20
      b.driftTimer = 60 + Math.random() * 120
    }
    b.driftY += (b.driftTarget - b.driftY) * 0.02 * dt
    if (b.fleeing) { b.fleeTimer -= dt; if (b.fleeTimer <= 0) b.fleeing = false; b.x += b.dir * 2 * dt }
    else { b.x += b.dir * b.speed * dt }
    if (b.x < -20) { b.x = w + 20; b.dir = -1 }
    if (b.x > w + 20) { b.x = -20; b.dir = 1 }
    rabbits.value.forEach(r => {
      if (r.y < -5) {
        const bfY = b.baseY + Math.sin(b.phase) * b.bobAmp + b.driftY, rY = -r.y
        const bdx = b.x - r.x, bdy = bfY - rY
        if (bdx * bdx + bdy * bdy < 1600 && !b.fleeing) { b.fleeing = true; b.fleeTimer = 30; b.dir = b.x > r.x ? 1 : -1 }
      }
    })
  })

  // Butterfly–rainbow color shift
  butterflies.value.forEach(bf => {
    if (bf.rainbowHue > 0) bf.rainbowHue = Math.max(0, bf.rainbowHue - 0.4 * dt)
    const bfY = bf.baseY + Math.sin(bf.phase) * bf.bobAmp + bf.driftY
    rainbows.value.forEach(rb => {
      if (rb.opacity < 0.1) return
      const dx = bf.x - rb.x
      const s = rb.phase
      const eRx = 136 * s, eRy = 88 * s
      if (eRx < 1 || eRy < 1) return
      const normSq = (dx / eRx) * (dx / eRx) + (bfY / eRy) * (bfY / eRy)
      if (normSq > 0.3025 && normSq < 0.9801) bf.rainbowHue = 100
    })
  })

  // ── Snails ──
  snails.value.forEach(s => {
    s.x += s.dir * s.speed * dt
    s.antennaPhase += 0.03 * dt
    // Body stretch oscillation (crawling motion)
    s.bodyStretch = Math.sin(s.antennaPhase * 2) * 0.8
    // Wall wrap
    if (s.x < -10) { s.x = w + 10; }
    if (s.x > w + 10) { s.x = -10; }
    // Occasionally change direction
    if (Math.random() < 0.0005 * dt) s.dir = -s.dir
  })

  // ── Sky (sun/moon) — throttled ──
  if (++skyFrame >= SKY_UPDATE_INTERVAL) {
    skyFrame = 0
    sky.value = computeSky(w)
  }

  // ── Clouds ──
  clouds.value.forEach(c => {
    c.x += (c.speed + weather.value.wind * 0.12) * dt
    if (c.x > w + 80) c.x = -90
  })

  // ── Rain / Snow ──
  const sh = stripH.value
  const groundLine = sh - groundY.value
  if (weather.value.type === 'rainy') {
    wxParticles.value.forEach(p => {
      p.y += p.speed * dt
      p.x += weather.value.wind * 2.5 * dt
      if (p.y > groundLine || p.x > w + 10 || p.x < -10) {
        p.y = -p.len - Math.random() * 50
        p.x = Math.random() * w
      }
    })
  } else if (weather.value.type === 'snowy') {
    wxParticles.value.forEach(p => {
      p.y += p.speed * dt
      p.swayPh += p.swaySp * dt
      p.x += (Math.sin(p.swayPh) * 0.25 + weather.value.wind * 0.4) * dt
      if (p.y > groundLine || p.x > w + 10 || p.x < -10) {
        p.y = -p.r * 2 - Math.random() * 40
        p.x = Math.random() * w
      }
    })
  }

  // ── Rainbows ──
  rainbows.value.forEach(rb => {
    const age = time - rb.spawnTime
    if (age < 400) rb.opacity = age / 400
    else if (age < 5000) rb.opacity = 1
    else if (age < 7000) rb.opacity = 1 - (age - 5000) / 2000
    else rb.opacity = 0
    rb.phase = Math.min(1, age / 400)
  })
  rainbows.value = rainbows.value.filter(rb => time - rb.spawnTime < 7000)

  // ── Cloud–rainbow → 七彩祥云 ──
  clouds.value.forEach(cl => {
    if (cl.rainbowHue > 0) {
      cl.rainbowHue = Math.max(0, cl.rainbowHue - 0.15 * dt)
      cl.rainbowPhase += 0.06 * dt
    }
    rainbows.value.forEach(rb => {
      if (rb.opacity < 0.1) return
      const dx = cl.x - rb.x
      const dy = cl.y
      const s = rb.phase
      const eRx = 136 * s, eRy = 88 * s
      if (eRx < 1 || eRy < 1) return
      const normSq = (dx / eRx) * (dx / eRx) + (dy / eRy) * (dy / eRy)
      if (normSq > 0.09 && normSq < 1.3225) cl.rainbowHue = 100
    })
  })

  // ── Spores ──
  spores.value.forEach(sp => {
    sp.x += sp.vx * dt
    sp.y += sp.vy * dt
    sp.vx += (Math.random() - 0.5) * 0.02 * dt
    sp.opacity = Math.max(0, 1 - (time - sp.spawnTime) / 4000) * 0.6
  })
  spores.value = spores.value.filter(sp => time - sp.spawnTime < 4000)

  // ── Holiday particles & decorations ──
  if (holidayParticles.value.length) {
    const wind = weather.value.wind
    holidayParticles.value.forEach(p => {
      p.swayPhase += p.swaySpeed * dt
      const sway = Math.sin(p.swayPhase) * 0.3
      p.x += (p.vx + sway + wind * 0.2) * dt
      p.y += p.vy * dt
      p.rotation += p.rotSpeed * dt
      if (p.life < 9999) {
        p.life -= dt
        p.opacity = Math.max(0, (p.life / p.maxLife) * 0.7)
      }
      // Boundary recycle
      if (p.y > sh) { p.y = -10; p.x = Math.random() * w }
      if (p.y < -20 && p.vy < 0) { p.y = sh + 10; p.x = Math.random() * w }
      if (p.x > w + 20) p.x = -10
      if (p.x < -20) p.x = w + 10
      // Firework spark: respawn when life ends
      if (p.type === 'firework-spark' && p.life <= 0) {
        p.x = Math.random() * w
        p.y = Math.random() * sh * 0.6
        p.vy = -(0.5 + Math.random() * 1.5)
        p.vx = (Math.random() - 0.5) * 0.8
        p.life = 60 + Math.random() * 60
        p.opacity = 0.4 + Math.random() * 0.4
      }
    })
    triggerRef(holidayParticles)
  }
  if (holidayDecorations.value.length) {
    holidayDecorations.value.forEach(d => {
      d.wobblePhase += d.wobbleSpeed * dt
    })
    triggerRef(holidayDecorations)
  }

  // ── Snake in grass ──
  snakeGrasses.value.forEach(sg => {
    const g = grasses.value[sg.grassIdx]
    if (!g) return
    if (!sg.rustling) {
      sg.rustleTimer -= dt
      if (sg.rustleTimer <= 0) {
        sg.rustling = true
        sg.rustleTimer = 20 + Math.random() * 15
      }
    } else {
      sg.rustlePhase += 0.5 * dt
      sg.rustleAmount = Math.sin(sg.rustlePhase * 3) * 6
      sg.rustleTimer -= dt
      if (sg.rustleTimer <= 0) {
        sg.rustling = false
        sg.rustleAmount = 0
        sg.rustleTimer = 120 + Math.random() * 300
      }
    }
    if (sg.rustling) g.bend += sg.rustleAmount
    const target = sg.hovered ? 1 : 0
    sg.tailReveal += (target - sg.tailReveal) * 0.06 * dt
    if (sg.tailReveal < 0.01) sg.tailReveal = 0
    if (sg.hissBubble) { sg.hissBubble.timer -= dt; if (sg.hissBubble.timer <= 0) sg.hissBubble = null }
    if (sg.hissCooldown > 0) sg.hissCooldown -= dt
    // Independent snake wriggle — faster when rustling or hovered
    const phaseSpeed = sg.rustling ? 0.18 : sg.hovered ? 0.1 : 0.04
    sg.snakePhase += phaseSpeed * dt
    const amp = sg.rustling ? 2.5 : sg.hovered ? 1.5 : 0.8
    sg.swayX = Math.sin(sg.snakePhase * 1.3) * amp
    sg.swayRot = Math.sin(sg.snakePhase * 0.9 + 0.7) * (amp * 1.5)
  })

  // ── Grass bending ──
  const windPush = weather.value.wind * 4
  grasses.value.forEach(g => {
    let target = windPush
    rabbits.value.forEach(r => {
      if (r.grabbed || r.y < -2) return
      const dist = Math.abs(r.x - g.x)
      if (dist < 24) {
        const inf = 1 - dist / 24
        target += Math.sign(r.vx) * inf * (r.tripping ? 32 : 20)
      }
    })
    g.bend += (target - g.bend) * 0.12 * dt
    if (Math.abs(g.bend - windPush) < 0.05 && target === windPush) g.bend = windPush
  })

  // Trigger shallow ref updates for Vue reactivity
  triggerRef(rabbits)
  triggerRef(mushrooms)
  triggerRef(clouds)
  triggerRef(butterflies)
  triggerRef(snails)
  triggerRef(grasses)
  triggerRef(snakeGrasses)
  if (rainbows.value.length) triggerRef(rainbows)
  if (spores.value.length) triggerRef(spores)
  if (wxParticles.value.length && weather.value.type !== 'clear') triggerRef(wxParticles)

  if (isVisible && !lightboxOpen) animFrame = requestAnimationFrame(tick)
}

// ── Drag ──
let grab = null
function onDown(e, idx) {
  e.preventDefault()
  const r = rabbits.value[idx]
  r.grabbed = true; r.glowing = true; r.vy = 0
  const rect = container.value.getBoundingClientRect()
  const elBottom = groundY.value - r.y
  grab = {
    idx, offX: e.clientX - rect.left - r.x,
    offY: e.clientY - (rect.bottom - elBottom - RABBIT_H),
    prevX: e.clientX, prevY: e.clientY, vx: 0, vy: 0, ts: performance.now()
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}
function onMove(e) {
  if (!grab) return
  const r = rabbits.value[grab.idx]
  const rect = container.value.getBoundingClientRect()
  r.x = e.clientX - rect.left - grab.offX
  r.y = groundY.value - (rect.bottom - (e.clientY - grab.offY) - RABBIT_H)
  const now = performance.now(), el = now - grab.ts
  if (el > 0) {
    const a = 0.3
    grab.vx = a * (e.clientX - grab.prevX) / el * 16 + (1 - a) * grab.vx
    grab.vy = a * (e.clientY - grab.prevY) / el * 16 + (1 - a) * grab.vy
  }
  grab.prevX = e.clientX; grab.prevY = e.clientY; grab.ts = now
}
function onUp() {
  if (!grab) return
  const r = rabbits.value[grab.idx]
  r.grabbed = false; r.glowing = false
  r.vx = Math.max(-8, Math.min(8, grab.vx))
  r.vy = Math.max(-8, Math.min(8, grab.vy))
  grab = null
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onUp)
}
function onResize() {
  measureGround()
  const w = container.value?.offsetWidth || 800
  rabbits.value.forEach(r => { if (r.x > w - RABBIT_W / 2) r.x = w - RABBIT_W / 2 })
}
let resizeTimer = 0
function onResizeThrottled() {
  if (resizeTimer) return
  resizeTimer = requestAnimationFrame(() => { resizeTimer = 0; onResize() })
}

onMounted(() => {
  measureGround()
  const footer = document.querySelector('.app-footer')
  if (footer) { resizeObs = new ResizeObserver(measureGround); resizeObs.observe(footer) }
  window.addEventListener('resize', onResizeThrottled)

  // Lazy init + visibility-driven loop: only compute when footer is in viewport
  visibilityObs = new IntersectionObserver((entries) => {
    const wasVisible = isVisible
    isVisible = entries[0].isIntersecting
    if (isVisible && !wasVisible) {
      if (!sceneReady) { initScene(); sceneReady = true }
      startLoop()
    }
    // stopLoop happens naturally: tick() checks isVisible before scheduling next frame
  }, { rootMargin: '100px' }) // start slightly before entering viewport
  if (container.value) visibilityObs.observe(container.value)
  window.addEventListener('lightbox-change', onLightboxChange)
})
onUnmounted(() => {
  if (resizeObs) resizeObs.disconnect()
  if (visibilityObs) visibilityObs.disconnect()
  stopLoop()
  if (resizeTimer) cancelAnimationFrame(resizeTimer)
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onUp)
  window.removeEventListener('resize', onResizeThrottled)
  window.removeEventListener('lightbox-change', onLightboxChange)
})

// ── Helpers ──
function earTilt(phase) { return Math.sin(phase) * 5 }
function wingScale(phase) { return 0.35 + 0.65 * Math.abs(Math.cos(phase)) }
function tripFade(r) { return r.tripping ? Math.min(1, r.tripTimer / 50) : 0 }

function getSquash(r) {
  if (r.grabbed) return { sx: 1.1, sy: 1.1 }
  // Landing squash
  if (r.squash > 0.003) return { sx: 1 + r.squash, sy: 1 - r.squash * 1.2 }
  // In air: stretch vertically
  if (r.y < -0.5) {
    const s = Math.min(0.07, Math.abs(r.vy) * 0.018)
    return { sx: 1 - s * 0.4, sy: 1 + s }
  }
  // Crouching before hop (last 35% of interval)
  if (r.y >= GROUND - 0.1 && !r.hopping) {
    const p = r.hopTimer / r.hopInterval
    if (p > 0.65) {
      const t = (p - 0.65) / 0.35
      return { sx: 1 + t * t * 0.07, sy: 1 - t * t * 0.1 }
    }
  }
  return { sx: 1, sy: 1 }
}

function bladePath(bx, baseY, h, lean, curve, w) {
  const hw = w * 0.5
  const tipX = bx + lean
  const tipY = baseY - h
  const cx = (bx + tipX) * 0.5 + curve
  const cpY = baseY - h * 0.55
  return `M${bx} ${baseY} Q${cx - hw} ${cpY}, ${tipX} ${tipY} Q${cx + hw} ${cpY}, ${bx} ${baseY} Z`
}

function rabbitTransform(r) {
  const sq = getSquash(r)
  const fade = tripFade(r)
  // Dizzy: scale pulse
  if (r.tripType === 'dizzy' && fade > 0) {
    const pulse = 1 + Math.sin(r.tripPhase * 4) * fade * 0.18
    sq.sx *= pulse; sq.sy *= pulse
  }
  // Sparkle: gentle pulse
  if (r.tripType === 'sparkle' && fade > 0) {
    const pulse = 1 + Math.sin(r.tripPhase * 3) * fade * 0.06
    sq.sx *= pulse; sq.sy *= pulse
  }
  const flipX = r.vx < 0 ? -1 : 1
  const boost = r.sizeBoost || 1
  let rot = ''
  if (r.tripType === 'rainbow' && fade > 0) rot = ` rotate(${Math.sin(r.tripPhase * 3) * fade * 8}deg)`
  if (r.tripType === 'dizzy' && fade > 0) rot = ` rotate(${Math.sin(r.tripPhase * 2) * fade * 14}deg)`
  if (r.tripType === 'sparkle' && fade > 0) rot = ` translateY(${Math.sin(r.tripPhase * 2) * fade * -4}px)`
  return `translateX(-15px) scaleX(${flipX * sq.sx * boost}) scaleY(${sq.sy * boost})${rot}`
}

function svgFilter(r) {
  const fade = tripFade(r)
  if (fade < 0.01) return ''
  if (r.tripType === 'rainbow') {
    return `hue-rotate(${(r.tripPhase * 65) % 360}deg) saturate(${1 + fade * 1.6}) brightness(${1 + fade * 0.12})`
  }
  if (r.tripType === 'dizzy') {
    return `brightness(${1 + Math.sin(r.tripPhase * 5) * fade * 0.18})`
  }
  if (r.tripType === 'sparkle') {
    return `brightness(${1 + fade * 0.25}) drop-shadow(0 0 ${3 * fade}px rgba(80, 160, 255, ${0.7 * fade}))`
  }
  return ''
}

// Combined filter for .rabbit wrapper div: base drop-shadow + trip effects.
// Transform is also applied on the .rabbit div (via rabbitTransform) so that filter and
// transform share the same element. Per CSS spec: paint content → apply filter → apply transform.
// This prevents Safari from clipping scaled overflow (ears) inside the filter compositing layer.
function rabbitDivFilter(r) {
  const base = 'drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1))'
  const trip = svgFilter(r)
  return trip ? `${base} ${trip}` : ''
}

// ── Snake helpers ──
function isSnakeGrass(idx) {
  return snakeGrasses.value.some(sg => sg.grassIdx === idx)
}
function getSnakeData(idx) {
  return snakeGrasses.value.find(sg => sg.grassIdx === idx)
}
function onGrassEnter(idx) {
  const sg = snakeGrasses.value.find(s => s.grassIdx === idx)
  if (sg) sg.hovered = true
}
function onGrassLeave(idx) {
  const sg = snakeGrasses.value.find(s => s.grassIdx === idx)
  if (sg) sg.hovered = false
}
function onSnakeClick(idx) {
  const sg = snakeGrasses.value.find(s => s.grassIdx === idx)
  if (!sg || sg.tailReveal < 0.3 || sg.hissBubble || sg.hissCooldown > 0) return
  const locale = lang.value?.replace(/\/.*/, '') || 'en'
  const pool = snakeHisses[locale] || snakeHisses['en']
  sg.hissBubble = { text: pool[Math.floor(Math.random() * pool.length)], timer: 100 }
  sg.hissCooldown = 200
  sg.rustling = true
  sg.rustleTimer = 20 + Math.random() * 15
}
</script>

<template>
  <div class="scene-strip" ref="container">
    <!-- ═══ Stars (night, clear/partly-cloudy) ═══ -->
    <template v-if="!sky.isSun && (weather.type === 'clear' || weather.type === 'partly-cloudy')">
      <div v-for="(s, i) in stars" :key="'st' + i"
        class="star" :class="{ 'star-glow': s.glow, 'star-warm': s.warm }"
        :style="{
          left: s.x + 'px',
          bottom: (groundY + s.y) + 'px',
          width: s.r * 2 + 'px', height: s.r * 2 + 'px',
          animationDelay: s.delay + 's',
          animationDuration: s.duration + 's'
        }" />
    </template>

    <!-- ═══ Sun / Moon ═══ -->
    <div
      class="celestial"
      :class="sky.isSun ? 'is-sun' : 'is-moon'"
      :style="{
        left: sky.x + 'px',
        bottom: (groundY + 55 + sky.arcY) + 'px'
      }"
    >
      <!-- Sun -->
      <svg v-if="sky.isSun" width="58" height="58" viewBox="0 0 36 36" overflow="visible">
        <defs>
          <radialGradient id="sunGrad" cx="42%" cy="38%" r="55%">
            <stop offset="0%" stop-color="#fffbe8" />
            <stop offset="35%" stop-color="#ffdd44" />
            <stop offset="100%" stop-color="#ff9922" />
          </radialGradient>
          <radialGradient id="sunGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#ffdd44" stop-opacity="0.25" />
            <stop offset="60%" stop-color="#ffaa22" stop-opacity="0.08" />
            <stop offset="100%" stop-color="#ff8800" stop-opacity="0" />
          </radialGradient>
        </defs>
        <!-- Outer glow -->
        <circle cx="18" cy="18" r="17" fill="url(#sunGlow)" />
        <!-- Rays -->
        <g opacity="0.35">
          <line v-for="n in 12" :key="n"
            :x1="18 + Math.cos(n * Math.PI / 6) * 9.5"
            :y1="18 + Math.sin(n * Math.PI / 6) * 9.5"
            :x2="18 + Math.cos(n * Math.PI / 6) * (n % 2 === 0 ? 16 : 13)"
            :y2="18 + Math.sin(n * Math.PI / 6) * (n % 2 === 0 ? 16 : 13)"
            stroke="#ffcc33" :stroke-width="n % 2 === 0 ? 1.5 : 1" stroke-linecap="round"
          />
        </g>
        <!-- Body -->
        <circle cx="18" cy="18" r="8" fill="url(#sunGrad)" />
        <circle cx="15.5" cy="15.5" r="3" fill="#fffbe8" opacity="0.3" />
      </svg>
      <!-- Moon -->
      <svg v-else width="48" height="48" viewBox="0 0 30 30" overflow="visible">
        <defs>
          <radialGradient id="moonGrad" cx="38%" cy="35%" r="60%">
            <stop offset="0%" stop-color="#f8f4e8" />
            <stop offset="55%" stop-color="#e8e0c8" />
            <stop offset="100%" stop-color="#d0c8a8" />
          </radialGradient>
          <!-- Soft-edge moon mask: lit area in white, shadow in black, feathered edge via filter -->
          <filter id="moonSoft" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="0.35" />
          </filter>
          <mask id="moonMask">
            <circle cx="15" cy="15" r="9.5" fill="black" />
            <path :d="moonPhasePath(15, 15, 9, sky.lunarPhase)" fill="white" filter="url(#moonSoft)" />
          </mask>
        </defs>
        <!-- Lit area with soft edge -->
        <circle cx="15" cy="15" r="9" fill="url(#moonGrad)" mask="url(#moonMask)" />
        <!-- Very subtle limb darkening on the lit edge -->
        <circle cx="15" cy="15" r="8.8" fill="none" stroke="#c8c0a0" stroke-width="0.3" opacity="0.08" mask="url(#moonMask)" />
        <!-- Craters on lit area -->
        <circle cx="11" cy="14" r="1.2" fill="#d0c8b0" opacity="0.25" mask="url(#moonMask)" />
        <circle cx="13" cy="19" r="0.9" fill="#d0c8b0" opacity="0.2" mask="url(#moonMask)" />
        <circle cx="9.5" cy="17" r="0.6" fill="#d0c8b0" opacity="0.15" mask="url(#moonMask)" />
        <!-- Surface texture -->
        <circle cx="16.5" cy="12" r="0.5" fill="#d8d0b8" opacity="0.12" mask="url(#moonMask)" />
        <circle cx="12" cy="16.5" r="0.7" fill="#d0c8b0" opacity="0.1" mask="url(#moonMask)" />
      </svg>
    </div>

    <!-- ═══ Ground light spot (from sun/moon) ═══ -->
    <div
      class="ground-light"
      :class="sky.isSun ? 'sun-light' : 'moon-light'"
      :style="{
        left: sky.x + 'px',
        bottom: groundY + 'px',
        opacity: Math.sin(sky.timePhase * Math.PI) * (sky.isSun ? 0.18 : 0.08 * (1 - Math.abs(Math.cos(sky.lunarPhase * 2 * Math.PI))))
      }"
    />

    <!-- ═══ Clouds ═══ -->
    <div v-for="(c, i) in clouds" :key="'cl' + i" class="cloud"
      :style="{
        left: c.x + 'px',
        bottom: (groundY + c.y) + 'px',
        opacity: c.opacity * (sky.isSun ? 1 : 0.65),
        transform: 'translateX(-50%) scale(' + c.scale + ')'
      }">
      <!-- Variant 0: Medium puffy cumulus -->
      <svg v-if="c.variant === 0" width="75" height="42" viewBox="0 0 75 42">
        <defs>
          <radialGradient :id="'cg0'+i" cx="50%" cy="35%" r="60%">
            <stop offset="0%" :stop-color="c.pal.top" />
            <stop offset="80%" :stop-color="c.pal.mid" />
            <stop offset="100%" :stop-color="c.pal.edge" />
          </radialGradient>
        </defs>
        <!-- Bottom shadow -->
        <ellipse cx="37" cy="36" rx="26" ry="4" :fill="c.pal.shadow" opacity="0.18" />
        <!-- Base fill -->
        <rect x="10" y="24" width="50" height="11" rx="5.5" :fill="c.pal.base" />
        <!-- Main body blobs -->
        <ellipse cx="20" cy="24" rx="13" ry="10" :fill="`url(#cg0${i})`" />
        <ellipse cx="37" cy="17" rx="16" ry="13" :fill="`url(#cg0${i})`" />
        <ellipse cx="52" cy="23" rx="12" ry="9" :fill="`url(#cg0${i})`" />
        <!-- Secondary bumps for fluffy texture -->
        <ellipse cx="26" cy="14" rx="9" ry="8" :fill="`url(#cg0${i})`" />
        <ellipse cx="45" cy="16" rx="8" ry="7" :fill="`url(#cg0${i})`" />
        <ellipse cx="15" cy="20" rx="7" ry="6" :fill="c.pal.mid" />
        <!-- Top highlights -->
        <ellipse cx="32" cy="10" rx="9" ry="5" :fill="c.pal.top" opacity="0.55" />
        <ellipse cx="44" cy="13" rx="5" ry="3.5" :fill="c.pal.top" opacity="0.4" />
        <ellipse cx="22" cy="12" rx="4" ry="3" :fill="c.pal.top" opacity="0.35" />
        <!-- Bottom edge darkening -->
        <ellipse cx="30" cy="32" rx="20" ry="3.5" :fill="c.pal.shadow" opacity="0.12" />
        <ellipse cx="45" cy="31" rx="12" ry="2.5" :fill="c.pal.shadow" opacity="0.08" />
        <!-- Rainbow overlay -->
        <g v-if="c.rainbowHue > 0" :opacity="c.rainbowHue / 100 * 0.75">
          <defs>
            <linearGradient :id="'rcl'+i" gradientUnits="userSpaceOnUse"
              :x1="37 + Math.cos(c.rainbowPhase) * 40" y1="5"
              :x2="37 + Math.sin(c.rainbowPhase) * 40" y2="35">
              <stop offset="0%" stop-color="#ff4466" />
              <stop offset="10%" stop-color="#ff7744" />
              <stop offset="20%" stop-color="#ffaa33" />
              <stop offset="30%" stop-color="#ffdd44" />
              <stop offset="42%" stop-color="#66ee66" />
              <stop offset="54%" stop-color="#33ddaa" />
              <stop offset="66%" stop-color="#44aaff" />
              <stop offset="76%" stop-color="#5577ff" />
              <stop offset="86%" stop-color="#8855dd" />
              <stop offset="100%" stop-color="#dd55aa" />
            </linearGradient>
            <linearGradient :id="'rclb'+i" gradientUnits="userSpaceOnUse"
              :x1="37 + Math.sin(c.rainbowPhase * 0.7 + 2) * 35" y1="30"
              :x2="37 + Math.cos(c.rainbowPhase * 0.7 + 2) * 35" y2="5">
              <stop offset="0%" stop-color="#44dddd" />
              <stop offset="18%" stop-color="#55aaff" />
              <stop offset="36%" stop-color="#aa66ff" />
              <stop offset="54%" stop-color="#ff66aa" />
              <stop offset="72%" stop-color="#ffaa55" />
              <stop offset="100%" stop-color="#ddff44" />
            </linearGradient>
          </defs>
          <ellipse cx="20" cy="24" rx="13" ry="10" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2) * 0.3" />
          <ellipse cx="37" cy="17" rx="16" ry="13" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.5 + 1) * 0.3" />
          <ellipse cx="52" cy="23" rx="12" ry="9" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 1.8 + 2) * 0.3" />
          <ellipse cx="26" cy="14" rx="9" ry="8" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 3 + 0.5) * 0.3" />
          <ellipse cx="45" cy="16" rx="8" ry="7" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.2 + 3) * 0.3" />
        </g>
      </svg>
      <!-- Variant 1: Wide stratocumulus -->
      <svg v-else-if="c.variant === 1" width="95" height="36" viewBox="0 0 95 36">
        <defs>
          <radialGradient :id="'cg1'+i" cx="50%" cy="38%" r="58%">
            <stop offset="0%" :stop-color="c.pal.top" />
            <stop offset="75%" :stop-color="c.pal.mid" />
            <stop offset="100%" :stop-color="c.pal.edge" />
          </radialGradient>
        </defs>
        <!-- Bottom shadow -->
        <ellipse cx="48" cy="32" rx="38" ry="3.5" :fill="c.pal.shadow" opacity="0.15" />
        <!-- Base -->
        <rect x="8" y="20" width="78" height="9" rx="4.5" :fill="c.pal.base" />
        <!-- Main blobs -->
        <ellipse cx="18" cy="19" rx="14" ry="8" :fill="`url(#cg1${i})`" />
        <ellipse cx="36" cy="14" rx="15" ry="10" :fill="`url(#cg1${i})`" />
        <ellipse cx="55" cy="16" rx="14" ry="9" :fill="`url(#cg1${i})`" />
        <ellipse cx="72" cy="18" rx="12" ry="8" :fill="`url(#cg1${i})`" />
        <!-- Secondary bumps -->
        <ellipse cx="28" cy="12" rx="8" ry="6" :fill="`url(#cg1${i})`" />
        <ellipse cx="46" cy="11" rx="9" ry="6" :fill="`url(#cg1${i})`" />
        <ellipse cx="64" cy="13" rx="7" ry="5" :fill="`url(#cg1${i})`" />
        <ellipse cx="82" cy="20" rx="8" ry="5" :fill="c.pal.mid" />
        <!-- Top highlights -->
        <ellipse cx="34" cy="9" rx="10" ry="4" :fill="c.pal.top" opacity="0.5" />
        <ellipse cx="54" cy="10" rx="7" ry="3.5" :fill="c.pal.top" opacity="0.4" />
        <ellipse cx="20" cy="14" rx="5" ry="3" :fill="c.pal.top" opacity="0.3" />
        <ellipse cx="70" cy="12" rx="5" ry="3" :fill="c.pal.top" opacity="0.3" />
        <!-- Bottom shading -->
        <ellipse cx="40" cy="27" rx="25" ry="3" :fill="c.pal.shadow" opacity="0.1" />
        <!-- Rainbow overlay -->
        <g v-if="c.rainbowHue > 0" :opacity="c.rainbowHue / 100 * 0.75">
          <defs>
            <linearGradient :id="'rcl'+i" gradientUnits="userSpaceOnUse"
              :x1="48 + Math.cos(c.rainbowPhase) * 45" y1="5"
              :x2="48 + Math.sin(c.rainbowPhase) * 45" y2="30">
              <stop offset="0%" stop-color="#ff4466" />
              <stop offset="10%" stop-color="#ff7744" />
              <stop offset="20%" stop-color="#ffaa33" />
              <stop offset="30%" stop-color="#ffdd44" />
              <stop offset="42%" stop-color="#66ee66" />
              <stop offset="54%" stop-color="#33ddaa" />
              <stop offset="66%" stop-color="#44aaff" />
              <stop offset="76%" stop-color="#5577ff" />
              <stop offset="86%" stop-color="#8855dd" />
              <stop offset="100%" stop-color="#dd55aa" />
            </linearGradient>
            <linearGradient :id="'rclb'+i" gradientUnits="userSpaceOnUse"
              :x1="48 + Math.sin(c.rainbowPhase * 0.7 + 2) * 40" y1="28"
              :x2="48 + Math.cos(c.rainbowPhase * 0.7 + 2) * 40" y2="5">
              <stop offset="0%" stop-color="#44dddd" />
              <stop offset="18%" stop-color="#55aaff" />
              <stop offset="36%" stop-color="#aa66ff" />
              <stop offset="54%" stop-color="#ff66aa" />
              <stop offset="72%" stop-color="#ffaa55" />
              <stop offset="100%" stop-color="#ddff44" />
            </linearGradient>
          </defs>
          <ellipse cx="18" cy="19" rx="14" ry="8" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2) * 0.3" />
          <ellipse cx="36" cy="14" rx="15" ry="10" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.5 + 1) * 0.3" />
          <ellipse cx="55" cy="16" rx="14" ry="9" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 1.8 + 2) * 0.3" />
          <ellipse cx="72" cy="18" rx="12" ry="8" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 3 + 0.5) * 0.3" />
        </g>
      </svg>
      <!-- Variant 2: Tall dramatic cumulus -->
      <svg v-else-if="c.variant === 2" width="65" height="48" viewBox="0 0 65 48">
        <defs>
          <radialGradient :id="'cg2'+i" cx="48%" cy="32%" r="62%">
            <stop offset="0%" :stop-color="c.pal.top" />
            <stop offset="70%" :stop-color="c.pal.mid" />
            <stop offset="100%" :stop-color="c.pal.edge" />
          </radialGradient>
        </defs>
        <!-- Bottom shadow -->
        <ellipse cx="33" cy="43" rx="24" ry="4" :fill="c.pal.shadow" opacity="0.2" />
        <!-- Base -->
        <rect x="8" y="32" width="46" height="9" rx="4.5" :fill="c.pal.base" />
        <!-- Main blobs (stacked high) -->
        <ellipse cx="20" cy="30" rx="13" ry="9" :fill="`url(#cg2${i})`" />
        <ellipse cx="33" cy="20" rx="15" ry="14" :fill="`url(#cg2${i})`" />
        <ellipse cx="45" cy="28" rx="12" ry="9" :fill="`url(#cg2${i})`" />
        <!-- Upper tower bumps -->
        <ellipse cx="28" cy="12" rx="10" ry="9" :fill="`url(#cg2${i})`" />
        <ellipse cx="38" cy="14" rx="8" ry="7" :fill="`url(#cg2${i})`" />
        <ellipse cx="22" cy="22" rx="8" ry="6" :fill="c.pal.mid" />
        <!-- Top highlights -->
        <ellipse cx="30" cy="8" rx="8" ry="5" :fill="c.pal.top" opacity="0.6" />
        <ellipse cx="37" cy="11" rx="5" ry="3.5" :fill="c.pal.top" opacity="0.45" />
        <ellipse cx="24" cy="10" rx="4" ry="3" :fill="c.pal.top" opacity="0.35" />
        <!-- Strong bottom shading for dramatic look -->
        <ellipse cx="30" cy="38" rx="22" ry="4" :fill="c.pal.shadow" opacity="0.18" />
        <ellipse cx="40" cy="36" rx="10" ry="3" :fill="c.pal.shadow" opacity="0.1" />
        <!-- Rainbow overlay -->
        <g v-if="c.rainbowHue > 0" :opacity="c.rainbowHue / 100 * 0.75">
          <defs>
            <linearGradient :id="'rcl'+i" gradientUnits="userSpaceOnUse"
              :x1="33 + Math.cos(c.rainbowPhase) * 30" y1="5"
              :x2="33 + Math.sin(c.rainbowPhase) * 30" y2="40">
              <stop offset="0%" stop-color="#ff4466" />
              <stop offset="10%" stop-color="#ff7744" />
              <stop offset="20%" stop-color="#ffaa33" />
              <stop offset="30%" stop-color="#ffdd44" />
              <stop offset="42%" stop-color="#66ee66" />
              <stop offset="54%" stop-color="#33ddaa" />
              <stop offset="66%" stop-color="#44aaff" />
              <stop offset="76%" stop-color="#5577ff" />
              <stop offset="86%" stop-color="#8855dd" />
              <stop offset="100%" stop-color="#dd55aa" />
            </linearGradient>
            <linearGradient :id="'rclb'+i" gradientUnits="userSpaceOnUse"
              :x1="33 + Math.sin(c.rainbowPhase * 0.7 + 2) * 28" y1="38"
              :x2="33 + Math.cos(c.rainbowPhase * 0.7 + 2) * 28" y2="5">
              <stop offset="0%" stop-color="#44dddd" />
              <stop offset="18%" stop-color="#55aaff" />
              <stop offset="36%" stop-color="#aa66ff" />
              <stop offset="54%" stop-color="#ff66aa" />
              <stop offset="72%" stop-color="#ffaa55" />
              <stop offset="100%" stop-color="#ddff44" />
            </linearGradient>
          </defs>
          <ellipse cx="20" cy="30" rx="13" ry="9" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2) * 0.3" />
          <ellipse cx="33" cy="20" rx="15" ry="14" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.5 + 1) * 0.3" />
          <ellipse cx="45" cy="28" rx="12" ry="9" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 1.8 + 2) * 0.3" />
          <ellipse cx="28" cy="12" rx="10" ry="9" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 3 + 0.5) * 0.3" />
        </g>
      </svg>
      <!-- Variant 3: Wispy cirrus -->
      <svg v-else-if="c.variant === 3" width="100" height="22" viewBox="0 0 100 22">
        <defs>
          <radialGradient :id="'cg3'+i" cx="50%" cy="40%" r="60%">
            <stop offset="0%" :stop-color="c.pal.top" />
            <stop offset="80%" :stop-color="c.pal.mid" />
            <stop offset="100%" :stop-color="c.pal.edge" />
          </radialGradient>
        </defs>
        <ellipse cx="25" cy="12" rx="20" ry="5" :fill="`url(#cg3${i})`" opacity="0.7" />
        <ellipse cx="50" cy="10" rx="22" ry="6" :fill="`url(#cg3${i})`" opacity="0.8" />
        <ellipse cx="75" cy="13" rx="18" ry="4.5" :fill="`url(#cg3${i})`" opacity="0.65" />
        <ellipse cx="38" cy="8" rx="12" ry="4" :fill="c.pal.top" opacity="0.35" />
        <ellipse cx="62" cy="9" rx="10" ry="3.5" :fill="c.pal.top" opacity="0.3" />
        <path d="M10 14 Q30 8, 50 11 Q70 7, 90 13" fill="none" :stroke="c.pal.mid" stroke-width="2" opacity="0.3" stroke-linecap="round" />
        <!-- Rainbow overlay -->
        <g v-if="c.rainbowHue > 0" :opacity="c.rainbowHue / 100 * 0.75">
          <defs>
            <linearGradient :id="'rcl'+i" gradientUnits="userSpaceOnUse"
              :x1="50 + Math.cos(c.rainbowPhase) * 50" y1="3"
              :x2="50 + Math.sin(c.rainbowPhase) * 50" y2="19">
              <stop offset="0%" stop-color="#ff4466" />
              <stop offset="10%" stop-color="#ff7744" />
              <stop offset="20%" stop-color="#ffaa33" />
              <stop offset="30%" stop-color="#ffdd44" />
              <stop offset="42%" stop-color="#66ee66" />
              <stop offset="54%" stop-color="#33ddaa" />
              <stop offset="66%" stop-color="#44aaff" />
              <stop offset="76%" stop-color="#5577ff" />
              <stop offset="86%" stop-color="#8855dd" />
              <stop offset="100%" stop-color="#dd55aa" />
            </linearGradient>
            <linearGradient :id="'rclb'+i" gradientUnits="userSpaceOnUse"
              :x1="50 + Math.sin(c.rainbowPhase * 0.7 + 2) * 45" y1="18"
              :x2="50 + Math.cos(c.rainbowPhase * 0.7 + 2) * 45" y2="3">
              <stop offset="0%" stop-color="#44dddd" />
              <stop offset="18%" stop-color="#55aaff" />
              <stop offset="36%" stop-color="#aa66ff" />
              <stop offset="54%" stop-color="#ff66aa" />
              <stop offset="72%" stop-color="#ffaa55" />
              <stop offset="100%" stop-color="#ddff44" />
            </linearGradient>
          </defs>
          <ellipse cx="25" cy="12" rx="20" ry="5" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2) * 0.3" />
          <ellipse cx="50" cy="10" rx="22" ry="6" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.5 + 1) * 0.3" />
          <ellipse cx="75" cy="13" rx="18" ry="4.5" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 1.8 + 2) * 0.3" />
        </g>
      </svg>
      <!-- Variant 4: Double-decker cumulus -->
      <svg v-else-if="c.variant === 4" width="80" height="55" viewBox="0 0 80 55">
        <defs>
          <radialGradient :id="'cg4'+i" cx="50%" cy="35%" r="58%">
            <stop offset="0%" :stop-color="c.pal.top" />
            <stop offset="75%" :stop-color="c.pal.mid" />
            <stop offset="100%" :stop-color="c.pal.edge" />
          </radialGradient>
        </defs>
        <ellipse cx="40" cy="49" rx="30" ry="4" :fill="c.pal.shadow" opacity="0.18" />
        <rect x="10" y="36" width="55" height="12" rx="6" :fill="c.pal.base" />
        <!-- Lower deck -->
        <ellipse cx="18" cy="35" rx="14" ry="10" :fill="`url(#cg4${i})`" />
        <ellipse cx="40" cy="32" rx="16" ry="11" :fill="`url(#cg4${i})`" />
        <ellipse cx="58" cy="36" rx="13" ry="9" :fill="`url(#cg4${i})`" />
        <!-- Upper deck -->
        <ellipse cx="30" cy="20" rx="13" ry="11" :fill="`url(#cg4${i})`" />
        <ellipse cx="48" cy="18" rx="11" ry="10" :fill="`url(#cg4${i})`" />
        <!-- Tower top -->
        <ellipse cx="36" cy="10" rx="9" ry="8" :fill="`url(#cg4${i})`" />
        <ellipse cx="44" cy="12" rx="7" ry="6" :fill="c.pal.mid" />
        <!-- Highlights -->
        <ellipse cx="34" cy="7" rx="7" ry="4" :fill="c.pal.top" opacity="0.55" />
        <ellipse cx="25" cy="16" rx="5" ry="3" :fill="c.pal.top" opacity="0.4" />
        <ellipse cx="50" cy="14" rx="4" ry="2.5" :fill="c.pal.top" opacity="0.35" />
        <!-- Bottom shading -->
        <ellipse cx="35" cy="44" rx="24" ry="3.5" :fill="c.pal.shadow" opacity="0.15" />
        <!-- Rainbow overlay -->
        <g v-if="c.rainbowHue > 0" :opacity="c.rainbowHue / 100 * 0.75">
          <defs>
            <linearGradient :id="'rcl'+i" gradientUnits="userSpaceOnUse"
              :x1="40 + Math.cos(c.rainbowPhase) * 35" y1="5"
              :x2="40 + Math.sin(c.rainbowPhase) * 35" y2="45">
              <stop offset="0%" stop-color="#ff4466" />
              <stop offset="10%" stop-color="#ff7744" />
              <stop offset="20%" stop-color="#ffaa33" />
              <stop offset="30%" stop-color="#ffdd44" />
              <stop offset="42%" stop-color="#66ee66" />
              <stop offset="54%" stop-color="#33ddaa" />
              <stop offset="66%" stop-color="#44aaff" />
              <stop offset="76%" stop-color="#5577ff" />
              <stop offset="86%" stop-color="#8855dd" />
              <stop offset="100%" stop-color="#dd55aa" />
            </linearGradient>
            <linearGradient :id="'rclb'+i" gradientUnits="userSpaceOnUse"
              :x1="40 + Math.sin(c.rainbowPhase * 0.7 + 2) * 32" y1="42"
              :x2="40 + Math.cos(c.rainbowPhase * 0.7 + 2) * 32" y2="5">
              <stop offset="0%" stop-color="#44dddd" />
              <stop offset="18%" stop-color="#55aaff" />
              <stop offset="36%" stop-color="#aa66ff" />
              <stop offset="54%" stop-color="#ff66aa" />
              <stop offset="72%" stop-color="#ffaa55" />
              <stop offset="100%" stop-color="#ddff44" />
            </linearGradient>
          </defs>
          <ellipse cx="18" cy="35" rx="14" ry="10" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2) * 0.3" />
          <ellipse cx="40" cy="32" rx="16" ry="11" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.5 + 1) * 0.3" />
          <ellipse cx="58" cy="36" rx="13" ry="9" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 1.8 + 2) * 0.3" />
          <ellipse cx="30" cy="20" rx="13" ry="11" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 3 + 0.5) * 0.3" />
          <ellipse cx="48" cy="18" rx="11" ry="10" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.2 + 3) * 0.3" />
          <ellipse cx="36" cy="10" rx="9" ry="8" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.8 + 1.5) * 0.3" />
        </g>
      </svg>
      <!-- Variant 5: Flat layered stratus -->
      <svg v-else width="90" height="28" viewBox="0 0 90 28">
        <defs>
          <radialGradient :id="'cg5'+i" cx="50%" cy="45%" r="55%">
            <stop offset="0%" :stop-color="c.pal.top" />
            <stop offset="80%" :stop-color="c.pal.mid" />
            <stop offset="100%" :stop-color="c.pal.edge" />
          </radialGradient>
        </defs>
        <ellipse cx="45" cy="25" rx="38" ry="3" :fill="c.pal.shadow" opacity="0.12" />
        <!-- Layered bands -->
        <rect x="5" y="16" width="80" height="8" rx="4" :fill="c.pal.base" />
        <ellipse cx="20" cy="16" rx="16" ry="7" :fill="`url(#cg5${i})`" />
        <ellipse cx="42" cy="13" rx="18" ry="8" :fill="`url(#cg5${i})`" />
        <ellipse cx="65" cy="15" rx="15" ry="7" :fill="`url(#cg5${i})`" />
        <ellipse cx="80" cy="17" rx="10" ry="5.5" :fill="`url(#cg5${i})`" />
        <!-- Secondary bumps -->
        <ellipse cx="30" cy="10" rx="10" ry="5.5" :fill="`url(#cg5${i})`" />
        <ellipse cx="52" cy="9" rx="11" ry="5" :fill="`url(#cg5${i})`" />
        <ellipse cx="12" cy="14" rx="9" ry="4.5" :fill="c.pal.mid" />
        <!-- Highlights -->
        <ellipse cx="38" cy="7" rx="12" ry="3.5" :fill="c.pal.top" opacity="0.45" />
        <ellipse cx="58" cy="8" rx="7" ry="3" :fill="c.pal.top" opacity="0.35" />
        <ellipse cx="22" cy="9" rx="6" ry="2.5" :fill="c.pal.top" opacity="0.3" />
        <!-- Bottom shading -->
        <ellipse cx="45" cy="22" rx="30" ry="2.5" :fill="c.pal.shadow" opacity="0.1" />
        <!-- Rainbow overlay -->
        <g v-if="c.rainbowHue > 0" :opacity="c.rainbowHue / 100 * 0.75">
          <defs>
            <linearGradient :id="'rcl'+i" gradientUnits="userSpaceOnUse"
              :x1="45 + Math.cos(c.rainbowPhase) * 42" y1="3"
              :x2="45 + Math.sin(c.rainbowPhase) * 42" y2="24">
              <stop offset="0%" stop-color="#ff4466" />
              <stop offset="10%" stop-color="#ff7744" />
              <stop offset="20%" stop-color="#ffaa33" />
              <stop offset="30%" stop-color="#ffdd44" />
              <stop offset="42%" stop-color="#66ee66" />
              <stop offset="54%" stop-color="#33ddaa" />
              <stop offset="66%" stop-color="#44aaff" />
              <stop offset="76%" stop-color="#5577ff" />
              <stop offset="86%" stop-color="#8855dd" />
              <stop offset="100%" stop-color="#dd55aa" />
            </linearGradient>
            <linearGradient :id="'rclb'+i" gradientUnits="userSpaceOnUse"
              :x1="45 + Math.sin(c.rainbowPhase * 0.7 + 2) * 38" y1="22"
              :x2="45 + Math.cos(c.rainbowPhase * 0.7 + 2) * 38" y2="3">
              <stop offset="0%" stop-color="#44dddd" />
              <stop offset="18%" stop-color="#55aaff" />
              <stop offset="36%" stop-color="#aa66ff" />
              <stop offset="54%" stop-color="#ff66aa" />
              <stop offset="72%" stop-color="#ffaa55" />
              <stop offset="100%" stop-color="#ddff44" />
            </linearGradient>
          </defs>
          <ellipse cx="20" cy="16" rx="16" ry="7" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2) * 0.3" />
          <ellipse cx="42" cy="13" rx="18" ry="8" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.5 + 1) * 0.3" />
          <ellipse cx="65" cy="15" rx="15" ry="7" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 1.8 + 2) * 0.3" />
          <ellipse cx="30" cy="10" rx="10" ry="5.5" :fill="`url(#rclb${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 3 + 0.5) * 0.3" />
          <ellipse cx="52" cy="9" rx="11" ry="5" :fill="`url(#rcl${i})`" :opacity="0.7 + Math.sin(c.rainbowPhase * 2.2 + 3) * 0.3" />
        </g>
      </svg>
    </div>

    <!-- ═══ Grass ═══ -->
    <div
      v-for="(g, i) in grasses" :key="'g' + i"
      class="grass-cluster" :class="{ 'grass-has-snake': isSnakeGrass(i) }"
      :style="{
        left: g.x + 'px', bottom: groundY + 'px',
        transform: `rotate(${g.bend}deg)`, transformOrigin: 'bottom center'
      }"
      @pointerenter="onGrassEnter(i)"
      @pointerleave="onGrassLeave(i)"
      @click="onSnakeClick(i)"
    >
      <svg :width="g.totalW" :height="g.maxH" :viewBox="`0 0 ${g.totalW} ${g.maxH}`" overflow="visible">
        <!-- Dark base band -->
        <rect x="0" :y="g.maxH - 2" :width="g.totalW" height="2" fill="#2a5a28" opacity="0.12" rx="1" />
        <path
          v-for="(b, j) in g.blades" :key="j"
          :d="bladePath(b.x, g.maxH, b.h, b.lean, b.curve, b.width)"
          :fill="b.color" :opacity="b.opacity"
        />
        <!-- Lighter highlight blade overlay on tallest blades -->
        <template v-for="(b, j) in g.blades" :key="'h' + j">
          <path
            v-if="b.h > 12"
            :d="bladePath(b.x + 0.3, g.maxH, b.h * 0.6, b.lean * 0.8, b.curve * 0.7, b.width * 0.4)"
            fill="#a0d898" opacity="0.2"
          />
        </template>
        <!-- Tiny wildflowers on some blades -->
        <template v-for="(b, j) in g.blades" :key="'f' + j">
          <g v-if="b.flower">
            <circle
              :cx="b.x + b.lean" :cy="g.maxH - b.h - 2"
              :r="b.flower.r" :fill="b.flower.color" :opacity="0.85"
            />
            <circle
              :cx="b.x + b.lean - 0.3" :cy="g.maxH - b.h - 2.3"
              :r="b.flower.r * 0.35" fill="#fff" opacity="0.5"
            />
            <circle
              :cx="b.x + b.lean" :cy="g.maxH - b.h - 2"
              :r="b.flower.r * 0.35" fill="#f8e858" opacity="0.9"
            />
          </g>
        </template>
        <!-- Snake tail (rattlesnake) -->
        <template v-if="getSnakeData(i)">
          <g :opacity="getSnakeData(i).tailReveal"
             :transform="`translate(${g.totalW * 0.55}, ${g.maxH})`">
            <svg width="14" height="30" viewBox="0 0 28 58" x="-7" y="-30" overflow="visible">
              <g :transform="`translate(0,58) scale(1,-1) translate(${getSnakeData(i).swayX}, 0) rotate(${getSnakeData(i).swayRot}, 14, 0)`">
                <!-- Body: S-curve sandy brown -->
                <path d="M10 0 Q18 5, 12 13 Q5 21, 13 28 Q19 33, 15 37"
                  fill="none" stroke="#c0944a" stroke-width="5.5" stroke-linecap="round" />
                <!-- Dorsal darker shade -->
                <path d="M10 0 Q18 5, 12 13 Q5 21, 13 28 Q19 33, 15 37"
                  fill="none" stroke="#8a6428" stroke-width="6.2" stroke-linecap="round" opacity="0.2" />
                <!-- Belly lighter center -->
                <path d="M10 0 Q18 5, 12 13 Q5 21, 13 28 Q19 33, 15 37"
                  fill="none" stroke="#dab868" stroke-width="2.2" stroke-linecap="round" opacity="0.5" />
                <!-- Diamond 1 -->
                <path d="M10 4.2 L13 2.5 L15.5 5 L13 7 Z" fill="#2a1808" opacity="0.5" />
                <path d="M9.5 4 L13 2 L16 5 L13 7.5 Z" fill="none" stroke="#f0e8d8" stroke-width="0.6" opacity="0.6" stroke-linejoin="round" />
                <path d="M11.5 4.5 L13 3.5 L14.2 5 L13 6 Z" fill="#4a3018" opacity="0.25" />
                <!-- Diamond 2 -->
                <path d="M7.5 12 L10.5 10 L13 12.5 L10.5 14.5 Z" fill="#2a1808" opacity="0.45" />
                <path d="M7 12 L10.5 9.5 L13.5 12.5 L10.5 15 Z" fill="none" stroke="#f0e8d8" stroke-width="0.55" opacity="0.55" stroke-linejoin="round" />
                <path d="M9 12.2 L10.5 11 L12 12.5 L10.5 13.8 Z" fill="#4a3018" opacity="0.2" />
                <!-- Diamond 3 -->
                <path d="M9.5 20 L12.5 18 L15.5 20.5 L12.5 22.5 Z" fill="#2a1808" opacity="0.4" />
                <path d="M9 20 L12.5 17.5 L16 20.5 L12.5 23 Z" fill="none" stroke="#f0e8d8" stroke-width="0.5" opacity="0.45" stroke-linejoin="round" />
                <!-- Diamond 4 (smaller, near tail) -->
                <path d="M12.5 27 L14.5 26 L16.5 27.5 L14.5 29 Z" fill="#2a1808" opacity="0.35" />
                <path d="M12 27 L14.5 25.5 L17 27.5 L14.5 29.5 Z" fill="none" stroke="#f0e8d8" stroke-width="0.45" opacity="0.4" stroke-linejoin="round" />
                <!-- White highlight accents between diamonds -->
                <path d="M11 3 Q13 2, 15 3.5" fill="none" stroke="#fff" stroke-width="0.4" opacity="0.25" stroke-linecap="round" />
                <path d="M8 11 Q10 9.5, 12 11" fill="none" stroke="#fff" stroke-width="0.35" opacity="0.2" stroke-linecap="round" />
                <path d="M10 18.5 Q12 17, 14.5 18.5" fill="none" stroke="#fff" stroke-width="0.3" opacity="0.18" stroke-linecap="round" />
                <!-- Dark speckles -->
                <circle cx="14.5" cy="8.5" r="0.35" fill="#3a2010" opacity="0.3" />
                <circle cx="8.5" cy="16" r="0.3" fill="#3a2010" opacity="0.25" />
                <circle cx="15" cy="18" r="0.3" fill="#3a2010" opacity="0.2" />
                <circle cx="10" cy="24" r="0.3" fill="#3a2010" opacity="0.2" />
                <!-- Tail bands: alternating white/black -->
                <path d="M15 35 Q16 34.5, 17 35.5" fill="none" stroke="#f0e8d8" stroke-width="2.8" stroke-linecap="butt" opacity="0.85" />
                <path d="M15.2 37.2 Q16 36.8, 17 37.5" fill="none" stroke="#1a1008" stroke-width="2.4" stroke-linecap="butt" opacity="0.7" />
                <path d="M15.3 39 Q16 38.5, 16.8 39.2" fill="none" stroke="#f0e8d8" stroke-width="2" stroke-linecap="butt" opacity="0.8" />
                <path d="M15.3 40.5 Q16 40.2, 16.5 40.8" fill="none" stroke="#1a1008" stroke-width="1.6" stroke-linecap="butt" opacity="0.65" />
                <!-- Rattle segment 1 -->
                <ellipse cx="15.8" cy="42.2" rx="3.4" ry="1.7" fill="#c4a058" stroke="#8a7030" stroke-width="0.35" />
                <line x1="12.5" y1="42.2" x2="19" y2="42.2" stroke="#8a7030" stroke-width="0.3" opacity="0.5" />
                <!-- Rattle segment 2 -->
                <ellipse cx="15.8" cy="44.2" rx="3" ry="1.5" fill="#b89850" stroke="#806828" stroke-width="0.35" />
                <line x1="13" y1="44.2" x2="18.6" y2="44.2" stroke="#806828" stroke-width="0.28" opacity="0.45" />
                <!-- Rattle segment 3 -->
                <ellipse cx="15.8" cy="46" rx="2.5" ry="1.3" fill="#ac9048" stroke="#786020" stroke-width="0.3" />
                <line x1="13.5" y1="46" x2="18" y2="46" stroke="#786020" stroke-width="0.25" opacity="0.4" />
                <!-- Rattle segment 4 -->
                <ellipse cx="15.8" cy="47.5" rx="1.8" ry="1" fill="#a08840" stroke="#705818" stroke-width="0.28" />
                <line x1="14.2" y1="47.5" x2="17.4" y2="47.5" stroke="#705818" stroke-width="0.22" opacity="0.38" />
                <!-- Terminal button -->
                <ellipse cx="15.8" cy="48.7" rx="1.2" ry="0.75" fill="#948038" stroke="#685010" stroke-width="0.25" />
                <line x1="14.8" y1="48.7" x2="16.8" y2="48.7" stroke="#685010" stroke-width="0.2" opacity="0.35" />
              </g>
            </svg>
          </g>
        </template>
      </svg>
      <!-- Snake hiss bubble -->
      <div v-if="getSnakeData(i)?.hissBubble" class="snake-bubble" :class="{ 'snake-bubble-dark': isDark }"
        :style="{
          opacity: Math.min(1, getSnakeData(i).hissBubble.timer / 15, (100 - getSnakeData(i).hissBubble.timer + 15) / 15)
        }">
        {{ getSnakeData(i).hissBubble.text }}
      </div>
    </div>

    <!-- ═══ Holiday decorations ═══ -->
    <div v-for="(d, i) in holidayDecorations" :key="'hd' + i"
      class="holiday-decoration"
      :style="{
        left: d.x + 'px',
        bottom: (['red-lantern','round-lantern','tanzaku','chunlian','fanous'].includes(d.type)
          ? groundY + 50 + Math.sin(d.wobblePhase * 0.5) * 5
          : ['ema','omamori'].includes(d.type)
          ? groundY + 40 + Math.sin(d.wobblePhase * 0.5) * 3
          : groundY) + 'px',
        transform: `translateX(-50%) rotate(${Math.sin(d.wobblePhase) * (['red-lantern','round-lantern','chunlian','fanous'].includes(d.type) ? 4 : ['ema','omamori'].includes(d.type) ? 3 : 2)}deg)`
      }">
      <!-- Red lantern 红灯笼 -->
      <svg v-if="d.type === 'red-lantern'" width="36" height="62" viewBox="0 0 36 62">
        <!-- Hanging string -->
        <line x1="18" y1="0" x2="18" y2="8" stroke="#aa7733" stroke-width="1" />
        <!-- Top bar -->
        <rect x="11" y="7" width="14" height="3.5" rx="1" fill="#cc8822" />
        <rect x="12" y="7.5" width="12" height="1" rx="0.5" fill="#ddaa44" opacity="0.5" />
        <!-- Body -->
        <ellipse cx="18" cy="30" rx="13" ry="17" fill="#cc2222" />
        <!-- Ribs (vertical lines) -->
        <ellipse cx="18" cy="30" rx="13" ry="17" fill="none" stroke="#aa1111" stroke-width="0.4" opacity="0.3" />
        <line x1="12" y1="13" x2="12" y2="47" stroke="#aa1111" stroke-width="0.4" opacity="0.25" />
        <line x1="24" y1="13" x2="24" y2="47" stroke="#aa1111" stroke-width="0.4" opacity="0.25" />
        <line x1="18" y1="10" x2="18" y2="50" stroke="#aa1111" stroke-width="0.3" opacity="0.15" />
        <!-- Highlight -->
        <ellipse cx="18" cy="26" rx="8" ry="11" fill="#ee4444" opacity="0.45" />
        <ellipse cx="15" cy="22" rx="4" ry="6" fill="#ff6644" opacity="0.3" />
        <ellipse cx="14" cy="20" rx="2" ry="3" fill="#ff8866" opacity="0.2" />
        <!-- Character label -->
        <rect x="12" y="24" width="12" height="12" rx="1.2" fill="#ffcc22" opacity="0.3" />
        <rect x="13" y="25" width="10" height="10" rx="0.8" fill="none" stroke="#ffdd44" stroke-width="0.5" opacity="0.45" />
        <text v-if="d.label" x="18" y="33.5" text-anchor="middle" style="font-size:9px" font-weight="bold" fill="#ffdd44" opacity="0.85" font-family="serif">{{ d.label }}</text>
        <!-- Bottom bar -->
        <rect x="11" y="46" width="14" height="3.5" rx="1" fill="#cc8822" />
        <rect x="12" y="47" width="12" height="1" rx="0.5" fill="#ddaa44" opacity="0.4" />
        <!-- Tassel -->
        <line x1="18" y1="49.5" x2="18" y2="56" stroke="#dd3333" stroke-width="1.2" />
        <line x1="15" y1="56" x2="18" y2="53" stroke="#dd3333" stroke-width="0.8" />
        <line x1="21" y1="56" x2="18" y2="53" stroke="#dd3333" stroke-width="0.8" />
        <line x1="16" y1="58" x2="18" y2="55" stroke="#cc2222" stroke-width="0.6" />
        <line x1="20" y1="58" x2="18" y2="55" stroke="#cc2222" stroke-width="0.6" />
        <circle cx="18" cy="56.5" r="1.2" fill="#dd3333" />
        <!-- Glow effect -->
        <ellipse cx="18" cy="30" rx="16" ry="20" fill="#ff4422" opacity="0.08" />
      </svg>
      <!-- Round lantern 圆灯笼 -->
      <svg v-else-if="d.type === 'round-lantern'" width="38" height="52" viewBox="0 0 38 52">
        <line x1="19" y1="0" x2="19" y2="6" stroke="#aa7733" stroke-width="1" />
        <circle cx="19" cy="24" r="16" fill="#dd4422" />
        <circle cx="19" cy="22" r="10" fill="#ee6644" opacity="0.35" />
        <circle cx="16" cy="18" r="5" fill="#ff8844" opacity="0.25" />
        <circle cx="14" cy="16" r="2.5" fill="#ffaa66" opacity="0.15" />
        <!-- Character label -->
        <text v-if="d.label" x="19" y="28" text-anchor="middle" style="font-size:13px" font-weight="bold" fill="#ffdd44" opacity="0.8" font-family="serif">{{ d.label }}</text>
        <line x1="19" y1="40" x2="19" y2="48" stroke="#dd4422" stroke-width="0.8" />
        <circle cx="19" cy="48" r="1" fill="#cc3311" />
        <circle cx="19" cy="24" r="19" fill="#ff6633" opacity="0.06" />
      </svg>
      <!-- Christmas tree 🎄 -->
      <svg v-else-if="d.type === 'christmas-tree'" width="38" height="56" viewBox="0 0 38 56">
        <rect x="15.5" y="46" width="7" height="9" rx="1" fill="#6b4226" />
        <rect x="16.5" y="47" width="2" height="7" rx="0.5" fill="#8b5a3a" opacity="0.3" />
        <polygon points="19,3 5,22 33,22" fill="#1a6b1a" />
        <polygon points="19,10 7,32 31,32" fill="#228b22" />
        <polygon points="19,20 8,46 30,46" fill="#2d8b2d" />
        <!-- Star -->
        <polygon points="19,0 20.5,3 23,3 21,5 21.8,8 19,6.5 16.2,8 17,5 15,3 17.5,3" fill="#ffd700" />
        <circle cx="19" cy="3.5" r="2.5" fill="#ffe44d" opacity="0.4" />
        <!-- Ornaments -->
        <circle cx="12" cy="20" r="1.8" fill="#ff3333" />
        <circle cx="25" cy="25" r="1.6" fill="#4488ff" />
        <circle cx="14" cy="32" r="1.8" fill="#ffdd44" />
        <circle cx="26" cy="35" r="1.5" fill="#ff88dd" />
        <circle cx="16" cy="40" r="1.6" fill="#ff3333" />
        <circle cx="22" cy="42" r="1.4" fill="#44dd88" />
        <!-- Snow patches -->
        <ellipse cx="10" cy="22" rx="4" ry="1.2" fill="#f0f4ff" opacity="0.35" />
        <ellipse cx="28" cy="32" rx="3" ry="1" fill="#f0f4ff" opacity="0.3" />
        <ellipse cx="12" cy="38" rx="3.5" ry="1" fill="#f0f4ff" opacity="0.25" />
      </svg>
      <!-- Kadomatsu 門松 -->
      <svg v-else-if="d.type === 'kadomatsu'" width="36" height="50" viewBox="0 0 36 50">
        <rect x="4" y="38" width="28" height="11" rx="2" fill="#8b6b3a" />
        <rect x="6" y="39" width="24" height="2.5" rx="1" fill="#ddcc88" opacity="0.5" />
        <rect x="6" y="10" width="7" height="32" rx="2" fill="#2d7a2d" />
        <polygon points="6,10 13,10 13,7 9.5,3" fill="#88bb44" />
        <rect x="14.5" y="3" width="7" height="39" rx="2" fill="#3a8a3a" />
        <polygon points="14.5,3 21.5,3 21.5,0 18,0" fill="#aadd66" />
        <rect x="23" y="14" width="7" height="28" rx="2" fill="#4a9a4a" />
        <polygon points="23,14 30,14 30,11 26.5,8" fill="#88bb44" />
        <!-- Pine branches -->
        <circle cx="8" cy="36" r="3.5" fill="#1a5a1a" opacity="0.6" />
        <circle cx="28" cy="36" r="3" fill="#1a5a1a" opacity="0.5" />
        <circle cx="18" cy="38" r="2.5" fill="#1a5a1a" opacity="0.4" />
      </svg>
      <!-- Pumpkin 🎃 -->
      <svg v-else-if="d.type === 'pumpkin'" width="34" height="32" viewBox="0 0 34 32">
        <ellipse cx="17" cy="20" rx="15" ry="11" fill="#dd7722" />
        <ellipse cx="10" cy="20" rx="8" ry="10" fill="#ee9944" opacity="0.3" />
        <ellipse cx="24" cy="20" rx="8" ry="10" fill="#bb5500" opacity="0.2" />
        <path d="M17 9 Q17 4, 21 2" fill="none" stroke="#556b2f" stroke-width="2" stroke-linecap="round" />
        <rect x="15.5" y="8.5" width="3" height="4" rx="1" fill="#556b2f" />
        <!-- Face -->
        <path d="M9 18 L11.5 21 L14 18" fill="none" stroke="#221100" stroke-width="1.2" />
        <path d="M20 18 L22.5 21 L25 18" fill="none" stroke="#221100" stroke-width="1.2" />
        <path d="M12 25 Q17 29, 22 25" fill="none" stroke="#221100" stroke-width="1.2" />
        <!-- Inner glow -->
        <ellipse cx="17" cy="20" rx="10" ry="7" fill="#ffaa33" opacity="0.12" />
      </svg>
      <!-- Shamrock ☘️ -->
      <svg v-else-if="d.type === 'shamrock'" width="28" height="30" viewBox="0 0 28 30">
        <line x1="14" y1="17" x2="14" y2="30" stroke="#1a5a1a" stroke-width="2" stroke-linecap="round" />
        <circle cx="10" cy="12" r="6" fill="#228b22" />
        <circle cx="18" cy="12" r="6" fill="#228b22" />
        <circle cx="14" cy="6.5" r="6" fill="#33aa33" />
        <circle cx="11" cy="10" r="2.2" fill="#33aa33" opacity="0.4" />
        <circle cx="17.5" cy="10" r="2" fill="#33aa33" opacity="0.3" />
        <circle cx="14" cy="5" r="2.2" fill="#44bb44" opacity="0.3" />
      </svg>
      <!-- Crescent & star ☪ -->
      <svg v-else-if="d.type === 'crescent-star'" width="36" height="36" viewBox="0 0 36 36">
        <circle cx="16" cy="18" r="12" fill="#ffd700" />
        <circle cx="21" cy="15" r="10.5" :fill="isDark ? '#1a1a2e' : '#e8ecf4'" />
        <polygon points="30,8 31.6,13 36,13 32.4,16 33.6,21 30,18 26.4,21 27.6,16 24,13 28.4,13" fill="#ffd700" />
        <circle cx="30" cy="14" r="1" fill="#fff2aa" opacity="0.5" />
        <circle cx="16" cy="18" r="14" fill="#ffd700" opacity="0.06" />
      </svg>
      <!-- Songpyeon 송편 -->
      <svg v-else-if="d.type === 'songpyeon'" width="26" height="18" viewBox="0 0 26 18">
        <ellipse cx="13" cy="11" rx="12" ry="6.5" fill="#f0e8d8" />
        <ellipse cx="13" cy="10" rx="9" ry="5" fill="#f8f4ec" opacity="0.4" />
        <ellipse cx="13" cy="12" rx="6" ry="3" fill="#88aa44" opacity="0.25" />
        <path d="M5 9 Q13 5, 21 9" fill="none" stroke="#ddcc88" stroke-width="0.8" opacity="0.5" />
        <ellipse cx="13" cy="8" rx="4" ry="2" fill="#faf6ee" opacity="0.3" />
      </svg>
      <!-- Tanzaku 短冊 -->
      <svg v-else-if="d.type === 'tanzaku'" width="18" height="48" viewBox="0 0 18 48">
        <line x1="9" y1="0" x2="9" y2="6" stroke="#ddcc88" stroke-width="0.8" />
        <rect x="1" y="6" width="16" height="32" rx="1"
          :fill="['#ff6688', '#6688ff', '#88dd44', '#ffdd44', '#dd88ff'][i % 5]" />
        <!-- Wish character (vertical) -->
        <text v-if="d.label" x="9" y="26" text-anchor="middle" style="font-size:11px" fill="#fff" opacity="0.7" font-family="serif">{{ d.label }}</text>
        <!-- Tassel threads -->
        <line x1="6" y1="38" x2="9" y2="46" stroke="#ddcc88" stroke-width="0.6" />
        <line x1="12" y1="38" x2="9" y2="46" stroke="#ddcc88" stroke-width="0.6" />
      </svg>
      <!-- Yolka Ёлка -->
      <svg v-else-if="d.type === 'yolka'" width="38" height="56" viewBox="0 0 38 56">
        <rect x="15.5" y="46" width="7" height="9" rx="1" fill="#6b4226" />
        <polygon points="19,3 5,22 33,22" fill="#1a6b4a" />
        <polygon points="19,10 7,32 31,32" fill="#228b5a" />
        <polygon points="19,20 8,46 30,46" fill="#2d8b6a" />
        <!-- Red star -->
        <polygon points="19,0 20.5,3 23,3 21,5 21.8,8 19,6.5 16.2,8 17,5 15,3 17.5,3" fill="#ff3333" />
        <circle cx="19" cy="3.5" r="2.2" fill="#ff6644" opacity="0.35" />
        <!-- Ornaments -->
        <circle cx="12" cy="20" r="1.6" fill="#4488ff" />
        <circle cx="25" cy="25" r="1.5" fill="#ffdd44" />
        <circle cx="14" cy="32" r="1.6" fill="#ff3333" />
        <circle cx="26" cy="35" r="1.4" fill="#44dd88" />
        <circle cx="16" cy="40" r="1.5" fill="#ffdd44" />
        <!-- Garland -->
        <path d="M8 20 Q14 18, 20 21 Q26 24, 30 22" fill="none" stroke="#ffdd44" stroke-width="0.8" opacity="0.45" />
        <path d="M9 32 Q15 30, 21 33 Q27 36, 29 34" fill="none" stroke="#ffdd44" stroke-width="0.7" opacity="0.35" />
        <!-- Snow -->
        <ellipse cx="10" cy="22" rx="4" ry="1.2" fill="#f0f4ff" opacity="0.3" />
        <ellipse cx="28" cy="32" rx="3" ry="1" fill="#f0f4ff" opacity="0.25" />
      </svg>
      <!-- Chunlian 春联 (vertical scroll couplet) -->
      <svg v-else-if="d.type === 'chunlian'" width="20" height="50" viewBox="0 0 20 50">
        <!-- Hanging string -->
        <line x1="10" y1="0" x2="10" y2="5" stroke="#aa7733" stroke-width="0.8" />
        <!-- Top cap -->
        <rect x="2" y="4" width="16" height="4" rx="1" fill="#ccaa44" />
        <rect x="3" y="5" width="14" height="1.5" rx="0.5" fill="#ddbb55" opacity="0.4" />
        <!-- Red body -->
        <rect x="3" y="8" width="14" height="34" rx="0.5" fill="#cc2222" />
        <!-- Gold border -->
        <rect x="3" y="8" width="14" height="34" rx="0.5" fill="none" stroke="#ccaa44" stroke-width="0.8" />
        <!-- Inner border -->
        <rect x="5" y="10" width="10" height="30" rx="0.3" fill="none" stroke="#ccaa44" stroke-width="0.4" opacity="0.5" />
        <!-- Vertical text -->
        <text v-if="d.label" x="10" y="28" text-anchor="middle" style="font-size:8px" font-weight="bold" fill="#ffcc44" font-family="serif" writing-mode="vertical-rl">{{ d.label }}</text>
        <!-- Bottom cap -->
        <rect x="2" y="42" width="16" height="4" rx="1" fill="#ccaa44" />
        <rect x="3" y="43" width="14" height="1.5" rx="0.5" fill="#ddbb55" opacity="0.4" />
        <!-- Tassel -->
        <line x1="10" y1="46" x2="10" y2="50" stroke="#dd3333" stroke-width="0.8" />
        <circle cx="10" cy="50" r="1" fill="#dd3333" />
      </svg>
      <!-- Ema 絵馬 (Japanese votive tablet) -->
      <svg v-else-if="d.type === 'ema'" width="30" height="26" viewBox="0 0 30 26">
        <!-- Hanging rope -->
        <path d="M12 2 Q15 0, 18 2" fill="none" stroke="#aa7733" stroke-width="1.2" stroke-linecap="round" />
        <!-- Pentagonal wood board -->
        <polygon points="15,2 28,8 26,24 4,24 2,8" fill="#d4a054" />
        <polygon points="15,3 27,8.5 25.5,23 4.5,23 3,8.5" fill="#e0b870" opacity="0.3" />
        <!-- Wood grain -->
        <line x1="5" y1="12" x2="25" y2="11" stroke="#b8863c" stroke-width="0.3" opacity="0.3" />
        <line x1="4" y1="18" x2="26" y2="17" stroke="#b8863c" stroke-width="0.3" opacity="0.25" />
        <!-- Text -->
        <text v-if="d.label" x="15" y="17" text-anchor="middle" style="font-size:9px" font-weight="bold" fill="#332211" font-family="serif">{{ d.label }}</text>
        <!-- Nail at top -->
        <circle cx="15" cy="5" r="1.2" fill="#aa7733" />
      </svg>
      <!-- Candy heart 💕 -->
      <svg v-else-if="d.type === 'candy-heart'" width="24" height="22" viewBox="0 0 24 22">
        <!-- Heart shape -->
        <path d="M12 20 C5 14, 0 8, 4 4 C7 1, 12 4, 12 7 C12 4, 17 1, 20 4 C24 8, 19 14, 12 20Z" fill="#ff8899" />
        <!-- Light highlight -->
        <path d="M7 6 C8 4, 10 5, 10 7" fill="none" stroke="#ffaabb" stroke-width="1.5" opacity="0.5" stroke-linecap="round" />
        <!-- Embossed text (dynamic size) -->
        <text v-if="d.label" x="12" y="13" text-anchor="middle"
          :style="{ fontSize: (d.label.length <= 2 ? 6 : d.label.length <= 4 ? 5 : 4) + 'px' }"
          font-weight="bold" fill="#cc3355" font-family="sans-serif">{{ d.label }}</text>
      </svg>
      <!-- Tombstone 🪦 -->
      <svg v-else-if="d.type === 'tombstone'" width="24" height="30" viewBox="0 0 24 30">
        <!-- Stone body -->
        <path d="M3 30 L3 10 C3 4, 12 2, 12 2 C12 2, 21 4, 21 10 L21 30 Z" fill="#888888" />
        <!-- Lighter face -->
        <path d="M5 28 L5 11 C5 6, 12 4, 12 4 C12 4, 19 6, 19 11 L19 28 Z" fill="#999999" opacity="0.4" />
        <!-- Engraved text -->
        <text v-if="d.label" x="12" y="17" text-anchor="middle" style="font-size:7px" font-weight="bold" fill="#333333" font-family="serif">{{ d.label }}</text>
        <!-- Grass at base -->
        <path d="M0 30 L2 25 L4 30 L6 26 L8 30 L10 25 L12 30 L14 26 L16 30 L18 25 L20 30 L22 26 L24 30 Z" fill="#3a7a3a" />
      </svg>
      <!-- Greeting card 💌 -->
      <svg v-else-if="d.type === 'greeting-card'" width="28" height="22" viewBox="0 0 28 22">
        <!-- Back panel (slightly visible) -->
        <rect x="2" y="2" width="24" height="18" rx="1.5" fill="#d8c8a8" />
        <!-- Front panel -->
        <rect x="4" y="3" width="22" height="17" rx="1.5" fill="#fff4e6" />
        <!-- Fold line -->
        <line x1="15" y1="3.5" x2="15" y2="19.5" stroke="#d8c8a8" stroke-width="0.5" stroke-dasharray="1.5,1" />
        <!-- Decorative heart on front -->
        <path d="M9 6.5 C8.2 5, 6 5.2, 6 6.8 C6 8, 9 9.5, 9 9.5 C9 9.5, 12 8, 12 6.8 C12 5.2, 9.8 5, 9 6.5Z" fill="#ee8899" opacity="0.35" />
        <!-- Front face text (dynamic size, softer style) -->
        <text v-if="d.label" x="9.5" y="16" text-anchor="middle"
          :style="{ fontSize: (d.label.length <= 1 ? 9 : d.label.length <= 2 ? 7 : d.label.length <= 4 ? 5.5 : 4.5) + 'px' }"
          fill="#cc4444" font-family="Georgia, 'Times New Roman', serif" font-style="italic">{{ d.label }}</text>
      </svg>
      <!-- Bokjumeoni 복주머니 (Korean fortune pouch) -->
      <svg v-else-if="d.type === 'bokjumeoni'" width="22" height="28" viewBox="0 0 22 28">
        <!-- Pouch body -->
        <path d="M3 10 Q3 26, 11 26 Q19 26, 19 10 Z" fill="#cc2266" />
        <!-- Lighter center -->
        <path d="M5 12 Q5 24, 11 24 Q17 24, 17 12 Z" fill="#dd4488" opacity="0.3" />
        <!-- Gathered top -->
        <path d="M3 10 Q5 7, 11 8 Q17 7, 19 10" fill="#cc2266" stroke="#aa1144" stroke-width="0.3" />
        <!-- Drawstring cord -->
        <path d="M6 9 Q11 6, 16 9" fill="none" stroke="#ffcc44" stroke-width="1.2" stroke-linecap="round" />
        <!-- Knot -->
        <circle cx="11" cy="7.5" r="1.5" fill="#ddaa22" />
        <!-- Cord tails -->
        <line x1="9.5" y1="7.5" x2="7" y2="3" stroke="#ffcc44" stroke-width="0.8" stroke-linecap="round" />
        <line x1="12.5" y1="7.5" x2="15" y2="3" stroke="#ffcc44" stroke-width="0.8" stroke-linecap="round" />
        <!-- Tassel left -->
        <line x1="7" y1="3" x2="5" y2="0" stroke="#ffcc44" stroke-width="0.6" />
        <line x1="7" y1="3" x2="7" y2="0" stroke="#ffcc44" stroke-width="0.6" />
        <!-- Tassel right -->
        <line x1="15" y1="3" x2="15" y2="0" stroke="#ffcc44" stroke-width="0.6" />
        <line x1="15" y1="3" x2="17" y2="0" stroke="#ffcc44" stroke-width="0.6" />
        <!-- Embroidered text -->
        <text v-if="d.label" x="11" y="20" text-anchor="middle"
          :style="{ fontSize: (d.label.length <= 1 ? 9 : d.label.length <= 2 ? 7 : 5) + 'px' }"
          font-weight="bold" fill="#ffdd66" font-family="serif">{{ d.label }}</text>
      </svg>
      <!-- Omamori お守り (Japanese charm amulet) -->
      <svg v-else-if="d.type === 'omamori'" width="16" height="26" viewBox="0 0 16 26">
        <!-- Hanging cord -->
        <line x1="8" y1="0" x2="8" y2="4" stroke="#ddaa44" stroke-width="0.8" />
        <!-- Cord knot -->
        <path d="M6 4 Q8 2.5, 10 4 Q8 5.5, 6 4Z" fill="#ffcc44" />
        <!-- Body -->
        <rect x="2" y="5" width="12" height="18" rx="1.5" fill="#8b2252" />
        <!-- Gold border -->
        <rect x="2" y="5" width="12" height="18" rx="1.5" fill="none" stroke="#ddaa44" stroke-width="0.6" />
        <!-- Inner decorative border -->
        <rect x="3.5" y="7" width="9" height="14" rx="0.8" fill="none" stroke="#ddaa44" stroke-width="0.4" opacity="0.5" />
        <!-- Highlight -->
        <rect x="3" y="6" width="4" height="6" rx="1" fill="#aa3366" opacity="0.3" />
        <!-- Text -->
        <text v-if="d.label" x="8" y="14" text-anchor="middle"
          :style="{ fontSize: (d.label.length <= 1 ? 7 : d.label.length <= 2 ? 5.5 : 4.5) + 'px' }"
          font-weight="bold" fill="#ffdd88" font-family="serif" writing-mode="vertical-rl">{{ d.label }}</text>
        <!-- Bottom tassel -->
        <line x1="8" y1="23" x2="8" y2="26" stroke="#ddaa44" stroke-width="0.6" />
        <circle cx="8" cy="26" r="0.8" fill="#ffcc44" />
      </svg>
      <!-- Fanous فانوس (Arabic festive lantern) -->
      <svg v-else-if="d.type === 'fanous'" width="22" height="36" viewBox="0 0 22 36">
        <!-- Hanging ring -->
        <circle cx="11" cy="2" r="2" fill="none" stroke="#ccaa44" stroke-width="1" />
        <!-- Top cap -->
        <polygon points="6,5 16,5 14,8 8,8" fill="#ccaa44" />
        <polygon points="7,5.5 15,5.5 13.5,7.5 8.5,7.5" fill="#ddbb55" opacity="0.4" />
        <!-- Lantern body (hexagonal profile) -->
        <path d="M5 8 L3 18 L5 28 L17 28 L19 18 L17 8 Z" fill="#22aa66" />
        <!-- Glass panels with lighter shade -->
        <path d="M6 9 L4.5 18 L6 27 L11 27 L11 9 Z" fill="#44cc88" opacity="0.25" />
        <!-- Frame lines -->
        <line x1="11" y1="8" x2="11" y2="28" stroke="#ccaa44" stroke-width="0.5" opacity="0.6" />
        <line x1="3.5" y1="18" x2="18.5" y2="18" stroke="#ccaa44" stroke-width="0.5" opacity="0.4" />
        <!-- Top/bottom frame -->
        <line x1="5" y1="8" x2="17" y2="8" stroke="#ccaa44" stroke-width="0.8" />
        <line x1="5" y1="28" x2="17" y2="28" stroke="#ccaa44" stroke-width="0.8" />
        <!-- Glow -->
        <ellipse cx="11" cy="18" rx="6" ry="8" fill="#44dd88" opacity="0.1" />
        <!-- Text -->
        <text v-if="d.label" x="11" y="20" text-anchor="middle"
          :style="{ fontSize: (d.label.length <= 1 ? 8 : d.label.length <= 2 ? 7 : 5) + 'px' }"
          font-weight="bold" fill="#ffeecc" font-family="serif">{{ d.label }}</text>
        <!-- Bottom finial -->
        <polygon points="8,28 14,28 11,32" fill="#ccaa44" />
        <line x1="11" y1="32" x2="11" y2="35" stroke="#ccaa44" stroke-width="0.6" />
        <circle cx="11" cy="35.5" r="0.8" fill="#ddbb55" />
      </svg>
      <!-- Daruma だるま (Japanese wishing doll) -->
      <svg v-else-if="d.type === 'daruma'" width="28" height="28" viewBox="0 0 28 28">
        <!-- Body (round) -->
        <ellipse cx="14" cy="16" rx="12" ry="11" fill="#cc2222" />
        <!-- Bottom flat -->
        <ellipse cx="14" cy="25" rx="10" ry="2.5" fill="#aa1111" />
        <!-- Highlight -->
        <ellipse cx="11" cy="12" rx="5" ry="6" fill="#dd4444" opacity="0.35" />
        <!-- Face area (white oval) -->
        <ellipse cx="14" cy="13" rx="7" ry="6" fill="#f5e6d0" />
        <!-- Eyebrows (gold arcs) -->
        <path d="M9 10 Q10.5 8, 12 10" fill="none" stroke="#ccaa44" stroke-width="1" stroke-linecap="round" />
        <path d="M16 10 Q17.5 8, 19 10" fill="none" stroke="#ccaa44" stroke-width="1" stroke-linecap="round" />
        <!-- Left eye (filled = wish made) -->
        <circle cx="10.5" cy="12.5" r="2" fill="#ffffff" />
        <circle cx="10.5" cy="12.5" r="1.3" fill="#111111" />
        <!-- Right eye (empty = wish pending) -->
        <circle cx="17.5" cy="12.5" r="2" fill="#ffffff" />
        <circle cx="17.5" cy="12.5" r="1.3" fill="#ffffff" stroke="#cccccc" stroke-width="0.3" />
        <!-- Nose dot -->
        <circle cx="14" cy="14.5" r="0.6" fill="#cc8866" opacity="0.5" />
        <!-- Mouth -->
        <path d="M12 16.5 Q14 17.5, 16 16.5" fill="none" stroke="#aa7755" stroke-width="0.5" opacity="0.5" />
        <!-- Belly text -->
        <text v-if="d.label" x="14" y="24" text-anchor="middle"
          :style="{ fontSize: (d.label.length <= 1 ? 7 : d.label.length <= 2 ? 5.5 : 4) + 'px' }"
          font-weight="bold" fill="#ffcc44" font-family="serif">{{ d.label }}</text>
      </svg>
    </div>

    <!-- ═══ Mushrooms ═══ -->
    <div
      v-for="(m, i) in mushrooms" :key="'m' + i"
      v-show="m.currentScale > 0.05"
      class="mushroom"
      :style="{
        left: m.x + 'px', bottom: groundY + 'px',
        opacity: m.eaten && m.scaleAtEat > 0 ? m.currentScale / m.scaleAtEat : 1
      }"
    >
      <svg :width="16 * m.currentScale" :height="18 * m.currentScale" viewBox="0 0 16 18">
        <!-- Cap base shape -->
        <path d="M1 10 Q1 2, 8 2 Q15 2, 15 10 Z" :fill="m.colors.cap" />
        <!-- Cap highlight arc -->
        <path d="M3.5 8 Q4 3.5, 8 3.5 Q10.5 3.5, 11 7"
          fill="none" :stroke="m.colors.capLight" stroke-width="1.5" opacity="0.4" stroke-linecap="round" />
        <!-- Cap bottom rim shadow -->
        <path d="M2 9.5 Q8 11.5, 14 9.5" fill="none" :stroke="m.colors.cap" stroke-width="0.8" opacity="0.25" />

        <!-- Rainbow type: classic toadstool spots + cap shading -->
        <g v-if="m.type === 'rainbow'">
          <circle cx="5" cy="5.5" r="1.4" :fill="m.colors.spots" opacity="0.88" />
          <circle cx="5" cy="5.5" r="0.7" :fill="m.colors.spots" opacity="0.3" />
          <circle cx="10.5" cy="4.8" r="1.1" :fill="m.colors.spots" opacity="0.8" />
          <circle cx="10.5" cy="4.8" r="0.5" :fill="m.colors.spots" opacity="0.25" />
          <circle cx="7.5" cy="7.8" r="1.2" :fill="m.colors.spots" opacity="0.7" />
          <circle cx="3.5" cy="8.2" r="0.7" :fill="m.colors.spots" opacity="0.5" />
          <circle cx="12" cy="7.5" r="0.6" :fill="m.colors.spots" opacity="0.45" />
          <!-- Top specular highlight -->
          <ellipse cx="7" cy="3.8" rx="2.5" ry="0.8" :fill="m.colors.capLight" opacity="0.25" />
        </g>

        <!-- Dizzy type: concentric rings + spiral hint -->
        <g v-else-if="m.type === 'dizzy'">
          <ellipse cx="8" cy="5.5" rx="3" ry="1.8" fill="none" :stroke="m.colors.spots" stroke-width="0.6" opacity="0.55" />
          <ellipse cx="8" cy="5.5" rx="1.5" ry="0.9" fill="none" :stroke="m.colors.spots" stroke-width="0.5" opacity="0.4" />
          <ellipse cx="8" cy="8" rx="4.8" ry="1.2" fill="none" :stroke="m.colors.spots" stroke-width="0.45" opacity="0.3" />
          <!-- Spiral accent -->
          <path d="M7 5.5 Q8.5 4, 9.5 5.5 Q10 6.5, 8.5 7" fill="none" :stroke="m.colors.spots" stroke-width="0.5" opacity="0.35" stroke-linecap="round" />
          <!-- Small texture dots -->
          <circle cx="4.5" cy="7.5" r="0.4" :fill="m.colors.spots" opacity="0.3" />
          <circle cx="11.5" cy="7" r="0.35" :fill="m.colors.spots" opacity="0.25" />
          <!-- Cap banding -->
          <path d="M2.5 9 Q8 7.5, 13.5 9" fill="none" :stroke="m.colors.capLight" stroke-width="0.4" opacity="0.2" />
        </g>

        <!-- Sparkle type: star crosses + diamond accents + glow dots -->
        <g v-else>
          <!-- Main star cross -->
          <line x1="5" y1="3.8" x2="5" y2="7.2" :stroke="m.colors.spots" stroke-width="0.9" stroke-linecap="round" opacity="0.88" />
          <line x1="3.2" y1="5.5" x2="6.8" y2="5.5" :stroke="m.colors.spots" stroke-width="0.9" stroke-linecap="round" opacity="0.88" />
          <!-- Smaller star cross -->
          <line x1="10.5" y1="3.5" x2="10.5" y2="6.5" :stroke="m.colors.spots" stroke-width="0.7" stroke-linecap="round" opacity="0.78" />
          <line x1="9" y1="5" x2="12" y2="5" :stroke="m.colors.spots" stroke-width="0.7" stroke-linecap="round" opacity="0.78" />
          <!-- Diamond accent -->
          <path d="M7.5 7 L8.2 8 L7.5 9 L6.8 8 Z" :fill="m.colors.spots" opacity="0.6" />
          <!-- Tiny glow dots -->
          <circle cx="3.8" cy="8.2" r="0.45" :fill="m.colors.spots" opacity="0.55" />
          <circle cx="12.2" cy="7.8" r="0.4" :fill="m.colors.spots" opacity="0.5" />
          <circle cx="8" cy="4" r="0.35" :fill="m.colors.spots" opacity="0.45" />
          <!-- Faint radial lines from stars -->
          <line x1="5" y1="5.5" x2="3.5" y2="8" :stroke="m.colors.spots" stroke-width="0.3" opacity="0.2" />
          <line x1="10.5" y1="5" x2="12" y2="7.2" :stroke="m.colors.spots" stroke-width="0.3" opacity="0.2" />
        </g>

        <!-- Stem -->
        <rect x="5.5" y="10" width="5" height="7.5" rx="2" :fill="m.colors.stem" />
        <!-- Stem left shade -->
        <rect x="5.5" y="10" width="2.5" height="7.5" rx="1" :fill="m.colors.stemShade" opacity="0.3" />
        <!-- Stem right highlight -->
        <rect x="8.5" y="10.5" width="1.2" height="6.5" rx="0.6" :fill="m.colors.spots" opacity="0.08" />
        <!-- Stem base ring -->
        <ellipse cx="8" cy="17" rx="3" ry="0.8" :fill="m.colors.stemShade" opacity="0.15" />
      </svg>
    </div>

    <!-- ═══ Spores ═══ -->
    <div v-for="(sp, i) in spores" :key="'sp' + i" class="spore"
      :style="{
        left: sp.x + 'px',
        bottom: (groundY - sp.y) + 'px',
        opacity: sp.opacity,
        width: sp.size + 'px',
        height: sp.size + 'px',
        background: sp.color,
        boxShadow: `0 0 ${sp.size}px ${sp.color}`
      }" />

    <!-- ═══ Snails ═══ -->
    <div
      v-for="(s, i) in snails" :key="'sn' + i"
      class="snail"
      :style="{
        left: s.x + 'px',
        bottom: groundY + 'px',
        transform: `translateX(-10px) scaleX(${s.dir})`
      }"
    >
      <svg width="22" height="18" viewBox="0 0 22 18" overflow="visible">
        <defs>
          <radialGradient :id="'snSh' + i" cx="45%" cy="40%" r="55%">
            <stop offset="0%" :stop-color="s.colors.shellLight" />
            <stop offset="70%" :stop-color="s.colors.shell" />
            <stop offset="100%" :stop-color="s.colors.shellDark" />
          </radialGradient>
        </defs>
        <!-- Slime trail -->
        <line x1="0" y1="17.5" x2="8" y2="17.5" :stroke="s.colors.bodyLight" stroke-width="0.8" opacity="0.15" stroke-linecap="round" />
        <!-- Body -->
        <ellipse
          :cx="10 + s.bodyStretch * 0.5" cy="16" :rx="8 + s.bodyStretch" ry="2"
          :fill="s.colors.body"
        />
        <ellipse
          :cx="10 + s.bodyStretch * 0.3" cy="15.5" :rx="6 + s.bodyStretch * 0.6" ry="1"
          :fill="s.colors.bodyLight" opacity="0.3"
        />
        <!-- Head -->
        <circle :cx="17 + s.bodyStretch" cy="14" r="2.2" :fill="s.colors.body" />
        <circle :cx="17.3 + s.bodyStretch" cy="13.6" r="1" :fill="s.colors.bodyLight" opacity="0.25" />
        <!-- Eye stalks -->
        <line
          :x1="16.5 + s.bodyStretch" y1="13"
          :x2="15.5 + s.bodyStretch + Math.sin(s.antennaPhase) * 0.8" y2="9.5 + Math.sin(s.antennaPhase * 1.3) * 0.5"
          :stroke="s.colors.body" stroke-width="0.7" stroke-linecap="round"
        />
        <line
          :x1="18 + s.bodyStretch" y1="12.5"
          :x2="18.5 + s.bodyStretch + Math.sin(s.antennaPhase + 1) * 0.8" y2="9 + Math.sin(s.antennaPhase * 1.3 + 0.5) * 0.5"
          :stroke="s.colors.body" stroke-width="0.7" stroke-linecap="round"
        />
        <!-- Eyes -->
        <circle
          :cx="15.5 + s.bodyStretch + Math.sin(s.antennaPhase) * 0.8"
          :cy="9.2 + Math.sin(s.antennaPhase * 1.3) * 0.5"
          r="1" :fill="s.colors.eye"
        />
        <circle
          :cx="15.8 + s.bodyStretch + Math.sin(s.antennaPhase) * 0.8"
          :cy="8.9 + Math.sin(s.antennaPhase * 1.3) * 0.5"
          r="0.35" fill="#fff" opacity="0.8"
        />
        <circle
          :cx="18.5 + s.bodyStretch + Math.sin(s.antennaPhase + 1) * 0.8"
          :cy="8.7 + Math.sin(s.antennaPhase * 1.3 + 0.5) * 0.5"
          r="1" :fill="s.colors.eye"
        />
        <circle
          :cx="18.8 + s.bodyStretch + Math.sin(s.antennaPhase + 1) * 0.8"
          :cy="8.4 + Math.sin(s.antennaPhase * 1.3 + 0.5) * 0.5"
          r="0.35" fill="#fff" opacity="0.8"
        />
        <!-- Shell -->
        <ellipse cx="9" cy="12" rx="5.5" ry="5.5" :fill="`url(#snSh${i})`" />
        <!-- Shell spiral -->
        <path d="M9 12 Q7 9, 9 8 Q11 7, 12 9 Q13 11, 11 12.5 Q9.5 14, 8 12.5"
          fill="none" :stroke="s.colors.shellDark" stroke-width="0.6" opacity="0.35" />
        <path d="M9 12 Q8 10.5, 9.5 9.5 Q10.5 9, 10.8 10"
          fill="none" :stroke="s.colors.shellDark" stroke-width="0.5" opacity="0.25" />
        <!-- Shell highlight -->
        <ellipse cx="7.8" cy="10.5" rx="2" ry="1.8" :fill="s.colors.shellLight" opacity="0.2" />
      </svg>
    </div>

    <!-- ═══ Butterflies ═══ -->
    <div
      v-for="(bf, i) in butterflies" :key="'bf' + i"
      class="butterfly"
      :style="{ left: bf.x + 'px', bottom: (groundY + bf.baseY + Math.sin(bf.phase) * bf.bobAmp + bf.driftY) + 'px' }"
    >
      <svg width="24" height="20" viewBox="0 0 24 20"
        :style="{
          transform: bf.dir < 0 ? 'scaleX(-1)' : '',
          filter: bf.rainbowHue > 0 ? `hue-rotate(${bf.rainbowHue * 3.6}deg) saturate(${1 + bf.rainbowHue * 0.01})` : ''
        }">
        <g :transform="`translate(12 0) scale(${wingScale(bf.wingPhase)} 1) translate(-12 0)`">
          <path d="M12 9 C8 3, 2 1, 1 5 C0 9, 5 13, 12 10" :fill="bf.colors.wing" opacity="0.85" />
          <path d="M12 9 C8 3, 2 1, 1 5 C0 9, 5 13, 12 10" fill="none" :stroke="bf.colors.edge" stroke-width="0.6" opacity="0.5" />
          <circle cx="5" cy="6" r="1.2" :fill="bf.colors.spot" opacity="0.25" />
          <path d="M11 8 C8 4, 4 3, 3 5.5" fill="none" :stroke="bf.colors.wingLight" stroke-width="1" opacity="0.3" stroke-linecap="round" />
          <path d="M12 10 C9 12, 3 13, 3 16 C3 18, 8 16, 12 11" :fill="bf.colors.wing" opacity="0.7" />
        </g>
        <g :transform="`translate(12 0) scale(${wingScale(bf.wingPhase)} 1) translate(-12 0)`">
          <path d="M12 9 C16 3, 22 1, 23 5 C24 9, 19 13, 12 10" :fill="bf.colors.wing" opacity="0.85" />
          <path d="M12 9 C16 3, 22 1, 23 5 C24 9, 19 13, 12 10" fill="none" :stroke="bf.colors.edge" stroke-width="0.6" opacity="0.5" />
          <circle cx="19" cy="6" r="1.2" :fill="bf.colors.spot" opacity="0.25" />
          <path d="M13 8 C16 4, 20 3, 21 5.5" fill="none" :stroke="bf.colors.wingLight" stroke-width="1" opacity="0.3" stroke-linecap="round" />
          <path d="M12 10 C15 12, 21 13, 21 16 C21 18, 16 16, 12 11" :fill="bf.colors.wing" opacity="0.7" />
        </g>
        <ellipse cx="12" cy="10" rx="0.9" ry="3.8" :fill="bf.colors.body" />
        <path d="M12 6.5 Q10 3, 8 1.5" fill="none" :stroke="bf.colors.body" stroke-width="0.5" />
        <path d="M12 6.5 Q14 3, 16 1.5" fill="none" :stroke="bf.colors.body" stroke-width="0.5" />
        <circle cx="8" cy="1.5" r="0.6" :fill="bf.colors.body" opacity="0.7" />
        <circle cx="16" cy="1.5" r="0.6" :fill="bf.colors.body" opacity="0.7" />
      </svg>
    </div>

    <!-- ═══ Rabbits ═══ -->
    <div
      v-for="(r, i) in rabbits" :key="'r' + i"
      class="rabbit" :class="{ grabbed: r.grabbed, glowing: r.glowing }"
      :style="{ left: r.x + 'px', bottom: (groundY - r.y) + 'px', cursor: r.grabbed ? 'grabbing' : 'grab', filter: rabbitDivFilter(r), transformOrigin: '50% 100%', transform: rabbitTransform(r) }"
      @pointerdown.stop="onDown($event, i)"
    >
      <svg width="30" height="30" viewBox="0 0 30 30" overflow="visible">
        <defs>
          <radialGradient :id="'rb' + i" cx="38%" cy="32%" r="62%">
            <stop offset="0%" :stop-color="r.colors.light" />
            <stop offset="70%" :stop-color="r.colors.body" />
            <stop offset="100%" :stop-color="r.colors.dark" />
          </radialGradient>
          <radialGradient :id="'rh' + i" cx="40%" cy="32%" r="60%">
            <stop offset="0%" :stop-color="r.colors.light" />
            <stop offset="80%" :stop-color="r.colors.body" />
            <stop offset="100%" :stop-color="r.colors.dark" />
          </radialGradient>
          <linearGradient :id="'re' + i" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" :stop-color="r.colors.body" />
            <stop offset="50%" :stop-color="r.colors.ear" />
            <stop offset="100%" :stop-color="r.colors.body" />
          </linearGradient>
        </defs>

        <!-- Ground shadow -->
        <ellipse cx="14" cy="29.5" rx="8" ry="1" fill="#00000010" />

        <!-- Back ear -->
        <ellipse cx="17" cy="5" :rx="r.isBaby ? 2.5 : 2.2" :ry="r.isBaby ? 3.8 : 5"
          :transform="`rotate(${r.grabbed ? earTilt(r.earPhase) * 1.5 : -5 + earTilt(r.earPhase) * 0.6}, 17, 11)`"
          :fill="`url(#re${i})`" :stroke="r.colors.dark" stroke-width="0.3" />

        <!-- Tail -->
        <circle cx="5.5" cy="19" :r="r.isBaby ? 3 : 2.5" :fill="r.colors.light" :stroke="r.colors.mid" stroke-width="0.3" />
        <circle cx="5" cy="18.5" :r="r.isBaby ? 1.6 : 1.2" :fill="r.colors.light" opacity="0.6" />

        <!-- Body -->
        <ellipse cx="14" cy="20" rx="8.5" ry="6" :fill="`url(#rb${i})`" />
        <ellipse cx="14" cy="24.5" rx="7" ry="1.5" :fill="r.colors.dark" opacity="0.1" />

        <!-- Hind foot -->
        <ellipse cx="9" cy="27.5" rx="3.8" ry="2" :fill="r.colors.paw" :stroke="r.colors.dark" stroke-width="0.3" />

        <!-- Head -->
        <circle cx="21" cy="13" :r="r.isBaby ? 6.8 : 5.8" :fill="`url(#rh${i})`" />
        <!-- Cheek blush -->
        <circle cx="24" :cy="r.isBaby ? 15.5 : 14.5" :r="r.isBaby ? 2.8 : 1.8" :fill="r.colors.ear" :opacity="r.isBaby ? 0.3 : 0.18" />

        <!-- Front ear -->
        <ellipse cx="21" cy="4" :rx="r.isBaby ? 2.6 : 2.3" :ry="r.isBaby ? 4 : 5.5"
          :transform="`rotate(${r.grabbed ? -earTilt(r.earPhase) * 1.5 : 5 - earTilt(r.earPhase)}, 21, 10)`"
          :fill="`url(#re${i})`" :stroke="r.colors.dark" stroke-width="0.3" />

        <!-- Eye — grabbed (surprised) / normal / rainbow spiral / dizzy cross -->
        <g v-if="r.grabbed">
          <!-- Wide surprised eye with visible sclera -->
          <circle cx="23.2" cy="11.8" r="2.2" fill="#fff" />
          <circle cx="23.2" cy="11.8" r="2.2" fill="none" :stroke="r.colors.dark" stroke-width="0.4" opacity="0.3" />
          <circle cx="23.4" cy="11.5" r="1.1" :fill="r.colors.eye" />
          <circle cx="23.7" cy="11" r="0.45" fill="#fff" opacity="0.95" />
        </g>
        <g v-else-if="!r.tripping">
          <circle cx="23.2" cy="12" :r="r.isBaby ? 2.3 : 1.6" :fill="r.colors.eye" />
          <circle :cx="r.isBaby ? 24 : 23.8" :cy="r.isBaby ? 11.2 : 11.4" :r="r.isBaby ? 0.9 : 0.6" fill="#fff" opacity="0.95" />
          <circle :cx="r.isBaby ? 22.6 : 22.8" :cy="r.isBaby ? 12.8 : 12.5" :r="r.isBaby ? 0.45 : 0.3" fill="#fff" opacity="0.5" />
        </g>
        <g v-else-if="r.tripType === 'rainbow'"
          :transform="`rotate(${r.tripPhase * 100}, 23.2, 12)`">
          <circle cx="23.2" cy="12" r="1.5" fill="none" :stroke="r.colors.eye" stroke-width="0.6" />
          <circle cx="23.2" cy="12" r="0.6" :fill="r.colors.eye" />
          <line x1="23.2" y1="10.5" x2="23.2" y2="11.3" :stroke="r.colors.eye" stroke-width="0.4" />
        </g>
        <g v-else-if="r.tripType === 'dizzy'" :transform="`rotate(${r.tripPhase * 60}, 23.2, 12)`">
          <line x1="21.9" y1="12" x2="24.5" y2="12" :stroke="r.colors.eye" stroke-width="0.7" stroke-linecap="round" />
          <line x1="23.2" y1="10.7" x2="23.2" y2="13.3" :stroke="r.colors.eye" stroke-width="0.7" stroke-linecap="round" />
        </g>
        <g v-else>
          <!-- Sparkle: glowing star eye -->
          <circle cx="23.2" cy="12" r="1.8" fill="#4888d8" :opacity="0.15 + Math.sin(r.tripPhase * 5) * 0.1" />
          <line x1="23.2" y1="10.2" x2="23.2" y2="13.8" stroke="#60a8ff" stroke-width="0.6" :opacity="0.6 + Math.sin(r.tripPhase * 5) * 0.3" />
          <line x1="21.4" y1="12" x2="25" y2="12" stroke="#60a8ff" stroke-width="0.6" :opacity="0.6 + Math.sin(r.tripPhase * 5) * 0.3" />
          <circle cx="23.2" cy="12" r="0.5" fill="#fff" :opacity="0.7 + Math.sin(r.tripPhase * 5) * 0.2" />
        </g>

        <!-- Nose -->
        <ellipse :cx="r.isBaby ? 26.5 : 26" cy="13.5" :rx="r.isBaby ? 0.9 : 0.7" :ry="r.isBaby ? 0.6 : 0.5" :fill="r.colors.nose" />
        <!-- Whiskers -->
        <line x1="25.5" y1="14" x2="29" y2="13" :stroke="r.colors.dark" stroke-width="0.3" :opacity="r.isBaby ? 0.12 : 0.2" />
        <line x1="25.5" y1="14.5" x2="29" y2="15" :stroke="r.colors.dark" stroke-width="0.3" :opacity="r.isBaby ? 0.12 : 0.2" />
        <!-- Mouth — surprised open mouth when grabbed, cute smile for baby, otherwise subtle line -->
        <ellipse v-if="r.grabbed" cx="25.2" cy="14.8" rx="1" ry="1.3" fill="#4a2828" opacity="0.35" />
        <path v-else-if="r.isBaby" d="M26.2 14.5 Q25.5 15.6, 24.5 15" fill="none" :stroke="r.colors.dark" stroke-width="0.35" opacity="0.2" />
        <path v-else d="M25.5 14 Q25 14.8, 24.5 14.5" fill="none" :stroke="r.colors.dark" stroke-width="0.3" opacity="0.15" />

        <!-- Front paw -->
        <ellipse cx="21" cy="27.5" rx="2.5" ry="2" :fill="r.colors.paw" :stroke="r.colors.dark" stroke-width="0.3" />
      </svg>
    </div>

    <!-- Speech bubbles — rendered outside .rabbit to avoid Safari filter clipping -->
    <div v-for="(r, i) in rabbits" :key="'rbub' + i">
      <div v-if="r.bubble" class="rabbit-bubble" :class="{ 'rabbit-bubble-dark': isDark }"
        :style="{
          left: r.x + 'px',
          bottom: (groundY - r.y + 34) + 'px',
          opacity: Math.min(1, r.bubble.timer / 15, (120 - r.bubble.timer + 15) / 15),
          transform: 'translateX(-50%)'
        }">
        {{ r.bubble.text }}
      </div>
    </div>

    <!-- ═══ Rainbows ═══ -->
    <div v-for="(rb, ri) in rainbows" :key="'rbow' + ri" class="rainbow-arc"
      :style="{
        left: rb.x + 'px',
        bottom: groundY + 'px',
        opacity: rb.opacity,
        transform: 'translateX(-50%) scale(' + rb.phase + ')'
      }">
      <svg width="280" height="92" viewBox="0 0 280 92">
        <g opacity="0.45">
          <path d="M 4 90 A 136 88 0 0 1 276 90" fill="none" stroke="#ff4444" stroke-width="4" />
          <path d="M 6 90 A 134 86.7 0 0 1 274 90" fill="none" stroke="#ff8844" stroke-width="4" />
          <path d="M 8 90 A 132 85.4 0 0 1 272 90" fill="none" stroke="#ffcc44" stroke-width="4" />
          <path d="M 10 90 A 130 84.1 0 0 1 270 90" fill="none" stroke="#44bb44" stroke-width="4" />
          <path d="M 12 90 A 128 82.8 0 0 1 268 90" fill="none" stroke="#4488ff" stroke-width="4" />
          <path d="M 14 90 A 126 81.5 0 0 1 266 90" fill="none" stroke="#6644cc" stroke-width="4" />
          <path d="M 16 90 A 124 80.2 0 0 1 264 90" fill="none" stroke="#cc44cc" stroke-width="4" />
        </g>
      </svg>
    </div>

    <!-- ═══ Holiday particles ═══ -->
    <svg v-if="holidayParticles.length" class="holiday-particle-overlay">
      <template v-for="(p, i) in holidayParticles" :key="'hp' + i">
        <!-- Sakura petal -->
        <ellipse v-if="p.type === 'sakura'"
          :cx="p.x" :cy="p.y" :rx="p.size * 0.6" :ry="p.size * 0.3"
          :fill="p.color" :opacity="p.opacity"
          :transform="`rotate(${p.rotation}, ${p.x}, ${p.y})`"
        />
        <!-- Lantern glow -->
        <g v-else-if="p.type === 'lantern-glow'">
          <circle :cx="p.x" :cy="p.y" :r="p.size * 1.8" :fill="p.color" :opacity="p.opacity * 0.15" />
          <circle :cx="p.x" :cy="p.y" :r="p.size" :fill="p.color" :opacity="p.opacity * 0.7" />
          <circle :cx="p.x" :cy="p.y" :r="p.size * 0.4" fill="#fff8dd" :opacity="p.opacity * 0.5" />
        </g>
        <!-- Firework spark -->
        <circle v-else-if="p.type === 'firework-spark'"
          :cx="p.x" :cy="p.y" :r="p.size * 0.4"
          :fill="p.color" :opacity="p.opacity"
        />
        <!-- Confetti -->
        <rect v-else-if="p.type === 'confetti'"
          :x="p.x - p.size * 0.3" :y="p.y - p.size * 0.5"
          :width="p.size * 0.6" :height="p.size"
          :fill="p.color" :opacity="p.opacity"
          :transform="`rotate(${p.rotation}, ${p.x}, ${p.y})`"
          rx="0.5"
        />
        <!-- Maple leaf (simplified) -->
        <g v-else-if="p.type === 'maple-leaf'"
          :transform="`translate(${p.x}, ${p.y}) rotate(${p.rotation}) scale(${p.size * 0.2})`"
          :opacity="p.opacity">
          <path d="M0,-5 L2,-2 L5,-3 L3,0 L5,2 L2,1 L0,5 L-2,1 L-5,2 L-3,0 L-5,-3 L-2,-2 Z"
            :fill="p.color" />
          <line x1="0" y1="-4" x2="0" y2="5" :stroke="p.color" stroke-width="0.5" opacity="0.5" />
        </g>
        <!-- Special snowflake (large star) -->
        <g v-else-if="p.type === 'snowflake-special'"
          :transform="`translate(${p.x}, ${p.y}) rotate(${p.rotation}) scale(${p.size * 0.25})`"
          :opacity="p.opacity">
          <line v-for="n in 6" :key="n"
            x1="0" y1="0"
            :x2="Math.cos(n * Math.PI / 3) * 5"
            :y2="Math.sin(n * Math.PI / 3) * 5"
            stroke="#ffffff" stroke-width="0.8" stroke-linecap="round" />
          <line v-for="n in 6" :key="'b'+n"
            :x1="Math.cos(n * Math.PI / 3) * 2"
            :y1="Math.sin(n * Math.PI / 3) * 2"
            :x2="Math.cos(n * Math.PI / 3 + 0.4) * 3.5"
            :y2="Math.sin(n * Math.PI / 3 + 0.4) * 3.5"
            stroke="#e8f0ff" stroke-width="0.5" stroke-linecap="round" />
          <circle cx="0" cy="0" r="1" fill="#ffffff" opacity="0.6" />
        </g>
        <!-- Heart -->
        <g v-else-if="p.type === 'heart'"
          :transform="`translate(${p.x}, ${p.y}) rotate(${p.rotation}) scale(${p.size * 0.15})`"
          :opacity="p.opacity">
          <path d="M0,3 C0,3 -5,-2 -5,-5 C-5,-8 -2,-9 0,-6 C2,-9 5,-8 5,-5 C5,-2 0,3 0,3 Z"
            :fill="p.color" />
        </g>
        <!-- Crescent sparkle -->
        <circle v-else-if="p.type === 'crescent-sparkle'"
          :cx="p.x" :cy="p.y" :r="p.size * 0.5"
          :fill="p.color" :opacity="p.opacity * 0.7"
        />
      </template>
    </svg>

    <!-- ═══ Rain / Snow overlay ═══ -->
    <svg v-if="weather.type === 'rainy' || weather.type === 'snowy'" class="weather-overlay">
      <defs>
        <!-- Rain drop gradient: bright core → transparent edges -->
        <radialGradient id="rainDrop" cx="50%" cy="30%" r="50%">
          <stop offset="0%" stop-color="#d0e4f8" stop-opacity="0.8" />
          <stop offset="50%" stop-color="#a0c0e0" stop-opacity="0.35" />
          <stop offset="100%" stop-color="#90b8d8" stop-opacity="0" />
        </radialGradient>
        <!-- Snowflake gradient: soft glowing center → transparent edge -->
        <radialGradient id="snowSoft" cx="45%" cy="40%" r="50%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95" />
          <stop offset="50%" stop-color="#f0f4fc" stop-opacity="0.5" />
          <stop offset="100%" stop-color="#e4e8f4" stop-opacity="0" />
        </radialGradient>
        <!-- Small snow shimmer -->
        <radialGradient id="snowShimmer" cx="40%" cy="35%" r="55%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.7" />
          <stop offset="100%" stop-color="#dde4f0" stop-opacity="0" />
        </radialGradient>
      </defs>
      <!-- Rain: elongated gradient ellipses for 3D water streaks -->
      <template v-if="weather.type === 'rainy'">
        <ellipse v-for="(p, i) in wxParticles" :key="'rn' + i"
          :cx="p.x" :cy="p.y"
          :rx="p.w * 0.6" :ry="p.len * 0.5"
          fill="url(#rainDrop)"
          :opacity="p.op * 1.5"
          :transform="`rotate(${Math.atan2(weather.wind * 5, p.len) * 57.3}, ${p.x}, ${p.y})`"
        />
      </template>
      <!-- Snow: gradient circles with depth-based glow -->
      <template v-else>
        <circle v-for="(p, i) in wxParticles" :key="'sf' + i"
          :cx="p.x" :cy="p.y" :r="p.r * 1.6"
          :fill="p.depth > 0.6 ? 'url(#snowSoft)' : 'url(#snowShimmer)'"
          :opacity="p.op"
        />
      </template>
    </svg>
  </div>
</template>

<style scoped>
.scene-strip {
  position: relative;
  width: 100%;
  height: 200px;
  margin-top: -200px;
  z-index: 11;
  user-select: none;
  touch-action: none;
  pointer-events: none;
  overflow: hidden;
}
.celestial {
  position: absolute;
  transform: translateX(-50%);
  pointer-events: none;
  z-index: 0;
}
.celestial.is-sun {
  filter: drop-shadow(0 0 12px rgba(255, 200, 50, 0.5)) drop-shadow(0 0 30px rgba(255, 160, 30, 0.2));
}
.celestial.is-moon {
  filter: drop-shadow(0 0 8px rgba(220, 215, 200, 0.4)) drop-shadow(0 0 20px rgba(200, 195, 180, 0.15));
}
.ground-light {
  position: absolute;
  transform: translateX(-50%);
  pointer-events: none;
  z-index: 0;
  width: 80px;
  height: 6px;
  border-radius: 50%;
}
.ground-light.sun-light {
  background: radial-gradient(ellipse, rgba(255, 210, 80, 0.6) 0%, transparent 70%);
  width: 100px;
}
.ground-light.moon-light {
  background: radial-gradient(ellipse, rgba(220, 215, 200, 0.5) 0%, transparent 70%);
  width: 60px;
}
.star {
  position: absolute;
  border-radius: 50%;
  background: #eee8d0;
  pointer-events: none;
  animation: twinkle 3s ease-in-out infinite;
}
.star-warm {
  background: #f0ddb0;
}
.star-glow {
  box-shadow: 0 0 3px 1px rgba(240, 232, 200, 0.5);
}
@keyframes twinkle {
  0%, 100% { opacity: 0.08; }
  50% { opacity: 0.85; }
}
.cloud {
  position: absolute;
  pointer-events: none;
  z-index: 2;
}
.weather-overlay {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 15;
}
.grass-cluster {
  position: absolute;
  pointer-events: none;
  z-index: 3;
}
.grass-has-snake {
  pointer-events: auto;
  cursor: pointer;
}
.mushroom {
  position: absolute;
  transform: translateX(-50%);
  transform-origin: bottom center;
  pointer-events: none;
  transition: opacity 0.12s ease;
  z-index: 3;
}
.snail {
  position: absolute;
  pointer-events: none;
  z-index: 4;
}
.rainbow-arc {
  position: absolute;
  pointer-events: none;
  z-index: 8;
  transform-origin: bottom center;
}
.butterfly {
  position: absolute;
  transform: translateX(-12px);
  pointer-events: none;
  z-index: 5;
}
.rabbit {
  position: absolute;
  pointer-events: auto;
  transition: filter 0.2s ease;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1));
  z-index: 6;
}
.rabbit:hover {
  filter: drop-shadow(0 2px 5px rgba(0, 0, 0, 0.18));
}
.rabbit.glowing {
  filter: drop-shadow(0 3px 10px rgba(0, 0, 0, 0.3));
}
.rabbit.grabbed {
  z-index: 10;
  cursor: grabbing !important;
}
.spore {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 4;
  transform: translate(-50%, 50%);
}
.rabbit-bubble {
  position: absolute;
  background: rgba(255, 255, 255, 0.92);
  border: 1.5px solid rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  padding: 3px 8px;
  font-size: 11px;
  line-height: 1.3;
  color: #3a2820;
  white-space: nowrap;
  pointer-events: none;
  font-family: system-ui, -apple-system, sans-serif;
  z-index: 20;
}
.rabbit-bubble::after {
  content: '';
  position: absolute;
  bottom: -5px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid rgba(255, 255, 255, 0.92);
}
.rabbit-bubble-dark {
  background: rgba(40, 36, 50, 0.92);
  color: #e8e0d8;
  border-color: rgba(255, 255, 255, 0.12);
}
.rabbit-bubble-dark::after {
  border-top-color: rgba(40, 36, 50, 0.92);
}
.snake-bubble {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 248, 230, 0.92);
  border: 1.5px solid rgba(160, 120, 40, 0.25);
  border-radius: 10px;
  padding: 3px 8px;
  font-size: 11px;
  line-height: 1.3;
  color: #4a3820;
  white-space: nowrap;
  pointer-events: none;
  font-family: system-ui, -apple-system, sans-serif;
  z-index: 20;
  margin-bottom: 4px;
}
.snake-bubble::after {
  content: '';
  position: absolute;
  bottom: -5px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid rgba(255, 248, 230, 0.92);
}
.snake-bubble-dark {
  background: rgba(45, 40, 30, 0.92);
  color: #e8dcc8;
  border-color: rgba(200, 170, 100, 0.2);
}
.snake-bubble-dark::after {
  border-top-color: rgba(45, 40, 30, 0.92);
}
.holiday-decoration {
  position: absolute;
  pointer-events: none;
  z-index: 3;
  transform-origin: bottom center;
}
.holiday-particle-overlay {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 7;
}
</style>
