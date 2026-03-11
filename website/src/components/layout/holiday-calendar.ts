// ── Holiday calendar: timezone-aware date detection + cultural holiday data ──
// All holidays are visible to ALL users regardless of locale.
// Each holiday uses its country's timezone to determine activation.
// Rabbit speech bubbles use the user's selected language, not the holiday's country.

export interface HolidayVisuals {
  particles?: { type: string; count: number; colors: string[] }
  decorations?: { type: string; count: number; label?: string } | { type: string; count: number; label?: string }[]
  weatherHint?: string | null
}

export interface Holiday {
  id: string
  timezone: string
  locale: string // which locale "owns" this holiday (for priority sorting)
  dateRange: (year: number) => { start: [number, number]; end: [number, number] } | null
  visuals: HolidayVisuals
  thoughts: Record<string, string[]>
}

// ── Timezone utility ──
export function getDateInTimezone(tz: string): { month: number; day: number; year: number } {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    year: 'numeric', month: 'numeric', day: 'numeric'
  })
  const parts = fmt.formatToParts(new Date())
  const get = (t: string) => parseInt(parts.find(p => p.type === t)!.value)
  return { month: get('month'), day: get('day'), year: get('year') }
}

// ── Lunar New Year dates (Chinese calendar) 2024–2035 ──
// Each entry: [month, day] of Lunar New Year's Day (正月初一) in Gregorian
const lunarNewYearDates: Record<number, [number, number]> = {
  2024: [2, 10], 2025: [1, 29], 2026: [2, 17], 2027: [2, 6],
  2028: [1, 26], 2029: [2, 13], 2030: [2, 3], 2031: [1, 23],
  2032: [2, 11], 2033: [1, 31], 2034: [2, 19], 2035: [2, 8]
}

// Lunar month 8, day 15 (Mid-Autumn / 中秋) in Gregorian
const midAutumnDates: Record<number, [number, number]> = {
  2024: [9, 17], 2025: [10, 6], 2026: [9, 25], 2027: [10, 15],
  2028: [10, 3], 2029: [9, 22], 2030: [9, 12], 2031: [10, 1],
  2032: [9, 19], 2033: [9, 8], 2034: [9, 28], 2035: [9, 17]
}

// Lunar month 5, day 5 (Dragon Boat / 端午) in Gregorian
const dragonBoatDates: Record<number, [number, number]> = {
  2024: [6, 10], 2025: [5, 31], 2026: [6, 19], 2027: [6, 9],
  2028: [5, 28], 2029: [6, 16], 2030: [6, 5], 2031: [6, 24],
  2032: [6, 13], 2033: [6, 3], 2034: [6, 22], 2035: [6, 11]
}

// Lunar month 1, day 15 (Lantern Festival / 元宵) in Gregorian
const lanternFestDates: Record<number, [number, number]> = {
  2024: [2, 24], 2025: [2, 12], 2026: [3, 3], 2027: [2, 20],
  2028: [2, 9], 2029: [2, 27], 2030: [2, 17], 2031: [2, 6],
  2032: [2, 25], 2033: [2, 14], 2034: [3, 5], 2035: [2, 22]
}

// ── Islamic calendar dates (Eid al-Fitr, Eid al-Adha) 2024–2035 ──
// Approximate Gregorian dates — shift ~11 days earlier each year
const eidAlFitrDates: Record<number, [number, number]> = {
  2024: [4, 10], 2025: [3, 30], 2026: [3, 20], 2027: [3, 9],
  2028: [2, 27], 2029: [2, 14], 2030: [2, 4], 2031: [1, 24],
  2032: [1, 14], 2033: [1, 2], 2034: [12, 22], 2035: [12, 12]
}

const eidAlAdhaDates: Record<number, [number, number]> = {
  2024: [6, 17], 2025: [6, 6], 2026: [5, 27], 2027: [5, 16],
  2028: [5, 4], 2029: [4, 24], 2030: [4, 13], 2031: [4, 2],
  2032: [3, 22], 2033: [3, 11], 2034: [3, 1], 2035: [2, 18]
}

// ── Easter date (for Maslenitsa: 7 weeks before Orthodox Easter) ──
// Orthodox Easter uses Julian calendar — precomputed Gregorian dates
const orthodoxEasterDates: Record<number, [number, number]> = {
  2024: [5, 5], 2025: [4, 20], 2026: [4, 12], 2027: [5, 2],
  2028: [4, 16], 2029: [4, 8], 2030: [4, 28], 2031: [4, 13],
  2032: [5, 2], 2033: [4, 24], 2034: [4, 9], 2035: [4, 29]
}

// US Thanksgiving: 4th Thursday of November
function thanksgivingDate(year: number): [number, number] {
  // Nov 1 day of week, find 4th Thursday
  const d = new Date(year, 10, 1) // Nov 1
  const dow = d.getDay() // 0=Sun
  const firstThurs = dow <= 4 ? (4 - dow + 1) : (11 - dow + 1)
  return [11, firstThurs + 21] // 4th Thursday
}

// Helper: check if a date falls within a range (handles year-crossing like Dec 31 – Jan 2)
function isInRange(
  month: number, day: number,
  start: [number, number], end: [number, number]
): boolean {
  const d = month * 100 + day
  const s = start[0] * 100 + start[1]
  const e = end[0] * 100 + end[1]
  if (s <= e) return d >= s && d <= e
  // Year-crossing range (e.g. Dec 31 – Jan 2)
  return d >= s || d <= e
}

// Helper: create date range around a lookup-table date ± offset days
function lunarRange(table: Record<number, [number, number]>, year: number, before: number, after: number): { start: [number, number]; end: [number, number] } | null {
  const base = table[year]
  if (!base) return null
  const d = new Date(year, base[0] - 1, base[1])
  const s = new Date(d); s.setDate(s.getDate() - before)
  const e = new Date(d); e.setDate(e.getDate() + after)
  return {
    start: [s.getMonth() + 1, s.getDate()],
    end: [e.getMonth() + 1, e.getDate()]
  }
}

// ── Holiday definitions ──

const holidays: Holiday[] = [
  // ════════════════ 🇺🇸 United States ════════════════
  {
    id: 'us-newyear', timezone: 'America/New_York', locale: 'en',
    dateRange: () => ({ start: [12, 31], end: [1, 2] }),
    visuals: { particles: { type: 'confetti', count: 20, colors: ['#ff4444', '#44aaff', '#ffdd44', '#44dd88', '#ff88dd', '#aa66ff'] } },
    thoughts: {
      'en': ['Happy New Year!', '3… 2… 1… 🎉', 'New year, new hops!', 'Party time!'],
      'zh-CN': ['新年快乐!', '3…2…1…🎉', '新的一年新的跳!', '派对时间!'],
      'zh-TW': ['新年快樂!', '3…2…1…🎉', '新的一年新的跳!', '派對時間!'],
      'ja': ['ハッピーニューイヤー!', '3…2…1…🎉', '新年もぴょんぴょん!', 'パーティータイム!'],
      'ko': ['새해 복 많이!', '3…2…1…🎉', '새해에도 깡충!', '파티 타임!'],
      'ru': ['С Новым годом!', '3…2…1…🎉', 'Новый год — новые прыжки!', 'Вечеринка!'],
      'es': ['¡Feliz Año Nuevo!', '3…2…1…🎉', '¡Año nuevo, saltos nuevos!', '¡Fiesta!'],
      'fr': ['Bonne année !', '3…2…1…🎉', 'Nouvelle année, nouveaux sauts !', 'C\'est la fête !'],
      'ar': ['سنة جديدة سعيدة!', '🎉…1…2…3', 'سنة جديدة، قفزات جديدة!', 'وقت الحفلة!'],
    }
  },
  {
    id: 'us-valentine', timezone: 'America/New_York', locale: 'en',
    dateRange: () => ({ start: [2, 13], end: [2, 15] }),
    visuals: {
      particles: { type: 'heart', count: 15, colors: ['#ff6688', '#ff4466', '#ff88aa', '#ee3366', '#ffaacc'] },
      decorations: { type: 'candy-heart', count: 2, label: 'LOVE' }
    },
    thoughts: {
      'en': ['Happy Valentine\'s!', 'Love is in the air~', 'Be my bunny?', '💕'],
      'zh-CN': ['情人节快乐!', '爱在空气中~', '做我的小兔子?', '💕'],
      'zh-TW': ['情人節快樂!', '愛在空氣中~', '做我的小兔子?', '💕'],
      'ja': ['ハッピーバレンタイン!', '愛が漂ってる~', 'うさぎのバレンタイン💕', '💕'],
      'ko': ['해피 발렌타인!', '사랑이 가득~', '내 토끼가 되어줘?', '💕'],
      'ru': ['С Днём Валентина!', 'Любовь витает в воздухе~', 'Будь моим зайкой?', '💕'],
      'es': ['¡Feliz San Valentín!', 'El amor está en el aire~', '¿Serás mi conejito?', '💕'],
      'fr': ['Joyeuse St-Valentin !', 'L\'amour est dans l\'air~', 'Sois mon lapin ?', '💕'],
      'ar': ['عيد حب سعيد!', 'الحب في الهواء~', 'كن أرنبي؟', '💕'],
    }
  },
  {
    id: 'us-stpatrick', timezone: 'America/New_York', locale: 'en',
    dateRange: () => ({ start: [3, 16], end: [3, 18] }),
    visuals: { decorations: { type: 'shamrock', count: 2 } },
    thoughts: {
      'en': ['Lucky hop!', 'Feeling green~', '☘️', 'Where\'s the gold?'],
      'zh-CN': ['幸运一跳!', '绿色心情~', '☘️', '金子在哪?'],
      'zh-TW': ['幸運一跳!', '綠色心情~', '☘️', '金子在哪?'],
      'ja': ['ラッキーホップ!', '緑な気分~', '☘️', '金はどこ?'],
      'ko': ['행운의 점프!', '초록 기분~', '☘️', '금은 어디?'],
      'ru': ['Удачный прыжок!', 'Зелёное настроение~', '☘️', 'Где золото?'],
      'es': ['¡Salto de suerte!', 'Me siento verde~', '☘️', '¿Dónde está el oro?'],
      'fr': ['Saut chanceux !', 'Vert de joie~', '☘️', 'Où est l\'or ?'],
      'ar': ['قفزة محظوظة!', 'أشعر بالخضرة~', '☘️', 'أين الذهب؟'],
    }
  },
  {
    id: 'us-july4', timezone: 'America/New_York', locale: 'en',
    dateRange: () => ({ start: [7, 3], end: [7, 5] }),
    visuals: { particles: { type: 'firework-spark', count: 18, colors: ['#ff3333', '#ffffff', '#3344ff', '#ffdd44'] } },
    thoughts: {
      'en': ['Fireworks!', 'Happy 4th!', 'Boom boom!', 'So sparkly!'],
      'zh-CN': ['烟花!', '砰砰砰!', '好闪耀!', '独立日快乐!'],
      'zh-TW': ['煙花!', '砰砰砰!', '好閃耀!', '獨立日快樂!'],
      'ja': ['花火だ!', 'ドカーン!', 'キラキラ!', 'ハッピー4th!'],
      'ko': ['불꽃놀이!', '펑펑!', '반짝반짝!', '해피 4th!'],
      'ru': ['Фейерверки!', 'Бум-бум!', 'Как сверкает!', 'С Днём независимости!'],
      'es': ['¡Fuegos artificiales!', '¡Bum bum!', '¡Qué brillante!', '¡Feliz 4 de julio!'],
      'fr': ['Feux d\'artifice !', 'Boum boum !', 'Ça brille !', 'Happy 4th !'],
      'ar': ['ألعاب نارية!', 'بوم بوم!', 'كم هي متألقة!', 'يوم الاستقلال!'],
    }
  },
  {
    id: 'us-halloween', timezone: 'America/New_York', locale: 'en',
    dateRange: () => ({ start: [10, 28], end: [11, 1] }),
    visuals: { decorations: [{ type: 'pumpkin', count: 2 }, { type: 'tombstone', count: 1, label: 'RIP' }] },
    thoughts: {
      'en': ['Boo!', 'Trick or treat!', 'Spooky hop~', '🎃'],
      'zh-CN': ['不给糖就捣蛋!', '哇!', '🎃', '好恐怖~'],
      'zh-TW': ['不給糖就搗蛋!', '哇!', '🎃', '好恐怖~'],
      'ja': ['ブー!', 'トリックオアトリート!', 'おばけぴょん~', '🎃'],
      'ko': ['부!', '사탕 안 주면 장난칠 거야!', '으스스 점프~', '🎃'],
      'ru': ['Бу!', 'Сладость или гадость!', 'Жуткий прыг~', '🎃'],
      'es': ['¡Bu!', '¡Truco o trato!', 'Salto espeluznante~', '🎃'],
      'fr': ['Bouh !', 'Des bonbons ou un sort !', 'Saut effrayant~', '🎃'],
      'ar': ['بو!', 'حلوى أو مقلب!', 'قفزة مخيفة~', '🎃'],
    }
  },
  {
    id: 'us-thanksgiving', timezone: 'America/New_York', locale: 'en',
    dateRange: (year) => {
      const [m, d] = thanksgivingDate(year)
      return { start: [m, d - 1], end: [m, d + 1] }
    },
    visuals: { particles: { type: 'maple-leaf', count: 12, colors: ['#cc4400', '#dd6622', '#ee8833', '#bb3300', '#ff9944'] } },
    thoughts: {
      'en': ['Thankful!', 'Gobble gobble!', 'So much food~', 'Grateful hop!'],
      'zh-CN': ['感恩!', '好多食物~', '感恩的一跳!', '感恩节快乐!'],
      'zh-TW': ['感恩!', '好多食物~', '感恩的一跳!', '感恩節快樂!'],
      'ja': ['感謝!', 'いっぱいご飯~', '感謝のジャンプ!', 'ハッピーサンクスギビング!'],
      'ko': ['감사해요!', '음식이 가득~', '감사한 점프!', '해피 추수감사절!'],
      'ru': ['Благодарю!', 'Столько еды~', 'Прыжок благодарности!', 'С Днём благодарения!'],
      'es': ['¡Agradecido!', 'Tanta comida~', '¡Salto de gratitud!', '¡Feliz Acción de Gracias!'],
      'fr': ['Reconnaissant !', 'Tant de nourriture~', 'Saut de gratitude !', 'Joyeux Thanksgiving !'],
      'ar': ['ممتن!', 'كثير من الطعام~', 'قفزة شكر!', 'عيد شكر سعيد!'],
    }
  },
  {
    id: 'us-christmas', timezone: 'America/New_York', locale: 'en',
    dateRange: () => ({ start: [12, 22], end: [12, 27] }),
    visuals: {
      particles: { type: 'snowflake-special', count: 12, colors: ['#ffffff', '#e8f0ff', '#d0e4ff'] },
      decorations: { type: 'christmas-tree', count: 2 },
      weatherHint: 'snowy'
    },
    thoughts: {
      'en': ['Merry Christmas!', 'Ho ho hop!', 'Jingle boing!', '🎄'],
      'zh-CN': ['圣诞快乐!', '叮叮跳!', '🎄', '圣诞老人来了!'],
      'zh-TW': ['聖誕快樂!', '叮叮跳!', '🎄', '聖誕老人來了!'],
      'ja': ['メリークリスマス!', 'ホーホーぴょん!', 'ジングルぴょん!', '🎄'],
      'ko': ['메리 크리스마스!', '호호 깡충!', '징글 깡충!', '🎄'],
      'ru': ['Счастливого Рождества!', 'Хо-хо-прыг!', 'Дзинь-прыг!', '🎄'],
      'es': ['¡Feliz Navidad!', '¡Jo jo hop!', '¡Jingle boing!', '🎄'],
      'fr': ['Joyeux Noël !', 'Ho ho hop !', 'Jingle boing !', '🎄'],
      'ar': ['عيد ميلاد مجيد!', 'هو هو قفز!', '🎄', 'جلجل قفز!'],
    }
  },

  // ════════════════ 🇨🇳 China ════════════════
  {
    id: 'cn-cny', timezone: 'Asia/Shanghai', locale: 'zh-CN',
    dateRange: (year) => lunarRange(lunarNewYearDates, year, 2, 6),
    visuals: {
      particles: { type: 'lantern-glow', count: 10, colors: ['#ff4444', '#ff6622', '#ffaa00', '#ff3333'] },
      decorations: { type: 'red-lantern', count: 3, label: '春' },
      weatherHint: null
    },
    thoughts: {
      'en': ['Happy Spring Festival!', 'Gong xi fa cai!', 'Red envelopes!', 'Year of luck!'],
      'zh-CN': ['新年快乐!', '恭喜发财!', '红包拿来!', '年年有余!', '春节好!'],
      'zh-TW': ['新年快樂!', '恭喜發財!', '紅包拿來!', '年年有餘!', '春節好!'],
      'ja': ['春節おめでとう!', '恭喜發財!', '新年快楽!', 'お年玉!'],
      'ko': ['춘절 축하해요!', '공시파차이!', '새해 복!', '홍바오!'],
      'ru': ['С Праздником Весны!', 'Гун си фа цай!', 'Красные конверты!', 'Удачный год!'],
      'es': ['¡Feliz Año Nuevo Chino!', '¡Gong xi fa cai!', '¡Sobres rojos!', '¡Año de suerte!'],
      'fr': ['Joyeux Nouvel An chinois !', 'Gong xi fa cai !', 'Enveloppes rouges !', 'Année chanceuse !'],
      'ar': ['عام صيني جديد سعيد!', 'غونغ شي فا تساي!', 'مظاريف حمراء!', 'سنة حظ!'],
    }
  },
  {
    id: 'cn-lantern', timezone: 'Asia/Shanghai', locale: 'zh-CN',
    dateRange: (year) => lunarRange(lanternFestDates, year, 1, 1),
    visuals: {
      particles: { type: 'lantern-glow', count: 8, colors: ['#ff6622', '#ffaa44', '#ff4444'] },
      decorations: { type: 'round-lantern', count: 2, label: '福' }
    },
    thoughts: {
      'en': ['Lantern Festival!', 'Round lanterns~', 'Sweet dumplings!', 'So many lights!'],
      'zh-CN': ['元宵节快乐!', '吃汤圆咯~', '花灯真美!', '团团圆圆!'],
      'zh-TW': ['元宵節快樂!', '吃湯圓咯~', '花燈真美!', '團團圓圓!'],
      'ja': ['元宵節!', 'ランタンがきれい~', '団子おいしい!', '明かりがいっぱい!'],
      'ko': ['원소절!', '등불이 예뻐~', '탕위안!', '둥글둥글!'],
      'ru': ['Праздник фонарей!', 'Круглые фонарики~', 'Сладкие клёцки!', 'Столько огней!'],
      'es': ['¡Festival de Faroles!', 'Faroles redondos~', '¡Bolas de arroz dulce!', '¡Tantas luces!'],
      'fr': ['Fête des lanternes !', 'Lanternes rondes~', 'Boulettes sucrées !', 'Tant de lumières !'],
      'ar': ['مهرجان الفوانيس!', 'فوانيس مستديرة~', 'كعكات حلوة!', 'كم من الأضواء!'],
    }
  },
  {
    id: 'cn-qingming', timezone: 'Asia/Shanghai', locale: 'zh-CN',
    dateRange: () => ({ start: [4, 4], end: [4, 6] }),
    visuals: { decorations: { type: 'chunlian', count: 1, label: '清明' } },
    thoughts: {
      'en': ['Qingming Festival', 'Spring cleaning~', 'Remembering...', 'Fresh spring air~'],
      'zh-CN': ['清明时节', '春风拂面~', '踏青去~', '雨纷纷...'],
      'zh-TW': ['清明時節', '春風拂面~', '踏青去~', '雨紛紛...'],
      'ja': ['清明節', '春の風~', 'お墓参り', '春の空気~'],
      'ko': ['청명절', '봄바람~', '성묘', '봄 공기~'],
      'ru': ['Цинмин', 'Весенний ветер~', 'Воспоминания...', 'Свежий воздух~'],
      'es': ['Festival Qingming', 'Brisa primaveral~', 'Recordando...', 'Aire fresco~'],
      'fr': ['Fête de Qingming', 'Brise printanière~', 'Souvenirs...', 'Air frais~'],
      'ar': ['مهرجان تشينغ مينغ', 'نسيم الربيع~', 'ذكريات...', 'هواء منعش~'],
    }
  },
  {
    id: 'cn-dragonboat', timezone: 'Asia/Shanghai', locale: 'zh-CN',
    dateRange: (year) => lunarRange(dragonBoatDates, year, 1, 1),
    visuals: { decorations: { type: 'chunlian', count: 1, label: '端午' } },
    thoughts: {
      'en': ['Dragon Boat Festival!', 'Zongzi time!', 'Row row row!', 'Dragon boats!'],
      'zh-CN': ['端午节快乐!', '吃粽子咯~', '划龙舟!', '屈原~'],
      'zh-TW': ['端午節快樂!', '吃粽子咯~', '划龍舟!', '屈原~'],
      'ja': ['端午の節句!', 'ちまき!', 'ドラゴンボート!', '競漕だ!'],
      'ko': ['단오절!', '쫑쯔!', '용선 경주!', '배 저어라!'],
      'ru': ['Праздник Драконьих лодок!', 'Цзунцзы!', 'Греби-греби!', 'Драконьи лодки!'],
      'es': ['¡Festival del Bote Dragón!', '¡Zongzi!', '¡Rema rema!', '¡Botes dragón!'],
      'fr': ['Fête des bateaux-dragons !', 'Zongzi !', 'Rame rame !', 'Bateaux-dragons !'],
      'ar': ['مهرجان قوارب التنين!', 'زونغزي!', 'جدّف جدّف!', 'قوارب التنين!'],
    }
  },
  {
    id: 'cn-midautumn', timezone: 'Asia/Shanghai', locale: 'zh-CN',
    dateRange: (year) => lunarRange(midAutumnDates, year, 1, 1),
    visuals: {
      particles: { type: 'lantern-glow', count: 6, colors: ['#ffcc44', '#ffaa22', '#ff8800'] },
      decorations: { type: 'chunlian', count: 1, label: '团圆' }
    },
    thoughts: {
      'en': ['Mid-Autumn Festival!', 'Mooncakes!', 'Full moon tonight~', 'Family reunion!'],
      'zh-CN': ['中秋快乐!', '吃月饼!', '月亮好圆~', '团圆!', '嫦娥~'],
      'zh-TW': ['中秋快樂!', '吃月餅!', '月亮好圓~', '團圓!', '嫦娥~'],
      'ja': ['中秋節!', '月餅!', '満月だ~', '団欒!'],
      'ko': ['중추절!', '월병!', '보름달~', '가족 모임!'],
      'ru': ['Праздник Середины Осени!', 'Лунные пирожки!', 'Полная луна~', 'Семейная встреча!'],
      'es': ['¡Festival de Medio Otoño!', '¡Pasteles de luna!', 'Luna llena~', '¡Reunión familiar!'],
      'fr': ['Fête de la Mi-Automne !', 'Gâteaux de lune !', 'Pleine lune~', 'Réunion familiale !'],
      'ar': ['مهرجان منتصف الخريف!', 'كعك القمر!', 'بدر الليلة~', 'لمّ الشمل!'],
    }
  },
  {
    id: 'cn-nationalday', timezone: 'Asia/Shanghai', locale: 'zh-CN',
    dateRange: () => ({ start: [10, 1], end: [10, 3] }),
    visuals: {
      particles: { type: 'firework-spark', count: 15, colors: ['#ff2222', '#ffdd00', '#ff4444'] },
      decorations: { type: 'red-lantern', count: 2, label: '庆' }
    },
    thoughts: {
      'en': ['Happy National Day!', 'Golden week!', 'Fireworks!', 'Holiday!'],
      'zh-CN': ['国庆快乐!', '黄金周!', '放烟花!', '放假咯!'],
      'zh-TW': ['國慶快樂!', '黃金週!', '放煙花!', '放假咯!'],
      'ja': ['中国の建国記念日!', 'ゴールデンウィーク!', '花火!', '休日だ!'],
      'ko': ['중국 국경절!', '골든위크!', '불꽃놀이!', '연휴다!'],
      'ru': ['С Днём КНР!', 'Золотая неделя!', 'Фейерверки!', 'Праздник!'],
      'es': ['¡Día Nacional de China!', '¡Semana dorada!', '¡Fuegos artificiales!', '¡Vacaciones!'],
      'fr': ['Fête nationale chinoise !', 'Semaine dorée !', 'Feux d\'artifice !', 'Vacances !'],
      'ar': ['يوم وطني سعيد!', 'الأسبوع الذهبي!', 'ألعاب نارية!', 'عطلة!'],
    }
  },

  // ════════════════ 🇹🇼 Taiwan ════════════════
  {
    id: 'tw-cny', timezone: 'Asia/Taipei', locale: 'zh-TW',
    dateRange: (year) => lunarRange(lunarNewYearDates, year, 2, 6),
    visuals: {
      particles: { type: 'lantern-glow', count: 10, colors: ['#ff4444', '#ff6622', '#ffaa00'] },
      decorations: { type: 'red-lantern', count: 3, label: '春' }
    },
    thoughts: {
      'en': ['Happy Lunar New Year!', 'Gong xi fa cai!', 'Red envelopes!', 'Year of luck!'],
      'zh-CN': ['新年快乐!', '恭喜发财!', '红包拿来!', '年年有余!'],
      'zh-TW': ['新年快樂!', '恭喜發財!', '紅包拿來!', '年年有餘!', '過年好!'],
      'ja': ['春節おめでとう!', '恭喜發財!', '新年快楽!', 'お年玉!'],
      'ko': ['설날 축하해요!', '공시파차이!', '새해 복!', '홍바오!'],
      'ru': ['С Праздником Весны!', 'Гун си фа цай!', 'Красные конверты!', 'Удачный год!'],
      'es': ['¡Feliz Año Nuevo Lunar!', '¡Gong xi fa cai!', '¡Sobres rojos!', '¡Año de suerte!'],
      'fr': ['Joyeux Nouvel An lunaire !', 'Gong xi fa cai !', 'Enveloppes rouges !', 'Année chanceuse !'],
      'ar': ['عام قمري جديد سعيد!', 'غونغ شي فا تساي!', 'مظاريف حمراء!', 'سنة حظ!'],
    }
  },
  {
    id: 'tw-lantern', timezone: 'Asia/Taipei', locale: 'zh-TW',
    dateRange: (year) => lunarRange(lanternFestDates, year, 1, 1),
    visuals: {
      particles: { type: 'lantern-glow', count: 8, colors: ['#ff6622', '#ffaa44', '#ff4444'] },
      decorations: { type: 'round-lantern', count: 2, label: '福' }
    },
    thoughts: {
      'en': ['Lantern Festival!', 'Sky lanterns~', 'Sweet dumplings!', 'Beautiful lights!'],
      'zh-CN': ['元宵节快乐!', '放天灯~', '吃汤圆!', '花灯好美!'],
      'zh-TW': ['元宵節快樂!', '放天燈~', '吃湯圓!', '花燈好美!'],
      'ja': ['元宵節!', '天灯が綺麗~', '団子!', 'ランタン!'],
      'ko': ['원소절!', '천등~', '탕위안!', '등불이 예뻐!'],
      'ru': ['Праздник фонарей!', 'Небесные фонарики~', 'Сладкие клёцки!', 'Красивые огни!'],
      'es': ['¡Festival de Faroles!', 'Linternas del cielo~', '¡Bolas de arroz dulce!', '¡Hermosas luces!'],
      'fr': ['Fête des lanternes !', 'Lanternes célestes~', 'Boulettes sucrées !', 'Belles lumières !'],
      'ar': ['مهرجان الفوانيس!', 'فوانيس السماء~', 'كعكات حلوة!', 'أضواء جميلة!'],
    }
  },
  {
    id: 'tw-midautumn', timezone: 'Asia/Taipei', locale: 'zh-TW',
    dateRange: (year) => lunarRange(midAutumnDates, year, 1, 1),
    visuals: {
      particles: { type: 'lantern-glow', count: 6, colors: ['#ffcc44', '#ffaa22', '#ff8800'] },
      decorations: { type: 'chunlian', count: 1, label: '團圓' }
    },
    thoughts: {
      'en': ['Mid-Autumn Festival!', 'Mooncakes!', 'BBQ time!', 'Beautiful moon~'],
      'zh-CN': ['中秋快乐!', '吃月饼!', '烤肉!', '月亮好美~'],
      'zh-TW': ['中秋快樂!', '吃月餅!', '烤肉時間!', '月亮好美~', '柚子~'],
      'ja': ['中秋節!', '月餅!', 'BBQ!', '月が綺麗~'],
      'ko': ['중추절!', '월병!', '바비큐!', '달이 예뻐~'],
      'ru': ['Праздник Середины Осени!', 'Лунные пирожки!', 'Барбекю!', 'Красивая луна~'],
      'es': ['¡Festival de Medio Otoño!', '¡Pasteles de luna!', '¡Hora del BBQ!', 'Luna hermosa~'],
      'fr': ['Fête de la Mi-Automne !', 'Gâteaux de lune !', 'Barbecue !', 'Belle lune~'],
      'ar': ['مهرجان منتصف الخريف!', 'كعك القمر!', 'وقت الشواء!', 'قمر جميل~'],
    }
  },
  {
    id: 'tw-doubletenday', timezone: 'Asia/Taipei', locale: 'zh-TW',
    dateRange: () => ({ start: [10, 9], end: [10, 11] }),
    visuals: { particles: { type: 'firework-spark', count: 12, colors: ['#ff0000', '#0000ff', '#ffffff', '#ffdd00'] } },
    thoughts: {
      'en': ['Double Tenth Day!', 'Fireworks!', 'National Day!', 'Celebration!'],
      'zh-CN': ['双十节快乐!', '烟花!', '国庆!', '庆典!'],
      'zh-TW': ['雙十節快樂!', '煙花!', '國慶!', '慶典!'],
      'ja': ['双十節!', '花火!', '国慶節!', 'お祝い!'],
      'ko': ['쌍십절!', '불꽃놀이!', '국경일!', '축하!'],
      'ru': ['День Двойной десятки!', 'Фейерверки!', 'Национальный праздник!', 'Торжество!'],
      'es': ['¡Doble Diez!', '¡Fuegos artificiales!', '¡Día Nacional!', '¡Celebración!'],
      'fr': ['Jour du Double Dix !', 'Feux d\'artifice !', 'Fête nationale !', 'Célébration !'],
      'ar': ['يوم العاشر المزدوج!', 'ألعاب نارية!', 'يوم وطني!', 'احتفال!'],
    }
  },

  // ════════════════ 🇯🇵 Japan ════════════════
  {
    id: 'jp-shogatsu', timezone: 'Asia/Tokyo', locale: 'ja',
    dateRange: () => ({ start: [12, 31], end: [1, 3] }),
    visuals: { decorations: { type: 'kadomatsu', count: 2 } },
    thoughts: {
      'en': ['Happy New Year!', 'Oshogatsu!', 'Mochi time!', 'New year hops!'],
      'zh-CN': ['新年快乐!', '吃年糕!', '正月!', '新的一年!'],
      'zh-TW': ['新年快樂!', '吃年糕!', '正月!', '新的一年!'],
      'ja': ['あけましておめでとう!', 'お正月!', 'お餅!', '初詣!', '今年もよろしく!'],
      'ko': ['새해 복 많이!', '오쇼가츠!', '떡!', '새해 점프!'],
      'ru': ['С Новым годом!', 'Осёгацу!', 'Моти!', 'Новогодние прыжки!'],
      'es': ['¡Feliz Año Nuevo!', '¡Oshogatsu!', '¡Mochi!', '¡Saltos de año nuevo!'],
      'fr': ['Bonne année !', 'Oshogatsu !', 'Mochi !', 'Sauts du Nouvel An !'],
      'ar': ['سنة جديدة سعيدة!', 'أوشوغاتسو!', 'موتشي!', 'قفزات سنة جديدة!'],
    }
  },
  {
    id: 'jp-setsubun', timezone: 'Asia/Tokyo', locale: 'ja',
    dateRange: () => ({ start: [2, 2], end: [2, 4] }),
    visuals: { decorations: { type: 'daruma', count: 1, label: '福' } },
    thoughts: {
      'en': ['Setsubun!', 'Oni wa soto!', 'Throw the beans!', 'Spring is coming!'],
      'zh-CN': ['节分!', '鬼在外!', '撒豆子!', '春天来了!'],
      'zh-TW': ['節分!', '鬼在外!', '撒豆子!', '春天來了!'],
      'ja': ['節分!', '鬼は外!', '福は内!', '豆まき!', '春が来る!'],
      'ko': ['세츠분!', '오니와 소토!', '콩 던져!', '봄이 온다!'],
      'ru': ['Сэцубун!', 'Они ва сото!', 'Бросай бобы!', 'Весна идёт!'],
      'es': ['¡Setsubun!', '¡Oni wa soto!', '¡Tira los frijoles!', '¡La primavera viene!'],
      'fr': ['Setsubun !', 'Oni wa soto !', 'Lance les haricots !', 'Le printemps arrive !'],
      'ar': ['سيتسوبون!', 'أوني وا سوتو!', 'ارمِ الفول!', 'الربيع قادم!'],
    }
  },
  {
    id: 'jp-hanami', timezone: 'Asia/Tokyo', locale: 'ja',
    dateRange: () => ({ start: [3, 25], end: [4, 10] }),
    visuals: {
      particles: { type: 'sakura', count: 20, colors: ['#ffb7c5', '#ff99b4', '#ffc8d6', '#ffa0b8', '#ffd0dd'] },
      decorations: { type: 'omamori', count: 1, label: '花見' }
    },
    thoughts: {
      'en': ['Cherry blossoms!', 'Hanami time~', 'So beautiful!', 'Petals everywhere!'],
      'zh-CN': ['樱花!', '赏花~', '好美!', '花瓣飘落~'],
      'zh-TW': ['櫻花!', '賞花~', '好美!', '花瓣飄落~'],
      'ja': ['桜!', 'お花見~', 'きれい!', '花びらが舞ってる~', 'ぴょんぴょん花見!'],
      'ko': ['벚꽃!', '하나미~', '예쁘다!', '꽃잎이 날린다~'],
      'ru': ['Сакура!', 'Ханами~', 'Красиво!', 'Лепестки повсюду~'],
      'es': ['¡Cerezo en flor!', 'Hanami~', '¡Qué hermoso!', '¡Pétalos por doquier!'],
      'fr': ['Cerisiers en fleurs !', 'Hanami~', 'Magnifique !', 'Des pétales partout !'],
      'ar': ['أزهار الكرز!', 'هانامي~', 'جميل جداً!', 'بتلات في كل مكان!'],
    }
  },
  {
    id: 'jp-tanabata', timezone: 'Asia/Tokyo', locale: 'ja',
    dateRange: () => ({ start: [7, 6], end: [7, 8] }),
    visuals: { decorations: { type: 'tanzaku', count: 2, label: '願' } },
    thoughts: {
      'en': ['Tanabata!', 'Star Festival!', 'Make a wish~', 'Orihime & Hikoboshi!'],
      'zh-CN': ['七夕!', '星星节!', '许个愿~', '织女牛郎!'],
      'zh-TW': ['七夕!', '星星節!', '許個願~', '織女牛郎!'],
      'ja': ['七夕!', '星祭り!', 'お願い事~', '織姫と彦星!', '短冊に書こう!'],
      'ko': ['타나바타!', '별 축제!', '소원을 빌어~', '오리히메와 히코보시!'],
      'ru': ['Танабата!', 'Звёздный фестиваль!', 'Загадай желание~', 'Орихимэ и Хикобоси!'],
      'es': ['¡Tanabata!', '¡Festival de estrellas!', 'Pide un deseo~', '¡Orihime y Hikoboshi!'],
      'fr': ['Tanabata !', 'Fête des étoiles !', 'Fais un vœu~', 'Orihime et Hikoboshi !'],
      'ar': ['تاناباتا!', 'مهرجان النجوم!', 'تمنَّ أمنية~', 'أوريهيمي وهيكوبوشي!'],
    }
  },
  {
    id: 'jp-obon', timezone: 'Asia/Tokyo', locale: 'ja',
    dateRange: () => ({ start: [8, 13], end: [8, 16] }),
    visuals: {
      particles: { type: 'lantern-glow', count: 8, colors: ['#ffcc44', '#ff9922', '#ffaa00'] },
      decorations: { type: 'ema', count: 1, label: '盆' }
    },
    thoughts: {
      'en': ['Obon Festival', 'Welcome back, spirits~', 'Lantern floating~', 'Family time~'],
      'zh-CN': ['盂兰盆节', '欢迎回来~', '放灯~', '家人团聚~'],
      'zh-TW': ['盂蘭盆節', '歡迎回來~', '放燈~', '家人團聚~'],
      'ja': ['お盆', 'おかえりなさい~', '灯篭流し~', '家族の時間~', 'ご先祖様~'],
      'ko': ['오본', '환영합니다~', '등불 띄우기~', '가족 시간~'],
      'ru': ['Фестиваль Обон', 'Добро пожаловать, духи~', 'Плавающие фонарики~', 'Семейное время~'],
      'es': ['Festival Obon', 'Bienvenidos, espíritus~', 'Linternas flotantes~', 'Tiempo familiar~'],
      'fr': ['Festival Obon', 'Bienvenue, esprits~', 'Lanternes flottantes~', 'Temps en famille~'],
      'ar': ['مهرجان أوبون', 'أهلاً بعودتكم~', 'فوانيس عائمة~', 'وقت العائلة~'],
    }
  },
  {
    id: 'jp-tsukimi', timezone: 'Asia/Tokyo', locale: 'ja',
    dateRange: (year) => lunarRange(midAutumnDates, year, 1, 1),
    visuals: { decorations: { type: 'ema', count: 1, label: '月見' } },
    thoughts: {
      'en': ['Tsukimi!', 'Moon viewing~', 'Beautiful moon!', 'Dango time!'],
      'zh-CN': ['赏月!', '月亮真美~', '吃团子!', '中秋月~'],
      'zh-TW': ['賞月!', '月亮真美~', '吃糰子!', '中秋月~'],
      'ja': ['お月見!', '月がきれい~', 'お団子!', 'すすき~', 'うさぎが餅つき!'],
      'ko': ['츠키미!', '달구경~', '달이 예뻐!', '당고!'],
      'ru': ['Цукими!', 'Любование луной~', 'Красивая луна!', 'Данго!'],
      'es': ['¡Tsukimi!', 'Contemplar la luna~', '¡Luna hermosa!', '¡Dango!'],
      'fr': ['Tsukimi !', 'Contemplation de la lune~', 'Belle lune !', 'Dango !'],
      'ar': ['تسوكيمي!', 'مشاهدة القمر~', 'قمر جميل!', 'دانغو!'],
    }
  },
  {
    id: 'jp-christmas', timezone: 'Asia/Tokyo', locale: 'ja',
    dateRange: () => ({ start: [12, 23], end: [12, 26] }),
    visuals: {
      particles: { type: 'snowflake-special', count: 10, colors: ['#ffffff', '#e8f0ff', '#d0e4ff'] },
      decorations: { type: 'christmas-tree', count: 1 }
    },
    thoughts: {
      'en': ['Merry Christmas!', 'Christmas cake!', 'KFC time!', '🎄'],
      'zh-CN': ['圣诞快乐!', '圣诞蛋糕!', '🎄', '快乐!'],
      'zh-TW': ['聖誕快樂!', '聖誕蛋糕!', '🎄', '快樂!'],
      'ja': ['メリークリスマス!', 'クリスマスケーキ!', 'チキン!', '🎄', 'イルミネーション!'],
      'ko': ['메리 크리스마스!', '크리스마스 케이크!', '🎄', '치킨!'],
      'ru': ['Счастливого Рождества!', 'Рождественский торт!', '🎄', 'Курица!'],
      'es': ['¡Feliz Navidad!', '¡Pastel navideño!', '🎄', '¡Pollo!'],
      'fr': ['Joyeux Noël !', 'Gâteau de Noël !', '🎄', 'Poulet !'],
      'ar': ['عيد ميلاد مجيد!', 'كعكة عيد الميلاد!', '🎄', 'دجاج!'],
    }
  },

  // ════════════════ 🇰🇷 South Korea ════════════════
  {
    id: 'kr-seollal', timezone: 'Asia/Seoul', locale: 'ko',
    dateRange: (year) => lunarRange(lunarNewYearDates, year, 2, 2),
    visuals: {
      particles: { type: 'firework-spark', count: 12, colors: ['#ff4444', '#ffdd44', '#ffffff'] },
      decorations: { type: 'bokjumeoni', count: 1, label: '복' }
    },
    thoughts: {
      'en': ['Happy Seollal!', 'Tteokguk time!', 'Sebae!', 'New Year!'],
      'zh-CN': ['新年快乐!', '年糕汤!', '拜年!', '新的一年!'],
      'zh-TW': ['新年快樂!', '年糕湯!', '拜年!', '新的一年!'],
      'ja': ['セオラル!', 'トックク!', 'セベ!', '新年おめでとう!'],
      'ko': ['새해 복 많이 받으세요!', '떡국!', '세배!', '설날!', '세뱃돈!'],
      'ru': ['С Соллаль!', 'Ттоккук!', 'Себэ!', 'Новый год!'],
      'es': ['¡Feliz Seollal!', '¡Tteokguk!', '¡Sebae!', '¡Año Nuevo!'],
      'fr': ['Joyeux Seollal !', 'Tteokguk !', 'Sebae !', 'Nouvel An !'],
      'ar': ['سيولال سعيد!', 'تيوكوك!', 'سيباي!', 'سنة جديدة!'],
    }
  },
  {
    id: 'kr-cherry', timezone: 'Asia/Seoul', locale: 'ko',
    dateRange: () => ({ start: [4, 1], end: [4, 15] }),
    visuals: { particles: { type: 'sakura', count: 18, colors: ['#ffb7c5', '#ff99b4', '#ffc8d6', '#ffa0b8'] } },
    thoughts: {
      'en': ['Cherry blossoms!', 'Spring in Korea!', 'So beautiful!', 'Petals falling~'],
      'zh-CN': ['樱花!', '韩国的春天!', '好美!', '花瓣飘落~'],
      'zh-TW': ['櫻花!', '韓國的春天!', '好美!', '花瓣飄落~'],
      'ja': ['韓国の桜!', '春だ!', 'きれい!', '花びら~'],
      'ko': ['벚꽃!', '봄이다!', '예쁘다!', '꽃잎이 흩날려~', '벚꽃 구경!'],
      'ru': ['Вишнёвый цвет!', 'Весна в Корее!', 'Красиво!', 'Лепестки падают~'],
      'es': ['¡Cerezo en flor!', '¡Primavera coreana!', '¡Hermoso!', 'Pétalos cayendo~'],
      'fr': ['Cerisiers en fleurs !', 'Printemps coréen !', 'Magnifique !', 'Pétales qui tombent~'],
      'ar': ['أزهار الكرز!', 'الربيع الكوري!', 'جميل جداً!', 'بتلات تتساقط~'],
    }
  },
  {
    id: 'kr-chuseok', timezone: 'Asia/Seoul', locale: 'ko',
    dateRange: (year) => lunarRange(midAutumnDates, year, 1, 1),
    visuals: {
      particles: { type: 'maple-leaf', count: 10, colors: ['#cc4400', '#dd6622', '#ee8833', '#bb3300'] },
      decorations: { type: 'songpyeon', count: 2 }
    },
    thoughts: {
      'en': ['Happy Chuseok!', 'Songpyeon!', 'Harvest moon!', 'Family!'],
      'zh-CN': ['中秋快乐!', '松糕!', '丰收月!', '家人!'],
      'zh-TW': ['中秋快樂!', '松糕!', '豐收月!', '家人!'],
      'ja': ['チュソク!', 'ソンピョン!', '収穫の月!', '家族!'],
      'ko': ['추석 잘 보내세요!', '송편!', '한가위!', '가족!', '보름달!'],
      'ru': ['С Чусоком!', 'Сонпхён!', 'Урожайная луна!', 'Семья!'],
      'es': ['¡Feliz Chuseok!', '¡Songpyeon!', '¡Luna de cosecha!', '¡Familia!'],
      'fr': ['Joyeux Chuseok !', 'Songpyeon !', 'Lune de moisson !', 'Famille !'],
      'ar': ['تشوسوك سعيد!', 'سونغبيون!', 'قمر الحصاد!', 'عائلة!'],
    }
  },
  {
    id: 'kr-christmas', timezone: 'Asia/Seoul', locale: 'ko',
    dateRange: () => ({ start: [12, 23], end: [12, 26] }),
    visuals: {
      particles: { type: 'snowflake-special', count: 10, colors: ['#ffffff', '#e8f0ff', '#d0e4ff'] },
      decorations: { type: 'christmas-tree', count: 1 }
    },
    thoughts: {
      'en': ['Merry Christmas!', 'Christmas cake!', '🎄', 'Snow!'],
      'zh-CN': ['圣诞快乐!', '🎄', '下雪了!', '圣诞蛋糕!'],
      'zh-TW': ['聖誕快樂!', '🎄', '下雪了!', '聖誕蛋糕!'],
      'ja': ['メリークリスマス!', '🎄', '雪だ!', 'ケーキ!'],
      'ko': ['메리 크리스마스!', '🎄', '눈이다!', '크리스마스 케이크!', '산타!'],
      'ru': ['Счастливого Рождества!', '🎄', 'Снег!', 'Торт!'],
      'es': ['¡Feliz Navidad!', '🎄', '¡Nieve!', '¡Pastel!'],
      'fr': ['Joyeux Noël !', '🎄', 'Neige !', 'Gâteau !'],
      'ar': ['عيد ميلاد مجيد!', '🎄', 'ثلج!', 'كعكة!'],
    }
  },

  // ════════════════ 🇷🇺 Russia ════════════════
  {
    id: 'ru-newyear', timezone: 'Europe/Moscow', locale: 'ru',
    dateRange: () => ({ start: [12, 31], end: [1, 2] }),
    visuals: {
      particles: { type: 'confetti', count: 15, colors: ['#ff4444', '#44aaff', '#ffdd44', '#44dd88', '#ff88dd'] },
      decorations: { type: 'yolka', count: 1 }
    },
    thoughts: {
      'en': ['Happy New Year!', 'Yolka!', 'Champagne!', 'Ded Moroz!'],
      'zh-CN': ['新年快乐!', '新年树!', '香槟!', '严寒老人!'],
      'zh-TW': ['新年快樂!', '新年樹!', '香檳!', '嚴寒老人!'],
      'ja': ['明けましておめでとう!', 'ヨールカ!', 'シャンパン!', 'ジェド・マロース!'],
      'ko': ['새해 복 많이!', '욜카!', '샴페인!', '데드 모로즈!'],
      'ru': ['С Новым годом!', 'Ёлка!', 'Шампанское!', 'Дед Мороз!', 'Оливье!'],
      'es': ['¡Feliz Año Nuevo!', '¡Yolka!', '¡Champán!', '¡Ded Moroz!'],
      'fr': ['Bonne année !', 'Yolka !', 'Champagne !', 'Ded Moroz !'],
      'ar': ['سنة جديدة سعيدة!', 'يولكا!', 'شامبانيا!', 'ديد موروز!'],
    }
  },
  {
    id: 'ru-christmas', timezone: 'Europe/Moscow', locale: 'ru',
    dateRange: () => ({ start: [1, 6], end: [1, 8] }),
    visuals: { particles: { type: 'snowflake-special', count: 10, colors: ['#ffffff', '#e8f0ff', '#d0e4ff'] } },
    thoughts: {
      'en': ['Merry Orthodox Christmas!', 'Rozhdestvo!', 'Christ is born!', '🎄'],
      'zh-CN': ['东正教圣诞快乐!', '基督诞生!', '🎄', '圣诞!'],
      'zh-TW': ['東正教聖誕快樂!', '基督誕生!', '🎄', '聖誕!'],
      'ja': ['正教会のクリスマス!', 'ロジュデストヴォ!', '🎄', 'キリスト誕生!'],
      'ko': ['정교회 성탄절!', '로즈데스트보!', '🎄', '그리스도 탄생!'],
      'ru': ['С Рождеством!', 'Христос родился!', 'Рождество!', '🎄', 'Колядки!'],
      'es': ['¡Feliz Navidad Ortodoxa!', '¡Rozhdestvo!', '¡Cristo nació!', '🎄'],
      'fr': ['Joyeux Noël orthodoxe !', 'Rozhdestvo !', 'Christ est né !', '🎄'],
      'ar': ['عيد ميلاد أرثوذكسي مجيد!', 'روجديستفو!', 'المسيح ولد!', '🎄'],
    }
  },
  {
    id: 'ru-8march', timezone: 'Europe/Moscow', locale: 'ru',
    dateRange: () => ({ start: [3, 7], end: [3, 9] }),
    visuals: { decorations: { type: 'greeting-card', count: 1, label: '8' } },
    thoughts: {
      'en': ['Happy Women\'s Day!', 'Flowers!', 'Spring!', 'Congratulations!'],
      'zh-CN': ['妇女节快乐!', '送花!', '春天!', '祝贺!'],
      'zh-TW': ['婦女節快樂!', '送花!', '春天!', '祝賀!'],
      'ja': ['国際女性デー!', 'お花!', '春!', 'おめでとう!'],
      'ko': ['세계 여성의 날!', '꽃!', '봄!', '축하해요!'],
      'ru': ['С 8 Марта!', 'Цветы!', 'Весна!', 'Поздравляю!', 'Мимоза!'],
      'es': ['¡Feliz Día de la Mujer!', '¡Flores!', '¡Primavera!', '¡Felicidades!'],
      'fr': ['Bonne fête des femmes !', 'Des fleurs !', 'Printemps !', 'Félicitations !'],
      'ar': ['يوم المرأة العالمي!', 'زهور!', 'ربيع!', 'مبروك!'],
    }
  },
  {
    id: 'ru-maslenitsa', timezone: 'Europe/Moscow', locale: 'ru',
    dateRange: (year) => {
      const easter = orthodoxEasterDates[year]
      if (!easter) return null
      const d = new Date(year, easter[0] - 1, easter[1])
      d.setDate(d.getDate() - 49) // 7 weeks before Easter
      const end = new Date(d); end.setDate(end.getDate() + 6)
      return {
        start: [d.getMonth() + 1, d.getDate()],
        end: [end.getMonth() + 1, end.getDate()]
      }
    },
    visuals: { decorations: { type: 'greeting-card', count: 1, label: '☀' } },
    thoughts: {
      'en': ['Maslenitsa!', 'Pancakes!', 'Farewell winter!', 'Spring is coming!'],
      'zh-CN': ['谢肉节!', '薄饼!', '告别冬天!', '春天来了!'],
      'zh-TW': ['謝肉節!', '薄餅!', '告別冬天!', '春天來了!'],
      'ja': ['マースレニツァ!', 'ブリヌイ!', '冬よさらば!', '春が来る!'],
      'ko': ['마슬레니차!', '팬케이크!', '겨울 안녕!', '봄이 온다!'],
      'ru': ['Масленица!', 'Блины!', 'Прощай, зима!', 'Весна идёт!', 'Чучело!'],
      'es': ['¡Maslenitsa!', '¡Panqueques!', '¡Adiós invierno!', '¡Viene la primavera!'],
      'fr': ['Maslenitsa !', 'Crêpes !', 'Adieu l\'hiver !', 'Le printemps arrive !'],
      'ar': ['ماسلينيتسا!', 'فطائر!', 'وداعاً الشتاء!', 'الربيع قادم!'],
    }
  },
  {
    id: 'ru-victory', timezone: 'Europe/Moscow', locale: 'ru',
    dateRange: () => ({ start: [5, 8], end: [5, 10] }),
    visuals: { decorations: { type: 'greeting-card', count: 1, label: '9 мая' } },
    thoughts: {
      'en': ['Victory Day!', 'Remembrance~', 'Thank you!', 'Peace!'],
      'zh-CN': ['胜利日!', '缅怀~', '感谢!', '和平!'],
      'zh-TW': ['勝利日!', '緬懷~', '感謝!', '和平!'],
      'ja': ['戦勝記念日!', '追悼~', 'ありがとう!', '平和!'],
      'ko': ['승전 기념일!', '추모~', '감사합니다!', '평화!'],
      'ru': ['С Днём Победы!', 'Помним~', 'Спасибо!', 'Мир!', '9 Мая!'],
      'es': ['¡Día de la Victoria!', 'Recuerdo~', '¡Gracias!', '¡Paz!'],
      'fr': ['Jour de la Victoire !', 'Souvenir~', 'Merci !', 'Paix !'],
      'ar': ['يوم النصر!', 'ذكرى~', 'شكراً!', 'سلام!'],
    }
  },

  // ════════════════ 🇪🇸 Spain ════════════════
  {
    id: 'es-newyear', timezone: 'Europe/Madrid', locale: 'es',
    dateRange: () => ({ start: [12, 31], end: [1, 2] }),
    visuals: { particles: { type: 'confetti', count: 18, colors: ['#ff4444', '#44aaff', '#ffdd44', '#44dd88', '#ff88dd'] } },
    thoughts: {
      'en': ['Happy New Year!', '12 grapes!', 'Feliz!', 'Olé!'],
      'zh-CN': ['新年快乐!', '十二颗葡萄!', '快乐!', 'Olé!'],
      'zh-TW': ['新年快樂!', '十二顆葡萄!', '快樂!', 'Olé!'],
      'ja': ['あけおめ!', '12粒のブドウ!', 'フェリス!', 'オレ!'],
      'ko': ['새해 복!', '포도 12알!', '펠리스!', '올레!'],
      'ru': ['С Новым годом!', '12 виноградин!', 'Фелис!', 'Оле!'],
      'es': ['¡Feliz Año Nuevo!', '¡Las 12 uvas!', '¡Felicidades!', '¡Olé!', '¡Campanadas!'],
      'fr': ['Bonne année !', '12 raisins !', 'Feliz !', 'Olé !'],
      'ar': ['سنة جديدة سعيدة!', '12 حبة عنب!', 'فيليث!', 'أوليه!'],
    }
  },
  {
    id: 'es-reyes', timezone: 'Europe/Madrid', locale: 'es',
    dateRange: () => ({ start: [1, 5], end: [1, 7] }),
    visuals: { decorations: { type: 'greeting-card', count: 1, label: 'Reyes' } },
    thoughts: {
      'en': ['Three Kings Day!', 'Gifts!', 'Rosca de Reyes!', 'Magi!'],
      'zh-CN': ['三王节!', '礼物!', '国王蛋糕!', '东方三贤士!'],
      'zh-TW': ['三王節!', '禮物!', '國王蛋糕!', '東方三賢士!'],
      'ja': ['三賢者の日!', 'プレゼント!', 'ロスカ!', '東方の三賢者!'],
      'ko': ['동방 박사의 날!', '선물!', '로스카!', '마기!'],
      'ru': ['День трёх королей!', 'Подарки!', 'Роска де Рейес!', 'Волхвы!'],
      'es': ['¡Día de Reyes!', '¡Regalos!', '¡Roscón de Reyes!', '¡Los Reyes Magos!', '¡Carbón dulce!'],
      'fr': ['Jour des Rois !', 'Cadeaux !', 'Roscón de Reyes !', 'Rois mages !'],
      'ar': ['يوم الملوك الثلاثة!', 'هدايا!', 'روسكا!', 'المجوس!'],
    }
  },
  {
    id: 'es-sanfermin', timezone: 'Europe/Madrid', locale: 'es',
    dateRange: () => ({ start: [7, 6], end: [7, 14] }),
    visuals: { particles: { type: 'confetti', count: 15, colors: ['#ff0000', '#ffffff', '#ff4444', '#ffdd44'] } },
    thoughts: {
      'en': ['San Fermín!', 'Run!', 'Fiesta!', 'Pamplona!'],
      'zh-CN': ['奔牛节!', '快跑!', '嘉年华!', '潘普洛纳!'],
      'zh-TW': ['奔牛節!', '快跑!', '嘉年華!', '潘普洛納!'],
      'ja': ['サン・フェルミン!', '走れ!', 'フィエスタ!', 'パンプローナ!'],
      'ko': ['산 페르민!', '달려!', '피에스타!', '팜플로나!'],
      'ru': ['Сан-Фермин!', 'Беги!', 'Фиеста!', 'Памплона!'],
      'es': ['¡San Fermín!', '¡Corre!', '¡Fiesta!', '¡Pamplona!', '¡Chupinazo!'],
      'fr': ['San Fermín !', 'Cours !', 'Fiesta !', 'Pampelune !'],
      'ar': ['سان فيرمين!', 'اركض!', 'فييستا!', 'بامبلونا!'],
    }
  },
  {
    id: 'es-christmas', timezone: 'Europe/Madrid', locale: 'es',
    dateRange: () => ({ start: [12, 23], end: [12, 27] }),
    visuals: {
      particles: { type: 'snowflake-special', count: 10, colors: ['#ffffff', '#e8f0ff', '#d0e4ff'] },
      decorations: { type: 'christmas-tree', count: 1 }
    },
    thoughts: {
      'en': ['Merry Christmas!', 'Nochebuena!', 'Turrón!', '🎄'],
      'zh-CN': ['圣诞快乐!', '平安夜!', '牛轧糖!', '🎄'],
      'zh-TW': ['聖誕快樂!', '平安夜!', '牛軋糖!', '🎄'],
      'ja': ['メリークリスマス!', 'ノチェブエナ!', 'トゥロン!', '🎄'],
      'ko': ['메리 크리스마스!', '노체부에나!', '투론!', '🎄'],
      'ru': ['Счастливого Рождества!', 'Ночебуэна!', 'Туррон!', '🎄'],
      'es': ['¡Feliz Navidad!', '¡Nochebuena!', '¡Turrón!', '🎄', '¡Polvorones!'],
      'fr': ['Joyeux Noël !', 'Nochebuena !', 'Turrón !', '🎄'],
      'ar': ['عيد ميلاد مجيد!', 'ليلة عيد الميلاد!', 'تورون!', '🎄'],
    }
  },

  // ════════════════ 🇫🇷 France ════════════════
  {
    id: 'fr-newyear', timezone: 'Europe/Paris', locale: 'fr',
    dateRange: () => ({ start: [12, 31], end: [1, 2] }),
    visuals: { particles: { type: 'confetti', count: 18, colors: ['#0055a4', '#ffffff', '#ef4135', '#ffdd44', '#44dd88'] } },
    thoughts: {
      'en': ['Happy New Year!', 'Champagne!', 'Bonne année!', 'Cheers!'],
      'zh-CN': ['新年快乐!', '香槟!', '干杯!', '新年好!'],
      'zh-TW': ['新年快樂!', '香檳!', '乾杯!', '新年好!'],
      'ja': ['あけおめ!', 'シャンパン!', 'ボナネ!', '乾杯!'],
      'ko': ['새해 복 많이!', '샴페인!', '본 아네!', '건배!'],
      'ru': ['С Новым годом!', 'Шампанское!', 'Бон ане!', 'За здоровье!'],
      'es': ['¡Feliz Año Nuevo!', '¡Champán!', '¡Bonne année!', '¡Salud!'],
      'fr': ['Bonne année !', 'Champagne !', 'Santé !', 'Réveillon !', 'Bisous !'],
      'ar': ['سنة جديدة سعيدة!', 'شامبانيا!', 'بون آني!', 'في صحتكم!'],
    }
  },
  {
    id: 'fr-bastille', timezone: 'Europe/Paris', locale: 'fr',
    dateRange: () => ({ start: [7, 13], end: [7, 15] }),
    visuals: { particles: { type: 'firework-spark', count: 18, colors: ['#0055a4', '#ffffff', '#ef4135', '#ffdd44'] } },
    thoughts: {
      'en': ['Bastille Day!', 'Vive la France!', 'Fireworks!', 'Liberty!'],
      'zh-CN': ['国庆日!', '法兰西万岁!', '烟花!', '自由!'],
      'zh-TW': ['國慶日!', '法蘭西萬歲!', '煙花!', '自由!'],
      'ja': ['パリ祭!', 'ヴィヴ・ラ・フランス!', '花火!', '自由!'],
      'ko': ['바스티유의 날!', '비브 라 프랑스!', '불꽃놀이!', '자유!'],
      'ru': ['День Бастилии!', 'Виват Франция!', 'Фейерверки!', 'Свобода!'],
      'es': ['¡Día de la Bastilla!', '¡Viva Francia!', '¡Fuegos artificiales!', '¡Libertad!'],
      'fr': ['Fête nationale !', 'Vive la France !', 'Feux d\'artifice !', 'Liberté !', '14 juillet !'],
      'ar': ['يوم الباستيل!', 'عاشت فرنسا!', 'ألعاب نارية!', 'حرية!'],
    }
  },
  {
    id: 'fr-christmas', timezone: 'Europe/Paris', locale: 'fr',
    dateRange: () => ({ start: [12, 23], end: [12, 27] }),
    visuals: {
      particles: { type: 'snowflake-special', count: 10, colors: ['#ffffff', '#e8f0ff', '#d0e4ff'] },
      decorations: { type: 'christmas-tree', count: 1 }
    },
    thoughts: {
      'en': ['Merry Christmas!', 'Bûche de Noël!', 'Père Noël!', '🎄'],
      'zh-CN': ['圣诞快乐!', '圣诞树桩蛋糕!', '圣诞老人!', '🎄'],
      'zh-TW': ['聖誕快樂!', '聖誕樹樁蛋糕!', '聖誕老人!', '🎄'],
      'ja': ['メリークリスマス!', 'ブッシュ・ド・ノエル!', 'ペール・ノエル!', '🎄'],
      'ko': ['메리 크리스마스!', '뷔슈 드 노엘!', '페르 노엘!', '🎄'],
      'ru': ['Счастливого Рождества!', 'Рождественское полено!', 'Пер Ноэль!', '🎄'],
      'es': ['¡Feliz Navidad!', '¡Bûche de Noël!', '¡Père Noël!', '🎄'],
      'fr': ['Joyeux Noël !', 'Bûche de Noël !', 'Père Noël !', '🎄', 'Réveillon !'],
      'ar': ['عيد ميلاد مجيد!', 'بوش دو نويل!', 'بير نويل!', '🎄'],
    }
  },

  // ════════════════ 🇸🇦 Saudi Arabia / Arabic ════════════════
  {
    id: 'sa-eidfitr', timezone: 'Asia/Riyadh', locale: 'ar',
    dateRange: (year) => lunarRange(eidAlFitrDates, year, 0, 2),
    visuals: {
      particles: { type: 'crescent-sparkle', count: 12, colors: ['#ffd700', '#ffcc00', '#ffe44d', '#fff2aa'] },
      decorations: { type: 'crescent-star', count: 2 }
    },
    thoughts: {
      'en': ['Eid Mubarak!', 'Blessed Eid!', 'Sweets!', 'Celebration!'],
      'zh-CN': ['开斋节快乐!', '甜食!', '庆祝!', '穆巴拉克!'],
      'zh-TW': ['開齋節快樂!', '甜食!', '慶祝!', '穆巴拉克!'],
      'ja': ['イード・ムバラク!', 'お菓子!', 'お祝い!', '幸福!'],
      'ko': ['이드 무바라크!', '과자!', '축하!', '축복!'],
      'ru': ['Ид Мубарак!', 'Сладости!', 'Праздник!', 'Благословение!'],
      'es': ['¡Eid Mubarak!', '¡Dulces!', '¡Celebración!', '¡Bendición!'],
      'fr': ['Aïd Moubarak !', 'Sucreries !', 'Célébration !', 'Bénédiction !'],
      'ar': ['عيد فطر مبارك!', 'حلويات!', 'عيد سعيد!', 'كل عام وأنتم بخير!', 'عيدية!'],
    }
  },
  {
    id: 'sa-eidadha', timezone: 'Asia/Riyadh', locale: 'ar',
    dateRange: (year) => lunarRange(eidAlAdhaDates, year, 0, 3),
    visuals: {
      particles: { type: 'crescent-sparkle', count: 12, colors: ['#ffd700', '#ffcc00', '#ffe44d', '#fff2aa'] },
      decorations: { type: 'crescent-star', count: 2 }
    },
    thoughts: {
      'en': ['Eid Mubarak!', 'Blessed Eid al-Adha!', 'Feast!', 'Celebration!'],
      'zh-CN': ['宰牲节快乐!', '盛宴!', '庆祝!', '穆巴拉克!'],
      'zh-TW': ['宰牲節快樂!', '盛宴!', '慶祝!', '穆巴拉克!'],
      'ja': ['イード・アル=アドハー!', 'ご馳走!', 'お祝い!', 'ムバラク!'],
      'ko': ['이드 알 아드하!', '잔치!', '축하!', '무바라크!'],
      'ru': ['Ид аль-Адха Мубарак!', 'Пир!', 'Праздник!', 'Мубарак!'],
      'es': ['¡Eid al-Adha Mubarak!', '¡Festín!', '¡Celebración!', '¡Mubarak!'],
      'fr': ['Aïd al-Adha Moubarak !', 'Festin !', 'Célébration !', 'Moubarak !'],
      'ar': ['عيد أضحى مبارك!', 'وليمة!', 'عيد سعيد!', 'كل عام وأنتم بخير!', 'تقبل الله منا ومنكم!'],
    }
  },
  {
    id: 'sa-nationalday', timezone: 'Asia/Riyadh', locale: 'ar',
    dateRange: () => ({ start: [9, 22], end: [9, 24] }),
    visuals: {
      particles: { type: 'firework-spark', count: 15, colors: ['#006c35', '#ffffff', '#ffdd00'] },
      decorations: { type: 'fanous', count: 1, label: '٩٣' }
    },
    thoughts: {
      'en': ['Saudi National Day!', 'Celebration!', 'Fireworks!', 'Pride!'],
      'zh-CN': ['沙特国庆日!', '庆祝!', '烟花!', '自豪!'],
      'zh-TW': ['沙特國慶日!', '慶祝!', '煙花!', '自豪!'],
      'ja': ['サウジ建国記念日!', 'お祝い!', '花火!', '誇り!'],
      'ko': ['사우디 국경일!', '축하!', '불꽃놀이!', '자부심!'],
      'ru': ['Национальный день Саудовской Аравии!', 'Праздник!', 'Фейерверки!', 'Гордость!'],
      'es': ['¡Día Nacional Saudí!', '¡Celebración!', '¡Fuegos artificiales!', '¡Orgullo!'],
      'fr': ['Fête nationale saoudienne !', 'Célébration !', 'Feux d\'artifice !', 'Fierté !'],
      'ar': ['اليوم الوطني السعودي!', 'احتفال!', 'ألعاب نارية!', 'فخر!', 'همة حتى القمة!'],
    }
  },
]

// ── Locale → holiday locale mapping for priority ──
const localeToHolidayLocale: Record<string, string> = {
  'en': 'en', 'zh-CN': 'zh-CN', 'zh-TW': 'zh-TW',
  'ja': 'ja', 'ko': 'ko', 'ru': 'ru',
  'es': 'es', 'fr': 'fr', 'ar': 'ar'
}

// ── Get all currently active holidays ──
export function getActiveHolidays(userLocale?: string): Holiday[] {
  const active: Holiday[] = []
  for (const h of holidays) {
    const { month, day, year } = getDateInTimezone(h.timezone)
    const range = h.dateRange(year)
    if (!range) continue
    if (isInRange(month, day, range.start, range.end)) {
      active.push(h)
    }
    // Also check previous year for year-crossing ranges (e.g. Dec 31 → Jan 2)
    if (month <= 2) {
      const rangePrev = h.dateRange(year - 1)
      if (rangePrev && rangePrev.start[0] > rangePrev.end[0]) {
        if (isInRange(month, day, rangePrev.start, rangePrev.end)) {
          if (!active.includes(h)) active.push(h)
        }
      }
    }
  }

  // Sort by priority: user's locale holidays first
  if (userLocale) {
    const pLocale = localeToHolidayLocale[userLocale] || 'en'
    active.sort((a, b) => {
      const aPri = a.locale === pLocale ? 0 : 1
      const bPri = b.locale === pLocale ? 0 : 1
      return aPri - bPri
    })
  }

  return active
}
